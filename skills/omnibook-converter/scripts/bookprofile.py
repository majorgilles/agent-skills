"""Book profile: every book-specific constant of the pipeline, read from <repo>/profile.json.
The file only needs the keys that differ from DEFAULTS (Book of Proof, the reference build); nested dicts are merged.
  BOOK_PROFILE=path/to/profile.json overrides the location (tests).
`python tools/survey.py work/Main.pdf --profile profile.json` writes a first draft for a new book."""
import os, re, json, copy, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

DEFAULTS = {
    'pdf': 'work/Main.pdf',
    'book': {
        'title': 'Book of Proof', 'author': 'Richard Hammack',
        'id': 'bop',                       # short unique slug: namespaces saved progress (books on one origin share storage)
        'license_html': ('<p><em>Book of Proof</em>, Third Edition, by Richard Hammack. © 2018 Richard Hammack. Licensed under '
                         '<a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">CC BY-NC-ND 4.0</a>. The original PDF is '
                         'freely available at <a href="https://richardhammack.github.io/BookOfProof/">richardhammack.github.io/BookOfProof</a>. '
                         'This site is an unmodified format conversion with added progress tracking and exercise checking; '
                         'it is not affiliated with or endorsed by the author.</p>'),
        'order': ['front'] + [f'ch{i:02d}' for i in range(1, 15)] + ['conclusion', 'solutions'],   # reading order of content/*.html
    },
    'page': {
        'top': 75, 'bottom': 675,          # running head above / footer (and watermarks) below, in PDF points
        'margin_even': 79, 'margin_odd': 54,   # body left margin by 0-based page parity (survey.py prints them)
    },
    'fonts': {                             # regexes on PDF font names
        'prose': '^TeXGyreSchola',         # the body text font: verify.py checks these words in order
        'text': '',                        # other text fonts (headings, notes, captions): never treated as math
        'mono': 'Mono|Courier|Consol|Code|Inconsolata|Menlo|Typewriter|CMTT|LMTT',   # code
        'bold': 'Bold|Demi|Heavy|Semibold',
        'italic': 'Italic$|Ital$|Oblique$',
        'math_italic': '^(CenturySchL-Ital|Fourier-Math-Letters-Ita)$',   # rendered <i>, excluded from the prose check
        # custom-encoded math glyphs -> Unicode (render a glyph sheet and map only what you identify with certainty)
        'fix': {'Fourier-Math-Symbols': {';': '∅', 'p': '√'},
                'Fourier-Math-Extension': {'©': '{', 'ª': '}', '¡': '(', '¢': ')', '£': '[', '¤': ']', '³': '(', '´': ')', 'µ': '(', '¶': ')'},
                'Fourier-Math-BlackBoard': dict(zip('CNQRZ', 'ℂℕℚℝℤ')), 'rsfs10': {'F': 'ℱ', 'P': '𝒫'}},
        'extension': ['Fourier-Math-Extension'],   # big-delimiter fonts: glyph boxes lie, placed by overlap; unmapped glyphs -> crop
        'radical': {'Fourier-Math-Symbols': 'p'},  # font -> raw char of the radical sign (its box sits above the ink)
        'radical_crop': True,              # crop each radical with its bar; false: keep √ as text (placed on the row below)
    },
    'sizes': {'small': 8.5, 'normal_min': 9, 'title': 13, 'dropcap': 20, 'section_min': 10.5},
    'layout': {
        'para_pitch': 1.4,                 # a baseline distance this many times the usual line pitch starts a paragraph
        'para_indent': 8,                  # first-line indent (pt) that starts a new paragraph
        'display_indent': 28,              # rows indented more than this are displays (centred formulas)
        'space_gap': 1.2,                  # a horizontal gap wider than this between glyphs is a word space
    },
    'patterns': {                          # regexes on a row's plain text
        'chapter_marker': r'^CHAPTER\s*(\d+)$',            # a row that only announces the chapter number
        'chapter_inline': r'^(\d+)\s+(\S.*)$',             # "3 Title" on the title row itself (Manning); '' disables
        'section': r'^(\d+)\.(\d+)\s+(.*)',
        'section_bold': True,
        'subsection': r'^(\d+)\.(\d+)\.(\d+)\s+(.*)',
        'subsection_min': 10,
        'exercises': r'^Exercises for (Section|Chapter) ([\d.]+)',
        'solutions': r'^(Sections?) (\d+\.\d+)$|^(Chapter) (\d+)( Exercises)?$',
        'item_exclusions': r'(Case|Step|Part)$',           # "Case 1." inside a proof is not an exercise number
        'item_bold': True,                 # exercise numbers are bold; false: regular type, cut where they continue the sequence
        'labels': ['Definition', 'Theorem', 'Proposition', 'Lemma', 'Corollary', 'Example', 'Fact'],
        'proof': r'^Proof',                # italic lead word of a proof
        'proof_end': '■|□|∎',              # end-of-proof marks
        'figure_caption': r'^Figure \d+\.\d+',
        'caption_bold': True,
        'listing_caption': r'^Listing \d+\.\d+',
        'table_caption': r'^Table \d+\.\d+',
        'callouts': ['NOTE', 'TIP', 'WARNING', 'IMPORTANT', 'DEFINITION', 'EXERCISE'],   # lead words of boxed notes
        'code_continuation': '',           # marker the typesetter prints on wrapped code lines, e.g. "[CA]" (Manning)
        'code_annotation': '',             # marker at the end of a code line, e.g. r"#([A-Z])\s*$" (Manning cueballs)
        'annotation_text': '',             # explanation rows below a listing, e.g. r"^#([A-Z])\s+"
    },
    'code_lang': 'python',                 # python | javascript | sql | other (runnable: python, javascript)
    'ocr': False,                          # scanned book: text layer and figure regions come from ocr.py
}


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict) and not k == 'fix': _merge(a[k], v)
        else: a[k] = v
    return a


def load():
    p = pathlib.Path(os.environ.get('BOOK_PROFILE', ROOT / 'profile.json'))
    prof = copy.deepcopy(DEFAULTS)
    if p.exists(): _merge(prof, json.loads(p.read_text(encoding='utf-8')))
    return prof


PROFILE = load()


def rx(name, group='patterns'):
    """Compiled regex for a profile pattern ('' -> None)."""
    s = PROFILE[group][name]
    return re.compile(s) if s else None


def pdf_path():
    return os.environ.get('BOOK_PDF') or str(ROOT / PROFILE['pdf'])
