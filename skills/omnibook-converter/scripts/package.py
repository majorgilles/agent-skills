"""Book package for Gilles's Omnibook Reader: one file, dist/<id>.omnibook (a zip), holding
  book.json        format, id, title, author, year, cover, license_html, code_lang, chapters [{slug, title}], audit summary
  cover.<ext>      the cover image (cover.py: profile.json book.cover, else found on Open Library)
  outline.json     per chapter: sections with their exercise ids (progress model, contents)
  chapters/<slug>.html   the verified content fragment; every block carries data-b="<n>" (bookmark/annotation anchor)
  figs/...         exact crops (SVG / PNG)
  solutions.json   {exercise id: solution html}
  search.json      [{c: slug, b: block, t: text}] for full-text search
  python tools/package.py            (reads profile.json book.* and content/*.html, site/figs)
The reader app does the rest (fonts, themes, bookmarks, highlights and notes, exercises, grading, proof maps)."""
import sys, re, json, html, zipfile, pathlib, datetime
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bookprofile import PROFILE
from cover import cover_and_year

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT, FIGS = ROOT / 'content', ROOT / 'site' / 'figs'
BLOCK = re.compile(r'<(p|li|h1|h2|h3|figure|pre|aside|table|div class="sol")\b')
FORMAT = 1


def chapter_h1(src):
    """The chapter's own heading (a Part page may come first in the same file), else the first <h1>."""
    return re.search(r'<section class="chapter"[^>]*>\s*<h1[^>]*>(.*?)</h1>', src, re.S) or re.search(r'<h1[^>]*>(.*?)</h1>', src, re.S)


def title_of(src):
    """The chapter's title without its number label."""
    m = chapter_h1(src)
    if not m: return 'Untitled'
    t = re.sub(r'<span class="num[^"]*">.*?</span>', ' ', m.group(1), flags=re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t))).strip() or 'Untitled'


def number_of(src):
    """The chapter number printed in the first <h1> label ("CHAPTER 4" -> "4"), or ''."""
    h = chapter_h1(src)
    m = re.match(r'\s*<span class="num[^"]*">(.*?)</span>', h.group(1), re.S) if h else None
    n = re.search(r'\d+', m.group(1)) if m else None
    return n.group(0) if n else ''


def outline(slug, src):
    """Sections with their exercise ids, used by the contents and the progress model."""
    secs = []
    for m in re.finditer(r'<section class="sec" id="([^"]+)" data-title="([^"]*)"', src):
        secs.append({'id': m.group(1), 'title': html.unescape(m.group(2)), 'ex': []})
    for chunk in src.split('<div class="exercises" data-for="')[1:]:
        key = chunk[:chunk.index('"')]
        ids = re.findall(r'<li class="ex" id="([^"]+)"', chunk)
        target = next((s for s in secs if s['id'] == 's' + key.replace('.', '-')), None)
        if target is None:                                         # chapter-level exercises become their own unit
            target = {'id': 'x-' + key, 'title': 'Exercises for Chapter ' + key.lstrip('ch'), 'ex': []}
            secs.append(target)
        target['ex'] += ids
    subs = [{'id': m.group(1), 'title': html.unescape(re.sub(r'<[^>]+>', ' ', m.group(2))).strip()}
            for m in re.finditer(r'<h3 id="([^"]+)">(.*?)</h3>', src, re.S)]
    return {'slug': slug, 'title': title_of(src), 'sections': secs, 'subsections': subs}


def number_blocks(src):
    """data-b="n" on every block element, in document order: stable anchors for bookmarks and annotations."""
    n = 0
    def tag(m):
        nonlocal n; n += 1
        return f'{m.group(0)} data-b="{n}"'
    return BLOCK.sub(tag, src)


def search_entries(slug, src):
    out = []
    for m in re.finditer(r'<(p|li|h1|h2|h3|figcaption|td|th|div class="sol")\b[^>]*?data-b="(\d+)"[^>]*>(.*?)</(?:p|li|h1|h2|h3|figcaption|td|th|div)>', src, re.S):
        t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', r' \1 ', m.group(3))))
        t = re.sub(r'<[^>]+>', ' ', t).strip()
        if len(t) > 2: out.append({'c': slug, 'b': int(m.group(2)), 't': re.sub(r'\s+', ' ', t)})
    return out


def audit_summary():
    reports = sorted((ROOT / 'work' / 'audit').glob('*.json')) if (ROOT / 'work' / 'audit').exists() else []
    summ = {}
    for f in reports:
        r = json.loads(f.read_text(encoding='utf-8'))
        summ[f.stem] = {'missing_chars': sum(v['n'] for v in r['missing_chars'].values()), 'extra_chars': sum(r['extra_chars'].values()),
                        'uncovered_drawings': len(r['uncovered_drawings']),
                        'pixel_mismatches': len(r['figure_pixels']) if isinstance(r['figure_pixels'], list) else None,
                        'structure': len(r['structure'])}
    return summ


def main():
    B = PROFILE['book']
    if not B.get('id'): sys.exit('profile.json book.id is required (short, unique among your books)')
    order = B.get('order') or sorted(p.stem for p in CONTENT.glob('*.html'))
    pages = [(s, (CONTENT / f'{s}.html').read_text(encoding='utf-8')) for s in order if (CONTENT / f'{s}.html').exists()]
    dist = ROOT / 'dist'; dist.mkdir(exist_ok=True)
    out = dist / f'{B["id"]}.omnibook'
    chapters, outl, search, sols, figs = [], [], [], {}, set()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for slug, src in pages:
            body = number_blocks(re.sub(r'^<!--.*?-->\s*', '', src, flags=re.S))
            body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
            figs |= set(re.findall(r'src="(figs/[^"]+)"', body))
            if slug == 'solutions':
                for m in re.finditer(r'<div class="sol" id="[^"]+" data-ex="([^"]+)"[^>]*>(.*?)</div>', body, re.S):
                    sols[m.group(1)] = m.group(2).strip()
            z.writestr(f'chapters/{slug}.html', body)
            chapters.append({'slug': slug, 'num': number_of(src), 'title': title_of(src)})
            outl.append(outline(slug, src) if slug != 'solutions' else {'slug': slug, 'title': title_of(src), 'sections': [], 'subsections': []})
            search += search_entries(slug, body)
        for f in sorted(figs):
            p = ROOT / 'site' / f
            if p.exists(): z.write(p, f, compress_type=zipfile.ZIP_STORED if p.suffix == '.png' else zipfile.ZIP_DEFLATED)
            else: print('  missing figure file', f)
        image, ext, year = cover_and_year(B)
        if image: z.writestr(f'cover.{ext}', image, compress_type=zipfile.ZIP_STORED)
        meta = {'format': FORMAT, 'id': B['id'], 'title': B['title'], 'author': B.get('author', ''), 'year': year,
                'cover': f'cover.{ext}' if image else None,
                'license_html': B.get('license_html', ''), 'code_lang': PROFILE.get('code_lang', 'other'),
                'chapters': chapters, 'built': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                'audit': audit_summary(), 'ocr': PROFILE.get('ocr', False)}
        z.writestr('book.json', json.dumps(meta, ensure_ascii=False, indent=1))
        z.writestr('outline.json', json.dumps(outl, ensure_ascii=False))
        z.writestr('solutions.json', json.dumps(sols, ensure_ascii=False))
        z.writestr('search.json', json.dumps(search, ensure_ascii=False))
    n_ex = sum(len(s['ex']) for c in outl for s in c['sections'])
    print(f'{out}: {len(chapters)} chapters, {n_ex} exercises, {len(sols)} solutions, {len(figs)} figures, '
          f'{len(search)} searchable blocks, {out.stat().st_size // 1024} KiB')


if __name__ == '__main__':
    main()
