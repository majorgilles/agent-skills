# Scanned books

`tools/ocr.py run` renders every image-only page (`--all`: every page) at 300 dpi, runs Tesseract (`--lang`, default
`eng`; install more `tesseract-data-*` for other languages), keeps each word's box and confidence in
`work/ocr/pNNNN.json`, finds **non-text ink** (ink left after blanking the words: figures, unreadable formulas), then
runs `resolve`, `review` and `build` below. `build` writes `work/Main.ocr.pdf`: the scan plus an invisible text layer
(Noto Sans; Noto Sans Math for characters it lacks) written word by word on Tesseract's line baselines, so layout
analysis, verify and audit work unchanged. Crops of scanned pages are PNG renders of the scan.

A PDF that already has an OCR layer (often ABBYY FineReader): copy it to `work/Original.pdf` before stripping its text
into `work/Main.pdf`. It becomes the **reference**, a second independent engine.

## The vote (`ocr.py resolve`)

Doubtful words: Tesseract confidence under 85, a word the rest of the book never uses, or a word the reference reads
differently. Each gets votes from independent readers:

1. Tesseract and the reference layer.
2. A model (`--model`, default `sonnet`) that sees only the word's image, framed in red on its line
   (`work/ocr/words/`), never the OCR text, through `claude -p` with no tools. Batches of 40, `--jobs` in parallel.
3. If still open, a second model (`--model2`, default `opus`), also blind.

A reading wins with 2+ votes and more than any other (compared without spaces and typographic variants), so one
model never decides alone. Model spellings win ties of form (real `−`, `√`, `π`). Reads are cached in
`work/ocr/reads/<model>.json`: a rerun only reads what is missing, and `--pages A-B` tries a range. A model may answer
"no text" (speck) or "unsure" (no vote). It also flags formulas: a Tesseract line with a formula and no prose word
(3+ letters other than sin, log…) leaves the text layer and its box becomes a figure region, shown as an exact image.

`work/ocr/resolved.json` keeps every vote. Measured on Lang's *Basic Mathematics* (495 pages, ABBYY reference):
23,593 doubtful words; 6,748 confirmed, 4,102 corrected, 3,399 formula lines turned into images, 297 specks dropped,
590 left for review (the review page used to list 19,711). Models: $7 sonnet + $8 opus, about 25 minutes at `--jobs 8`.

## Review (`ocr.py review`)

`work/ocr/review.html` lists only the open words: image, each reading as a button, an input, a remaining count;
choices persist in the browser. "[formula]" shows that word's ink as an image, "no text" drops it. Download
`corrections.json`, then `ocr.py build --corrections work/ocr/corrections.json`.

After that the gate guarantees the HTML equals the resolved, reviewed text layer exactly, and that every non-text
ink region is shown (audit "scan ink"). Still unverified: words all readers misread the same way, and formula
fragments inside prose lines kept as their plain-text reading (x2 for x²).
