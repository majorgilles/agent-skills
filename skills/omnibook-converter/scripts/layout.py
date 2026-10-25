"""Page layout analysis: turns a PDF page into rows of styled spans, figure boxes and hard-math boxes.
Text is taken verbatim from the PDF text layer; only custom-encoded math glyphs are remapped (profile fonts.fix).
Every book-specific constant comes from profile.json (see bookprofile.py)."""
import re, pymupdf
from bookprofile import PROFILE, pdf_path

F, SZ, PG = PROFILE['fonts'], PROFILE['sizes'], PROFILE['page']
FIX = F['fix']
NEG = {'=': '≠', '∈': '∉', '⊆': '⊈', '⊂': '⊄', '⊇': '⊉', '⊃': '⊅', '≡': '≢', '|': '∤', '∃': '∄', '<': '≮', '>': '≯',
       '≤': '≰', '≥': '≱', '∼': '≁', '≈': '≉', '∣': '∤', '⇒': '⇏', '⇐': '⇍', '⇔': '⇎', '→': '↛', '←': '↚', '↔': '↮',
       '∋': '∌', '≅': '≇', '≃': '≄', '≺': '⊀', '≻': '⊁', '⊢': '⊬', '⊨': '⊭', '∥': '∦', '≍': '≭', '⊑': '⋢', '⊒': '⋣'}
NEGATED = set(NEG.values())   # a negation must never be lost: it reverses the meaning (audit.py negations_check)
TOP, BOTTOM = PG['top'], PG['bottom']
PROSE, MONO, BOLD, ITAL, MATHITAL = (re.compile(F[k]) for k in ('prose', 'mono', 'bold', 'italic', 'math_italic'))
TEXT = re.compile(F['text']) if F['text'] else None
EXT, RADICAL = set(F['extension']), F['radical']
SMALL, NORMAL = SZ['small'], SZ['normal_min']
GAP = PROFILE['layout']['space_gap']


class Span:
    def __init__(self, s, slashes=(), accents=None):
        self.font, self.size = s['font'], s['size']
        ch = [c for c in s['chars'] if c['c'].strip()] or s['chars']   # char boxes: span boxes can take the whole line's height
        self.x0, self.x1 = s['bbox'][0], s['bbox'][2]
        self.y0 = min(c['bbox'][1] for c in ch); self.y1 = max(c['bbox'][3] for c in ch)
        self.base = sorted(c['origin'][1] for c in ch)[len(ch) // 2]
        fix = FIX.get(self.font, {})
        def glyph(c):   # a zero-width U+0338 drawn at the same spot negates the symbol (≠, ∉, ...)
            g = fix.get(c['c'], c['c'])
            if any(abs(c['origin'][0] - x) < 0.6 and abs(c['origin'][1] - y) < 0.6 for x, y in slashes):
                g = NEG.get(g, g + '\u0338')      # no precomposed sign: keep the slash as a combining mark, never drop it
            if accents and char_key(c) in accents[1]: g += '\u0304'   # the bar drawn over it (P̄ "not P", z̄, Ā)
            if accents and char_key(c) in accents[2]: g += '\u0305'   # under a drawn overline or root bar (u̅+̅v̅, 1.8̅1̅3̅)
            return g
        chars = [c for c in s['chars'] if c['c'] != '̸' and not (accents and char_key(c) in accents[0])]
        out, i = [], 0
        while i < len(chars):   # an overstrike: "/" printed on top of "0" is the empty set ∅ (two glyphs in the text layer)
            a, b = chars[i], chars[i + 1] if i + 1 < len(chars) else None
            if b and {a['c'], b['c']} == {'/', '0'} and b['bbox'][0] < a['bbox'][2] - 1 and a['bbox'][0] < b['bbox'][2] - 1:
                out.append('∅'); i += 2; continue
            out.append(glyph(a)); i += 1
        self.text = ''.join(out).replace('\xa0', ' ')
        self.hard = self.font in EXT and any(c['c'] not in fix for c in s['chars'] if c['c'].strip())
        self.hard |= F['radical_crop'] and self.font in RADICAL and RADICAL[self.font] in ''.join(c['c'] for c in s['chars'])
        self.role = ''            # '', 'sup' or 'sub' (set per row)

    @property
    def prose(self): return bool(PROSE.search(self.font))
    @property
    def mono(self): return bool(MONO.search(self.font))   # code font (coding books)
    @property
    def textfont(self): return self.prose or bool(TEXT and TEXT.search(self.font))
    @property
    def bold(self): return bool(BOLD.search(self.font))
    @property
    def italic(self): return bool(ITAL.search(self.font)) and not self.mathital
    @property
    def mathital(self): return bool(MATHITAL.search(self.font))
    @property
    def ext(self): return self.font in EXT
    def rect(self): return pymupdf.Rect(self.x0, self.y0, self.x1, self.y1)


class Row:
    def __init__(self, spans):
        self.spans = sorted(spans, key=lambda s: s.x0)
        normal = [s for s in self.spans if s.size >= NORMAL and not s.ext] or [s for s in self.spans if s.size >= NORMAL] or self.spans   # extension glyphs report fake baselines
        self.base = max(set(round(s.base) for s in normal), key=lambda b: sum(1 for s in normal if round(s.base) == b))
        self.size = max(s.size for s in normal)
        self.x0 = min(s.x0 for s in self.spans); self.x1 = max(s.x1 for s in self.spans)
        self.y0 = min(s.y0 for s in normal); self.y1 = max(s.y1 for s in normal)
        for s in self.spans:
            if s.size < 0.85 * self.size and not s.hard:
                s.role = 'sup' if s.base < self.base - 1.5 else 'sub' if s.base > self.base + 1.5 else ''
        self.items = []           # filled by page analysis: ('span', Span) | ('math', Rect)
        self.bullet = False       # a drawn bullet mark sits left of the row
        self.panel = None         # the shaded box (listing / sidebar) the row sits in, if any
        self.table = None         # the Table the row belongs to, if any

    def text(self): return ''.join(s.text for s in self.spans)


ROOT_SIGN = lambda font, text: (font in RADICAL and '√' in text) or (font.startswith('CMEX') and text.strip() in tuple('pqrs'))
char_key = lambda c: (c['c'], round(c['origin'][0], 1), round(c['origin'][1], 1))
ACCENTS = '¯ˉ'   # a bar accent (TeX \\bar) is its own glyph, set before its letter: "¯P" prints as P̄


def bar_accents(raw):
    """(keys of the bar accent glyphs, keys of the letters they stand over): the accent is joined to its letter as a
    combining macron. A bar can be a negation (P̄ = "not P"), a complement or a conjugate: it must stay on its letter.
    An accent with no letter under it stays a visible "¯" (audit.py reports it)."""
    chars = [c for s in raw for c in s['chars'] if c['c'].strip()]
    drop, over = set(), set()
    for a in chars:
        if a['c'] not in ACCENTS: continue
        mx = (a['bbox'][0] + a['bbox'][2]) / 2
        under = [c for c in chars if c['c'] not in ACCENTS and c['bbox'][0] - 1.5 <= mx <= c['bbox'][2] + 1.5
                 and -1 < c['origin'][1] - a['origin'][1] < 10]
        if not under: continue
        b = min(under, key=lambda c: abs((c['bbox'][0] + c['bbox'][2]) / 2 - mx) + abs(c['origin'][1] - a['origin'][1]))
        drop.add(char_key(a)); over.add(char_key(b))
    return drop, over


def overlines(page, raw):
    """Keys of the characters under a drawn overline: a thin loose bar with text just under it and no numerator over
    it (not a fraction bar). Conjugates of sums (u+v with a bar), recurring decimals (1.813 with a bar over 813) and
    the radicand of a root: a lost bar changes the meaning, so each character gets a combining overline. Words of 3+
    letters under a long rule are a table header, not math."""
    chars = [dict(c, size=s['size'], font=s['font']) for s in raw for c in s['chars'] if c['c'].strip()]
    keys = set()
    for r in map(pymupdf.Rect, loose_marks(page)):
        if r.height > 1.6 or r.width < 3: continue
        inx = lambda c: r.x0 - 0.5 <= (c['bbox'][0] + c['bbox'][2]) / 2 <= r.x1 + 0.5
        under = [c for c in chars if inx(c) and 0 < c['origin'][1] - r.y1 < 16 and c['c'] not in ACCENTS]
        if under:                                              # the line just under the bar (a tall root: its scripts too)
            full = [c['origin'][1] for c in under if c['size'] >= NORMAL]
            base = min(full) if full else min(c['origin'][1] for c in under)
            under = [c for c in under if c['origin'][1] <= base + 4]
        if not under or any(inx(c) and 0 < r.y0 - c['origin'][1] < 8 for c in chars): continue
        text = ''.join(c['c'] for c in sorted(under, key=lambda c: c['origin'][0]))
        if re.search(r'[^\W\d_]{3,}', text): continue
        root = any(ROOT_SIGN(c['font'], c['c']) and abs(c['bbox'][2] - r.x0) < 2.5 for c in chars)
        if root and len(text) <= 2: continue                   # √2, √n: the root bar adds nothing in text
        keys |= {char_key(c) for c in under}
    return keys


def split_at_roots(page, raw):
    """A text span that runs past the end of a root bar ("√(n+2" then "2. Then") is split there, so the root can be
    cropped whole without cutting a span."""
    bars = [pymupdf.Rect(d['rect']) for d in page.get_drawings() if d['rect'].height < 1.2]
    bars += [r for r in map(pymupdf.Rect, loose_marks(page)) if r.height < 1.2]
    bars = [r for r in bars if any(ROOT_SIGN(s['font'], ''.join(c['c'] for c in s['chars'])) and abs(s['bbox'][2] - r.x0) < 1.5
                                   and s['bbox'][1] - 1 <= r.y0 <= s['bbox'][3] for s in raw)]
    if not bars: return raw
    out = []
    for s in raw:
        cut = next((r for r in bars if 0 < s['origin'][1] - r.y1 < 16 and s['bbox'][0] < r.x1 < s['bbox'][2]), None)
        if cut is None or len(s['chars']) < 2: out.append(s); continue
        side = [(c['bbox'][0] + c['bbox'][2]) / 2 <= cut.x1 + 0.5 for c in s['chars']]
        groups = []
        for c, k in zip(s['chars'], side):
            if groups and groups[-1][0] == k: groups[-1][1].append(c)
            else: groups.append((k, [c]))
        for _, cs in groups:
            bb = pymupdf.Rect(cs[0]['bbox'])
            for c in cs: bb |= c['bbox']
            out.append(dict(s, chars=cs, bbox=(bb.x0, s['bbox'][1], bb.x1, s['bbox'][3]), origin=cs[0]['origin']))
    return out


def page_spans(page):
    slashes = [(ch[2][0], ch[2][1]) for sp in page.get_texttrace() for ch in sp['chars'] if ch[0] == 0x338]
    spans = lambda flags: [s for b in page.get_text('rawdict', flags=flags)['blocks'] for l in b.get('lines', []) for s in l['spans']]
    raw = spans(pymupdf.TEXTFLAGS_RAWDICT)
    odd = lambda s: s['font'] in EXT or (not F['radical_crop'] and s['font'] in RADICAL   # (cropped radicals are placed
                                         and any(c['c'] == RADICAL[s['font']] for c in s['chars']))   # by their font box)
    if any(map(odd, raw)):                                     # big delimiters and radicals: font boxes reach far past
        key = lambda s: (s['font'], round(s['origin'][0], 1), round(s['origin'][1], 1))   # the ink, so take the
        exact = {key(s): s for s in spans(pymupdf.TEXTFLAGS_RAWDICT | pymupdf.TEXT_ACCURATE_BBOXES) if odd(s)}   # outlines' boxes
        raw = [exact.get(key(s), s) if odd(s) else s for s in raw]
    raw = split_at_roots(page, raw)
    accents = bar_accents(raw) + (overlines(page, raw),)
    return [Span(s, slashes, accents) for s in raw if s['chars'] and TOP <= s['bbox'][1] <= BOTTOM]   # space-only spans are word gaps


def margin(pno):
    """Body left margin of a 0-based page (books alternate margins by page parity)."""
    return PG['margin_odd'] if pno % 2 else PG['margin_even']


def _white(d):
    f = d.get('fill')
    return d['type'] == 'f' and f is not None and min(f) > 0.97


def page_furniture(page, spans):
    """Drawings that are layout, not content: page backgrounds, white fills, shaded panels behind text
    (code listings, sidebars) and small bullet marks. Returns (ignored drawing indices, panels, marks)."""
    ignore, panels, marks = set(), [], []
    area, left = page.rect.get_area(), margin(page.number)
    drawings = page.get_drawings()
    ink = [pymupdf.Rect(d['rect']) for d in drawings if not _white(d) and pymupdf.Rect(d['rect']).get_area() < 0.6 * area]
    centre = lambda s: pymupdf.Point((s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2)
    for i, d in enumerate(drawings):
        r = pymupdf.Rect(d['rect'])
        if r.get_area() > 0.6 * area: ignore.add(i); continue   # page background
        if _white(d):                                           # white box behind text (equations); white shapes in a
            if any(s.text.strip() and r.contains(centre(s)) for s in spans): ignore.add(i)   # drawing stay with it
            continue
        if d['type'] in ('f', 's', 'fs') and 1 < r.width < 7 and 1 < r.height < 7 and -5 < r.x0 - left < 90:   # bullet (nested lists too):
            line = [s for s in spans if s.text.strip() and s.y0 - 2 < (r.y0 + r.y1) / 2 < s.y1 + 2]  # first thing on its line,
            alone = not any(o != r and o.intersects(r + (-4, -4, 4, 4)) for o in ink)               # not part of a drawing
            if alone and line and 0 <= min(s.x0 for s in line) - r.x1 < 30 and not any(s.rect().intersects(r) for s in line):
                marks.append(r); ignore.add(i); continue
        if d['type'] == 'f' and 4 < r.width < 60 and 4 < r.height < 30:   # badge: a word printed on a small shape
            on = [s for s in spans if s.text.strip() and r.contains(pymupdf.Point((s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2))]
            line = [s for s in spans if s.text.strip() and s.y0 - 2 < (r.y0 + r.y1) / 2 < s.y1 + 2 and s.x1 <= r.x0 + 1]
            if on and len(''.join(s.text for s in on).strip()) <= 12 and (
                    (-5 < r.x0 - left < 45 and not line) or all(s.size >= SZ['title'] for s in on)):
                ignore.add(i); continue                        # NOTE / TIP labels, chapter-number squares
        if r.height < 1.5 and r.width > 2:                    # underline (links): a rule right under words, ending with them
            above = [s for s in spans if s.text.strip() and s.textfont and -0.5 < r.y0 - s.base < 4
                     and s.x0 - 1.5 < r.x1 and r.x0 < s.x1 + 1.5]
            if any(abs(r.x0 - s.x0) < 1.5 for s in above) and any(abs(r.x1 - s.x1) < 1.5 for s in above):
                ignore.add(i); continue
        if d['type'] == 'f' and r.height < 14 and r.width < 300:   # highlight bar behind words inside a running line
            on = [s for s in spans if s.text.strip() and s.textfont and r.contains(pymupdf.Point((s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2))]
            beside = [s for s in spans if s.text.strip() and s.textfont and abs(s.base - (on[0].base if on else -99)) < 2
                      and (s.x1 <= r.x0 + 1 or s.x0 >= r.x1 - 1)]
            if on and beside:
                ignore.add(i); continue
        if d['type'] == 'f' and r.width > 150 and r.height > 10:
            inside = sum(len(s.text.strip()) for s in spans if (r + (-1, -1, 1, 1)).contains(s.rect()))
            if inside > 40 or (r.height < 24 and inside > 0):   # shaded box behind text, or a caption bar
                panels.append(r); ignore.add(i)
    for box, ids in frames(drawings):                          # boxes drawn around text (outlines, boxed facts)
        words = sum(len(w) for s in spans if box.contains(s.rect()) for w in re.findall(r'[^\W\d_]{2,}', s.text))
        if words > 40 and not ids & ignore:
            panels.append(box); ignore |= ids
    return ignore, panels, marks


def frames(drawings):
    """Rectangles drawn as one stroked rect or as four separate lines -> [(rect, drawing indices)]."""
    out, hs, vs = [], [], []
    for i, d in enumerate(drawings):
        r = pymupdf.Rect(d['rect'])
        if d['type'] in ('s', 'fs') and r.width > 30 and r.height > 20 and any(it[0] == 're' for it in d['items']) \
                and (d['type'] == 's' or _white(d) or min(d.get('fill') or (0,)) > 0.9):
            out.append((r, {i}))
        elif r.height < 1.5 and r.width > 30: hs.append((i, r))
        elif r.width < 1.5 and r.height > 20: vs.append((i, r))
    near = lambda a, b: abs(a - b) < 1.5
    for i, top in hs:
        for j, bot in hs:
            if bot.y0 <= top.y0 + 20 or not (near(top.x0, bot.x0) and near(top.x1, bot.x1)): continue
            left = next((k for k, v in vs if near(v.x0, top.x0) and near(v.y0, top.y0) and near(v.y1, bot.y1)), None)
            right = next((k for k, v in vs if near(v.x0, top.x1) and near(v.y0, top.y0) and near(v.y1, bot.y1)), None)
            if left is not None and right is not None:
                out.append((pymupdf.Rect(top.x0, top.y0, top.x1, bot.y1), {i, j, left, right}))
    return out


OCR = PROFILE.get('ocr', False)
_OCR_FIGS = None


def ocr_figures(name='figures'):
    """Regions of scanned pages written by ocr.py: work/ocr/figures.json (non-text ink) or formulas.json (formula
    lines and words, shown as math images in their row)."""
    global _OCR_FIGS
    if _OCR_FIGS is None: _OCR_FIGS = {}
    if name not in _OCR_FIGS:
        import json, pathlib
        f = pathlib.Path(__file__).resolve().parent.parent / 'work' / 'ocr' / f'{name}.json'
        _OCR_FIGS[name] = json.loads(f.read_text(encoding='utf-8')) if OCR and f.exists() else {}
    return _OCR_FIGS[name]


def solid_mark(block):
    """A 1×1-pixel image stretched into a small filled rectangle (Ghostscript output): a rule or bar over a heading, a
    fraction bar or overbar, a vertical rule, or an end-of-proof mark, unless it is part of a drawing (loose_marks)."""
    r = pymupdf.Rect(block['bbox'])
    return block.get('width') == 1 and block.get('height') == 1 and (r.height <= 5 or r.width <= 1.2 or (r.width <= 6 and r.height <= 12))


MATH_NAMES = r'\b(?:sin|cos|tan|cot|sec|csc|log|exp|lim|max|min|sup|inf|mod|gcd|lcm|det|deg|ker|arg)\b'

def loose_marks(page):
    """Rects of the solid marks that stand alone (a heading bar, a fraction bar or overbar, a proof mark): layout.
    Marks that touch other marks in a group of 3 or more, or a group wider and taller than 12pt, draw a figure
    (lines and arcs rasterised into many stretched 1×1 images): those are figure ink."""
    marks = [pymupdf.Rect(b['bbox']) for b in page.get_text('dict')['blocks'] if b['type'] == 1 and solid_mark(b)]
    groups = []
    for m in marks:
        hit = [g for g in groups if any((m + (-1, -1, 1, 1)).intersects(o) for o in g)]
        for g in hit: groups.remove(g)
        groups.append(sum(hit, []) + [m])
    loose = set()
    for g in groups:
        box = pymupdf.Rect(g[0])
        for o in g: box |= o
        if len(g) < 3 and min(box.width, box.height) <= 12: loose |= {tuple(o) for o in g}
    return loose


def figure_boxes(page, spans, ignore=()):
    """Clusters of vector drawings (and raster images) that are real figures, grown to include their text labels."""
    rects = []
    for i, d in enumerate(page.get_drawings()):
        if i in ignore: continue
        r = pymupdf.Rect(d['rect'])
        if r.x0 < -2 or r.y0 < -2 or r.x1 > page.rect.x1 + 2 or r.y1 > page.rect.y1 + 2 or (r.width < 0.5 and r.height < 0.5): continue
        if r.y0 < TOP or r.y1 > BOTTOM + 5: continue
        if r.height < 1.2 and (r.width > 250 or r.width < 30): continue   # full-width rules; fraction bars are math
        rects.append(r + (-0.5 * (r.width < 1), -0.5 * (r.height < 1), 0.5 * (r.width < 1), 0.5 * (r.height < 1)))  # strokes have no area
    area = page.rect.get_area()
    images = [b for b in page.get_text('dict')['blocks'] if b['type'] == 1 and TOP < b['bbox'][3] and b['bbox'][1] < BOTTOM
              and not (OCR and pymupdf.Rect(b['bbox']).get_area() > 0.6 * area)]    # a scanned page's own image
    loose = loose_marks(page)
    rects += [pymupdf.Rect(b['bbox']) for b in images if tuple(pymupdf.Rect(b['bbox'])) not in loose]
    marks = [pymupdf.Rect(m) for m in loose]
    while True:                                                # marks touching figure ink (a square's sides) are figure ink
        joined = [m for m in marks if any((m + (-3, -3, 3, 3)).intersects(r) for r in rects)]
        if not joined: break
        rects += joined; marks = [m for m in marks if m not in joined]
    rects += [pymupdf.Rect(r) for r in ocr_figures().get(str(page.number), [])]     # non-text ink found by ocr.py
    prose_lines = sorted({round(sp.base) for sp in spans if sp.prose and sp.text.strip()})
    def line_of(r):                                            # the prose baseline a thin drawing sits beside, if any
        if r.height > 10: return None
        c = (r.y0 + r.y1) / 2
        return next((b for b in prose_lines if 0 < b - c < 7 and any(sp.prose and round(sp.base) == b and (sp.x1 < r.x0 or r.x1 < sp.x0) for sp in spans)), None)
    clusters = []                                              # [unpadded box, item count, beside-line baselines]
    for r in rects:
        ln = line_of(r)
        hit = [c for c in clusters if (c[0] + (-8, -8, 8, 8)).intersects(r + (-8, -8, 8, 8))
               and (c[0].intersects(r) or not (ln is not None and c[2] and ln not in c[2]))]   # thin drawings beside different lines (one per bullet) stay apart
        box, n, lines = pymupdf.Rect(r), 1, set() if ln is None else {ln}
        for c in hit: clusters.remove(c); box |= c[0]; n += c[1]; lines |= c[2]
        clusters.append([box, n, lines])
    figs = []
    for box, n, _ in clusters:
        if box.height < 2 or box.width < 2: continue          # bars / underlines: handled as math
        for _ in range(2):                                     # absorb labels touching the drawing
            for s in spans:
                r = s.rect()
                near = (r & (box + (-6, -6, 6, 6))).get_area() > 0.5 * r.get_area() and r.width < 120
                if near or (r.width < 40 and s.text.strip() and (box + (-10, -10, 10, 10)).contains(r)):
                    box |= r
        for s in spans:                                        # isolated 1-2 char labels a little further out (ℓ, A, x1)
            r = s.rect()
            if not s.prose and 0 < len(s.text.strip()) <= 2 and (box + (-14, -14, 14, 14)).contains(r) and not box.contains(r) \
                    and not any(t.prose and t.text.strip() and abs(t.base - s.base) < 3 and min(abs(t.x0 - r.x1), abs(r.x0 - t.x1)) < 20
                                for t in spans):
                grown = box | r                                # never at the cost of covering prose
                half = lambda b, t: (t.rect() & b).get_area() > 0.4 * max(t.rect().get_area(), .01)   # as figure membership
                if not any(t.prose and t.text.strip() and half(grown + (-2, -2, 2, 2), t) and not half(box + (-2, -2, 2, 2), t) for t in spans):
                    box = grown
        words = sum(len(w) for s in spans if s.prose and box.contains(s.rect()) for w in re.findall(r'[^\W\d_]{2,}', s.text))
        scanned = any((box + (-0.5, -0.5, 0.5, 0.5)).contains(pymupdf.Rect(r)) for r in ocr_figures().get(str(page.number), []))   # ink OCR could not read
        if words > 40 and not scanned: continue                # a frame drawn around text (boxed outline/fact), not a figure
        figs.append(box + (-2, -2, 2, 2))
    return figs


class Table:
    """A table on one page: bbox, column boundaries (x), y of the rule under the header row (or None)."""
    def __init__(self, bbox, cols, header_y=None):
        self.bbox, self.cols, self.header_y, self.rows, self.open = bbox, cols, header_y, [], False


def page_tables(page, ignore, panels=()):
    """Tables drawn with horizontal rules only (booktabs style: a rule is split into one segment per column, which
    gives the column boundaries) or with a full grid (PyMuPDF find_tables). -> (tables, drawing indices used)."""
    segs = [(i, pymupdf.Rect(d['rect'])) for i, d in enumerate(page.get_drawings())
            if i not in ignore and d['rect'].height < 1.5 and d['rect'].width > 15 and TOP < d['rect'].y0 < BOTTOM]
    lines = {}
    for i, r in segs:
        y = round((r.y0 + r.y1) / 2)
        key = next((k for k in lines if abs(k - y) <= 1), y)
        lines.setdefault(key, []).append((i, r))
    runs = []                                                   # (y, x0, x1, boundaries, drawing indices)
    for y, ls in lines.items():
        ls.sort(key=lambda t: t[1].x0)
        cur = [ls[0]]
        for t in ls[1:]:
            if abs(t[1].x0 - cur[-1][1].x1) < 1.5: cur.append(t)
            else: runs.append(cur); cur = [t]
        runs.append(cur)
    runs = [(round((c[0][1].y0 + c[0][1].y1) / 2, 1), c[0][1].x0, c[-1][1].x1, [c[0][1].x0] + [t[1].x1 for t in c], [t[0] for t in c])
            for c in runs]
    tables, used = [], set()
    for y, x0, x1, bounds, ids in sorted(runs, key=lambda r: -len(r[3])):
        if len(bounds) < 3 or set(ids) & used: continue          # a rule split into >= 2 column segments
        group = sorted([r for r in runs if abs(r[1] - x0) < 3 and abs(r[2] - x1) < 3 and not set(r[4]) & used], key=lambda r: r[0])
        k = next(j for j, r in enumerate(group) if r[0] == y)
        lo = hi = k                                             # contiguous rules around this one, at most 160pt apart
        while lo > 0 and group[lo][0] - group[lo - 1][0] < 160: lo -= 1
        while hi + 1 < len(group) and group[hi + 1][0] - group[hi][0] < 160: hi += 1
        group = group[lo:hi + 1]
        for r in group: used |= set(r[4])
        if len(group) == 1:                                     # only a rule under the header: extent found from rows
            t = Table(pymupdf.Rect(x0, y - 16, x1, y + 1), bounds, y); t.open = True; tables.append(t)
        else:
            tables.append(Table(pymupdf.Rect(x0, group[0][0] - 1, x1, group[-1][0] + 1), bounds,
                                group[1][0] if len(group) >= 3 else None))
    try:
        found = page.find_tables(strategy='lines').tables
    except Exception:
        found = []
    for t in found:                                             # full grids
        b = pymupdf.Rect(t.bbox)
        if any(b.intersects(x.bbox) for x in tables) or t.col_count < 2 or t.row_count < 2: continue
        if b.get_area() > 0.5 * page.rect.get_area() or any(b.intersects(p) for p in panels): continue   # backgrounds, listings
        ruling = [pymupdf.Rect(d['rect']) for d in page.get_drawings() if (b + (-2, -2, 2, 2)).contains(pymupdf.Rect(d['rect']))]
        if sum(r.height < 1.5 and r.width > 8 for r in ruling) < 2 or sum(r.width < 1.5 and r.height > 8 for r in ruling) < 2:
            continue                                            # find_tables also infers grids from aligned text alone
        cols = sorted({round(c[0], 1) for c in t.cells if c} | {round(c[2], 1) for c in t.cells if c})
        first = [c for c in t.cells if c and abs(c[1] - b.y0) < 1]
        tables.append(Table(b, cols, max(c[3] for c in first) if first else None))
        used |= {i for i, d in enumerate(page.get_drawings()) if (pymupdf.Rect(d['rect']) & (b + (-1, -1, 1, 1))) == pymupdf.Rect(d['rect'])}
    return tables, used


def build_rows(spans, bars=()):
    """Rows are defined by normal-size text baselines; small spans (scripts, fraction parts, matrix entries)
    join the nearest baseline, and so do full-size spans sitting on or under a fraction bar; big delimiters join
    the row they overlap most."""
    ext = [s for s in spans if s.ext or (s.font in RADICAL and '√' in s.text)]  # glyph boxes lie; place by position
    small = [s for s in spans if s not in ext and (s.size < SMALL or not s.text.strip())]
    giant = [s for s in spans if s.size > SZ['dropcap'] and len(s.text.strip()) == 1]   # drop caps
    normal = [s for s in spans if s not in ext and s not in small and s not in giant]
    rows = []                                                  # [base, y0, y1, spans, all baselines]
    for s in sorted(normal, key=lambda s: s.base):
        if rows and abs(s.base - rows[-1][0]) < 3:
            r = rows[-1]; r[3].append(s); r[1] = min(r[1], s.y0); r[2] = max(r[2], s.y1)
        else:
            rows.append([s.base, s.y0, s.y1, [s], [s.base]])
    for r in list(rows):                                       # a superscript in a big title ("nth"): smaller type set
        big = [o for o in rows if o is not r and len(r[3]) <= 3 and abs(o[0] - r[0]) < 0.6 * max(t.size for t in o[3])
               and all(t.size < 0.85 * max(u.size for u in o[3]) for t in r[3])
               and all(any(min(abs(t.x0 - u.x1), abs(u.x0 - t.x1)) < 2 for u in o[3]) for t in r[3] if t.text.strip())]
        if big and r in rows:                                  # beside the larger words, raised: one row with them
            o = big[0]; o[3] += r[3]; o[1] = min(o[1], r[1]); o[2] = max(o[2], r[2]); rows.remove(r)
    def on_bar(s):
        return any(min(s.x1, b.x1) - max(s.x0, b.x0) > 0.5 * (s.x1 - s.x0) and (abs(s.y0 - b.y1) < 3 or abs(b.y0 - s.y1) < 3) for b in bars)
    for r in sorted(rows, key=lambda r: len(''.join(s.text for s in r[3]).strip())):   # full-size fraction parts (m/n)
        if len(''.join(s.text for s in r[3]).strip()) > 40 or any(s.mono or (s.textfont and re.search(r'[^\W\d_]{3,}', s.text))
                                                                   for s in r[3]): continue   # words are text, not a fraction part
        if not all(on_bar(s) for s in r[3] if s.text.strip()): continue
        x0, x1 = min(s.x0 for s in r[3]), max(s.x1 for s in r[3])
        fraction_part = lambda q: all(on_bar(s) for s in q[3] if s.text.strip())
        between = lambda o: any(q is not r and q is not o and (q[0] - o[0]) * (r[0] - o[0]) < 0 and abs(q[0] - o[0]) < 9
                                and fraction_part(q) for q in rows) \
            or any((b - o[0]) * (r[0] - o[0]) < 0 and abs(b - o[0]) < 9 for b in o[4][1:])   # (one already merged in)
        near = [o for o in rows if o is not r and abs(o[0] - r[0]) < 9 and (between(o) or len(o[3]) > len(r[3])
                and min(s.x0 for s in o[3]) - 2 < x0 and x1 < max(s.x1 for s in o[3]) + 2)]
        if near:
            o = min(near, key=lambda o: abs(o[0] - r[0]))
            o[3] += r[3]; o[1] = min(o[1], r[1]); o[2] = max(o[2], r[2]); o[4] += r[4]; rows.remove(r)
    gap = lambda r, s: min(abs(b - s.base) for b in r[4])     # to the nearest baseline (a merged numerator's too)
    after_delim = lambda s: any(abs(e.x1 - s.x0) < 1.5 and e.y0 - 3 <= s.y0 <= e.y1 for e in ext)   # ")²": raised further
    def bar_of(s):                                             # the bar a script sits on or under (a small fraction)
        return next((b for b in bars if min(s.x1, b.x1) - max(s.x0, b.x0) > 0.5 * (s.x1 - s.x0)
                     and (abs(s.y0 - b.y1) < 3 or abs(b.y0 - s.y1) < 3)), None)
    for s in small:
        b = bar_of(s) if s.text.strip() else None
        if b is not None and rows:                             # its line is the one the bar sits in, not the nearest baseline
            best = min(rows, key=lambda r: abs((r[1] + r[2]) / 2 - (b.y0 + b.y1) / 2))
            if abs((best[1] + best[2]) / 2 - (b.y0 + b.y1) / 2) < 8: best[3].append(s); continue
        best = min(rows, key=lambda r: gap(r, s), default=None)
        if best is not None and (gap(best, s) < 8 or (gap(best, s) < 12 and after_delim(s))): best[3].append(s)
        elif s.text.strip(): rows.append([s.base, s.y0, s.y1, [s], [s.base]])
    for s in ext:
        best = max(rows, key=lambda r: min(s.y1, r[2]) - max(s.y0, r[1]), default=None)
        if rows and '√' in s.text:                            # radical glyph box sits above its ink: take the row below
            to = lambda r: min(abs(t.base - s.y1) for t in r[3])   # a text radical (TeX cmsy): its box ends at the radicand's
            near = min(rows, key=to)                             # baseline (a script's, in a small fraction)
            if F['radical_crop'] or to(near) > 3: near = min(rows, key=lambda r: abs(r[1] - s.y1))
            near[3].append(s)
        elif best is not None and min(s.y1, best[2]) - max(s.y0, best[1]) > 0: best[3].append(s)
        else: rows.append([s.base, s.y0, s.y1, [s], [s.base]])
    rows += [[s.base, s.y0, s.y1, [s], [s.base]] for s in giant]
    return [Row(r[3]) for r in sorted(rows, key=lambda r: r[1]) if ''.join(x.text for x in r[3]).strip()]


def hard_math(row, bars):
    """Find regions of a row that plain text can't express: stacked spans (fractions, matrices, binomials),
    unmapped big delimiters, radicals, and anything touching a fraction bar. Returns merged rects."""
    ms = [s for s in row.spans if not s.textfont and not s.mono]
    seeds = [s.rect() for s in ms if s.hard]
    radical = lambda s: s.font in RADICAL and '√' in s.text            # its box sits above the row: no stacked part
    seeds += [s.rect() for s in ms if not s.ext and not radical(s) and s.size >= NORMAL and abs(s.base - row.base) > 3
              and s.text.strip()]                                     # full-size stacked parts
    for i, a in enumerate(ms):
        for b in ms[i + 1:]:
            if min(a.x1, b.x1) - max(a.x0, b.x0) > 1.5 and abs(a.base - b.base) > 3 and (a.size < NORMAL or b.size < NORMAL) \
                    and a.text.strip() and b.text.strip():
                seeds.append(a.rect() | b.rect())
    figures = [s for s in row.spans if s.textfont and s.text.strip() and len(s.text.strip()) <= 8
               and not re.search(r'[^\W\d_]{3,}', s.text)]          # numerals and letters set in the text font (m/n, 12/8)
    for bar in bars:
        if row.y0 - 6 < bar.y0 < row.y1 + 4:
            box = bar + (0, -0.6, 0, 0.6)                      # bars are zero-height; give them area
            on = lambda s: min(s.x1, bar.x1) - max(s.x0, bar.x0) > 0.5 * (s.x1 - s.x0) and s.text.strip()
            over = lambda s: on(s) and abs(bar.y0 - s.y1) < 3
            under = lambda s: on(s) and abs(s.y0 - bar.y1) < 3
            parts = ms + (figures if any(map(over, figures + ms)) and any(map(under, figures + ms)) else [])
            for s in parts:                                    # what sits directly on or under the bar belongs to it
                if over(s) or under(s): box |= s.rect()
            seeds.append(box)
    boxes = []
    for r in seeds:                                            # grow over touching math spans (not prose)
        r = pymupdf.Rect(r)
        for _ in range(3):
            for s in ms:
                if (s.rect() + (-1.5, -2, 1.5, 2)).intersects(r) and (s.size < NORMAL or s.hard or s.ext):
                    r |= s.rect()
        for i, b in enumerate(boxes):
            if (b + (-1, -1, 1, 1)).intersects(r): boxes[i] = b | r; break
        else: boxes.append(r)
    merged = True
    while merged:                                              # stacked pieces (limits over Σ, a numerator over its bar) are one crop
        merged = False
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if min(a.x1, b.x1) - max(a.x0, b.x0) > 0.5 and max(a.y0, b.y0) - min(a.y1, b.y1) < 3:
                    boxes[i] = a | b; boxes.remove(b); merged = True; break
            if merged: break
    for i, b in enumerate(boxes):                              # a big delimiter's glyph box covers its top piece only:
        if b.width < 8 and any(s.ext and s.hard and b.contains(s.rect()) for s in ms):   # it is as tall as what it encloses
            others = [o for o in boxes if o is not b]
            grown = pymupdf.Rect(b.x0, min([b.y0] + [o.y0 for o in others]), b.x1, max([b.y1] + [o.y1 for o in others]))
            if not any((grown & o).get_area() > 0 for o in others): boxes[i] = grown   # never over a neighbour (Σ limits)
    return boxes


def analyse(page):
    """-> (rows, figs). Rows carry .items (spans, word spaces, math crop rects), .bullet, .panel and .table."""
    spans = page_spans(page)
    ignore, panels, marks = page_furniture(page, spans)
    tables, ruled = page_tables(page, ignore, panels)
    ignore = ignore | ruled
    figs = figure_boxes(page, spans, ignore)
    formulas = [pymupdf.Rect(r) for r in ocr_figures('formulas').get(str(page.number), [])]   # OCR formula lines: math, not figures
    in_fig = lambda s: any((s.rect() & f).get_area() > 0.5 * s.rect().get_area() for f in figs + [g + (-1, -1, 1, 1) for g in formulas])   # as the audit pads
    text_spans = [s for s in spans if not in_fig(s)]
    drawings = page.get_drawings()
    bars = [pymupdf.Rect(d['rect']) for i, d in enumerate(drawings) if i not in ignore
            and d['rect'].height < 1.2 and d['rect'].width < 250 and not any(pymupdf.Rect(d['rect']).intersects(f) for f in figs)]
    vinculum = lambda r: any(t.font in RADICAL and '√' in t.text and abs(t.x1 - r.x0) < 1.5 and t.y0 <= r.y0 <= t.y1 for t in spans)
    bars += [r for r in map(pymupdf.Rect, loose_marks(page))   # bars drawn as stretched images
             if r.height < 1.2 and 2 < r.width < 250 and TOP < r.y0 < BOTTOM and not vinculum(r) and not any(r.intersects(f) for f in figs)]
    rows = build_rows(text_spans, bars)
    for t in tables:                                            # header-rule-only tables: grow down over aligned rows
        if not t.open: continue
        below = sorted((r for r in rows if r.y0 > t.header_y), key=lambda r: r.y0)
        bottom, last = t.header_y, t.header_y
        for r in below:
            aligned = any(abs(s.x0 - c) < 4 for s in r.spans for c in t.cols[:-1])
            if r.y0 - last > 9 or not aligned or r.x1 > t.bbox.x1 + 3: break
            bottom = last = r.y1
        t.bbox.y1 = bottom + 1
        head = [r for r in rows if r.y1 <= t.header_y + 1 and t.header_y - r.y1 < 6]
        if head: t.bbox.y0 = min(r.y0 for r in head) - 1
    # small drawings sitting inside a text line (e.g. dice faces in a sentence) are inline math, not block figures
    alone = []
    for f in formulas:                                         # a formula touching a figure is part of it
        hit = [i for i, g in enumerate(figs) if f.intersects(g)]
        for i in hit: figs[i] = figs[i] | f
        if not hit: alone.append(f)
    inline = [f for f in figs if f.height < 28 and any(r.y0 - 4 < (f.y0 + f.y1) / 2 < r.y1 + 4 and r.x0 - 5 < f.x0 < r.x1 + 5 for r in rows)]
    beside = lambda f: any(r.y0 - 2 < (f.y0 + f.y1) / 2 < r.y1 + 2 for r in rows)   # a formula on a row of text ("3. [formula]")
    formulas = alone
    inline += [f for f in formulas if beside(f)]
    figs = [f for f in figs if f not in inline and f.width > 10 and f.height > 10] + [f for f in formulas if f not in inline]   # a formula alone on its line
    home = {id(f): min(rows, key=lambda r: abs((r.y0 + r.y1) / 2 - (f.y0 + f.y1) / 2)) for f in inline}   # one row each
    on_it = lambda r, b: any(min(t.x1, b.x1) - max(t.x0, b.x0) > 0.5 * (t.x1 - t.x0) and t.text.strip()
                             and (abs(t.y0 - b.y1) < 3 or abs(b.y0 - t.y1) < 3) for t in r.spans)
    owner = {i: min(rows, key=lambda r: (not on_it(r, b), abs((r.y0 + r.y1) / 2 - b.y0)))   # the row whose spans sit on or
             for i, b in enumerate(bars)} if rows else {}                                       # under the bar, else nearest
    row_boxes = {id(row): hard_math(row, [b for i, b in enumerate(bars) if owner[i] is row]) + [f for f in inline if home[id(f)] is row]
                 for row in rows}
    sign_of = lambda r: next((t for t in spans if ROOT_SIGN(t.font, t.text) and abs(t.x1 - r.x0) < 1.5
                              and t.y0 - 1 <= r.y0 <= t.y1), None)   # √ (text font) or a TeX big radical (CMEX p q r s)
    roots = [pymupdf.Rect(d['rect']) for d in drawings if d['rect'].height < 1.2]
    roots += [r for r in map(pymupdf.Rect, loose_marks(page)) if r.height < 1.2]
    for r in roots:                                            # a root over more than a symbol (√(x²+y²)): its bar is the
        sign = sign_of(r)
        if sign is None: continue
        under = [t for t in text_spans if t.text.strip() and r.x0 - 0.5 <= (t.x0 + t.x1) / 2 <= r.x1 + 0.5
                 and 0 < t.base - r.y1 < 16]                   # only sign of its extent: crop the whole root, exactly
        if len(''.join(t.text for t in under).replace(' ', '')) <= 2: continue   # √2, √n: plain text is exact
        home_row = next((row for row in rows if any(t is sign for t in row.spans)), None) \
            or min(rows, key=lambda row: abs(row.base - sign.base), default=None)
        if home_row is None: continue
        box = sign.rect() | r
        for t in under: box |= t.rect()
        boxes = row_boxes[id(home_row)]
        hit = [i for i, b in enumerate(boxes) if (b + (-1, -1, 1, 1)).intersects(box)]   # one crop, never the sign twice
        for i in hit: box |= boxes[i]
        row_boxes[id(home_row)] = [b for i, b in enumerate(boxes) if i not in hit] + [box]
    wordy = lambda t: re.search(r'[^\W\d_]{3,}', re.sub(MATH_NAMES, ' ', t)) is not None   # prose, not cos or lim
    absorbed = set()
    for row in rows:                                           # a line of math only (no words) with several crops or a big
        if id(row) in absorbed: continue
        words = any(t.textfont and wordy(t.text) for t in row.spans)   # delimiter: one crop, whole
        tall = any(t.ext and t.y1 - t.y0 > 1.4 * t.size for t in row.spans)
        boxes = row_boxes[id(row)]
        crops = [b for b in boxes if b not in inline]
        ink = sorted(row.spans, key=lambda t: t.x0)
        columns = any(b.x0 - a.x1 > 25 for a, b in zip(ink, ink[1:]) if a.text.strip() and b.text.strip())   # two columns of items
        if words or columns or not ((len(crops) >= 2 and sum(b.width for b in crops) > 0.4 * (row.x1 - row.x0)) or (tall and boxes)):
            continue
        whole = pymupdf.Rect(row.spans[0].rect())
        for t in row.spans: whole.include_rect(t.rect())
        for b in boxes: whole.include_rect(b)
        for o in rows:                                         # its exponents, numerators, denominators set as rows of their own
            if o is not row and whole.x0 - 2 < o.x0 and o.x1 < whole.x1 + 2 \
                    and (whole + (0, -12, 0, 12)).intersects(pymupdf.Rect(o.x0, o.y0, o.x1, o.y1)) \
                    and not any(t.textfont and wordy(t.text) for t in o.spans):
                for t in o.spans: whole.include_rect(t.rect())
                for b in row_boxes[id(o)]: whole.include_rect(b)
                row_boxes[id(o)] = [b for b in row_boxes[id(o)] if b in inline]; absorbed.add(id(o))
        row_boxes[id(row)] = [whole] + [b for b in boxes if b in inline]
    inside = lambda s, b: (s.rect() & (b + (-1.8, -1.8, 1.8, 1.8))).get_area() > 0.5 * max(s.rect().get_area(), 0.01)
    member = {}                                                # span -> its box, by the audit's rule (the published crop,
    for _ in range(4):                                         # 0.8pt padded, padded 1pt more); the box grows to cover
        grown = False                                          # its own row's spans, until no box grows
        for row in rows:
            for s in row.spans:
                if id(s) in member: continue
                box = next((b for b in row_boxes[id(row)] if inside(s, b)), None)
                if box is not None: member[id(s)] = box; box.include_rect(s.rect()); grown = True
        if not grown: break
    for row in rows:                                           # then a neighbour's tall crop takes what it shows (no growth:
        for s in row.spans:                                    # a grown crop would reach further rows)
            if id(s) not in member:
                box = next((b for o in rows if o is not row for b in row_boxes[id(o)] if b not in inline and inside(s, b)), None)
                if box is not None: member[id(s)] = box
    for row in rows:
        row.bullet = any(row.y0 - 2 < (m.y0 + m.y1) / 2 < row.y1 + 2 and 0 <= row.x0 - m.x1 < 30 for m in marks)
        row.panel = next((p for p in panels if (p + (-1, -1, 1, 1)).contains(row.spans[0].rect())), None)
        row.table = next((t for t in tables if t.bbox.y0 < (row.y0 + row.y1) / 2 < t.bbox.y1
                          and t.bbox.x0 - 3 < row.x0 and row.x1 < t.bbox.x1 + 3), None)
        if row.table: row.table.rows.append(row)
        boxes = row_boxes[id(row)]
        placed, used, last = [], set(), None
        for s in row.spans:
            box = member.get(id(s))
            if box is None: placed.append((s.x0, 'span', s))
            elif not any(box is b for b in boxes): continue    # shown in a neighbouring row's crop
            elif id(box) not in used: used.add(id(box)); placed.append((box.x0, 'math', box + (-0.8, -0.8, 0.8, 0.8)))
        held = {id(b) for b in member.values()}                # a crop holding only other rows' spans is still shown
        placed += [(b.x0, 'math', b + (-0.8, -0.8, 0.8, 0.8) if b not in inline else b) for b in boxes
                   if id(b) not in used and (b in inline or id(b) in held)]
        for x0, kind, v in sorted(placed, key=lambda t: t[0]):
            if last is not None and x0 - last[0] > GAP and not last[1].endswith(' ') and not (kind == 'span' and v.text.startswith(' ')):
                row.items.append(('space', None))                # word gap encoded as positioning, not a space glyph
            row.items.append((kind, v))
            last = (v.x1, v.text if kind == 'span' else 'm')
    return rows, figs


_VOCAB = None


def vocab():
    """Words (and hyphenated compounds) the book uses mid-line; decides how to rejoin a word broken at a line end."""
    global _VOCAB
    if _VOCAB is None:
        import json, pathlib
        cache = pathlib.Path(__file__).resolve().parent.parent / 'work' / 'vocab.json'
        if cache.exists():
            _VOCAB = set(json.loads(cache.read_text(encoding='utf-8')))
        else:
            doc = pymupdf.open(pdf_path()); words = set()
            for p in doc:
                for line in p.get_text().splitlines():
                    toks = line.split()
                    for t in toks[:-1] if line.rstrip().endswith('-') else toks:
                        words.add(re.sub(r"[^\w\-']", '', t).lower())
            _VOCAB = words
            cache.parent.mkdir(exist_ok=True)
            cache.write_text(json.dumps(sorted(words)), encoding='utf-8')
    return _VOCAB


GLUE = {'and', 'of', 'on', 'to', 'the', 'in', 'with', 'for', 'a'}


def unglue(title):
    """OCR merges the tight words of big titles ("DistanceandAngles", "SomeAnalyticGeometry"): split a token into
    words the book uses, where the split falls at a capital or a small word (and, of, on...). Titles only."""
    V = vocab()
    def split(t):
        best = {0: []}
        for i in range(1, len(t) + 1):
            for j in range(max(0, i - 20), i - 1):
                part = t[j:i]
                if j in best and part.lower() in V and part != t:   # (the glued token itself is in the OCR layer's vocabulary)
                    if i not in best or len(best[j]) + 1 < len(best[i]): best[i] = best[j] + [part]
        return best.get(len(t))
    out = []
    for tok in re.sub(r',(?=[A-Za-z])', ', ', title).split(' '):
        parts = split(tok) if tok.isalpha() and tok.lower() not in GLUE else None
        ok = parts and len(parts) > 1 and all(p.lower() in GLUE or p[0].isupper() for p in parts[1:])
        out += parts if ok else [tok]
    return ' '.join(out)


def rejoin(left, right):
    """left ends with '-' at a line break. Keep the hyphen for real compounds, drop it for TeX hyphenation."""
    a = re.findall(r"[\w']+-$", left); b = re.findall(r"^[\w']+", right)
    if not a or not b: return left[:-1] + right if left.endswith('-') else left + right
    v = vocab(); joined, compound = (a[0][:-1] + b[0]).lower(), (a[0] + b[0]).lower()
    left_w, right_w = a[0][:-1].lower(), b[0].lower()
    keep = joined not in v and (compound in v or (left_w in v and right_w in v and len(right_w) > 2))  # e.g. "or-equal"
    return (left if keep else left[:-1]) + right
