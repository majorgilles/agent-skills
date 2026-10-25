"""OCR for scanned books (pages that are images without a text layer), so the rest of the pipeline runs unchanged.
  python tools/ocr.py run [--dpi 300] [--lang eng] [--all]   OCR every image-only page (--all: every page) with
                                                              Tesseract, keep each word with its box and confidence,
                                                              then resolve, review and build (below)
  python tools/ocr.py recover   add the words Tesseract never detected (uncovered word-sized ink), read again alone
  python tools/ocr.py resolve [--reference work/Original.pdf] [--model sonnet] [--model2 opus] [--jobs 6] [--batch 40] [--pages A-B]
                              settle doubtful words by vote (Tesseract, a reference text layer, blind model reads)
  python tools/ocr.py review  write work/ocr/review.html: only the words the vote could not settle
  python tools/ocr.py build [--corrections work/ocr/corrections.json] [--keep-heads]   rebuild the PDF with resolved +
                              reviewed words, leaving out running heads and lone page numbers (scans shift: no margin fits)
The built PDF holds the original scan with an invisible text layer written by this script (Noto Sans, Noto Sans
Math for words with math symbols; one word at a time on Tesseract's line baselines), plus work/ocr/figures.json: regions of ink that are not text (figures),
and work/ocr/formulas.json: formula lines and "[formula]" words, shown as images inline in their row.
Then set in profile.json:  "pdf": "work/Main.ocr.pdf", "ocr": true, "fonts": {"prose": "^NotoSans"}.

Accuracy: a scan has no ground truth to verify against. A word is doubtful when Tesseract's confidence is low, the
rest of the book never uses it, or the reference text layer (another engine's OCR, e.g. the PDF's original ABBYY
layer) reads it differently. Doubtful words go to a vote between independent readers: Tesseract, the reference, and
a model that sees only the word's image (never the OCR text), then a second model if still open. A reading wins with
2+ votes and more than any other, so one model never decides alone; otherwise the word goes to review.html for a
human. Lines made only of formula (no prose word, a model saw math) leave the text layer and are shown as images.
verify.py/audit.py then guarantee the HTML matches the (resolved, reviewed) text layer exactly."""
import sys, os, re, json, html, base64, bisect, shutil, threading, subprocess, unicodedata, pathlib, collections, concurrent.futures, pymupdf
sys.path.insert(0, str(pathlib.Path(__file__).parent))

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'work' / 'Main.pdf'
OUT = ROOT / 'work' / 'ocr'
PDF_OUT = ROOT / 'work' / 'Main.ocr.pdf'
RESOLVED, READS, WORDS, CORRECTIONS = OUT / 'resolved.json', OUT / 'reads', OUT / 'words', OUT / 'corrections.json'
LOW = 85                                   # words under this Tesseract confidence (0-100) are doubtful
FOLD = str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"', '—': '-', '–': '-', '−': '-', '\xad': None})
BODY_PT = 10                               # text layer size of body lines (OCR has no font sizes; titles scale up)
FONTS = {'ocr': '/usr/share/fonts/noto/NotoSans-Regular.ttf',         # text layer fonts, in order of preference
         'ocrmath': '/usr/share/fonts/noto/NotoSansMath-Regular.ttf'}   # (Helvetica cannot write − √ ≠ π or curly quotes)
COST = collections.Counter()                 # model -> USD, as `claude -p` reports it
ITEM_NO = re.compile(r'^\(?(\d{1,2}|[a-h])[.)]$')
MATH_NAMES = {'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'log', 'lim', 'max', 'min', 'exp', 'det', 'mod', 'gcd', 'lcm'}
PROMPT = '''You read words in images of a scanned printed book. Each image is part of one printed line, with one word
framed by a red box. For each image give exactly the characters printed inside the red box, never the characters
just outside it even when the word or formula continues there, as printed: keep case,
punctuation and hyphens inside the box; superscripts and subscripts as ordinary characters in reading order (x² -> x2);
Greek letters and math symbols as their Unicode characters (π, ≤, ×, −). If the box holds no printed characters (a
speck, part of a drawing or rule) give "". If you cannot read every character with certainty, give null: never guess.
"formula" is true when the boxed characters belong to a mathematical formula rather than prose.
Reply with only a JSON object: {"1": {"text": "...", "formula": false}, "2": ...} with one entry per image.'''


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def needs_ocr(page):
    return len(page.get_text().strip()) < 20 and bool(page.get_images())


def tesseract(png, lang, psm=1):
    """-> list of word dicts {text, conf, box (px), line (block, par, line), line_box (px)} from Tesseract's TSV."""
    tsv = subprocess.run(['tesseract', str(png), '-', '-l', lang, '--psm', str(psm), 'tsv'], capture_output=True, text=True, check=True).stdout
    rows = [r.split('\t') for r in tsv.splitlines()[1:] if r.count('\t') >= 11]
    lines, words = {}, []
    for r in rows:
        lvl, blk, par, ln = int(r[0]), r[2], r[3], r[4]
        box = (int(r[6]), int(r[7]), int(r[6]) + int(r[8]), int(r[7]) + int(r[9]))
        if lvl == 4: lines[(blk, par, ln)] = box
        if lvl == 5 and r[11].strip():
            words.append({'text': r[11], 'conf': float(r[10]), 'box': box, 'line': (blk, par, ln)})
    for w in words: w['line_box'] = lines.get(w['line'], w['box'])
    return words


def figure_regions(page_png, words, scale):
    """Ink that is not text: render -> mask dark pixels -> blank word boxes -> group what is left on a coarse grid.
    Returns rects in PDF points. Regions smaller than ~30x30 pt or thinner than 6 pt (rules, specks) are dropped."""
    pix = pymupdf.Pixmap(str(page_png))
    if pix.n > 1: pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    w, h, s = pix.width, pix.height, pix.samples
    cell = max(4, round(8 * scale / 4))                      # ~2 pt cells
    gw, gh = w // cell + 1, h // cell + 1
    text = bytearray(gw * gh)
    for wd in words:                                           # words (slightly grown) are text, not figure ink
        x0, y0, x1, y1 = wd['box']
        for gy in range(max(0, (y0 - 3) // cell), min(gh, (y1 + 3) // cell + 1)):
            for gx in range(max(0, (x0 - 3) // cell), min(gw, (x1 + 3) // cell + 1)):
                text[gy * gw + gx] = 1
    ink = bytearray(gw * gh)
    for y in range(0, h, 2):
        row = y * pix.stride
        for x in range(0, w, 2):
            if s[row + x] < 128:
                g = (y // cell) * gw + x // cell
                if not text[g]: ink[g] = 1
    seen, regions = bytearray(gw * gh), []
    for start in range(gw * gh):                               # connected components, 2-cell reach (bridges gaps)
        if not ink[start] or seen[start]: continue
        stack, cells = [start], []
        seen[start] = 1
        while stack:
            c = stack.pop(); cells.append(c)
            cy, cx = divmod(c, gw)
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < gh and 0 <= nx < gw:
                        n = ny * gw + nx
                        if ink[n] and not seen[n]: seen[n] = 1; stack.append(n)
        ys, xs = [c // gw for c in cells], [c % gw for c in cells]
        r = pymupdf.Rect(min(xs) * cell, min(ys) * cell, (max(xs) + 1) * cell, (max(ys) + 1) * cell) / scale
        if r.width > 30 and r.height > 30 and min(r.width, r.height) > 6:
            regions.append(r)
    merged = []
    for r in sorted(regions, key=lambda r: r.y0):              # overlapping/near regions are one figure
        for m in merged:
            if (m + (-6, -6, 6, 6)).intersects(r): m |= r; break
        else: merged.append(pymupdf.Rect(r))
    return [[round(v, 1) for v in m] for m in merged]


def missed_ink(page_png, words, regions, scale):
    """Word-sized ink that no word box or figure region covers: words Tesseract never detected (a hanging "6.", a
    lone "x"). -> boxes in pixels, 3-30 pt tall and under 100 pt wide (smaller specks and rules are not words)."""
    pix = pymupdf.Pixmap(str(page_png))
    if pix.n > 1: pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    w, h, s, cell = pix.width, pix.height, pix.samples, 4      # ~1 pt cells
    gw, gh = w // cell + 1, h // cell + 1
    covered = bytearray(gw * gh)
    for x0, y0, x1, y1 in [wd['box'] for wd in words] + [[v * scale for v in r] for r in regions]:
        for gy in range(max(0, int(y0 - 3) // cell), min(gh, int(y1 + 3) // cell + 1)):
            covered[gy * gw + max(0, int(x0 - 3) // cell):gy * gw + min(gw, int(x1 + 3) // cell + 1)] = b'\x01' * (min(gw, int(x1 + 3) // cell + 1) - max(0, int(x0 - 3) // cell))
    ink = bytearray(gw * gh)
    for y in range(0, h, 2):
        row = y * pix.stride
        for x in range(0, w, 2):
            if s[row + x] < 110:
                g = (y // cell) * gw + x // cell
                if not covered[g]: ink[g] = 1
    seen, boxes = bytearray(gw * gh), []
    for start in range(gw * gh):
        if not ink[start] or seen[start]: continue
        stack, cells = [start], []
        seen[start] = 1
        while stack:
            c = stack.pop(); cells.append(c)
            cy, cx = divmod(c, gw)
            for dy in (-1, 0, 1):
                for dx in (-2, -1, 0, 1, 2):                   # letters of a word are ~1 pt apart
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < gh and 0 <= nx < gw:
                        n = ny * gw + nx
                        if ink[n] and not seen[n]: seen[n] = 1; stack.append(n)
        ys, xs = [c // gw for c in cells], [c % gw for c in cells]
        bw, bh = (max(xs) - min(xs) + 1) * cell / scale, (max(ys) - min(ys) + 1) * cell / scale
        if 3 <= bh <= 30 and bw < 100 and len(cells) >= 4:
            boxes.append([min(xs) * cell, min(ys) * cell, (max(xs) + 1) * cell, (max(ys) + 1) * cell])
    return boxes


def recover():
    """Add the words Tesseract never detected (missed_ink, each read again as a single word) to work/ocr/pNNNN.json
    as doubtful words ("recovered"): the vote reads them like any other. Run once, after `run`."""
    lang, pages = arg('--lang', 'eng'), load_pages()
    tmp = OUT / 'tmp'; tmp.mkdir(exist_ok=True)
    def one(pno):
        p = pages[pno]
        if p.get('recovered') is not None: return pno, 0
        png, scale = OUT / f'p{pno:04d}.png', p['dpi'] / 72
        src = pymupdf.Pixmap(str(png))
        new = []
        for b in missed_ink(png, p['words'], p['figures'], scale):
            clip = pymupdf.IRect(max(0, b[0] - 12), max(0, b[1] - 12), min(src.width, b[2] + 12), min(src.height, b[3] + 12))
            crop = pymupdf.Pixmap(src.colorspace, clip, False); crop.copy(src, clip); crop.set_origin(0, 0)
            f = tmp / f'p{pno:04d}-{len(new)}.png'; crop.save(f)
            got = [x for x in tesseract(f, lang, psm=7) if x['text'].strip()]
            f.unlink()
            text, conf = (' '.join(x['text'] for x in got), min(x['conf'] for x in got)) if got else ('?', 0.0)
            if got:                                             # Tesseract's own box: it holds the "." the ink scan left out
                b = [min(b[0], clip.x0 + min(x['box'][0] for x in got)), min(b[1], clip.y0 + min(x['box'][1] for x in got)),
                     max(b[2], clip.x0 + max(x['box'][2] for x in got)), max(b[3], clip.y0 + max(x['box'][3] for x in got))]
            host = max(p['words'], default=None, key=lambda wd: min(b[3], wd['line_box'][3]) - max(b[1], wd['line_box'][1]))
            same = host is not None and min(b[3], host['line_box'][3]) - max(b[1], host['line_box'][1]) > 0.5 * (b[3] - b[1])
            new.append({'text': text, 'conf': conf, 'box': b, 'recovered': True,
                        'line': host['line'] if same else ['r', len(new), 0], 'line_box': host['line_box'] if same else b})
        p['words'] += new
        p['recovered'] = len(new)
        (OUT / f'p{pno:04d}.json').write_text(json.dumps(p), encoding='utf-8')
        return pno, len(new)
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:   # the time is in tesseract
        total = sum(n for _, n in ex.map(one, sorted(pages)))
    print(f'{total} missed words recovered (they are doubtful: run resolve)')


def run():
    dpi, lang = int(arg('--dpi', 300)), arg('--lang', 'eng')
    if not shutil.which('tesseract'): sys.exit('tesseract is not installed (Arch: pacman -S tesseract tesseract-data-eng)')
    doc = pymupdf.open(SRC); OUT.mkdir(parents=True, exist_ok=True)
    pages = [i for i, p in enumerate(doc) if '--all' in sys.argv or needs_ocr(p)]
    print(f'{len(pages)} of {doc.page_count} pages need OCR')
    def one(pno):
        png = OUT / f'p{pno:04d}.png'
        if not png.exists(): doc[pno].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY).save(png)
        words = tesseract(png, lang)
        figs = figure_regions(png, words, dpi / 72)
        (OUT / f'p{pno:04d}.json').write_text(json.dumps({'dpi': dpi, 'words': words, 'figures': figs}), encoding='utf-8')
        return pno, len(words)
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        for pno, n in ex.map(one, pages): print(f'  page {pno}: {n} words')
    recover(); resolve(); review(); build()


def load_pages():
    return {int(f.stem[1:]): json.loads(f.read_text(encoding='utf-8')) for f in sorted(OUT.glob('p[0-9]*.json'))}


def norm(s):
    """Readings compare with typographic variants folded (quotes, dashes, ligatures, soft hyphens) and spaces removed
    (Tesseract writes "y=3x+", a model "y = 3x +")."""
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', s).translate(FOLD))


def pt_box(w, p):
    return tuple(v * 72 / p['dpi'] for v in w['box'])


def reference_reader(path):
    """-> f(pno, box): the reference text layer's reading of a box (its words mostly inside it, left to right; '' when
    it has none there), or None when the reference has no text on that page. None when there is no reference PDF."""
    if not path.exists(): return None
    ref, cache = pymupdf.open(path), {}
    def read(pno, box):
        if pno not in cache:
            ws = sorted((w[:5] for w in ref[pno].get_text('words')), key=lambda w: w[1]) if pno < ref.page_count else []
            cache[pno] = (ws, [w[1] for w in ws])
        ws, tops = cache[pno]
        if not ws: return None
        x0, y0, x1, y1 = box
        hit = []
        for w in ws[bisect.bisect_left(tops, y0 - 40):bisect.bisect_right(tops, y1)]:
            ix, iy = min(x1, w[2]) - max(x0, w[0]), min(y1, w[3]) - max(y0, w[1])
            if ix > 0 and iy > 0 and ix * iy > 0.5 * (w[2] - w[0]) * (w[3] - w[1]):   # mostly inside: "Ifa" is no reading of "If"
                hit.append(w)
        return ''.join(w[4] for w in sorted(hit))
    return read


def doubtful(pages, reference):
    """-> {"page:index": votes} for every word Tesseract may have misread: low confidence, unknown to the rest of the
    book, or read differently by the reference layer. votes: {tesseract, reference} (a missing reading is None)."""
    vocab = collections.Counter(re.sub(r'\W', '', w['text']).lower() for p in pages.values() for w in p['words'])
    out = {}
    for pno, p in pages.items():
        for i, w in enumerate(p['words']):
            key = re.sub(r'\W', '', w['text']).lower()
            rare = key and vocab[key] < 2 and len(key) > 3
            ref = reference(pno, pt_box(w, p)) if reference else None
            if w['conf'] >= LOW and not rare and not w.get('recovered') and (ref is None or norm(ref) == norm(w['text'])): continue
            out[f'{pno}:{i}'] = {'tesseract': None if w['text'] == '?' else w['text'], 'reference': ref or None}
    return out


_LINES = {}


def overreach(pages, key, reading):
    """True when a reading is this word plus the start of the next word(s) or the end of the previous one(s) on its
    line (a model reading past the red box, a reference word spanning two Tesseract words): it would duplicate them."""
    pno, i = map(int, key.split(':'))
    p = pages[pno]
    if pno not in _LINES:
        lines = collections.defaultdict(list)
        for j, w in enumerate(p['words']): lines[tuple(w['line'])].append(j)
        _LINES[pno] = {j: line for line in lines.values() for j in line}
    line = _LINES[pno][i]
    at, toks = line.index(i), [norm(p['words'][j]['text']) for j in line]
    r, own = norm(reading), toks[at]
    if len(r) <= len(own) or own not in r: return False
    head, tail = r[:r.index(own)], r[r.index(own) + len(own):]
    return (not tail or ''.join(toks[at + 1:at + 5]).startswith(tail)) and (not head or ''.join(toks[max(0, at - 4):at]).endswith(head))


def valid(pages, key, votes):
    """The votes that count: overreaching readings cast none."""
    return {v: (None if r and v != 'tesseract' and overreach(pages, key, r) else r) for v, r in votes.items()}


def decide(votes):
    """The reading with 2+ votes and more than any other (compared normalised), spelled as a model wrote it if one
    voted for it (real − √ π and spacing), else as the OCR did; None while undecided. '' (no text) can win too: the
    word is dropped."""
    tally = collections.Counter(norm(v) for v in votes.values() if v is not None)
    if not tally: return None
    (top, n), *rest = tally.most_common()
    if n < 2 or (rest and rest[0][1] == n): return None
    return next(votes[s] for s in ('model', 'model2', 'tesseract', 'reference') if votes.get(s) is not None and norm(votes[s]) == top)


_PAGE = {}


def word_image(pages, key):
    """work/ocr/words/pNNNN-i.png: the word framed in red on its line, with ~1.4 inch of context each side.
    Cut from the 300 dpi page render ocr.py run saved (call from one thread: the last page stays loaded)."""
    WORDS.mkdir(exist_ok=True)
    pno, i = map(int, key.split(':'))
    out = WORDS / f'p{pno:04d}-{i}.png'
    if out.exists(): return out
    p, w = pages[pno], pages[pno]['words'][i]
    if _PAGE.get('pno') != pno:
        png = OUT / f'p{pno:04d}.png'
        src = pymupdf.Pixmap(str(png)) if png.exists() else pymupdf.open(SRC)[pno].get_pixmap(dpi=p['dpi'], colorspace=pymupdf.csGRAY)
        if src.n > 1: src = pymupdf.Pixmap(pymupdf.csGRAY, src)
        _PAGE.update(pno=pno, pix=src)
    src = _PAGE['pix']
    x0, y0, x1, y1 = w['box']
    pad = p['dpi'] * 1.4
    clip = pymupdf.IRect(max(0, x0 - pad), max(0, min(y0, w['line_box'][1]) - 12),
                         min(src.width, x1 + pad), min(src.height, max(y1, w['line_box'][3]) + 12))
    crop = pymupdf.Pixmap(pymupdf.csGRAY, clip, False)
    crop.copy(src, clip)
    crop = pymupdf.Pixmap(pymupdf.csRGB, crop)
    crop.set_origin(0, 0)
    bx0, by0, bx1, by1 = x0 - clip.x0 - 5, y0 - clip.y0 - 5, x1 - clip.x0 + 5, y1 - clip.y0 + 5
    for r in ((bx0, by0, bx1, by0 + 3), (bx0, by1 - 3, bx1, by1), (bx0, by0, bx0 + 3, by1), (bx1 - 3, by0, bx1, by1)):
        crop.set_rect(pymupdf.IRect(*r) & pymupdf.IRect(0, 0, crop.width, crop.height), (220, 0, 0))
    crop.save(out)
    return out


def ask_model(model, batch):
    """One blind read of a batch of word images through `claude -p` (no tools, never shown the OCR text).
    -> {key: [text or None, formula]} for the images the model answered."""
    content = [{'type': 'text', 'text': f'{len(batch)} images:'}]
    for n, (key, png) in enumerate(batch, 1):
        content += [{'type': 'text', 'text': f'Image {n}:'},
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': base64.b64encode(png.read_bytes()).decode()}}]
    msg = json.dumps({'type': 'user', 'message': {'role': 'user', 'content': content}})
    cmd = ['claude', '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose', '--model', model,
           '--tools', '', '--strict-mcp-config', '--no-session-persistence', '--setting-sources', '', '--system-prompt', PROMPT]
    try:
        r = subprocess.run(cmd, input=msg + '\n', capture_output=True, text=True, timeout=900)
        result = next(j for j in map(json.loads, r.stdout.splitlines()) if j.get('type') == 'result')
        answer = json.loads(re.search(r'\{.*\}', result.get('result') or '', re.S).group(0))
        COST[model] += result.get('total_cost_usd') or 0
    except Exception as e:                                      # the batch stays unread: a rerun retries it
        print(f'    {model}: batch failed ({type(e).__name__}: {str(e)[:120]})', flush=True)
        return {}
    out = {}
    for n, (key, _) in enumerate(batch, 1):
        a = answer.get(str(n))
        if isinstance(a, dict) and (a.get('text') is None or isinstance(a.get('text'), str)):
            out[key] = [a.get('text'), bool(a.get('formula'))]
    return out


def read_words(pages, keys, model, jobs, size):
    """Blind model reads of these words, cached in work/ocr/reads/<model>.json (a rerun only reads what is missing)."""
    READS.mkdir(exist_ok=True)
    path = READS / f'{model}.json'
    reads = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    todo = [k for k in keys if k not in reads]
    if todo and not shutil.which('claude'): sys.exit('model reads need the claude CLI (or pass --model none)')
    print(f'  {model}: {len(keys) - len(todo)} cached, {len(todo)} to read', flush=True)
    batches = [[(k, word_image(pages, k)) for k in todo[n:n + size]] for n in range(0, len(todo), size)]
    lock, done = threading.Lock(), [0]
    def one(batch):
        got = ask_model(model, batch)
        with lock:
            reads.update(got); done[0] += len(batch)
            path.write_text(json.dumps(reads, ensure_ascii=False), encoding='utf-8')
            print(f'    {model}: {done[0]}/{len(todo)}', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(one, batches))
    return reads


def item_prefix(d):
    """(number, reading) when 2+ readers read a word as an item number fused to a formula ("3. (a − b) + ..."), else None."""
    got = [(m.group(1), v) for v in (d.get('votes') or {}).values() if v for m in [re.match(r'^\(?(\d{1,2}\.)\s*\S', v)] if m]
    top = collections.Counter(n for n, _ in got).most_common(1)
    return (top[0][0], next(v for n, v in got if n == top[0][0])) if top and top[0][1] >= 2 else None


def display_lines(pages, words):
    """Lines that are formulas, not prose (no word of 3+ letters but sin, log...; a model saw a formula there): their
    words leave the text layer and the line's ink is shown as an image. -> {pno: [{words, box}]}."""
    flagged = collections.defaultdict(set)
    for k, d in words.items():
        if d['formula']:
            pno, i = map(int, k.split(':'))
            flagged[pno].add(i)
    out = {}
    for pno, idx in flagged.items():
        p, lines = pages[pno], collections.defaultdict(list)
        for i, w in enumerate(p['words']): lines[tuple(w['line'])].append(i)
        for line in {tuple(p['words'][i]['line']) for i in idx}:
            ws = lines[line]
            def prose(i):                                       # a word of 3+ letters (as resolved) no model saw as math
                d = words.get(f'{pno}:{i}', {})
                text = d.get('text') or p['words'][i]['text']
                return not d.get('formula') and any(len(r) >= 3 and r.lower() not in MATH_NAMES for r in re.findall(r'[^\W\d_]+', text))
            if any(map(prose, ws)): continue
            ws = sorted(ws, key=lambda i: p['words'][i]['box'][0])
            segs, prev, splits, boxes_of = [[]], None, {}, {}   # item numbers opening a column ("4. ...   5. ...") stay text
            for i in ws:
                b = list(pt_box(p['words'][i], p))
                d = words.get(f'{pno}:{i}', {})
                opens = prev is None or b[0] - prev > 15
                if opens and ITEM_NO.match(d.get('text') or p['words'][i]['text']): segs.append([])
                elif opens and item_prefix(d):                  # "3.(a—b)+..." read as one word: the number stays text
                    num, reading = item_prefix(d)
                    cut = b[0] + (b[2] - b[0]) * (len(num) + 1) / max(len(reading), len(num) + 2)
                    splits[i] = (num, [round(v * p['dpi'] / 72) for v in (b[0], b[1], cut - 1, b[3])])
                    segs.append([i]); b[0] = cut
                else:
                    if prev is not None and b[0] - prev > 25 and segs[-1]: segs.append([])   # a column gap: two formulas
                    segs[-1].append(i)
                prev = b[2]
                boxes_of[i] = b
            for seg in filter(None, segs):
                boxes = [boxes_of[i] for i in seg]
                box = [min(b[0] for b in boxes) - 2, min(b[1] for b in boxes) - 2, max(b[2] for b in boxes) + 2, max(b[3] for b in boxes) + 2]
                out.setdefault(pno, []).append({'words': seg, 'box': [round(v, 1) for v in box],
                                                'splits': {str(i): v for i, v in splits.items() if i in seg}})
    return out


def absorb(pages, words):
    """A recovered word read with its neighbour ("2." over Tesseract's lone ".") absorbs that word: the neighbour leaves
    the layer, so nothing is written twice. Word indices never change (the reviewer's answers are keyed by them)."""
    for pno, p in pages.items():
        for i, r in enumerate(p['words']):
            t = words.get(f'{pno}:{i}', {}).get('text') if r.get('recovered') else None
            if not t: continue
            R = pymupdf.Rect(r['box'])
            for j, o in enumerate(p['words']):
                if o.get('recovered') or j == i: continue
                O, d = pymupdf.Rect(o['box']), words.get(f'{pno}:{j}')
                own = d['text'] if d and d['text'] is not None else o['text']
                if own and not (d or {}).get('human') and (O & R).get_area() > 0.6 * max(O.get_area(), 1) and norm(own) in norm(t):
                    words.setdefault(f'{pno}:{j}', {'votes': {'tesseract': o['text']}, 'formula': False})['text'] = ''


def resolve():
    """Settle doubtful words by vote and write work/ocr/resolved.json; the rest go to review.html."""
    pages = load_pages()
    reference = reference_reader(ROOT / arg('--reference', 'work/Original.pdf'))
    jobs, size = int(arg('--jobs', 6)), int(arg('--batch', 40))
    votes = doubtful(pages, reference)
    if '--pages' in sys.argv:                                   # a trial on a page range (0-based, inclusive)
        a, b = map(int, arg('--pages', '').split('-'))
        votes = {k: v for k, v in votes.items() if a <= int(k.split(':')[0]) <= b}
    formula = collections.defaultdict(bool)
    print(f'{len(votes)} doubtful words{"" if reference else " (no reference layer)"}', flush=True)
    for stage, model in (('model', arg('--model', 'sonnet')), ('model2', arg('--model2', 'opus'))):
        open_ = [k for k, v in votes.items() if decide(valid(pages, k, v)) is None]
        if model == 'none' or not open_: continue
        reads = read_words(pages, open_, model, jobs, size)
        for k in open_:
            if k in reads:
                votes[k][stage] = reads[k][0]
                formula[k] |= reads[k][1]
    words = {k: {'votes': v, 'text': decide(valid(pages, k, v)), 'formula': formula[k]} for k, v in votes.items()}
    corr = CORRECTIONS.exists() and json.loads(CORRECTIONS.read_text(encoding='utf-8')) or {}
    for k, t in corr.items():                                   # the reviewer decides (work/ocr/corrections.json)
        m = re.match(r'^(\(?\d{1,2}[.)])\s+\S', t)            # "26. x2 < 2" typed for the box "26.": its neighbours hold the rest
        if k in words: words[k].update(text=m.group(1) if m and overreach(pages, k, t) else t, human=True)
    absorb(pages, words)
    display = display_lines(pages, words)
    for pno, lines in display.items():
        for line in lines:
            for i in line['words']:
                w = words.setdefault(f'{pno}:{i}', {'votes': {'tesseract': pages[pno]['words'][i]['text']}, 'formula': True})
                w['text'] = ''
                if str(i) in line['splits']: w['text'], w['box'] = line['splits'][str(i)]   # its number, in its own box
    RESOLVED.write_text(json.dumps({'words': words, 'display': display}, ensure_ascii=False, indent=0), encoding='utf-8')
    how = collections.Counter('open' if d['text'] is None else 'dropped' if d['text'] == '' else
                              'kept' if norm(d['text']) == norm(d['votes']['tesseract'] or '') else 'changed' for d in words.values())
    if COST: print('model cost: ' + ', '.join(f'{m} ${c:.2f}' for m, c in COST.items()))
    print(f'resolved: {how["kept"]} confirmed, {how["changed"]} corrected, {how["dropped"]} dropped '
          f'({sum(map(len, display.values()))} formula lines shown as images), {how["open"]} left for review -> {RESOLVED}')


def review():
    """work/ocr/review.html: every word the vote left open (without resolved.json: every doubtful word) with its image,
    each reading as a button and an input; progress stays in the browser. 'Download' saves corrections.json
    ({"page:index": "text"}; "" drops the word, "[formula]" shows its ink as an image) for `ocr.py build --corrections`."""
    pages = load_pages()
    if RESOLVED.exists():
        items = {k: d['votes'] for k, d in json.loads(RESOLVED.read_text(encoding='utf-8'))['words'].items() if d['text'] is None}
    else:
        items = doubtful(pages, None)
    rows = []
    for k, votes in sorted(items.items(), key=lambda kv: tuple(map(int, kv[0].split(':')))):
        img = word_image(pages, k).relative_to(OUT)
        tess = votes['tesseract'] or ''
        opts = list(dict.fromkeys(v for v in votes.values() if v)) + ['[formula]', '']
        chips = ''.join(f'<button data-v="{html.escape(v)}" title="{html.escape(", ".join(n for n, x in votes.items() if x == v))}">'
                        f'{html.escape(v) if v else "no text"}</button>' for v in opts)
        rows.append(f'<tr><td>{k.split(":")[0]}</td><td><img src="{img}"></td><td>{chips}</td>'
                    f'<td><input data-k="{k}" data-o="{html.escape(tess)}" value="{html.escape(tess)}"></td></tr>')
    (OUT / 'review.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>OCR review</title>
<style>body{{font:15px system-ui;margin:24px}}td{{padding:4px 10px;border-bottom:1px solid #ddd}}img{{max-height:48px}}
input{{font:16px monospace;width:16em}}button{{font:14px monospace;margin:1px}}tr.done{{opacity:.45}}</style>
<h1>OCR review: {len(rows)} words</h1><p>The readers (Tesseract, the reference layer, two models) did not agree on
these. Click the reading that matches the red box or type it ("[formula]": show that ink as an image; "no text": drop
it). Your choices stay in this browser. Then download and run
<code>python tools/ocr.py build --corrections work/ocr/corrections.json</code>. <b id="left"></b></p>
<button onclick="save()">Download corrections.json</button>
<table><tr><th>page</th><th>image</th><th>readings</th><th>text</th></tr>{"".join(rows)}</table>
<script>const S='ocr-review:'+location.pathname;let st={{}};try{{st=JSON.parse(localStorage.getItem(S))||{{}}}}catch(e){{}}
const ins=[...document.querySelectorAll('input')];
function mark(i){{i.closest('tr').classList.toggle('done',i.dataset.k in st)}}
function count(){{document.getElementById('left').textContent=ins.filter(i=>!(i.dataset.k in st)).length+' left'}}
function set(i,v){{i.value=v;st[i.dataset.k]=v;try{{localStorage.setItem(S,JSON.stringify(st))}}catch(e){{}}mark(i);count()}}
ins.forEach(i=>{{if(i.dataset.k in st)i.value=st[i.dataset.k];mark(i);i.onchange=()=>set(i,i.value);
  i.closest('tr').querySelectorAll('button').forEach(b=>b.onclick=()=>set(i,b.dataset.v))}});count();
function save(){{const c={{}};ins.forEach(i=>{{if(i.value!==i.dataset.o)c[i.dataset.k]=i.value}});
const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(c,null,1)],{{type:'application/json'}}));a.download='corrections.json';a.click()}}</script>''',
        encoding='utf-8')
    print(f'{len(rows)} words to review -> {OUT / "review.html"}')


FOLIO = re.compile(r'^(A-)?\d{1,3}$|^[ivxlc]{1,6}$')


def head_title(head):
    return ' '.join(t for _, _, t in head if not FOLIO.match(t.rstrip('.')))


def furniture(p, texts, known=()):
    """Indices of a page's running head (the top band: a page number at one end, no lowercase word, or a head seen
    with a number on other pages: `known`) and of a lone page number at the bottom: page furniture, left out of the
    text layer. Scans shift, so no fixed margin works."""
    pt = 72 / p['dpi']
    ws = [(i, [v * pt for v in w['box']], texts[i]) for i, w in enumerate(p['words']) if texts[i]]
    if not ws: return set()
    out = set()
    top = min(b[1] for _, b, _ in ws)
    head = sorted((x for x in ws if x[1][1] < top + 6), key=lambda x: x[1][0])
    numbered = FOLIO.match(head[0][2]) or FOLIO.match(head[-1][2].rstrip('.'))
    if (numbered or head_title(head) in known) and not any(re.search(r'[a-z]{3}', t) for _, _, t in head) and len(head) < 12:
        out |= {i for i, _, _ in head}
    bottom = max(b[3] for _, b, _ in ws)
    foot = [x for x in ws if x[1][3] > bottom - 6]
    if len(foot) == 1 and FOLIO.match(foot[0][2]) and foot[0][1][1] > 560: out.add(foot[0][0])
    return out


def build():
    path = arg('--corrections', None)                          # the reviewer's answers: kept as work/ocr/corrections.json
    if path and pathlib.Path(path).resolve() != CORRECTIONS.resolve():  # and decided by resolve (cached reads: no cost)
        shutil.copyfile(path, CORRECTIONS)
    if path: resolve()
    write_pdf()


def write_pdf():
    """Copy the source PDF; on OCR'd pages add each word (as resolved, then as the reviewer corrected it) as invisible
    text on its line's baseline. Dropped words leave the layer; formula lines and "[formula]" words become figure regions."""
    words, display, boxes = {}, {}, {}
    if RESOLVED.exists():
        d = json.loads(RESOLVED.read_text(encoding='utf-8'))
        words, display = {k: w['text'] for k, w in d['words'].items() if w['text'] is not None}, d['display']
        boxes = {k: w['box'] for k, w in d['words'].items() if 'box' in w}   # an item number split off a formula word
    corr = {k: w for k, w in d['words'].items() if w.get('human')} if RESOLVED.exists() else {}   # resolve applied them
    doc, pages = pymupdf.open(SRC), load_pages()
    missing = [f for f in FONTS.values() if not pathlib.Path(f).exists()]
    if missing: sys.exit(f'missing fonts {missing} (Arch: pacman -S noto-fonts)')
    fonts = {name: pymupdf.Font(fontfile=f) for name, f in FONTS.items()}
    figures, formulas, lost = {}, {}, collections.Counter()
    texts_of = lambda pno: [t if t != '[formula]' else '' for t in (words.get(f'{pno}:{i}', '' if w.get('recovered') else w['text']) for i, w in enumerate(pages[pno]['words']))]
    known = collections.Counter()                               # running-head titles printed with a page number
    for pno, p in pages.items():
        t = texts_of(pno)
        for_head = [(i, [v * 72 / p['dpi'] for v in p['words'][i]['box']], t[i]) for i in furniture(p, t)]
        if len(for_head) > 1: known[head_title(sorted(for_head, key=lambda x: x[1][0]))] += 1
    known = {k for k, n in known.items() if n >= 3}
    for pno, p in pages.items():
        page, scale = doc[pno], p['dpi'] / 72
        for name, f in FONTS.items(): page.insert_font(fontname=name, fontfile=f)
        figures[pno] = list(p['figures'])
        formulas[pno] = [line['box'] for line in display.get(str(pno), [])]
        heads = set() if '--keep-heads' in sys.argv else furniture(p, texts_of(pno), known)
        heights, tops = collections.defaultdict(list), {}
        for w in p['words']:
            heights[tuple(w['line'])].append((w['box'][3] - w['box'][1]) / scale)
            tops[tuple(w['line'])] = min(tops.get(tuple(w['line']), 1e9), w['box'][1] / scale)
        med = {k: sorted(v)[len(v) // 2] for k, v in heights.items()}
        body = sorted(med.values())[len(med) // 2] if med else 1   # the page's usual line: one body size for all of it
        title = lambda line: med[line] > 1.6 * body and tops[line] < 0.2 * page.rect.height   # tall and at the top: a title
        size_of = lambda line: BODY_PT * (med[line] / body if title(line) else 1)   # (a tall line lower down holds a formula)
        for i, w in enumerate(p['words']):
            text = '' if i in heads else words.get(f'{pno}:{i}', '' if w.get('recovered') else w['text'])   # unread: not written
            if text == '[formula]': formulas[pno].append([round(v, 1) for v in pymupdf.Rect(pt_box(w, p)) + (-2, -2, 2, 2)])
            if text in ('', '[formula]'): continue
            nums = re.findall(r'\d{1,2}\.', text) if re.fullmatch(r'(\d{1,2}\.\s*){2,}', text) else []
            beside = sorted({tuple(o['line_box']) for o in p['words'] if o is not w and o['box'][0] > w['box'][2]
                             and w['box'][1] - 5 < (o['line_box'][1] + o['line_box'][3]) / 2 < w['box'][3] + 5}, key=lambda b: b[1])
            if nums and len(beside) == len(nums):                # a column of item numbers read as one word: one per line
                for n, lb in zip(nums, beside):
                    page.insert_text((w['box'][0] / scale, lb[3] / scale - 0.22 * (lb[3] - lb[1]) / scale), n, fontname='ocr',
                                     fontsize=size_of(tuple(w['line'])), render_mode=3)
                continue
            # each character in the first font that has it: the math font's digits and letters extract wrongly
            runs = []
            for c in text:
                name = next((n for n, f in fonts.items() if c.isspace() or f.has_glyph(ord(c))), None)
                if name is None: lost[c] += 1; continue
                if runs and runs[-1][0] == name: runs[-1][1] += c
                else: runs.append([name, c])
            x0, y0, x1, y1 = (v / scale for v in boxes.get(f'{pno}:{i}', w['box']))
            lx0, ly0, lx1, ly1 = (v / scale for v in w['line_box'])
            size = size_of(tuple(w['line']))
            width = sum(fonts[n].text_length(t, size) for n, t in runs)
            if width > x1 - x0: size *= max(0.87, (x1 - x0) / width)   # shrink to fit, never so far it reads as a superscript
            base = ly1 - 0.22 * (ly1 - ly0)                      # one baseline per line: rows group by baseline,
            if ly1 - ly0 > 2.2 * med[tuple(w['line'])]:          # unless the "line" is a column ("2." over "3." over "4.")
                base = y1 - 0.22 * (y1 - y0)
            x = x0
            for n, t in runs:
                page.insert_text((x, base), t, fontname=n, fontsize=size, render_mode=3)
                x += fonts[n].text_length(t, size)
    doc.save(PDF_OUT, garbage=3, deflate=True)
    (OUT / 'figures.json').write_text(json.dumps(figures), encoding='utf-8')
    for pno, boxes in formulas.items():                         # overlapping regions (numerators, the main line,
        merged = []                                             # denominators: Tesseract lines) are one formula
        for r in sorted(map(pymupdf.Rect, boxes), key=lambda r: r.y0):
            for i, m in enumerate(merged):
                if m.intersects(r): merged[i] = m | r; break
            else: merged.append(r)
        again = True
        while again:
            again = False
            for i, a in enumerate(merged):
                for b in merged[i + 1:]:
                    if a.intersects(b): merged[i] = a | b; merged.remove(b); again = True; break
                if again: break
        formulas[pno] = [[round(v, 1) for v in r] for r in merged]
    (OUT / 'formulas.json').write_text(json.dumps(formulas), encoding='utf-8')
    print(f'wrote {PDF_OUT} ({len(pages)} OCR pages, {sum(len(f) for f in figures.values())} figure regions, '
          f'{sum(len(f) for f in formulas.values())} formula regions, '
          f'{len(words)} resolved or corrected words{f", {len(corr)} from review" if corr else ""})')
    if lost: print(f'WARNING: characters no OCR font has, lost from the text layer: {dict(lost)}')


if __name__ == '__main__':
    {'run': run, 'recover': recover, 'resolve': resolve, 'review': review, 'build': build}[sys.argv[1]]()
