"""Step 1 for a new book: learn its typography before adapting the converter.
  python survey.py work/Main.pdf
Prints: license page text, fonts (with glyph inventories for non-text fonts), body margins by page parity,
exercise/solution heading patterns, and chapter page ranges from the PDF outline (0-based, for convert_all.sh)."""
import sys, re, collections, pymupdf

d = pymupdf.open(sys.argv[1])
print(f'{d.page_count} pages; metadata: {d.metadata.get("creator")} / {d.metadata.get("producer")}\n')
print('--- first pages (look for the license) ---')
for i in range(min(4, d.page_count)):
    t = d[i].get_text().strip()
    if re.search(r'licen[cs]e|creative commons|copyright|©', t, re.I): print(f'[page {i}]', t[:600], '\n')

fonts = collections.defaultdict(collections.Counter)
margins = collections.defaultdict(collections.Counter)
heads = collections.Counter()
for pno, p in enumerate(d):
    for b in p.get_text('rawdict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                for c in s['chars']: fonts[s['font']][c['c']] += 1
            first = l['spans'][0]
            if l['spans'] and 9 < first['size'] < 12: margins[pno % 2][round(l['bbox'][0])] += 1
            txt = ''.join(c['c'] for s in l['spans'] for c in s['chars']).strip()
            if 'Bold' in first['font'] and re.match(r'(Exercises|Problems|Solutions|Answers|Section|Chapter)\b', txt):
                heads[re.sub(r'[\d.]+', 'N', txt)[:40]] += 1

print('--- fonts: chars used (text fonts: count only; math/symbol fonts: full glyph list) ---')
for f, c in sorted(fonts.items(), key=lambda x: -sum(x[1].values())):
    glyphs = ''.join(sorted(c))
    textish = len(c) > 60
    print(f'{f:32s} {sum(c.values()):7d} chars {len(c):3d} glyphs', '' if textish else repr(glyphs[:120]))
print('\n--- body left margin by page parity (most common x of text lines) ---')
for par in (0, 1):
    print('even' if par == 0 else 'odd ', 'pages:', margins[par].most_common(3))
print('\n--- bold heading patterns (exercise/solution structure) ---')
for h, n in heads.most_common(15): print(f'{n:4d}  {h}')
print('\n--- outline -> 0-based page ranges (slug first last) ---')
toc = [t for t in d.get_toc() if t[0] <= 2]
for k, (lvl, title, page) in enumerate(toc):
    end = toc[k + 1][2] - 2 if k + 1 < len(toc) else d.page_count - 1
    print(f'{"  " * (lvl - 1)}{title[:50]:50s} {page - 1:4d} {end:4d}')
