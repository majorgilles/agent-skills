# profile.json

Only keys that differ from `scripts/bookprofile.py` DEFAULTS (Book of Proof) are needed; nested objects merge.
`survey.py --profile` drafts one. Every regex matches PDF font names or a row's plain text.

| Key | Meaning | How to find it |
|---|---|---|
| `pdf` | source PDF (`work/Main.ocr.pdf` for scans) | |
| `book.id/title/author/license_html/order` | package identity; `order` = content slugs in reading order | copyright page |
| `page.top/bottom` | running head above / footer and watermarks below (pt) | survey "running heads" |
| `page.margin_even/odd` | body left margin by 0-based page parity | survey margins |
| `fonts.prose` | body text font: verify.py checks these words in order | survey body font |
| `fonts.text` | other text fonts (headings, notes, captions); never treated as math. Never list math fonts here | survey fonts |
| `fonts.mono` | code fonts (Type3 code fonts by name, e.g. `^Type3`) | survey (fixed-width detection) |
| `fonts.bold/italic/math_italic` | style detection | |
| `fonts.fix` | custom-encoded math glyphs → Unicode, per font | glyph sheet: map only what you identify for certain |
| `fonts.extension/radical` | big-delimiter fonts and radical glyphs (placed by position, cropped when unmapped) | |
| `sizes.small/normal_min/title/dropcap/section_min` | script size, body floor, chapter titles, drop caps, section headings (pt) | survey sizes |
| `layout.para_pitch` | baseline distance (× usual line pitch) that starts a paragraph | default 1.4 |
| `layout.para_indent/display_indent/space_gap` | first-line indent, display (centred formula) indent, word-gap width | |
| `patterns.chapter_marker` / `chapter_inline` | "CHAPTER 4" row / "3 Title" on the title row | |
| `patterns.section/subsection(_min)/section_bold` | numbered headings | |
| `patterns.exercises/solutions/item_exclusions/labels/proof/proof_end` | exercise blocks, solution appendix, theorem labels | survey heading patterns |
| `patterns.figure_caption/listing_caption/table_caption/caption_bold` | captions (attached to their figure/listing/table) | |
| `patterns.callouts` | lead words of notes (NOTE, TIP, WARNING…) | |
| `patterns.code_continuation/code_annotation/annotation_text` | wrap marker (`[CA]`), end-of-line cueball (`#A`), its explanation row | Manning profile |
| `code_lang` | python / javascript run in the reader; others display only | |
| `ocr` | scanned book: figure regions come from `work/ocr/figures.json` | |
