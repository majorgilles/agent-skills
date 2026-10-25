"""AI-written worked solutions for every exercise of a package, stored in it as generated.json: the reader shows each one
collapsed under its exercise, labelled as AI-generated. The book's own text and solutions are never touched.
  python tools/solve.py dist/<id>.omnibook [--model sonnet] [--jobs 8] [--batch 4] [--limit N] [--estimate]
Each exercise goes to the model with its group instructions, its section and chapter, the images of its formula crops
and the book's own solution when there is one, through `claude -p` (no tools). The reply is a small HTML subset with
LaTeX (\\( \\) and \\[ \\]) in @@E1@@ sections, sanitised here. Results are cached in ~/.cache/omnibook/solve/<book id>.json keyed by
exercise id and a hash of its content, so re-packaging a book only pays for the exercises that changed.
--estimate solves 8 exercises and prints the projected cost of the rest."""
import sys, re, io, os, json, html, base64, hashlib, zipfile, pathlib, datetime, threading, subprocess, collections, concurrent.futures
import pymupdf

CACHE = pathlib.Path.home() / '.cache' / 'omnibook' / 'solve'
LI = re.compile(r'<li\b[^>]*\bclass="ex"[^>]*\bid="(ex-[^"]+)"[^>]*>(.*?)</li>', re.S)
IMG = re.compile(r'<img\b[^>]*\bsrc="(figs/[^"]+)"[^>]*>')
ALLOWED = {'p', 'ol', 'ul', 'li', 'strong', 'em', 'i', 'b', 'br', 'sub', 'sup', 'code', 'pre', 'table', 'tr', 'td', 'th', 'h4'}
PROMPT = '''You write worked solutions to exercises from a textbook, for a student who reads them to learn how to solve
such exercises before writing their own. For each exercise: state the approach in one sentence, then solve it step by
step at the level of the book, justifying each step with the book's own facts, and end with the answer (or the end of
the proof). Proofs must be complete and rigorous. Be concise. Exercise images show the printed formulas exactly; the
book's own short answer, when given, is reliable: agree with it, and explain it if it is all the book gives.
An exercise's text may end with an instruction that introduces the next exercises ("Find the largest power of 2 which
divides the following integers."): ignore it there; the next exercises get it as their group instructions. Write for the
page, never to the reader: no offers, no requests for more information. If part of an exercise is truly illegible, solve
what is there and say in one short sentence what is missing.
Write HTML using only <p>, <ol>, <ul>, <li>, <strong>, <em>, <sub>, <sup>, <code>, <pre>, <table>; math in LaTeX
inside \\( ... \\) (inline) or \\[ ... \\] (display). No Markdown.
Reply with each solution after a line holding only its label between @@, and nothing else:
@@E1@@
<p>...</p>
@@E2@@
<p>...</p>'''
GROUP = re.compile(r'<p[^>]*class="ex-group"[^>]*>(.*?)</p>', re.S)
TRAILING = re.compile(r'(?:^|[.?!)]\s+|\d\s+)([A-Z][^.?!:]*\bfollowing\b[^.?!:]*[.:])\s*$')
COST = collections.Counter()


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def text_of(fragment):
    """Exercise HTML -> plain text with LaTeX kept and [image n] where a formula crop stands."""
    t = re.sub(r'<span class="tex"[^>]*>(.*?)</span>', lambda m: f'\\({html.unescape(m.group(1))}\\)', fragment, flags=re.S)
    n = iter(range(1, 999))
    t = IMG.sub(lambda m: f' [image {next(n)}] ', t)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t))).strip()


def png_of(files, path):
    """A crop as PNG bytes (SVG crops are rendered; tiny crops scaled up so the model can read them)."""
    data = files.get(path)
    if data is None: return None
    if path.endswith('.png'): return data
    doc = pymupdf.open(stream=data, filetype='svg')
    page = doc[0]
    z = max(2.0, 60 / max(page.rect.height, 1))
    return page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False).tobytes('png')


def exercises(files):
    """-> [{id, text, images, context, group, answer, hash}] for every exercise of the package, in reading order. The group
    instruction is the last ex-group paragraph of the exercise list, or a later sentence that a conversion left at the end
    of the previous exercise ("Find the largest power of 2 which divides the following integers.") and holds for the short
    exercises after it."""
    book = json.loads(files['book.json'])
    sols = json.loads(files.get('solutions.json', b'{}'))
    out = []
    for ch in book.get('chapters', []):
        src = files.get(f"chapters/{ch['slug']}.html", b'').decode('utf-8')
        carried = (-1, '')                                      # (offset, instruction) left at the end of an exercise
        for m in LI.finditer(src):
            before = src[:m.start()]
            sec = re.findall(r'<h2[^>]*>(.*?)</h2>', before, re.S)
            start = before.rfind('<div class="exercises"')
            groups = [(start + g.start(), g.group(1)) for g in GROUP.finditer(before[start:])] if start >= 0 else []
            group = text_of(groups[-1][1]) if groups else ''
            own = TRAILING.sub('', re.sub(r'\[image \d+\]', '', text_of(m.group(2))))
            words = re.findall(r'[A-Za-z]{2,}', own)
            if len(words) >= 6: carried = (-1, '')                # an exercise in words of its own ends the carried group
            if carried[0] > max(start, groups[-1][0] if groups else -1): group = carried[1]
            context = ' / '.join(x for x in (ch.get('title', ''), text_of(sec[-1]) if sec else '') if x)
            images = [p for p in IMG.findall(m.group(2))]
            ans = sols.get(m.group(1))
            item = {'id': m.group(1), 'text': text_of(m.group(2)), 'images': images, 'context': context,
                    'group': group, 'answer': text_of(ans) if ans else ''}
            blob = json.dumps(item, sort_keys=True).encode() + b''.join(files.get(p, b'') for p in images)
            item['hash'] = hashlib.sha1(blob).hexdigest()[:16]
            item['number'] = m.group(1).rsplit('-', 1)[-1]
            out.append(item)
            tail = TRAILING.search(item['text'])
            if tail: carried = (m.start(), tail.group(1))
    return book, out


def ask(model, title, batch, files):
    """One `claude -p` call for a batch of exercises -> {exercise id: html}."""
    content = [{'type': 'text', 'text': f'Textbook: {title}. {len(batch)} exercises follow.'}]
    for n, ex in enumerate(batch, 1):
        parts = [f'E{n}. Section: {ex["context"]}.', ex['group'] and f'Instructions for this group: {ex["group"]}',
                 f'Exercise {ex.get("number", "")}: {ex["text"]}', ex['answer'] and f"The book's own answer: {ex['answer']}"]
        content.append({'type': 'text', 'text': '\n'.join(p for p in parts if p)})
        for k, path in enumerate(ex['images'], 1):
            png = png_of(files, path)
            if png:
                content += [{'type': 'text', 'text': f'E{n} [image {k}]:'},
                            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': base64.b64encode(png).decode()}}]
    msg = json.dumps({'type': 'user', 'message': {'role': 'user', 'content': content}})
    cmd = ['claude', '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose', '--model', model,
           '--tools', '', '--strict-mcp-config', '--no-session-persistence', '--setting-sources', '', '--system-prompt', PROMPT]
    try:
        r = subprocess.run(cmd, input=msg + '\n', capture_output=True, text=True, timeout=1800)
        result = next(j for j in map(json.loads, r.stdout.splitlines()) if j.get('type') == 'result')
        COST[model] += result.get('total_cost_usd') or 0
        answer = parse(result.get('result') or '')
    except Exception as e:                                      # the batch stays unsolved: a rerun retries it
        print(f'  batch failed ({type(e).__name__}: {str(e)[:120]})', flush=True)
        return {}
    return {ex['id']: clean(answer[f'E{n}']) for n, ex in enumerate(batch, 1) if answer.get(f'E{n}')}


def parse(reply):
    """The reply's sections: {"E1": html, ...}, each after its @@E1@@ line (no escaping, so LaTeX arrives intact)."""
    parts = re.split(r'^\s*@@(E\d+)@@\s*$', reply, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def bad(entry):
    r"""A damaged cached solution: math cut short by the old tag filter, or from the JSON reply format with LaTeX
    turned into control characters."""
    h = entry['html']
    if h.count('\\(') != h.count('\\)') or h.count('\\[') != h.count('\\]'): return True   # math eaten as a tag
    return 'sections' not in entry and (any(c in h for c in '\f\b\t\r') or re.search(r'\n(eq|abla|u|ot|e[^\w])', h) is not None)


def clean(h):
    """Keep only the allowed tags, without attributes (the reader inserts this HTML into the page); < and > inside math
    are escaped first, or "\\(x<9\\), so <strong>" would read as a tag."""
    def tag(m):
        name = m.group(2).lower()
        return f'<{m.group(1)}{name}>' if name in ALLOWED else ''
    h = re.sub(r'\\\(.*?\\\)|\\\[.*?\\\]', lambda m: m.group(0).replace('<', '&lt;').replace('>', '&gt;'), h, flags=re.S)
    h = re.sub(r'<(script|style)\b.*?</\1>', '', h, flags=re.S | re.I)
    return re.sub(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>', tag, h).strip()


def main():
    path = pathlib.Path(sys.argv[1])
    model, jobs, size = arg('--model', 'sonnet'), int(arg('--jobs', 8)), int(arg('--batch', 4))
    with zipfile.ZipFile(path) as z: files = {n: z.read(n) for n in z.namelist()}
    book, items = exercises(files)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE / f"{book['id']}.json"
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    todo = [ex for ex in items if cache.get(ex['id'], {}).get('hash') != ex['hash'] or bad(cache[ex['id']])]
    print(f"{book['title']}: {len(items)} exercises, {len(items) - len(todo)} cached, {len(todo)} to solve", flush=True)
    if '--estimate' in sys.argv: todo = todo[:8]
    elif '--limit' in sys.argv: todo = todo[:int(arg('--limit', 0))]
    lock, done = threading.Lock(), [0]
    def one(batch):
        got = ask(model, book['title'], batch, files)
        with lock:
            for ex in batch:
                if ex['id'] in got: cache[ex['id']] = {'hash': ex['hash'], 'html': got[ex['id']], 'model': model, 'sections': True}
            done[0] += len(batch)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
            print(f'  {done[0]}/{len(todo)}', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(one, [todo[i:i + size] for i in range(0, len(todo), size)]))
    if '--estimate' in sys.argv:
        per = sum(COST.values()) / max(1, len(todo))
        rest = sum(1 for ex in items if cache.get(ex['id'], {}).get('hash') != ex['hash'])
        print(f'cost so far ${sum(COST.values()):.2f} (${per:.3f} per exercise): about ${per * rest:.0f} for the {rest} left')
        return
    current = {ex['id']: ex['hash'] for ex in items}
    sols = {k: {'html': v['html']} for k, v in cache.items() if current.get(k) == v['hash']}
    files['generated.json'] = json.dumps({'model': f'Claude ({model})', 'created': datetime.date.today().isoformat(),
                                          'solutions': sols}, ensure_ascii=False).encode()
    tmp = path.with_suffix('.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, data in files.items(): z.writestr(n, data)
    os.replace(tmp, path)
    print(f'wrote {len(sols)} of {len(items)} worked solutions into {path}' + (f' (${sum(COST.values()):.2f})' if COST else ''))


if __name__ == '__main__':
    main()
