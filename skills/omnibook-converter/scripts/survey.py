"""Step 1 for a new book: learn its typography before converting.
  python tools/survey.py work/Main.pdf [--profile profile.json]
Prints: license page text, scanned (image-only) pages, fonts (with glyph inventories for non-text fonts), body size,
margins by page parity, running head/footer bands, heading patterns and chapter page ranges from the PDF outline.
--profile writes a first-draft profile.json (only the keys that differ from the defaults); review it, then convert
one chapter and iterate with verify.py and audit.py."""
import sys, re, json, collections, pymupdf

d = pymupdf.open(sys.argv[1])
print(f'{d.page_count} pages; metadata: {d.metadata.get("creator")} / {d.metadata.get("producer")}\n')
print('--- first pages (look for the license) ---')
for i in range(min(6, d.page_count)):
    t = d[i].get_text().strip()
    if re.search(r'licen[cs]e|creative commons|copyright|©|all rights reserved', t, re.I): print(f'[page {i}]', t[:600], '\n')

scanned = [i for i, p in enumerate(d) if len(p.get_text().strip()) < 20 and p.get_images()]
if scanned:
    print(f'--- {len(scanned)} scanned pages without a text layer (first: {scanned[:10]}) -> run tools/ocr.py first ---\n')

fonts = collections.defaultdict(collections.Counter)
sizes = collections.defaultdict(collections.Counter)            # font -> size -> chars
margins = collections.defaultdict(collections.Counter)
heads = collections.Counter()
bands = collections.Counter()                                   # (rounded y, short text kind) of lines repeated on pages
widths = collections.defaultdict(list)                          # glyph advance / size per font: monospace = all equal
for pno, p in enumerate(d):
    H = p.rect.height
    for b in p.get_text('rawdict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                for c in s['chars']:
                    fonts[s['font']][c['c']] += 1
                    if c['c'].strip(): widths[s['font']].append(round((c['bbox'][2] - c['bbox'][0]) / max(s['size'], 1), 3))
                sizes[s['font']][round(s['size'], 1)] += len(s['chars'])
            if not l['spans']: continue
            first = l['spans'][0]
            txt = ''.join(c['c'] for s in l['spans'] for c in s['chars']).strip()
            margins[pno % 2][round(l['bbox'][0])] += 1
            if len(txt) < 80 and (l['bbox'][3] < 0.10 * H or l['bbox'][1] > 0.90 * H):
                bands[(round(l['bbox'][1] / 4) * 4, 'top' if l['bbox'][3] < 0.10 * H else 'bottom')] += 1
            if re.search(r'Bold|Demi|Semibold|Heavy', first['font']) and re.match(r'(Exercises?|Problems|Solutions|Answers|Section|Chapter|Listing|Figure|Table)\b', txt):
                heads[re.sub(r'[\d.]+', 'N', txt)[:40]] += 1

total = {f: sum(c.values()) for f, c in fonts.items()}
print('--- fonts: chars used (text fonts: count only; math/symbol fonts: full glyph list) ---')
for f, c in sorted(fonts.items(), key=lambda x: -total[x[0]]):
    top_size = sizes[f].most_common(1)[0][0]
    print(f'{f:32s} {total[f]:7d} chars {len(c):3d} glyphs  size {top_size:5}', '' if len(c) > 60 else repr(''.join(sorted(c))[:120]))
body_font = max(total, key=total.get)
body_size = sizes[body_font].most_common(1)[0][0]
print(f'\nbody font: {body_font} at {body_size} pt')
print('\n--- most common left x of lines by page parity (0-based page index) ---')
for par in (0, 1):
    print('even' if par == 0 else 'odd ', 'pages:', margins[par].most_common(3))
n = d.page_count
rep = sorted(((y, k) for (y, k), c in bands.items() if c > 0.4 * n), key=lambda t: t[0])
top = max([y for y, k in rep if k == 'top'], default=None)
bottom = min([y for y, k in rep if k == 'bottom'], default=None)
print(f'\n--- running heads / footers: lines repeated on >40% of pages at y {[y for y, _ in rep]} ---')
print('\n--- bold heading patterns (exercise/solution/listing structure) ---')
for h, c in heads.most_common(15): print(f'{c:4d}  {h}')
print('\n--- outline -> 0-based page ranges (slug first last) ---')
toc = [t for t in d.get_toc() if t[0] <= 2]
for k, (lvl, title, page) in enumerate(toc):
    end = toc[k + 1][2] - 2 if k + 1 < len(toc) else d.page_count - 1
    print(f'{"  " * (lvl - 1)}{title[:50]:50s} {page - 1:4d} {end:4d}')

if '--profile' in sys.argv:
    out = sys.argv[sys.argv.index('--profile') + 1]
    def fixed_width(f):
        w = collections.Counter(widths[f]).most_common(1)
        return len(fonts[f]) > 30 and w and w[0][1] > 0.9 * len(widths[f])
    mono = [f for f in total if re.search(r'Mono|Courier|Consol|Code|Inconsolata|Menlo|Typewriter|CMTT|LMTT', f, re.I) or fixed_width(f)]
    family = re.split(r'[-,+]', body_font.split('+')[-1])[0]
    texty = [re.split(r'[-,+ ]', f.split('+')[-1])[0] for f in total if f not in mono and total[f] > 0.01 * total[body_font]
             and len(fonts[f]) > 40 and not f.startswith(family)
             and not re.search(r'Math|Symbol|Extension|BlackBoard|Letters|rsfs|^CM|^LM|Fourier|CenturySch|Ital$', f)]
    m0, m1 = margins[0].most_common(1)[0][0], margins[1].most_common(1)[0][0]
    prof = {
        'book': {'title': '', 'author': '', 'id': '', 'license_html': '<p>Personal study copy. Not for distribution.</p>', 'order': []},
        'page': {'top': top + 14 if top is not None else 40, 'bottom': bottom - 2 if bottom is not None else d[0].rect.height,
                 'margin_even': m0, 'margin_odd': m1},
        'fonts': {'prose': '^' + re.escape(family), 'text': ('^(' + '|'.join(sorted(set(map(re.escape, texty)))) + ')') if texty else '',
                  'mono': '|'.join(sorted(set('^' + re.escape(f) if f.startswith('Type3') else re.escape(re.split(r'[-,]', f.split('+')[-1])[0])
                                              for f in mono))) or
                          'Mono|Courier|Consol|Code|Inconsolata|Menlo|Typewriter|CMTT|LMTT',
                  'fix': {}, 'extension': [], 'radical': {}},
        'sizes': {'small': round(0.85 * body_size, 1), 'normal_min': round(0.9 * body_size, 1), 'title': round(1.6 * body_size, 1),
                  'dropcap': round(2.2 * body_size, 1), 'section_min': round(1.15 * body_size, 1)},
        'code_lang': 'python' if mono else 'other',
    }
    json.dump(prof, open(out, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print(f'\ndraft profile written to {out}: check page.top/bottom (running heads must fall outside), fonts '
          '(fonts.text must hold only text fonts: math fonts there would stop math being cropped), '
          'patterns (headings, exercises, captions) and code markers, then convert one chapter.')
