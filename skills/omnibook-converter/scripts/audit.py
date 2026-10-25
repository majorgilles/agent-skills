"""Completeness audit of one converted content file against its PDF pages. Where verify.py checks prose words in
reading order, this accounts for *everything* printed on the pages:
  1. characters  every glyph outside a crop must appear in the HTML text (multiset, all fonts: math letters, digits,
                 code, captions, notes, markers); every crop region must be an image or a checked LaTeX transcription.
  2. drawings    every vector drawing and raster image must lie inside a crop (or be known page furniture:
                 backgrounds, rules, bullets, badges, shaded panels behind text).
  3. pixels      every figure crop (SVG) is rendered and compared with the same region of the PDF page.
  4. structure   exercise numbers gap-free per block, solutions without orphans, listing annotations matched.
  python tools/audit.py content/ch01.html [--no-pixels]
Writes work/audit/<slug>.json (+ PNGs of anything unaccounted for) and exits 1 if anything is unaccounted for."""
import sys, os, re, json, html, pathlib, collections, pymupdf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import page_spans, page_furniture, loose_marks, _white, TOP, BOTTOM, OCR, NEGATED, ACCENTS, overlines, char_key, bar_accents
from bookprofile import pdf_path

ROOT = pathlib.Path(__file__).resolve().parent.parent
CROP = re.compile(r'data-crop="(\d+):([\d.]+),([\d.]+),([\d.]+),([\d.]+)"')
LIG = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}


def crops_of(src):
    by_page = collections.defaultdict(list)
    for m in CROP.finditer(src):
        by_page[int(m.group(1))].append(pymupdf.Rect(*map(float, m.groups()[1:])))
    return by_page


def html_chars(src):
    """Visible text characters of the content file (crops and LaTeX stand in for their regions)."""
    src = re.sub(r'<!--.*?-->', ' ', src, flags=re.S)
    src = re.sub(r'<span class="tex"[^>]*>.*?</span>', ' ', src, flags=re.S)          # transcribed crops
    src = re.sub(r'\\\(.*?\\\)|\\\[.*?\\\]', ' ', src, flags=re.S)
    nums = ''.join(f'{v}.' for v in re.findall(r'<li class="ex"[^>]*\bvalue="(\d+)"', src))   # numbers drawn by <ol>
    text = html.unescape(re.sub(r'<[^>]+>', '', src)) + nums
    for a, b in LIG.items(): text = text.replace(a, b)
    return collections.Counter(c for c in text if not c.isspace())


def in_crop(s, boxes):
    """Same rule the converter uses: a span belongs to a crop when most of its box lies inside."""
    r = s.rect()
    return any((r & b).get_area() > 0.5 * max(r.get_area(), 0.01) for b in boxes)


def missing_lines(pages, crops, doc, src):
    """PDF text lines (outside crops) whose characters don't occur, in order, anywhere in the HTML text:
    localises what the character totals report."""
    from layout import analyse
    text = re.sub(r'<span class="tex"[^>]*>.*?</span>|\\\(.*?\\\)', ' ', src, flags=re.S)
    flat = ''.join(c for c in html.unescape(re.sub(r'<[^>]+>', '', text)) if not c.isspace())
    for a, b in LIG.items(): flat = flat.replace(a, b)
    out = []
    for pno in pages:
        boxes = [c + (-1, -1, 1, 1) for c in crops.get(pno, [])]
        for row in analyse(doc[pno])[0]:
            t = ''.join(v.text for k, v in row.items if k == 'span' and not in_crop(v, boxes)
                        and not (v.bold and re.fullmatch(r'\s*\d+\.\s*', v.text)))   # list numbers are drawn by <ol>
            for a, b in LIG.items(): t = t.replace(a, b)
            t = ''.join(c for c in t if not c.isspace()).rstrip('-')
            if len(t) >= 6 and t not in flat:
                out.append({'page': pno, 'y': round(row.y0, 1), 'text': t[:80]})
    return out


def pdf_chars(pages, crops, doc):
    """Glyphs on the pages outside every crop, plus the number of line-end hyphens (rejoined words lose them)."""
    cnt, hyph, where = collections.Counter(), 0, collections.defaultdict(list)
    for pno in pages:
        boxes = [c + (-1, -1, 1, 1) for c in crops.get(pno, [])]
        for s in page_spans(doc[pno]):
            t = s.text
            for a, b in LIG.items(): t = t.replace(a, b)
            if in_crop(s, boxes): continue
            for c in t:
                if not c.isspace(): cnt[c] += 1; where[c].append(pno)
            if t.rstrip().endswith('-'): hyph += 1
    return cnt, hyph, where


def negations_check(pages, crops, doc, src):
    """Every negation printed outside a crop must be negated in the HTML: a lost slash reverses the meaning
    ("does not imply" read as "implies"). Counted straight from the PDF, not through layout.Span: negation slashes
    (U+0338, drawn over a symbol) plus precomposed negated glyphs (≠, ∉, ⇏, ...), against the negated signs and
    combining slashes in the visible HTML text. Returns [] or one issue with the PDF pages that carry negations."""
    n_pdf, where = 0, []
    for pno in pages:
        boxes = crops.get(pno, [])
        chars = [c for b in doc[pno].get_text('rawdict')['blocks'] for l in b.get('lines', []) for s in l['spans']
                 for c in s['chars'] if c['c'].strip() and c['c'] != '\u0338']
        def out(c):                                            # the centre of the glyph decides, as for a span
            r = pymupdf.Rect(c['bbox']); return not any(pymupdf.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2) in b for b in boxes)
        def base(x, y):                                        # the symbol a slash is drawn over (same origin)
            return next((c for c in chars if abs(c['origin'][0] - x) < 0.6 and abs(c['origin'][1] - y) < 0.6), None)
        k = 0
        for sp in doc[pno].get_texttrace():
            for ch in sp['chars']:
                if ch[0] == 0x338:
                    c = base(*ch[2])
                    k += 1 if c is None or out(c) else 0       # a slash over nothing is still a negation to account for
        k += sum(1 for c in chars if c['c'] in NEGATED and out(c))
        n_pdf += k
        if k: where.append(pno)
    text = re.sub(r'<!--.*?-->|<span class="tex"[^>]*>.*?</span>|\\\(.*?\\\)|\\\[.*?\\\]', ' ', src, flags=re.S)
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    n_html = sum(1 for c in text if c in NEGATED or c == '\u0338')
    return [] if n_pdf == n_html else [{'pdf_negations': n_pdf, 'html_negations': n_html, 'pages': where}]


def bars_check(pages, crops, doc, src):
    """Bars change the meaning (P̄ "not P", z̄ conjugate, 1.8̅1̅3̅ recurring, √ over a sum): none may be lost.
    1. every bar accent glyph outside a crop is a combining macron (U+0304) in the HTML, and no loose "¯" is left;
    2. every drawn overline outside a crop is in the HTML over the same characters (combining U+0305 on each)."""
    issues, n_pdf, runs, native_overlines = [], 0, [], 0
    for pno in pages:
        boxes = crops.get(pno, [])
        raw = [s for b in doc[pno].get_text('rawdict')['blocks'] for l in b.get('lines', []) for s in l['spans']]
        chars = [c for s in raw for c in s['chars'] if c['c'].strip()]
        out = lambda c: not any(pymupdf.Point((c['bbox'][0] + c['bbox'][2]) / 2, (c['bbox'][1] + c['bbox'][3]) / 2) in b
                                for b in boxes)
        drop, over = bar_accents(raw)                          # an accent counts where its letter is (as the converter places it)
        n_pdf += sum(1 for c in chars if char_key(c) in over and out(c))
        n_pdf += sum(1 for c in chars if c['c'] in ACCENTS and char_key(c) not in drop and out(c))   # on no letter: lost
        n_pdf += sum(1 for c in chars if c['c'] == '\u0304' and out(c))   # already combined in the text layer (OCR)
        native_overlines += sum(1 for c in chars if c['c'] == '\u0305' and out(c))
        keys = overlines(doc[pno], raw)
        line = sorted((c for c in chars if char_key(c) in keys and out(c)), key=lambda c: (round(c['origin'][1]), c['origin'][0]))
        if line: runs.append((pno, ''.join(c['c'] + '\u0305' for c in line)))
    text = re.sub(r'<!--.*?-->|<span class="tex"[^>]*>.*?</span>|\\\(.*?\\\)|\\\[.*?\\\]', ' ', src, flags=re.S)
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    flat = ''.join(c for c in text if not c.isspace())
    n_html = text.count('\u0304')
    if n_pdf != n_html: issues.append({'bar_accents_pdf': n_pdf, 'combining_macrons_html': n_html})
    if any(c in text for c in ACCENTS): issues.append({'loose_bar_accents_html': sum(text.count(c) for c in ACCENTS)})
    marked = sum(1 for c in flat if c == '\u0305')
    expected = sum(r.count('\u0305') for _, r in runs) + native_overlines
    if marked != expected: issues.append({'overlined_chars_pdf': expected, 'overlined_chars_html': marked,
                                          'pages': [p for p, _ in runs]})
    return issues


def words_in_crops(pages, crops, doc):
    """Crops containing words of the prose font: diagram labels are fine, a swallowed sentence is not. Neither the
    character check nor verify.py looks inside crops, so these are listed for review (PNG in work/audit)."""
    out = []
    for pno in pages:
        spans = [s for s in page_spans(doc[pno]) if s.prose]
        for c in crops.get(pno, []):
            ws = [w for s in spans if (c + (-1, -1, 1, 1)).contains(pymupdf.Point((s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2))
                  for w in re.findall(r'[^\W\d_]{3,}', s.text)]
            if len(ws) >= 4: out.append({'page': pno, 'rect': [round(x, 1) for x in c], 'words': len(ws), 'sample': ' '.join(ws[:6])})
    return out


def drawings_check(pages, crops, doc, out_dir, slug):
    missing = []
    for pno in pages:
        page = doc[pno]
        ignore, panels, marks = page_furniture(page, page_spans(page))
        loose = loose_marks(page)                                    # lone bars and marks drawn as images: layout
        boxes = [c + (-2, -2, 2, 2) for c in crops.get(pno, [])]
        items = [(i, pymupdf.Rect(d['rect']), 'drawing') for i, d in enumerate(page.get_drawings())
                 if i not in ignore and not _white(d)]           # white on white paper carries no ink
        items += [(None, pymupdf.Rect(b['bbox']), 'image') for b in page.get_text('dict')['blocks'] if b['type'] == 1
                  and not (OCR and pymupdf.Rect(b['bbox']).get_area() > 0.6 * page.rect.get_area())   # the scan itself
                  and tuple(pymupdf.Rect(b['bbox'])) not in loose]
        for i, r, kind in items:
            if r.y1 < TOP or r.y0 > BOTTOM: continue                 # running heads, footers
            if r.height < 1.2 and (r.width > 250 or r.width < 30): continue   # rules (decoration) / bar slivers
            if r.width < 0.5 and r.height < 0.5: continue
            pad = r + (-0.5, -0.5, 0.5, 0.5)
            inside = sum((pad & b).get_area() for b in boxes)
            if inside >= 0.5 * pad.get_area(): continue
            if any((p + (-2, -2, 2, 2)).contains(r) for p in panels): continue   # a panel's own frame or shading
            missing.append({'page': pno, 'kind': kind, 'rect': [round(x, 1) for x in r]})
            png = out_dir / f'{slug}-p{pno}-{len(missing)}.png'
            doc[pno].get_pixmap(dpi=110, clip=(r + (-20, -20, 20, 20)) & page.rect).save(png)
    if OCR:                                                          # scans: non-text ink regions found by ocr.py
        from layout import ocr_figures
        for pno in pages:
            for r in map(pymupdf.Rect, ocr_figures().get(str(pno), []) + ocr_figures('formulas').get(str(pno), [])):
                if not any((r & b).get_area() > 0.5 * r.get_area() for b in crops.get(pno, [])):
                    missing.append({'page': pno, 'kind': 'scan ink', 'rect': [round(x, 1) for x in r]})
    return missing


class Browser:
    """Renders SVG crops the way readers see them: headless Chromium via Playwright (MuPDF's own SVG reader
    mis-draws some valid SVGs, e.g. clipped patterns). CHROMIUM=/path/to/chrome picks a specific binary.
    Without Playwright the audit falls back to MuPDF and says so."""
    def __init__(self):
        self.pw = self.browser = None; self.pages = {}
        try:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(**({'executable_path': os.environ['CHROMIUM']} if os.environ.get('CHROMIUM') else {}))
        except Exception as e:
            print(f'  (no browser for SVG rendering, using MuPDF: {str(e).splitlines()[0][:100]})')
            if self.pw: self.pw.stop()
            self.pw = None

    def render(self, path, z):
        if not self.browser: return None
        if z not in self.pages: self.pages[z] = self.browser.new_context(device_scale_factor=z).new_page()
        pg = self.pages[z]
        head = path.read_text(encoding='utf-8')[:600]
        w, h = (float(re.search(rf'\b{k}="([\d.]+)', head).group(1)) for k in ('width', 'height'))
        pg.set_viewport_size({'width': int(w) + 2, 'height': int(h) + 2})
        pg.goto(path.resolve().as_uri())                                       # an SVG document draws at its own size, from 0,0
        png = pg.screenshot(clip={'x': 0, 'y': 0, 'width': -(-w // 1), 'height': -(-h // 1)})   # whole CSS px, rounded up
        p = pymupdf.Pixmap(png)
        return pymupdf.Pixmap(p, 0) if p.alpha else p

    def close(self):
        if self.pw: self.browser.close(); self.pw.stop()


def pixels_check(src, doc, browser):
    """Render each figure crop (SVG or PNG) and the PDF region at the same size; report crops whose pixels differ."""
    bad = []
    for m in re.finditer(r'<img (?:class="m" )?src="(figs/[^"]+\.(?:svg|png))"[^>]*?' + CROP.pattern, src):
        path = ROOT / 'site' / m.group(1)
        pno, r = int(m.group(2)), pymupdf.Rect(*map(float, m.groups()[2:]))
        if not path.exists() or path.stat().st_size < 50:
            bad.append({'file': m.group(1), 'error': 'missing or empty'}); continue
        try:
            if path.suffix == '.png':                                # compare at the PNG's own resolution
                a = pymupdf.Pixmap(str(path)); est = max(a.width / r.width, a.height / r.height) * 72   # the export dpi: the one that
                size = lambda d: (lambda q: (q.width, q.height))(doc[pno].get_pixmap(matrix=pymupdf.Matrix(d / 72, d / 72), clip=r))
                z = next((d / 72 for d in (round(est), int(est), int(est) + 1, 150, 300)   # renders the PNG's own size
                          if size(d) == (a.width, a.height)), round(est) / 72)             # (rounding alone misses by 1)
                if a.alpha: a = pymupdf.Pixmap(a, 0)
            else:
                z = 3 if r.width * r.height < 4000 else 2   # small crops: finer grid
                a = browser.render(path, z) or pymupdf.open(str(path))[0].get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
        except Exception as e:
            bad.append({'file': m.group(1), 'error': f'unreadable image: {e}'}); continue
        b = doc[pno].get_pixmap(matrix=pymupdf.Matrix(z, z), clip=r, alpha=False)
        w, h = min(a.width, b.width), min(a.height, b.height)
        if abs(a.width - b.width) > 3 or abs(a.height - b.height) > 3:
            bad.append({'file': m.group(1), 'error': f'size {a.width}x{a.height} vs PDF {b.width}x{b.height}'}); continue
        (miss, n_miss), (extra, n_extra) = ink_compare(a, b, w, h, round(2.5 * z))
        blob = 5 * z * z                                             # ~5 pt² of ink: less is anti-aliasing at stroke ends
        if (miss > 0.02 and n_miss > blob) or (extra > 0.02 and n_extra > blob):
            bad.append({'file': m.group(1), 'error': f'ink differs: {100 * miss:.1f}% of the PDF ink missing, {100 * extra:.1f}% extra'})
    return bad


def ink_compare(a, b, w, h, edge=0):
    """Share of PDF ink pixels with no crop ink within 2 px, and the reverse. Anti-aliasing (glyphs drawn as outlines
    vs the font rasterizer) and sub-pixel grid offsets don't count; missing or extra ink does. PDF ink within `edge`
    px of the border is not required: neighbouring lines poke into the rectangle and are (rightly) not in the crop."""
    def mask(p, level):
        s, n, out = p.samples, p.n, bytearray(w * h)
        for y in range(h):
            r = y * p.stride
            for x in range(w):
                out[y * w + x] = min(s[r + x * n: r + x * n + min(n, 3)]) < level
        return out
    A, B, A_faint, B_faint = mask(a, 140), mask(b, 140), mask(a, 225), mask(b, 225)   # dark ink must meet any ink
    R = 2                                                            # within 2 px (sub-point at the scales used)
    def unmatched(P, Q, edge=0):
        total = bad = 0
        for y in range(edge, h - edge):
            for x in range(edge, w - edge):
                if not P[y * w + x]: continue
                total += 1
                if not any(Q[yy * w + xx] for yy in range(max(0, y - R), min(h, y + R + 1)) for xx in range(max(0, x - R), min(w, x + R + 1))):
                    bad += 1
        return (bad / total if total else 0.0), bad
    return unmatched(B, A_faint, edge), unmatched(A, B_faint)


def structure_check(src, slug):
    issues = []
    for blk in re.findall(r'<div class="exercises" data-for="([^"]+)">(.*?)(?=<div class="exercises"|$)', src, flags=re.S):
        nums = [int(v) for v in re.findall(r'<li class="ex"[^>]*\bvalue="(\d+)"', blk[1])] or \
               [int(v) for v in re.findall(r'id="sol-[^"]*-(\d+)"', blk[1])]
        if not nums: continue
        dup = [k for k, c in collections.Counter(nums).items() if c > 1]
        if dup: issues.append(f'exercises {blk[0]}: duplicate numbers {dup}')
        if slug != 'solutions':                                      # solutions legitimately skip (odd-only answers)
            gaps = sorted(set(range(1, max(nums) + 1)) - set(nums))
            if gaps: issues.append(f'exercises {blk[0]}: missing numbers {gaps}')
    if slug == 'solutions':
        ids = set()
        for f in (ROOT / 'content').glob('*.html'):
            if f.stem != 'solutions': ids |= set(re.findall(r'<li class="ex" id="([^"]+)"', f.read_text(encoding='utf-8')))
        orphans = [x for x in re.findall(r'data-ex="([^"]+)"', src) if x not in ids]
        if orphans: issues.append(f'{len(orphans)} solutions without an exercise, e.g. {orphans[:5]}')
    for lst in re.findall(r'<figure class="listing".*?</figure>', src, flags=re.S):
        code = re.findall(r'<pre.*?</pre>', lst, flags=re.S)
        in_code = set(re.findall(r'class="anno" data-a="([^"]+)"', ''.join(code)))
        listed = set(re.findall(r'<li data-a="([^"]+)"', lst))
        if in_code != listed:
            cap = re.sub(r'<[^>]+>', '', re.search(r'<figcaption>(.*?)</figcaption>', lst, flags=re.S).group(1))[:40]
            issues.append(f'listing "{cap}": markers in code {sorted(in_code)} vs annotations {sorted(listed)}')
    ids = re.findall(r'\bid="([^"]+)"', src)
    dups = [k for k, c in collections.Counter(ids).items() if c > 1]
    if dups: issues.append(f'duplicate element ids {dups[:8]}')
    return issues


def main(f, pixels=True):
    src = open(f, encoding='utf-8').read()
    slug = pathlib.Path(f).stem
    a, b = map(int, re.search(r'<!-- pages: (\d+)-(\d+) -->', src).groups())
    m = re.search(r'<!-- skip: (\d+)-(\d+) -->', src)
    skip = set(range(int(m.group(1)), int(m.group(2)) + 1)) if m else set()
    pages = [p for p in range(a, b + 1) if p not in skip]
    doc, crops = pymupdf.open(pdf_path()), crops_of(src)
    regions = crops_of(src.replace('data-region=', 'data-crop='))   # tables cover their rules (their text is checked)
    out_dir = ROOT / 'work' / 'audit'; out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f'{slug}-p*.png'): old.unlink()

    browser = Browser() if pixels else None
    P, hyph, where = pdf_chars(pages, crops, doc)
    H = html_chars(src)
    missing, extra = P - H, H - P
    if missing.get('-', 0) <= hyph: missing.pop('-', None)          # hyphens of words rejoined across line breaks
    report = {
        'file': f, 'pages': [a, b], 'pdf_chars': sum(P.values()), 'html_chars': sum(H.values()),
        'crops': sum(len(v) for v in crops.values()),
        'missing_chars': {c: {'n': n, 'pages': sorted(set(where[c]))[:10]} for c, n in missing.most_common()},
        'extra_chars': dict(extra.most_common()),
        'uncovered_drawings': drawings_check(pages, regions, doc, out_dir, slug),
        'figure_pixels': pixels_check(src, doc, browser) if pixels else 'skipped',
        'structure': structure_check(src, slug),
        'negations': negations_check(pages, crops, doc, src),
        'bars': bars_check(pages, crops, doc, src),
        'words_in_crops': words_in_crops(pages, crops, doc),   # review list, not a failure
        'lines_not_found': missing_lines(pages, crops, doc, src) if missing else [],
    }
    if browser: browser.close()
    (out_dir / f'{slug}.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    fails = len(report['missing_chars']) + len(report['extra_chars']) + len(report['uncovered_drawings']) \
        + (len(report['figure_pixels']) if pixels else 0) + len(report['structure']) + len(report['negations']) + len(report['bars'])
    print(f"{f}: {report['pdf_chars']} chars in PDF outside crops, {report['html_chars']} in HTML, {report['crops']} crops | "
          f"missing {sum(missing.values())} {''.join(list(missing)[:20])!r} | extra {sum(extra.values())} {''.join(list(extra)[:20])!r} | "
          f"uncovered drawings {len(report['uncovered_drawings'])} | figure pixel mismatches "
          f"{len(report['figure_pixels']) if pixels else 'skipped'} | structure issues {len(report['structure'])} | negations lost {len(report['negations'])} | bars lost {len(report['bars'])}")
    if report['words_in_crops']:
        print(f"  review: {len(report['words_in_crops'])} crops contain prose words "
              f"({sum(c['words'] for c in report['words_in_crops'])} words); see words_in_crops in the JSON")
    for s in report['lines_not_found'][:8]: print('  line not in HTML:', s['page'], s['y'], s['text'][:50])
    for s in report['structure']: print('  structure:', s)
    for s in report['negations']: print('  NEGATION LOST (meaning reversed):', s)
    for s in report['bars']: print('  BAR LOST (meaning changed):', s)
    for d in report['uncovered_drawings'][:10]: print('  uncovered:', d)
    if pixels:
        for d in report['figure_pixels'][:10]: print('  pixels:', d)
    return fails


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1], '--no-pixels' not in sys.argv) else 0)
