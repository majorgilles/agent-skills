"""The book's cover image and year of publication, for the reader's library (book.json `cover`, `year`).
package.py calls cover_and_year(): profile.json book.cover (an image path, or false for none) and book.year win;
otherwise Open Library is searched by title and author, and the result is kept in work/cover.json and work/cover.<ext>
so a rebuild does not search again. The reader looks a cover up itself for a package without one.
  python tools/cover.py dist/<id>.omnibook [--image PATH|URL] [--year YYYY]   puts a cover into a built package
Without --image it searches Open Library; it bumps book.json `built`, so every reader takes the new package."""
import sys, re, json, zipfile, pathlib, datetime, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEARCH = 'https://openlibrary.org/search.json'
UA = {'User-Agent': 'omnibook-converter (personal library)'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read(), r.headers.get_content_type()


def words(s):
    return re.sub(r'[^a-z0-9 ]+', ' ', (s or '').lower()).split()


def look_up(title, author=''):
    """-> (image bytes or None, extension, year or None) of the best Open Library match: an edition with this exact
    title and a cover, else any result with a cover. The year is the earliest first publication of that title."""
    q = {'title': title, 'fields': 'title,first_publish_year,cover_i', 'limit': 10}
    if author: q['author'] = author
    docs = json.loads(get(f'{SEARCH}?{urllib.parse.urlencode(q)}')[0]).get('docs', [])
    same = [d for d in docs if words(d.get('title')) == words(title)]
    best = next((d for d in same + docs if d.get('cover_i')), (same or docs or [None])[0])
    if not best: return None, '', None
    years = [d['first_publish_year'] for d in same + [best] if d.get('first_publish_year')]
    image = get(f"https://covers.openlibrary.org/b/id/{best['cover_i']}-L.jpg")[0] if best.get('cover_i') else None
    return image, 'jpg', min(years) if years else None


def read_image(src):
    """An image from a path or URL -> (bytes, extension)."""
    if re.match(r'https?://', src):
        data, ctype = get(src)
        return data, {'image/png': 'png', 'image/webp': 'webp'}.get(ctype, 'jpg')
    p = pathlib.Path(src)
    return p.read_bytes(), p.suffix.lstrip('.').lower().replace('jpeg', 'jpg')


def cover_and_year(book, work=ROOT / 'work'):
    """profile.json `book` -> (image bytes or None, extension, year or None), searching Open Library once per book."""
    year = book.get('year')
    if book.get('cover') is False: return None, '', year
    if book.get('cover'):
        data, ext = read_image(str(ROOT / book['cover']) if not re.match(r'https?://', book['cover']) else book['cover'])
        return data, ext, year
    cache = work / 'cover.json'
    if cache.exists():
        c = json.loads(cache.read_text(encoding='utf-8'))
        img = work / f"cover.{c['ext']}" if c.get('ext') else None
        return (img.read_bytes() if img and img.exists() else None), c.get('ext', ''), year or c.get('year')
    try:
        data, ext, found = look_up(book['title'], book.get('author', ''))
    except OSError as e:
        print(f'  no cover: Open Library unreachable ({e}); the reader will look it up')
        return None, '', year
    work.mkdir(exist_ok=True)
    if data: (work / f'cover.{ext}').write_bytes(data)
    cache.write_text(json.dumps({'ext': ext if data else '', 'year': found}), encoding='utf-8')
    print(f'  cover from Open Library: {"found" if data else "none"}, first published {found or "?"} '
          '(profile.json book.cover / book.year override it)')
    return data, ext, year or found


def main():
    path = pathlib.Path(sys.argv[1])
    arg = lambda n: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else None
    with zipfile.ZipFile(path) as z: files = {n: z.read(n) for n in z.namelist()}
    meta = json.loads(files['book.json'])
    if arg('--image'): (data, ext), found = read_image(arg('--image')), None
    else: data, ext, found = look_up(meta['title'], meta.get('author', ''))
    if meta.get('cover'): files.pop(meta['cover'], None)
    if data:
        meta['cover'] = f'cover.{ext}'
        files[meta['cover']] = data
    meta['year'] = int(arg('--year') or meta.get('year') or found or 0) or None
    meta['built'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    files['book.json'] = json.dumps(meta, ensure_ascii=False, indent=1).encode()
    tmp = path.with_suffix('.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in files.items(): z.writestr(n, b)
    tmp.replace(path)
    print(f"{path}: cover {meta.get('cover') or 'none'}, year {meta['year'] or '?'}")


if __name__ == '__main__':
    main()
