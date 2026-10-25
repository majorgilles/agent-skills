"""Deterministic PDF -> HTML converter. Prose comes verbatim from the PDF text layer (never retyped);
figures and hard math become exact SVG crops. Book-specific constants live in profile.json (bookprofile.py).
  python tools/convert.py ch01 14 44 [skip-first skip-last]"""
import sys, re, html, pathlib, pymupdf
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from layout import analyse, rejoin, margin, unglue, Row
from bookprofile import PROFILE, rx, pdf_path

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF = pymupdf.open(pdf_path())                       # BOOK_PDF overrides (tests)
PAT, LAY, SZ = PROFILE['patterns'], PROFILE['layout'], PROFILE['sizes']
LABELS, CALLOUTS = tuple(PAT['labels']), tuple(PAT['callouts'])
NUM = re.compile(r'^(\d+)\.$')
CODE_LANG = PROFILE['code_lang']
CHAPTER_MARK, CHAPTER_INLINE = rx('chapter_marker'), rx('chapter_inline')
SECTION, SUBSECTION = rx('section'), rx('subsection')
EXERCISES, SOLUTIONS, ITEM_EXCL = rx('exercises'), rx('solutions'), rx('item_exclusions')
PROOF, FIG_CAP, LST_CAP, TBL_CAP = rx('proof'), rx('figure_caption'), rx('listing_caption'), rx('table_caption')
CONT, ANNO, ANNO_TXT = PAT['code_continuation'], rx('code_annotation'), rx('annotation_text')
UNSTYLED = PROFILE['ocr']        # an OCR text layer has no bold or italic: structure comes from patterns and position
PLAIN_ITEMS = UNSTYLED or not PROFILE['patterns']['item_bold']   # exercise numbers in regular type: cut by sequence
PLAIN_SOLUTIONS = UNSTYLED or not PROFILE['patterns'].get('solution_item_bold', PROFILE['patterns']['item_bold'])


def raster_dpi(pno, r):
    """Effective resolution of raster images in region r (0 if none): such regions are exported as PNG,
    rendered from the page itself (SVG export loses soft masks: transparent areas turn black)."""
    best = 0
    for info in PDF[pno].get_image_info():
        b = pymupdf.Rect(info['bbox'])
        if info['width'] == 1 and info['height'] == 1: continue   # a stretched 1×1 image is a solid bar, sharp in SVG
        if (b & r).get_area() > 0.2 * min(max(b.get_area(), 1), max(r.get_area(), 1)) and b.width > 0:   # image in the crop
            best = max(best, info['width'] / b.width * 72)
    return min(300, max(150, round(best))) if best else 0


def crop(pno, r, path):
    """Exact crop of page region r: vector SVG with everything outside removed, or PNG for raster content.
    Returns the clipped rect and the path actually written (.svg or .png)."""
    dpi = raster_dpi(pno, r)
    if dpi:
        path = path[:-4] + '.png'; r = r & PDF[pno].rect
        (ROOT / 'site' / path).parent.mkdir(parents=True, exist_ok=True)
        PDF[pno].get_pixmap(dpi=dpi, clip=r, alpha=False).save(ROOT / 'site' / path)
        return r, path
    tmp = pymupdf.open(); tmp.insert_pdf(PDF, from_page=pno, to_page=pno)
    p = tmp[0]; M = p.rect; r = r & M
    k = r + (-24, -24, 24, 24)                                 # keep a margin: a glyph whose font box overhangs the crop
    for a in [(0, 0, M.x1, k.y0), (0, k.y1, M.x1, M.y1), (0, k.y0, k.x0, k.y1), (k.x1, k.y0, M.x1, k.y1)]:   # (big delimiters,
        if not pymupdf.Rect(a).is_empty: p.add_redact_annot(pymupdf.Rect(a))   # radicals) would be redacted; the crop box clips
    p.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_REMOVE, graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                       text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    o = p.cropbox.tl                                   # a CropBox offset inside the MediaBox (printer's marks)
    p.set_cropbox(r + (o.x, o.y, o.x, o.y))
    (ROOT / 'site' / path).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / 'site' / path).write_text(p.get_svg_image(text_as_path=True), encoding='utf-8')
    return r, path


def crop_attr(pno, r):
    return f'data-crop="{pno}:{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}"'


class Conv:
    def __init__(self, slug):
        self.slug, self.n = slug, 0

    def math_img(self, pno, r, row, alt):
        self.n += 1
        r, path = crop(pno, r, f'figs/m/{self.slug}-{self.n:04d}.svg')
        drop = max(0.0, r.y1 - row.base)
        return (f'<img class="m" src="{path}" alt="{html.escape(alt, quote=True)}" {crop_attr(pno, r)} '
                f'style="height:{r.height:.1f}pt;vertical-align:-{drop:.1f}pt">')

    def figure(self, pno, r):
        self.n += 1
        r, path = crop(pno, r, f'figs/{self.slug}-{self.n:04d}.svg')
        return f'<figure><img src="{path}" alt="Figure" {crop_attr(pno, r)} style="width:{r.width:.0f}pt"></figure>'

    def inline(self, pno, row, items=None):
        """Render row items to inline HTML, merging runs of the same style."""
        out, cur, buf = [], None, []
        def flush():
            if not buf: return
            t = html.escape(''.join(buf), quote=False)
            tags = {'b': 'strong', 'i': 'em', 'v': 'i', 'c': 'code', 'sup': 'sup', 'sub': 'sub'}
            for k in (cur or ()):
                t = f'<{tags[k]}>{t}</{tags[k]}>'
            out.append(t); buf.clear()
        for kind, v in (items if items is not None else row.items):
            if kind == 'space': style, text = cur, ' '
            elif kind == 'math':
                flush(); cur = None
                alt = ''.join(s.text for s in row.spans if (s.rect() & v).get_area() > 0.5 * max(s.rect().get_area(), .01))
                out.append(self.math_img(pno, v, row, alt.strip())); continue
            else:
                style = tuple(k for k, on in (('b', v.bold and not v.mono), ('i', v.italic), ('v', v.mathital), ('c', v.mono),
                                              (v.role, bool(v.role))) if on)
                text = v.text
                if not text.strip(): style = cur              # spaces never change style
            if style != cur: flush(); cur = style
            buf.append(text)
        flush()
        return ''.join(out)


def add(pieces, piece):
    """Append a line's HTML, rejoining a word hyphenated across the line break."""
    m = re.search(r'(?<![\s>])-((?:</\w+>)*)$', pieces[-1]) if pieces else None   # hyphen, maybe before closing tags
    if not m:
        pieces.append(piece); return
    core, closers = pieces[-1][:m.start()], m.group(1)
    keep = rejoin(re.sub(r'<[^>]+>', '', core) + '-', re.sub(r'<[^>]+>', '', piece)).endswith('-' + re.sub(r'<[^>]+>', '', piece))
    pieces[-1] = core + ('-' if keep else '') + closers + piece


def row_text(row):
    """A row's text with its positional word gaps as spaces (an OCR layer writes each word as its own span)."""
    return re.sub(r' +', ' ', ''.join(' ' if k == 'space' else v.text if k == 'span' else '' for k, v in row.items)).strip()


def first_text(row):
    return next((v for k, v in row.items if k == 'span' and v.text.strip()), None)


def code_line(x, x0, cw, text):
    """One code line as HTML: indentation from the x offset, the typesetter's wrap marker and end-of-line
    annotation marker kept verbatim but tagged (the runner strips them, CSS draws them as ↪ and a cueball)."""
    lead = ' ' * round((x - x0) / cw)
    cont = ''
    if CONT and text.lstrip().startswith(CONT):
        i = text.index(CONT); lead += text[:i]; text = text[i + len(CONT):]
        cont = f'<span class="cont" aria-hidden="true">{html.escape(CONT)}</span>'
    m = ANNO.search(text) if ANNO else None
    tail = ''
    if m:
        tail = f'<span class="anno" data-a="{html.escape(m.group(1))}">{html.escape(m.group(0).strip())}</span>'
        text = text[:m.start()]
    return html.escape(lead) + cont + html.escape(text.rstrip()) + tail


def code_html(lines):
    x0 = min(x for x, _, _ in lines)
    body = '\n'.join(code_line(x, x0, cw, t) for x, cw, t in lines)
    return f'<pre class="code" data-lang="{CODE_LANG}"><code>{body}</code></pre>'


def heading_html(C, pno, row, title):
    """A heading's title with its inline styling (math italic x in "cos(x)"), the number printed before it left out;
    plain when the row's text does not end with the title."""
    items, text = list(row.items), ''
    while items and not ''.join(v.text for k, v in items if k == 'span').strip().startswith(title.strip()[:1] or ' ') \
            or (items and items[0][0] == 'space'):
        items.pop(0)
    shown = C.inline(pno, row, items).strip() if items else ''
    plain = re.sub(r'\s+', '', html.unescape(re.sub(r'<[^>]+>', '', shown)))
    return shown if plain == re.sub(r'\s+', '', title) else html.escape(title)

def table_html(C, pno, t):
    """A detected Table as <table>: each text row's items go to the column under their centre; a row whose first
    column is empty continues the cells of the row above (wrapped cell text)."""
    def col(x):
        return max(0, min(len(t.cols) - 2, next((k for k in range(len(t.cols) - 1) if x < t.cols[k + 1]), len(t.cols) - 2)))
    body, head = [], []
    centre = lambda k, v: pymupdf.Point((v.x0 + v.x1) / 2, (v.y0 + v.y1) / 2)
    cells_hold_all = t.grid and all(any(c is not None and c.contains(centre(k, v)) for g in t.grid for c in g)
                                    for r in t.rows for k, v in r.items if k != 'space')
    if cells_hold_all:                                         # ruled cells: each cell's lines, read inside the cell (a
                                                               # wrapped cell, an exponent above its line)
        for n, grow in enumerate(t.grid):
            cells = []
            for cell in grow:
                items, last = [], None
                for row in sorted(t.rows, key=lambda r: r.y0):
                    for k, v in row.items:
                        if k == 'space':
                            if last is not None: items.append((k, v, last))
                            continue
                        last = v if cell is not None and cell.contains(centre(k, v)) else None
                        if last is not None: items.append((k, v, v))
                spans = [v for k, v, _ in items if k == 'span']
                lines = []                                     # the cell's own lines; Row() sets sup/sub against them
                for v in sorted(spans, key=lambda v: v.base):
                    if lines and abs(v.base - lines[-1][0]) < 0.5 * v.size: lines[-1][1].append(v)
                    else: lines.append([v.base, [v]])
                main = [ls for ls in lines if max(x.size for x in ls[1]) >= 0.85 * max(x.size for x in spans)] or lines
                for ls in lines:
                    if ls not in main: min(main, key=lambda m: abs(m[0] - ls[0]))[1].extend(ls[1])
                rows = [Row(ls[1]) for ls in main]
                line_of = lambda v: min(range(len(rows)), key=lambda i: abs((rows[i].y0 + rows[i].y1) / 2 - (v.y0 + v.y1) / 2)) if rows else 0
                parts = [[] for _ in rows] or [[]]
                for k, v, anchor in sorted(items, key=lambda it: (line_of(it[2]), it[2].x0)):
                    parts[line_of(anchor)].append((k, v))
                cells.append(' '.join(x for x in (C.inline(pno, row or t.rows[0], p).strip()
                                                  for row, p in zip(rows or [None], parts)) if x))
            for f in t.figs:
                hit = [k for k, c in enumerate(grow) if c is not None and c.contains(pymupdf.Point((f.x0 + f.x1) / 2, (f.y0 + f.y1) / 2))]
                for k in hit: cells[k] = (cells[k] + ' ' + C.figure(pno, f)).strip()
            (head if n == 0 and t.header_y is not None else body).append(cells)
        tr = lambda cells, tag: '<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>'
        b = t.bbox
        return (f'<table class="tbl" data-region="{pno}:{b.x0:.1f},{b.y0:.1f},{b.x1:.1f},{b.y1:.1f}">'
                + (f'<thead>{"".join(tr(r, "th") for r in head)}</thead>' if head else '')
                + f'<tbody>{"".join(tr(r, "td") for r in body)}</tbody></table>')
    for row in sorted(t.rows, key=lambda r: r.y0):
        cells, last = [[] for _ in t.cols[:-1]], 0
        for kind, v in row.items:
            if kind == 'space': cells[last].append((kind, v)); continue
            last = col((v.x0 + v.x1) / 2); cells[last].append((kind, v))
        html_cells = [C.inline(pno, row, c).strip() for c in cells]
        for f in t.figs:                                       # pictures: the cell under their centre, on this row
            if min(t.rows, key=lambda r: abs((r.y0 + r.y1) / 2 - (f.y0 + f.y1) / 2)) is row:
                k = col((f.x0 + f.x1) / 2)
                html_cells[k] = (html_cells[k] + ' ' + C.figure(pno, f)).strip()
        target = head if t.header_y is not None and (row.y0 + row.y1) / 2 < t.header_y else body
        if target and not html_cells[0]:
            for k, h in enumerate(html_cells):
                if h: target[-1][k] = (target[-1][k] + ' ' + h).strip()
        else:
            target.append(html_cells)
    tr = lambda cells, tag: '<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>'
    b = t.bbox
    return (f'<table class="tbl" data-region="{pno}:{b.x0:.1f},{b.y0:.1f},{b.x1:.1f},{b.y1:.1f}">'
            + (f'<thead>{"".join(tr(r, "th") for r in head)}</thead>' if head else '')
            + f'<tbody>{"".join(tr(r, "td") for r in body)}</tbody></table>')


def slugify(text):
    m = re.match(r'^(\w+)\s+(\d+(?:\.\d+)*)', text)
    return f'{m.group(1).lower()}-{m.group(2).replace(".", "-")}' if m else None


def flow(slug, a, b, skip=()):
    """Yield (kind, pno, obj, left margin) in reading order across the page range."""
    for pno in (p for p in range(a, b + 1) if p not in skip):
        rows, figs = analyse(PDF[pno])
        def place(f):                                          # a small figure beside a line of text follows that line
            side = [r for r in rows if r.y0 - 2 < (f.y0 + f.y1) / 2 < r.y1 + 2 and (r.x1 < f.x0 or f.x1 < r.x0)]
            return ('figbeside', side[0].y0 + 0.01) if side and f.height < 40 else ('fig', f.y0)
        els = [('row', r.y_order, r) for r in rows] + [(k, y, f) for f in figs for k, y in [place(f)]]
        for kind, _, obj in sorted(els, key=lambda e: e[1]):
            yield kind, pno, obj, margin(pno)


def convert(slug, a, b, skip=(), solutions=False):
    C = Conv(slug)
    out = [f'<!-- pages: {a}-{b} -->'] + ([f'<!-- skip: {skip[0]}-{skip[-1]} -->'] if skip else [])
    para, para_cls = [], ''
    cont = None                    # x positions where wrapped lines of the open list item, note or caption start
    stack = []                     # open <section> tags
    ex = None                      # exercise-block state
    lst = None                     # open code listing: {'cap', 'code', 'annos', 'font'}
    side = None                    # open sidebar: (pno, panel rect)
    last_row_y = None
    code_buf = []

    def flush_code():
        if code_buf: out.append(code_html(code_buf)); code_buf.clear()

    def close_para():
        nonlocal para, para_cls, cont
        flush_code()
        if para:
            text = ' '.join(para).replace('  ', ' ')
            if para_cls == 'caption' and out and out[-1].startswith('<figure') and '<figcaption' not in out[-1]:
                fid = slugify(re.sub(r'<[^>]+>', '', text))
                out[-1] = out[-1].replace('<figure>', f'<figure id="{fid}">' if fid else '<figure>', 1) \
                                 .replace('</figure>', f'<figcaption>{text}</figcaption></figure>')
            elif para_cls.startswith('callout'):
                word = para_cls.split()[1].upper()
                text = re.sub(rf'^((?:<[^>]+>)*){word}\b', rf'\1<span class="lead">{word}</span>', text, count=1)
                out.append(f'<aside class="{para_cls}"><p>{text}</p></aside>')
            else:
                cls = f' class="{para_cls}"' if para_cls else ''
                out.append(f'<p{cls}>{text}</p>')
        para, para_cls, cont = [], '', None

    def close_listing():
        nonlocal lst
        if not lst: return
        annos = ''.join(f'<li data-a="{html.escape(k)}"><span class="anno" data-a="{html.escape(k)}">{html.escape(mk)}</span> {" ".join(t)}</li>'
                        for k, mk, t in lst['annos'])
        fid = slugify(re.sub(r'<[^>]+>', '', lst['cap']))
        out.append(f'<figure class="listing"{f" id={chr(34)}{fid}{chr(34)}" if fid else ""}><figcaption>{lst["cap"]}</figcaption>'
                   + (code_html(lst['code']) if lst['code'] else '') + (f'<ol class="annos">{annos}</ol>' if annos else '') + '</figure>')
        lst = None

    def close_side():
        nonlocal side
        if side: close_para(); out.append('</aside>'); side = None

    def close_ex():
        nonlocal ex
        if not ex: return
        items = sorted(ex['items'], key=lambda it: (it['group'], it['num']))
        cur_group = None
        for it in items:
            if it['group'] != cur_group:
                if cur_group is not None: out.append('</ol>')
                if ex['groups'].get(it['group']): out.append(f'<p class="ex-group">{ex["groups"][it["group"]]}</p>')
                out.append('<ol class="ex-list">'); cur_group = it['group']
            body = ' '.join(it['html']).strip() + (code_html(it['code']) if it.get('code') else '')
            if solutions:
                out.append(f'<li><div class="sol" id="sol-{ex["key"]}-{it["num"]}" data-ex="ex-{ex["key"]}-{it["num"]}">'
                           f'<p><strong>{it["num"]}.</strong> {body}</p></div></li>')
            else:
                out.append(f'<li class="ex" id="ex-{ex["key"]}-{it["num"]}" value="{it["num"]}">{body}</li>')
        if cur_group is not None: out.append('</ol>')
        out.append('</div>'); ex = None

    def close_all():
        close_para(); close_listing(); close_side(); close_ex()

    def open_sec(level, tag):
        while stack and stack[-1][0] >= level:
            out.append('</section>'); stack.pop()
        out.append(tag); stack.append((level, tag))

    chapter_no, chapter_word, dropcap, wrap, title_row = None, '', '', 0, False
    cur_sec = None                 # "chapter.section" of the open section (keys exercise blocks headed only "EXERCISES")
    unnumbered = 0                 # unnumbered sections so far in this file (a section pattern with only a title group)
    title_pno = None               # page of the chapter title
    last_base, pitches, para_y0, para_at = None, [], 0, None
    done_tables, fronts = set(), 0
    for kind, pno, obj, left in flow(slug, a, b, skip):
        if kind in ('fig', 'figbeside'):
            fig = C.figure(pno, obj)
            if ex and ex['items']:
                col = min(ex['cols'], key=lambda c: abs(c - (obj.x0 - left))) if ex['cols'] else None   # columns are margin-relative
                target = [it for it in ex['items'] if it['col'] == col and it['y'] < obj.y1] or ex['items']
                max(target, key=lambda it: (it['pno'], it['y']))['html'].append(fig)
            else:
                close_para(); close_listing()
                if kind == 'figbeside' and out and out[-1].startswith('<p'):   # shown beside its line, as printed
                    out[-1] = f'<div class="beside">{out[-1]}{fig}</div>'
                else:
                    out.append(fig)
            title_row = False
            continue
        row = obj
        if row.table is not None:                              # rows of a table are emitted together, once
            if id(row.table) not in done_tables:
                done_tables.add(id(row.table)); close_para(); close_listing()
                tbl = table_html(C, pno, row.table)
                if out and re.match(r'<p class="caption">', out[-1]):   # "Table 3.1 ..." caption printed above it
                    cap = out.pop()[len('<p class="caption">'):-len('</p>')]
                    fid = slugify(re.sub(r'<[^>]+>', '', cap))
                    tbl = f'<figure class="table"{f" id={chr(34)}{fid}{chr(34)}" if fid else ""}><figcaption>{cap}</figcaption>{tbl}</figure>'
                out.append(tbl)
            last_row_y = row.y1
            continue
        ft = first_text(row)
        text = row_text(row) if UNSTYLED else row.text().strip()
        if not ft and any(k == 'math' for k, _ in row.items):   # a row that is only a formula (an OCR formula line)
            if ex is not None and ex['items']: max(ex['items'], key=lambda it: (it['pno'], it['y']))['html'].append(C.inline(pno, row))
            else: close_para(); out.append(f'<p class="display">{C.inline(pno, row)}</p>')
            last_row_y = row.y1
            continue
        if not ft: continue
        gap = (row.y0 - last_row_y) if last_row_y is not None and last_row_y < row.y0 else 0
        if row.size > SZ['dropcap'] and len(text) == 1:       # drop cap: belongs to the paragraph's first line
            if para and para_at == (pno, True) and para_y0 >= row.y0 - 8:   # that line was read first (its top is lower)
                para[0] = re.sub(r'^((?:<[^>]+>)*)', lambda m: m.group(1) + html.escape(text), para[0], count=1); wrap = 1
            else:
                dropcap, wrap = text, 2
            continue
        if chapter_no == '' and row.size >= SZ['title'] and re.fullmatch(r'\d+', text.strip()):   # the number set apart
            chapter_no = text.strip(); continue                # from its CHAPTER mark (a big digit in a box)
        # --- chapter / part titles (big) ---
        if row.size >= SZ['title'] and (re.search(r'[^\W\d_]{2,}', text) or (CHAPTER_MARK and CHAPTER_MARK.match(text))) \
                and not (UNSTYLED and chapter_no and pno != title_pno):  # OCR: one chapter per file; a tall formula row is no title
            m = CHAPTER_MARK.match(text) if CHAPTER_MARK else None
            if m:                                              # as printed; a spaced-out "C H A P T E R" closes up
                close_all(); title_row = False
                chapter_no, chapter_word = m.group(1) or '', re.sub(r'(?<=\S) (?=\S)', '', text[:m.start(1)]).strip() + ' '
                continue
            if title_row and out[-1].startswith('<h1'):       # a title set on several lines
                out[-1] = out[-1][:-5] + ' ' + html.escape(text) + '</h1>'; last_row_y = row.y1; continue
            close_all()
            m = CHAPTER_INLINE.match(text) if CHAPTER_INLINE else None
            if m: chapter_no, chapter_word, text = m.group(1), '', m.group(2)   # the PDF prints only the number
            if UNSTYLED: text = unglue(text)
            if chapter_no:
                title_pno = pno
                open_sec(1, f'<section class="chapter" id="ch{chapter_no}">')
                out.append(f'<h1><span class="num{"" if chapter_word else " bare"}">{chapter_word}{chapter_no}</span> {html.escape(text)}</h1>')
            else:
                fronts += 1
                open_sec(1, f'<section class="front" id="{slug}{"" if fronts == 1 else f"-{fronts}"}">'); out.append(f'<h1>{html.escape(text)}</h1>')
            title_row, last_row_y = True, row.y1
            continue
        title_row = False
        # --- section / subsection headings ---
        m = SECTION.match(text) if SECTION else None
        if m and (ft.bold or UNSTYLED or not PAT['section_bold']) and row.size > SZ['section_min'] and (abs(row.x0 - left) < 6 or UNSTYLED) \
                and not (SUBSECTION and SUBSECTION.match(text)):
            close_all()
            g = m.groups()                                     # (chapter, section, title), (section, title): "§2. TITLE", or (title)
            if len(g) == 1: unnumbered += 1; g = (str(unnumbered), g[0])
            ch, sec, title = (chapter_no or slug, *g) if len(g) == 2 else g
            sid, title, cur_sec = f'{ch}.{sec}', title.strip(), f'{ch}.{sec}'
            if len(m.groups()) < 3: sid = text[:m.start(2)].strip() if len(m.groups()) == 2 else ''   # "§2." as printed, or none
            open_sec(2, f'<section class="sec" id="s{ch}-{sec}" data-title="{html.escape(title, quote=True)}">')
            out.append(f'<h2>{f"<span class={chr(34)}num{chr(34)}>{sid}</span> " if sid else ""}{heading_html(C, pno, row, title)}</h2>')
            last_row_y = row.y1
            continue
        m = SUBSECTION.match(text) if SUBSECTION else None
        if m and ft.bold and row.size > PAT['subsection_min'] and abs(row.x0 - left) < 6:
            close_all()
            sid = '.'.join(m.groups()[:3])
            out.append(f'<h3 id="s{sid.replace(".", "-")}"><span class="num">{sid}</span> {html.escape(m.group(4).strip())}</h3>')
            last_row_y = row.y1
            continue
        # --- exercise block header (in the Solutions appendix: "Chapter N Exercises" / "Section X.Y") ---
        m = (SOLUTIONS if solutions else EXERCISES)
        m = m.match(text) if m else None
        gd = m.groupdict() if m else {}
        if solutions and m and not gd: m = re.match(r'(\w+) ([\d.]+)', m.group(0))
        if (ft.bold or UNSTYLED) and m:
            close_all()
            if gd.get('sec'): key = f"{gd.get('ch') or chapter_no or slug}.{gd['sec']}"   # named groups: "Chapter 1, §2"
            elif gd.get('ch'): key = f"ch{gd['ch']}"                                      # "Chapter 4" (no sections)
            elif not m.groups(): key = cur_sec or f'ch{chapter_no}'                       # a bare "EXERCISES" heading
            else: key = m.group(2) if m.group(1).startswith('Section') else 'ch' + m.group(2)
            out.append(f'<div class="exercises" data-for="{key}"><h3>{html.escape(text)}</h3>')
            ex = {'key': key, 'items': [], 'groups': {}, 'group': 0, 'cols': [], 'intro': []}
            continue
        # --- code listing caption ("Listing 3.1 ...") ---
        if LST_CAP and LST_CAP.match(text) and ex is None:
            close_para(); close_listing()
            lst = {'cap': C.inline(pno, row), 'code': [], 'annos': [], 'font': None}
            last_row_y = row.y1
            continue
        # --- code (coding books): rows set entirely in a monospace font ---
        vis = [v for k, v in row.items if k == 'span' and v.text.strip()]
        if vis and all(v.mono for v in vis) and not any(k == 'math' for k, _ in row.items):
            cw = next(((v.x1 - v.x0) / len(v.text) for v in vis if len(v.text) > 3), 5.0)   # monospace char width
            line = ''.join(v.text for k, v in row.items if k == 'span')
            last_row_y = row.y1
            if lst is not None and not lst['annos']:
                lst['code'].append((row.x0, cw, line)); continue
            close_listing()
            if ex is not None and ex['items']:                # code inside an exercise
                ex['items'][-1].setdefault('code', []).append((row.x0, cw, line)); continue
            if para: close_para()
            code_buf.append((row.x0, cw, line)); continue
        # --- listing annotations ("#A explanation") below the code ---
        if lst is not None:
            m = ANNO_TXT.match(text) if ANNO_TXT else None
            if m:
                body = C.inline(pno, row); mk = m.group(0).strip()
                body = re.sub(rf'^((?:<[^>]+>)*){re.escape(mk)}\s*', r'\1', body, count=1)
                lst['annos'].append((m.group(1), mk, [body])); lst['font'] = (ft.font, round(row.x0)); last_row_y = row.y1; continue
            if lst['annos'] and lst['font'] == (ft.font, round(row.x0)) and gap < 0.6 * row.size:
                add(lst['annos'][-1][2], C.inline(pno, row)); last_row_y = row.y1; continue
            close_listing()
        # --- shaded sidebars (text inside a panel) ---
        if row.panel is not None and ex is None:
            if side is None or (side[0] == pno and side[1] != row.panel):
                close_side(); close_para(); out.append('<aside class="sidebar">')
            side = (pno, row.panel)
        elif side is not None and ex is None:
            close_side()
        if ex is not None:
            # group heading "A. ..." (bold) or its bold continuation
            if ft.bold and re.match(r'^[A-Z]\.\s', text) and not NUM.match(ft.text.strip()):
                ex['group'] += 1; ex['groups'][ex['group']] = C.inline(pno, row); ex['last'] = 'group'; continue
            # split row at bold item numbers (two-column layouts put two items on one row)
            def prev_word(i):
                return next((v.text.strip() for k, v in reversed(row.items[:i]) if k == 'span' and v.text.strip()), '')
            seq = [max((it['num'] for it in ex['items']), default=0)]   # the last number, as this row's cuts are taken
            def unstyled_cut(i):                               # OCR or plain numbers: an item number opens the row or a column, in sequence
                v, last = row.items[i][1], seq[0]
                n = int(NUM.match(v.text.strip()).group(1))
                tol = 25 if UNSTYLED else 8                    # OCR boxes drift; a text PDF's number column does not
                at_col = any(abs(v.x0 - left - c) < tol for c in ex['cols']) if ex['cols'] else v.x0 - left < 40
                prev = next((w for k, w in reversed(row.items[:i]) if k == 'math' or (k == 'span' and w.text.strip())), None)
                gap = prev is None or v.x0 - prev.x1 > 12
                new_col = prev is not None and v.x0 - prev.x1 > 20 and last < n <= last + 2   # "8. 16   9. 24   10. 32" on one row
                ok = gap and (at_col or new_col) and last < n <= last + (99 if solutions else 5)
                if ok: seq[0] = n
                return ok
            cuts = [i for i, (k, v) in enumerate(row.items) if k == 'span' and NUM.match(v.text.strip())
                    and (v.bold or ((PLAIN_SOLUTIONS if solutions else PLAIN_ITEMS) and unstyled_cut(i))) and not (ITEM_EXCL and ITEM_EXCL.search(prev_word(i)))]
            if not cuts:
                if ex.get('last') == 'group' and all(v.bold for k, v in row.items if k == 'span' and v.text.strip()):
                    ex['groups'][ex['group']] += ' ' + C.inline(pno, row); continue
                if not ex['items']:                           # untitled intro paragraph before the first item
                    ex['groups'][ex['group']] = (ex['groups'].get(ex['group'], '') + ' ' + C.inline(pno, row)).strip(); continue
                col = min(ex['cols'], key=lambda c: abs(c - (row.x0 - left)))
                tgt = max((it for it in ex['items'] if it['col'] == col), key=lambda it: (it['pno'], it['y']))
                add(tgt['html'], C.inline(pno, row)); continue
            if cuts[0] > 0:                                   # text before the first number continues the left column item
                pre = row.items[:cuts[0]]
                if ex['items']: add(ex['items'][-1]['html'], C.inline(pno, row, pre))
            for j, c in enumerate(cuts):
                seg = row.items[c + 1:(cuts[j + 1] if j + 1 < len(cuts) else None)]
                x0 = row.items[c][1].x0 - left              # odd/even pages have different margins
                col = next((cc for cc in ex['cols'] if abs(cc - x0) < 25), None)
                if col is None: ex['cols'].append(x0); col = x0
                ex['items'].append({'num': int(row.items[c][1].text.strip()[:-1]), 'group': ex['group'], 'col': col,
                                    'y': row.y0, 'pno': pno, 'html': [C.inline(pno, row, seg)]})
            ex['last'] = 'item'
            continue
        flush_code()
        # --- body text ---
        indent = row.x0 - left
        if wrap: wrap -= 1; indent = 0                         # lines wrapped around a drop cap are indented
        last_row_y = row.y1
        pitch = row.base - last_base[1] if last_base and last_base[0] == pno else None   # baseline to baseline
        usual = sorted(pitches)[len(pitches) // 2] if len(pitches) >= 3 else 1.3 * row.size
        spaced = pitch is not None and pitch > LAY['para_pitch'] * usual                 # extra space: new paragraph
        if pitch is not None and 0.8 * row.size < pitch < 2.2 * row.size and not spaced:
            pitches.append(pitch); del pitches[:-40]                                     # the book's line pitch, learnt
        last_base = (pno, row.base)
        word = ft.text.strip().split(' ')[0]
        starts_label = word in LABELS and (ft.bold or (UNSTYLED and re.match(rf'^{word}\s+\d+\.', text) is not None))
        starts_proof = (ft.italic or UNSTYLED) and PROOF and PROOF.match(ft.text.strip())
        callout = text.split(' ')[0].rstrip(':') if text.split(' ')[0].rstrip(':') in CALLOUTS else None
        bullet = text.startswith('•') or row.bullet
        caption = (ft.bold or not PAT['caption_bold']) and any(p and p.match(text) for p in (FIG_CAP, TBL_CAP))
        item = indent > 3 and re.match(r'^\d+\.(?!\d)', text) is not None   # numbered list inside the body
        display = indent > LAY['display_indent'] and not bullet and not caption and not item and not callout
        wrapped = cont is not None and (abs(row.x0 - cont[0]) < 3 or (abs(row.x0 - cont[1]) < 3 and indent <= LAY['para_indent'])) \
            and not spaced \
            and not (bullet or callout or caption or starts_label or item)   # a wrapped line of a list item, note or caption
        new = not para or indent > LAY['para_indent'] or spaced or starts_label or starts_proof or bullet \
            or caption or display or item or callout or para_cls == 'display'
        if wrapped: new = False
        if para and re.search(r'\w-(</\w+>)*$', para[-1]): new = False     # a word broken across lines never ends a paragraph
        if new:
            close_para()
            para_y0, para_at = row.y0, (pno, True)
            para_cls = ('display' if display else 'caption' if caption else ('bullet l2' if indent > 60 else 'bullet') if bullet
                        else 'item' if item else
                        f'callout {callout.lower()}' if callout else
                        f'lbl {word.lower()}' if starts_label else 'proof' if starts_proof else '')
        if (bullet or callout or caption or item) and new:     # its wrapped lines start under the text (after "•", "4.")
            text_x = next((v.x0 for k, v in row.items if k == 'span' and v.text.strip()
                           and not re.fullmatch(r'[•\d.)]+', v.text.strip())), row.x0)
            cont = (text_x, row.x0)
        piece = C.inline(pno, row)
        if dropcap: piece, dropcap = dropcap + piece, ''
        add(para, piece)
    close_all()
    while stack: out.append('</section>'); stack.pop()
    return '\n'.join(out) + '\n', C.n


if __name__ == '__main__':
    slug, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    skip = range(int(sys.argv[4]), int(sys.argv[5]) + 1) if len(sys.argv) > 5 else ()
    src, n = convert(slug, a, b, skip, solutions=slug == 'solutions')
    (ROOT / 'content').mkdir(exist_ok=True)
    (ROOT / 'content' / f'{slug}.html').write_text(src, encoding='utf-8')
    print(f'content/{slug}.html written, {n} crops')
