# pdf-book-to-study-site

An agent skill (Claude Code / any agent that reads `SKILL.md`) that turns a PDF textbook into a verbatim study website:

- text copied by script from the PDF text layer (never retyped by a model), checked word-for-word against the PDF
- figures as exact vector crops; formulas as MathJax, each transcription checked against the PDF's characters
- Khan-style mastery tracking per section, chapter and book (stored in the browser, export/import)
- exercise checking with the reader's own LLM key (Anthropic, OpenAI, Gemini, OpenRouter, any OpenAI-compatible API),
  using the book's own solutions as reference
- coding books: runnable Python (Pyodide) and JavaScript blocks; code answers are executed and the output is graded
- themes (light, sepia, dark, high contrast) and text size

Example: [Book of Proof](https://majorgilles.github.io/book-of-proof/) ([source](https://github.com/majorgilles/book-of-proof)).

## Install

```sh
git clone https://github.com/majorgilles/pdf-book-to-study-site ~/.agents/skills/pdf-book-to-study-site
# Claude Code: also available if cloned into ~/.claude/skills/
```

Then ask your agent to "turn this PDF book into a study site". `SKILL.md` holds the full procedure, the constants to
adapt per book, the definition of done and the pitfalls; `scripts/` and `assets/` are the tested reference pipeline.

## Two modes

- **Openly licensed books** (e.g. Creative Commons): publish on GitHub Pages, keeping the author's attribution and
  license notice.
- **Books you bought**: a personal study copy. Keep the repo private and host the site where only you can open it
  (locally, or Cloudflare Pages behind Cloudflare Access). Note that GitHub Pages built from a private repo is still
  public on GitHub Free/Pro. Use DRM-free PDFs you legitimately own; the skill does not remove DRM.
