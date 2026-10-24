---
name: pdf-book-to-study-site
description: Turn a PDF textbook (math or coding) into a verbatim, readable HTML study site with exact figures, real math, runnable Python/JavaScript code, themes and text size, Khan-style mastery tracking and automatic exercise checking via the reader's own LLM key plus real code execution. Openly licensed books can be published on GitHub Pages; books the user has purchased are built as a private personal study copy (local or access-controlled hosting). Use when the user wants to "convert this PDF book into a website", "make an interactive/HTML version of a textbook with progress tracking", or "reproduce a book like the Book of Proof site".
---

# PDF book → verbatim study site

Reference build: Book of Proof (Hammack), repo `majorgilles/book-of-proof`, 380 pages, 846 exercises, 420 solutions.
`scripts/` and `assets/` are that working pipeline; the constants marked below are book-specific and must be adapted.

## Non-negotiables

1. **Pick the mode from the copyright page** (`survey.py` prints it). Keep wording verbatim in both modes; skip the
   printed contents and index (navigation apparatus); convert everything else.
   - **Open license** that allows redistribution (CC BY, CC BY-NC-ND, …): public GitHub Pages is fine. Footer
     (`build.py` `LICENSE`) credits the author, links the license, says "unmodified format conversion, not affiliated".
   - **Purchased / all rights reserved: personal study copy.** Everything stays private:
     - The **repo must be private** (`content/` and `site/` hold the book's full text).
     - The **site must be access-controlled**. GitHub Pages from a private repo is *still public* on GitHub
       Free/Pro, so don't use it. Use one of: local (`python -m http.server -d site`, or open via a local
       static server); **Cloudflare Pages + Cloudflare Access** (free for small teams, email/Google login);
       GitHub Enterprise Cloud private Pages; any host behind authentication. Never produce a public URL.
     - Footer: "Personal study copy of <title>, © <holder>. Not for distribution."
     - Only **DRM-free** PDFs the user legitimately has. Do not help remove DRM or obtain the book elsewhere.
     - If the user asks to make a purchased book public or share it, explain it would need the rights holder's
       permission and don't publish.
2. **The book's text never passes through a model.** A subagent asked to retype a chapter refused, and was right to:
   prose must flow from the PDF text layer through the deterministic converter. Models only transcribe short
   *formula snippets* (step 6), each machine-checked against the PDF.
3. **Verify, don't eyeball.** `verify.py` compares every prose word with the PDF. Screenshots (`shot.py`) catch layout.

## Layout

```
<repo>/tools/      layout.py convert.py verify.py crops.py build.py convert_all.sh build_all.sh
<repo>/content/    one HTML fragment per chapter (+ solutions.html), generated
<repo>/site/       assets/{app.js,style.css}, figs/, generated pages   <- GitHub Pages serves this
<repo>/work/       Main.pdf, crops/, latex/, vocab.json               <- gitignored
<repo>/.github/workflows/pages.yml
```
Copy `scripts/*.py|sh` → `tools/`, `assets/app.js|style.css` → `site/assets/`, `assets/pages.yml` → workflow.
Python needs `pymupdf`. Screenshots/e2e need Playwright (any env that has it, e.g. `uv tool` notebooklm-py's python).

## Steps

0. **Ask where to publish — before any work** (AskUserQuestion), after reading the copyright page (`survey.py`):
   - **Cloudflare Pages + Cloudflare Access (private)** — login-protected, reachable from any device; private GitHub
     repo as source/backup. Default for purchased or "personal use only" books.
   - **Local only** — `python -m http.server -d site`; private GitHub repo as backup.
   - **Public GitHub Pages + bookshelf** — offer only if the license allows redistribution (open license).
   If the user asks for public hosting of a book whose terms forbid redistribution, say so in one line and offer the
   two private options; don't publish it publicly. Record the choice; step 7 follows it.
1. **Survey**: `python tools/survey.py work/Main.pdf` → license, fonts + glyph inventories, body margin per page
   parity, bold heading patterns (exercise/solution structure), outline page ranges.
2. **Adapt constants** (search for them):
   - `layout.py FIX`: remap custom-encoded math glyphs to Unicode. Render a glyph sheet of every non-text font's
     glyphs (clip each char bbox from the page, view the PNG) and map only what you identify with certainty; unknown
     glyphs are treated as "hard" → cropped. `NEG` + `get_texttrace()` fold zero-width U+0338 into ≠ ∉ ⊈ …
   - prose font test: `Span.prose` (`startswith('TeXGyreSchola')`); `verify.py` reuses it.
   - `TOP/BOTTOM` running-head/footer cutoffs; size thresholds (small < 8.5, titles ≥ 13, drop cap > 20).
   - `convert.py flow()`: `left = 54 if pno % 2 else 79` margins by parity (from survey).
   - heading regexes: section `^\d+\.\d+ Title` (bold, flush left), `Exercises for (Section|Chapter)`,
     solutions `^(Sections?) N.N$|^Chapter N( Exercises)?$`, labels (`LABELS`), "Case/Step/Part N." exclusions.
   - `convert_all.sh`: slug + 0-based page ranges; optional skip range (printed TOC); `solutions` slug last.
   - `build.py`: `BOOK` (title, also used in the grader prompt), `AUTHOR` (bookshelf), `BOOK_ID` (short unique slug — namespaces saved
     progress, since every book on one `<user>.github.io` shares browser storage), `LICENSE` footer text, page `order`.
   - Coding books: `MONO` (layout.py) and `CODE_LANG` (convert.py) — see "Coding books".
3. **One chapter first**: `python tools/convert.py ch01 A B` → `python tools/verify.py content/ch01.html` →
   `shot.py ch01.html out.png` (serve `site/` after `python tools/build.py`). Iterate to 0 discrepancies, then run all.
   Acceptable residue: word order inside figures/diagrams, math-font words. Anything else is a converter bug.
4. **Exercise integrity**: per block, numbers 1..max with no gaps/duplicates, and a hand count of one chapter.
   Solutions: every `data-ex` must match an exercise id (no orphans); odd-exercise counts vs solution counts per
   block, and confirm any shortfall is the book's (grep the page text), not the parser's.
5. **Math crops → LaTeX**: `python tools/crops.py export 120` (dedupes by image hash) → spawn ~7 subagents, 3 batches
   each, with the prompt below → `crops.py check` (digits, letters, blackboard letters must match the PDF both ways;
   big-operator glyphs excluded) → `crops.py apply` (also deletes crop SVGs no longer referenced).
   Expect ~35% nulls (fragments) — they stay exact SVG crops, which is fine.
6. **Build + test**: `sh tools/build_all.sh`, then all four browser tests (copy them to `work/`, run from the repo
   root): `e2e.py` (progress), `e2e_grade.py` (grading via mock LLM), `e2e_reading.py` (themes/size), and for coding
   books `e2e_code.py`. The e2e scripts target Book of Proof ids (`ch01`, section 1.6, `ex-1.1-1`): point them at an
   equivalent section/exercise of the new book.
7. **Publish** (commit without Co-Authored-By unless the user's config wants it):
   - Open license: `gh repo create <user>/<name> --public --source . --push`, then
     `gh api -X POST repos/<user>/<name>/pages -f build_type=workflow` (uses `assets/pages.yml`), then
     `gh repo edit <user>/<name> --add-topic study-book` so it appears on the user's **bookshelf**.
     Bookshelf = `assets/shelf.html` as `index.html` of the repo `<user>.github.io` (create it once; GitHub enables Pages
     for it automatically). It lists public repos tagged `study-book` that have Pages, reading each book's `book.json`
     (`build.py` writes title/id/author) and showing the reader's mastery from shared browser storage.
   - **Cloudflare warning:** wrangler 4.x `pages project create` (Pages is now part of Workers) auto-deploys the
     *current directory* publicly to `<name>.<subdomain>.workers.dev`. Never run it from the project folder. Safe order:
     deploy a placeholder `index.html` from an empty temp dir → user enables Cloudflare Access for the workers.dev URL
     (Worker → Settings → Domains & Routes) → `curl` shows a redirect to `*.cloudflareaccess.com` → only then
     `wrangler deploy --assets site`. Probe the URL after every Cloudflare command.
   - Purchased book: `gh repo create <user>/<name> --private --source . --push` (backup only; do NOT enable Pages and
     do not add `pages.yml`). Serve locally, or deploy `site/` to Cloudflare Pages (`npx wrangler pages deploy site
     --project-name <name>`) and protect the project with a Cloudflare Access application **before** sharing the URL
     with the user; verify an anonymous request is redirected to the login page.
   Auto mode may block publication steps ("Create Public Surface" / "Out-of-Place Publication"): don't work around
   it — give the user the exact `! …` command (no leading space before `!`). Later updates: rebuild, user pushes.

## Definition of done (every book, same bar as Book of Proof)

- [ ] Mode decided from the copyright page. Open license: attribution + license link footer. Purchased: private
      repo, access-controlled hosting (anonymous request gets a login page, not the book), "not for distribution" footer.
- [ ] Every chapter, front matter, conclusion and solutions converted by script (no model-typed prose).
- [ ] `verify.py`: 0 discrepancies, or only documented figure/diagram word-order residue.
- [ ] Exercise ids gap-free per block; one chapter hand-counted; solutions have no orphans.
- [ ] Math crops transcribed + `crops.py check`ed + applied; code blocks (coding books) runnable.
- [ ] Screenshots of a prose page, an exercise page, a figure-heavy page, mobile width, dark theme.
- [ ] All applicable e2e tests pass; no console errors.
- [ ] Repo pushed (public or private per mode); site reachable where intended and nowhere else; `BOOK_ID` unique
      among the user's books.

## Reader features (built into assets, nothing to adapt)

- **Themes + text size** (top of the Settings dialog): Auto (follows OS) / Light / Sepia / Dark / High contrast, and a 14–26 px slider.
  Stored in `localStorage['bop-reader-v1']`, applied by an inline `<head>` script before first paint (no flash).
  Theme = CSS tokens on `:root[data-theme=…]`; figures and math crops follow via `filter: var(--ink)`.
  Test: `e2e_reading.py`; look: `shot_theme.py <page> dark|sepia|contrast <scrollY> out.png`.
- **Progress**: Khan-style levels per section from the share of exercises graded correct (30/70/100%), manual override,
  chapter and book mastery bars, export/import JSON. Test: `e2e.py`.
- **Grading**: reader's own key, Anthropic / OpenAI / Gemini / OpenRouter / any OpenAI-compatible URL (Ollama needs
  `OLLAMA_ORIGINS`). The prompt carries the exercise, its group instruction and the book's solution when one exists;
  book name comes from the page header. Test: `e2e_grade.py` (mock LLM).

## Coding books

The converter and site handle code automatically once `MONO` (layout.py) matches the book's code font and
`CODE_LANG` (convert.py) names the language:
- Rows set entirely in a monospace font become `<pre class="code" data-lang="…">` blocks, verbatim from the text layer,
  indentation rebuilt from x offsets ÷ character width. Code inside an exercise stays inside that exercise.
- Runnable in the browser, each language in a Web Worker with a 10 s timeout (infinite loops are killed):
  **python** via Pyodide (lazy-loaded from jsDelivr, `loadPackagesFromImports` pulls numpy/pandas… on demand),
  **javascript** natively. Code blocks get "▶ Run" and are editable so readers can experiment.
- Exercises on a page with runnable code that show code or ask to write/implement/print… get a monospace editor
  (Tab = 4 spaces), "▶ Run", and "Check answer" = run first, then grade with the real stdout/stderr/error in the prompt
  (a crash or wrong output is never "correct").
- Other languages (Java, C, Rust, SQL…): blocks render but are not runnable; grading is LLM-only. To add one, add a
  `WORKERS[lang]` entry in app.js (e.g. sql.js for SQLite, a WASM toolchain) that posts `{ out, error }`.
- Mixed-language books: set `data-lang` per block (e.g. from a caption like "Listing 3.2 (Python)") instead of one
  `CODE_LANG`. Code in proportional fonts (rare) won't be detected; widen `MONO` or special-case the font.
- Verify: `make_codetest_pdf.py` → `BOOK_PDF=work/codetest.pdf python tools/convert.py codetest 0 0` →
  `e2e_code.py` (block prints 14, JS block, editor, 27, infinite-loop stop, execution result reaches the grader);
  delete `content/codetest.html` afterwards. Check a real chapter's code blocks against the PDF by eye too:
  `verify.py` only covers prose, so compare `pre.code` text with the monospace spans of the same pages.

## Transcription agent prompt (step 5)

> Transcribe short math-formula images to LaTeX (format conversion of formula snippets only, no prose). Batches:
> batch_NN… in `<repo>/work/crops/` (JSON list of {id, png, text_layer}). For each item: view the PNG with Read;
> write LaTeX for exactly what it shows, no delimiters (\binom{26}{3}, \frac{3\pi}{2}, \sqrt{2}, bmatrix,
> \mathbb{Z}, \mathscr{P}, \emptyset, \lim_{x\to c}). text_layer = the PDF chars in that region (order scrambled,
> radicals/bars missing): every digit/letter must appear. If the image is not a complete self-contained formula
> (sliver, cut-off bracket, piece of a drawing) or you are unsure: null. Never guess. Write
> `<repo>/work/latex/batch_NN.json` {id: latex|null}, valid JSON, confirm it parses. Reply with counts.

## Pitfalls that cost time last run

- `get_text('rawdict')` drops zero-width glyphs (combining slash of ≠) → use `get_texttrace()`.
- Word spaces are often positional gaps, not glyphs: insert a space for gaps > 1.2 pt; keep whitespace-only spans.
- Row building: define rows from normal-size baselines only, then attach scripts/fraction parts by nearest baseline,
  big delimiters by overlap, radicals to the row *below* (their glyph box sits above the ink).
- Each fraction/radical bar belongs to exactly one row (nearest row center) or it gets cropped twice.
- PyMuPDF: `b |= r` inside `for b in boxes` doesn't update the list; zero-height rects vanish in unions (pad them).
- Figure detection: exclude full-width rules and short flat strokes (fraction bars); a drawn frame with > 40 prose
  chars inside is a box around text, not a figure; small drawings inside a text line become inline crops.
- Columns in two-column exercise/solution lists must be margin-relative, or page turns attach lines to the wrong item.
- Line-end hyphens: rejoin using the book's own vocabulary (`layout.rejoin`); handle a hyphen before closing tags;
  a line ending in a word hyphen never ends a paragraph.
- Drop caps: own row, glued to the next line; the next ~2 lines are indented (not displays).
- Windows: `PYTHONIOENCODING=utf-8`; the Bash tool mangles backslashes in heredocs → write regex code with Write/Edit.
- Always `rm -rf site/figs` before a full rebuild (crop numbering shifts; never publish stale files).
- Add math font fallbacks (Cambria Math, STIX Two Math, Segoe UI Symbol, Noto Sans Math) for ℕℤℚℝ.
