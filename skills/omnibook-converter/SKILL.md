---
name: omnibook-converter
description: Convert a PDF book (text or scanned) into a verbatim, audited .omnibook package for Gilles's Omnibook Reader, word by word and figure by figure, with exercises, solutions, code listings and math. Use when the user wants to turn a PDF textbook into a readable/studyable book, add a book to the Omnibook reader, OCR a scanned book, or check a conversion's accuracy.
---

# Omnibook converter: PDF book → verbatim .omnibook package

The skill is the **converter**; reading happens in the reader app (`~/dev/omarchy_apps/omnibook_reader`, the
**Omnibook Reader**: fonts, themes, bookmarks, highlights and notes, search, exercise checking with the reader's own
LLM key, proof maps, Google Drive sync). Output: `dist/<id>.omnibook`, one zip per book (format in `scripts/package.py`).

Reference builds: Book of Proof (open license, 380 pages, 846 exercises) and a Manning MEAP chapter
(`assets/profiles/manning-meap.json`): both pass the gate.

## Non-negotiables

1. **Verbatim.** Prose flows from the PDF text layer (or the resolved OCR layer) through the deterministic converter.
   Models never write the book's prose: they only transcribe short formula crops (step 6) and cast blind votes on
   doubtful OCR words (step 2), each checked against independent readers.
2. **The gate decides.** `check_all.sh` (verify + audit) is the definition of accurate, never eyeballing.
3. **Rights.** Read the copyright page (`survey.py` prints it). A purchased book is a personal study copy: the
   package stays in the user's library (local folder, their own Google Drive) and is never published or shared.
   Only DRM-free PDFs the user legitimately has; no DRM removal. An open license that allows redistribution may be
   shared with its attribution in `book.license_html`.

## Layout

```
<repo>/tools/       scripts/* (copy them)          <repo>/profile.json   book constants (bookprofile.py)
<repo>/content/     one verified HTML fragment per chapter (+ solutions.html)
<repo>/site/figs/   exact crops (SVG vector, PNG raster/scan)
<repo>/work/        Main.pdf, Main.ocr.pdf, ocr/, crops/, latex/, audit/, vocab.json   (gitignored)
<repo>/dist/        <id>.omnibook
```
Python needs `pymupdf`; audit pixel checks need Playwright + Chromium (`CHROMIUM=` picks a binary); OCR needs
`tesseract` (+ language data). A purchased book's repo is private.

## Steps

1. **Survey**: `python tools/survey.py work/Main.pdf --profile profile.json`. Done when you know the license, the
   chapter page ranges, and whether pages are scanned (it says so).
2. **Scanned pages → OCR** (skip for text PDFs): keep a PDF's existing OCR layer as `work/Original.pdf` (it votes),
   `python tools/ocr.py run` (Tesseract, then `resolve`: a vote settles doubtful words, then `review`, `build`). Only
   the words the vote left open go to the user in `work/ocr/review.html`; then `ocr.py build --corrections …`. Set
   `"pdf": "work/Main.ocr.pdf", "ocr": true, "fonts": {"prose": "^NotoSans"}`. Done when every open word was
   confirmed or corrected. Details and accuracy limits: [OCR.md](OCR.md).
3. **Profile**: fill `book.*` (id unique among the user's books, title, author, license_html, order) and check every
   key the draft guessed against the survey: running-head band, fonts, sizes, heading/exercise/caption patterns,
   code markers. Keys and how to read them: [PROFILE.md](PROFILE.md). Manning books: start from
   `assets/profiles/manning-meap.json`.
4. **One chapter first**: `python tools/convert.py ch01 A B` → `sh tools/check_all.sh`. Iterate on the profile (and,
   when a layout is new, the converter) until the chapter's line says OK. Then look at it in the reader once
   (`python tools/package.py` → add the file in the app): headings, paragraphs, lists, notes, listings, figures.
5. **All chapters**: list slugs and 0-based page ranges in `tools/convert_all.sh`, `sh tools/build_all.sh`.
6. **Math crops → LaTeX** (math books): `python tools/crops.py export 120` → transcription agents with the prompt in
   [TRANSCRIBE.md](TRANSCRIBE.md) → `crops.py check` → `crops.py apply`. Done when check reports 0 failing.
7. **Gate**: `sh tools/check_all.sh`. Done when every file is OK, or each remaining item is reviewed (its PNG in
   `work/audit/`) and recorded as residue in the repo README with page numbers (e.g. word order inside a diagram).
   Also review `words_in_crops` in each audit JSON: prose swallowed by a crop is invisible to both checks.
8. **Exercises**: per block, numbers 1..max without gaps (audit structure), one chapter hand-counted, solutions without
   orphans; a shortfall must be the book's (grep the page text), not the parser's.
9. **Package**: `python tools/package.py` → `dist/<id>.omnibook`; add it with `omnibook add dist/<id>.omnibook` (local
   library) or the reader's file picker (it then syncs to Google Drive if signed in).
   It adds the cover image and year of publication on its own (`scripts/cover.py`: the PDF's own cover page when page 1
   is a full-page image, else Open Library by title and author, kept in `work/cover.*`); check the printed result and
   set `book.year` (the edition's year) or `book.cover` (an image path or URL, or `false`) in profile.json when the
   match is a different edition.
   `python tools/cover.py dist/<id>.omnibook --image URL --year YYYY` changes the cover of a built package.
10. **Worked solutions** (every book): `python tools/solve.py dist/<id>.omnibook` adds `generated.json`, an AI-written
   worked solution per exercise that the reader shows collapsed and labelled under each exercise (read before
   answering). It never touches the book's text or its solutions; cached per exercise, so rerun it after every
   `package.py` (unchanged exercises cost nothing), before `omnibook add`. `--estimate` prices it first (about $0.003 an exercise).
   Rerun until it reports `wrote N of N` (a failed batch is retried on the next run), then grep the solutions for remarks
   such as "not included" or "I can't": they point at exercise text the conversion lost or merged (fix the conversion,
   or delete those entries from `~/.cache/omnibook/solve/<id>.json` and rerun).

## What the gate checks

- `verify.py`: every prose word in reading order, every code line, tables and exercise blocks as multisets.
- `audit.py`: every glyph outside crops is in the HTML (all fonts); every drawing and image is inside a crop or is
  known page furniture (backgrounds, rules, bullets, badges, link underlines, panels, table rules); every crop's ink
  matches the PDF as rendered by a browser; exercise numbering, solutions, listing annotations, unique ids;
  for scans, every non-text ink region is shown; **meaning marks**, counted from the PDF and not through the converter
  (a lost one reverses or changes the meaning, while the character totals can still balance):
  `negations` (every negation slash and negated glyph: ⇏ must never read ⇒) and `bars` (every bar accent P̄ "not P",
  z̄, and every drawn overline 1.8̅1̅3̅, u̅+̅v̅ outside a crop is on the same characters in the HTML).
  `untabled`: a pair of rules of one extent with lines of text between that did not become a `<table>` (printed as
  lines, columns run together: "it is not raining no deduction possible"). Review, not a failure:
  `columns_to_review` lists plain lines that share a column gap outside tables; look at each in the HTML and record
  real tables as residue or fix them. Exercise parts set in columns ((a)–(e) left, (f)–(i) right) are read in label
  order (`layout.part_columns`).
  `crops.py check` also fails a LaTeX transcription that drops or adds a negation.

When the converter meets a layout it does not know, read [PITFALLS.md](PITFALLS.md) before changing it, and rerun
the gate on the reference books after any converter change (regressions are common).
