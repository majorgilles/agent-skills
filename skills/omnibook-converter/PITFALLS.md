# Converter pitfalls (each cost a debugging session)

Text layer
- `get_text('rawdict')` drops zero-width glyphs (combining slash of ≠): use `get_texttrace()` (layout.NEG).
- A negation slash over a symbol missing from `layout.NEG` was dropped: "⇏" read "⇒", the opposite meaning, and the
  audit was blind because it counted through the same `Span` text. Now an unknown pair keeps U+0338, and
  `audit.negations_check` counts slashes straight from `get_texttrace()`.
- Overstrikes: TeX books may print ∅ as "/" over "0" (two glyphs, 3.8 pt overlap): `Span` reads the pair as ∅.
- Bar accents (TeX \\bar) are their own glyph "¯", set before the letter: `layout.bar_accents` joins each to the letter
  under it as U+0304 (P̄ is "not P" in logic books). Drawn overlines (\\overline, recurring decimals) are stretched
  1×1 images, not text: `layout.overlines` puts U+0305 on each character under one (no numerator over it, no word).
- Root bars: TeX big radicals are CMEX glyphs p q r s, not "√" (`layout.ROOT_SIGN`). A root over more than 2
  characters is cropped whole, and a span that runs past the bar's end is split there (`split_at_roots`).
- Word spaces are often positional gaps, also inside one span: insert a space for gaps > `space_gap`.
- Bold regexes: `Black` matched `Fourier-Math-BlackBoard`; keep style regexes specific.
- Floating point: rounded rects in JSON vs PDF floats; compare containment with a 0.5 pt tolerance.

Rows and paragraphs
- Rows come from normal-size baselines; scripts and fraction parts attach by nearest baseline, big delimiters by
  overlap, radicals to the row below. Each fraction bar belongs to one row (nearest centre) or it is cropped twice.
- Full-size fraction parts (Book of Proof's m/n in ℚ = {x : x = m/n}) make their own baseline: a short all-math row
  within 9 pt of a wider row joins it. A big brace's glyph box covers its top piece only: grow it to the row's math.
- Paragraph breaks: compare baseline pitch with the learnt line pitch, never box gaps (a line of x-height letters has
  a smaller box). Wrapped lines of bullets, numbered items, notes and captions continue at the item's text x.
- Drop caps: the first line can come before the giant letter in y order; attach the letter to it.
- Line-end hyphens: rejoin with the book's own vocabulary (`layout.rejoin`); a line ending in a hyphen never ends a paragraph.

Drawings
- Page furniture is not a figure: page-sized and white background fills, white boxes behind text, shaded panels
  behind code or sidebars, frames (one stroked rect or four lines) around text, bullets (small, isolated, at a line
  start: dice pips are not bullets), badges (NOTE label, chapter-number square), link underlines (start and end with
  words), highlight bars. A frame with > 40 letters of words inside is boxed text; punctuation and single letters
  inside a drawing (dice grids, set diagrams) are labels.
- Tables: Manning rules are split per column and may have only a header rule (extent from aligned rows);
  `find_tables` also invents grids from aligned text, so require real ruling lines.
- Raster figures export as PNG rendered from the page (SVG loses soft masks: transparency turns black).
- MuPDF's SVG reader mis-draws some valid SVGs: judge crops in a browser (audit does).
- A label 10–14 pt from its drawing: absorb only if isolated, and never at the cost of covering prose.
- One small drawing per bullet (interval number lines): thin drawings beside different prose lines do not merge, and
  a small figure beside a line is emitted after that line (its labels start above it).

Process
- `rm -rf site/figs` before a full rebuild (crop numbering shifts). Rerun the gate on Book of Proof and the Manning
  chapter after any converter change: most fixes here first broke the other book.
- Windows: `PYTHONIOENCODING=utf-8`; write regex code with an editor, not a shell heredoc.
