"""Verbatim check, in reading order: prose words (profile fonts.prose) from the PDF pages vs the visible text of a
content file, plus every code line (profile fonts.mono rows) vs the <pre class="code"> lines.
  python tools/verify.py content/ch01.html      (file must start with <!-- pages: A-B -->, 0-based PDF indices)
Text inside figures and math crops is excluded (those are exact images; audit.py accounts for them).
Exit 1 if any prose word run or code line is missing, changed or inserted."""
import pymupdf, re, sys, os, html, difflib
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from layout import analyse, page_spans, rejoin, unglue
from bookprofile import PROFILE, rx, pdf_path

LIG = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl', '’': "'", '‘': "'", '“': '"', '”': '"', '–': '-', '—': '-'}
MATHWORDS = {'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'log', 'exp', 'max', 'min', 'lim', 'mod', 'gcd', 'lcm', 'det', 'arctan', 'arcsin'}
EXERCISES, SOLUTIONS, SECTION = rx('exercises'), rx('solutions'), rx('section')
CONT, ANNO = PROFILE['patterns']['code_continuation'], rx('code_annotation')


def norm(t):
    for a, b in LIG.items(): t = t.replace(a, b)
    t = re.sub(r'[-—–]', ' ', re.sub(r'\d', '', t))            # digits are math; dashes split words
    t = re.sub(r'\b(?:[^\W\d_] ){3,}[^\W\d_]\b', lambda m: m.group(0).replace(' ', ''), t)   # "C H A P T E R" set spaced out
    return [w for w in (re.sub(r"[^\w']", '', x).lower() for x in t.split()) if w and w not in MATHWORDS]


def code_norm(line):
    """A code line compared without layout: wrap/annotation markers and runs of spaces removed."""
    if CONT: line = line.replace(CONT, ' ')
    if ANNO: line = ANNO.sub('', line)
    return ' '.join(line.split())


def pdf_words(a, b, skip=(), solutions=False):
    """Returns (body words in reading order, [word list per exercise block], prose chars inside crops, code lines)."""
    d = pymupdf.open(pdf_path()); parts, cropped, code, tables = [[]], 0, [], []   # parts[0] = body lines, parts[1:] = exercise blocks
    cur, block, prev_row = parts[0], SOLUTIONS if solutions else EXERCISES, None
    for i in (p for p in range(a, b + 1) if p not in skip):
        rows, figs = analyse(d[i])
        allp = sum(len(s.text.replace(' ', '')) for s in page_spans(d[i]) if s.prose)
        for r in rows:
            if r.table is not None:                     # tables: compared as one multiset each (cells wrap)
                entry = next((t for t in tables if t[0] is r.table), None)   # side-by-side tables share their lines
                if entry is None: entry = [r.table, []]; tables.append(entry)
                col = lambda v: sum(x < (v.x0 + v.x1) / 2 for x in r.table.cols[1:-1])   # cells are words apart
                cells = {}
                for k, v in r.items:
                    if k == 'span': cells.setdefault(col(v), []).append(v.text if not v.mathital and not v.mono else ' ')
                    elif cells: cells[max(cells)].append(' ')
                entry[1] += norm(' '.join(''.join(c) for _, c in sorted(cells.items())))
                continue
            vis = [v for k, v in r.items if k == 'span' and v.text.strip()]
            if vis and all(v.mono for v in vis) and not any(k == 'math' for k, _ in r.items):
                code.append(code_norm(''.join(v.text for k, v in r.items if k == 'span')))
            # prose words, plus other non-math text (braces, punctuation) exactly where the HTML keeps it
            t = ''.join(v.text if k == 'span' and not v.mathital and not v.mono else ' ' if k != 'space' else ' '
                        for k, v in r.items).strip()
            first = next((v for k, v in r.items if k == 'span' and v.text.strip()), None)
            if PROFILE['ocr'] and r.size >= PROFILE['sizes']['title']: t = unglue(t)   # as the converter splits OCR titles
            strong = first and (first.bold or PROFILE['ocr'])   # an OCR layer has no bold: patterns alone mark headings
            if strong and block and block.match(t): parts.append([]); cur = parts[-1]
            elif first and (strong and SECTION and SECTION.match(t) and r.size > PROFILE['sizes']['section_min']
                            or r.size >= PROFILE['sizes']['title']): cur = parts[0]
            cap = r.size > PROFILE['sizes']['dropcap'] and len(t) == 1 and t.isupper()
            if cap and cur and prev_row and prev_row[0] == i and prev_row[1] >= r.y0 - 8:   # drop cap after its first line
                cur[-1] = t + cur[-1]
            elif t and cur and len(cur[-1]) == 1 and cur[-1].isupper() and cur is parts[0]: cur[-1] += t   # drop cap before it
            elif t: cur.append(t)
            if t and not cap: prev_row = (i, r.y0)
        cropped += allp - sum(len(''.join(v.text for k, v in r.items if k == 'span' and v.prose).replace(' ', '')) for r in rows)
    def dehyph(ls):                                   # undo end-of-line hyphenation the same way the converter does
        out = []
        for l in ls:
            if out and out[-1].endswith('-'): out[-1] = rejoin(out[-1], l)
            else: out.append(l)
        return norm('\n'.join(out))
    return dehyph(parts[0]), [dehyph(p) for p in parts[1:]], cropped, code, [t[1] for t in tables]


def exercise_blocks(src):
    """Split out every <div class="exercises"> with its nested divs -> ([block html], rest of the page)."""
    blocks, rest, i = [], [], 0
    for m in re.finditer(r'<div class="exercises"', src):
        if m.start() < i: continue
        depth, j = 0, m.start()
        for t in re.finditer(r'<div\b|</div>', src[m.start():]):
            depth += 1 if t.group(0) == '<div' else -1
            if depth == 0: j = m.start() + t.end(); break
        rest.append(src[i:m.start()]); blocks.append(src[m.start():j]); i = j
    return blocks, ' '.join(rest) + src[i:]


def html_words(src):
    marks = lambda l: re.sub(r'<span class="(anno|cont)"[^>]*>.*?</span>', ' ', l)   # tagged markers (audit.py counts them)
    code = [code_norm(html.unescape(re.sub(r'<[^>]+>', '', marks(l))))
            for c in re.findall(r'<pre class="code"[^>]*><code>(.*?)</code></pre>', src, flags=re.S) for l in c.split('\n')]
    src = re.sub(r'<(script|style|svg)\b.*?</\1>', ' ', src, flags=re.S)
    src = re.sub(r'<pre class="code".*?</pre>', ' ', src, flags=re.S)
    src = re.sub(r'<i>.*?</i>', ' ', src, flags=re.S)   # math italic letters: math fonts are excluded on the PDF side too
    src = re.sub(r'<code>.*?</code>', ' ', src, flags=re.S)   # inline code is set in the mono font, not the prose font
    src = re.sub(r'\\\(.*?\\\)|\\\[.*?\\\]', ' ', src, flags=re.S)  # MathJax math is not prose
    tables = re.findall(r'<table class="tbl".*?</table>', src, flags=re.S)
    src = re.sub(r'<table class="tbl".*?</table>', ' ', src, flags=re.S)
    blocks, body = exercise_blocks(src)
    words = lambda s: norm(html.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'</?(strong|em|sup|sub|span)\b[^>]*>', '', s))))  # inline tags are zero-width
    return words(body), [words(x) for x in blocks], [c for c in code if c], [words(x) for x in tables]


def main(f):
    src = open(f, encoding='utf-8').read()
    a, b = map(int, re.search(r'<!-- pages: (\d+)-(\d+) -->', src).groups())
    m = re.search(r'<!-- skip: (\d+)-(\d+) -->', src)
    P, PX, cropped, PC, PT = pdf_words(a, b, range(int(m.group(1)), int(m.group(2)) + 1) if m else (), 'solutions' in os.path.basename(f))
    H, HX, HC, HT = html_words(src)
    bad = 0
    if len(PX) != len(HX):
        bad += 1; print(f'[blocks] PDF has {len(PX)} exercise blocks, HTML has {len(HX)}')
    for k, (p, h) in enumerate(zip(PX, HX)):          # exercise order legitimately differs (columns): compare as multisets
        cp, ch = Counter(w for w in p if re.search(r'[a-z]{3,}', w)), Counter(w for w in h if re.search(r'[a-z]{3,}', w))
        if cp != ch:
            bad += 1; print(f'[exercise block {k + 1}] missing: {dict(cp - ch)} extra: {dict(ch - cp)}')
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, P, H, autojunk=False).get_opcodes():
        if op == 'equal': continue
        miss, extra = ' '.join(P[i1:i2]), ' '.join(H[j1:j2])
        if not re.search(r'[a-z]{3,}', miss + ' ' + extra): continue   # math letters/numbers: noise
        bad += 1; ctx = ' '.join(P[max(0, i1 - 5):i1])
        print(f'[{op}] ...{ctx} | PDF: "{miss[:120]}" | HTML: "{extra[:120]}"')
    if len(PT) != len(HT):
        bad += 1; print(f'[tables] PDF has {len(PT)} tables, HTML has {len(HT)}')
    for k, (p, h) in enumerate(zip(PT, HT)):
        if Counter(p) != Counter(h):
            bad += 1; print(f'[table {k + 1}] missing: {dict(Counter(p) - Counter(h))} extra: {dict(Counter(h) - Counter(p))}')
    PC = [c for c in PC if c]
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, PC, HC, autojunk=False).get_opcodes():
        if op == 'equal': continue
        bad += 1; print(f'[code {op}] PDF: {PC[i1:i2][:3]} | HTML: {HC[j1:j2][:3]}')
    print(f'{f}: {len(P)} prose words in PDF, {len(H)} in HTML, {len(PC)} code lines in PDF, {len(HC)} in HTML, '
          f'{bad} discrepancies; {cropped} prose chars inside figure/math crops')
    return bad


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1]) else 0)
