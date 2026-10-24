---
name: course-creator
description: Turn a course page, playlist, blog series, syllabus, local PDF/book, or similar learning source into a structured follow-along GitHub repository with lesson notes, transcripts/extracts when appropriate, workspaces, uv/Python scaffolding when requested, and one GitHub issue per lesson/chapter/unit. Use when the user asks to create a course repo, curriculum tracker, study project, lesson issues, or split learning material into actionable work items.
---

# Course Creator

Create a durable, follow-along course repository from one or more learning sources.

The skill accepts input such as:

- A course/syllabus URL, e.g. a page listing lessons and videos.
- A YouTube playlist or individual lesson links.
- A series of blog posts or article URLs.
- A local PDF/book/DOCX/PPTX file to parse and split into chapters or sections.
- A hand-written outline pasted by the user.

The default output is a GitHub repository with a clean learning structure and one GitHub issue per lesson/chapter/unit.

## Key principles

- Preserve source attribution and link back to originals.
- Prefer one issue per independently followable lesson/chapter/unit.
- Make every issue actionable: source links, summary, workspace link, and checklist.
- Keep copyrighted books/articles safe: create summaries, reading guides, notes, and citations; do not publish full copyrighted text unless the user confirms they own it or it is licensed for redistribution.
- Ask before creating or changing a remote GitHub repo unless the user has clearly requested it.
- Do not download full video/audio for speech-to-text unless the user explicitly approves that fallback.

## Minimal clarification questions

If any of these are missing and cannot be inferred, ask briefly before mutating state:

1. Repository target: new repo name or existing repo?
2. Visibility: public or private?
3. Granularity: one issue per lesson/post/chapter, or another unit?
4. Transcript/excerpt policy: store full transcripts/extracts, summaries only, or links only?
5. Coding environment: plain repo, Python/uv, JavaScript, notebooks, or no code?

If the user already specified enough, proceed without extra questions.

## Source ingestion

### Course or syllabus URL

1. Fetch the page with `fetch_content`.
2. If the extracted content omits links or structure, inspect the raw HTML with `bash`/Python or use `web_search` for corroborating sources.
3. Extract lesson units with:
   - number/order
   - title
   - URL
   - duration/pages/date if available
   - description

### YouTube videos or playlists

1. Extract video IDs locally.
2. For transcripts, load and follow the `youtube-transcript-fallback` skill, which uses `yt-dlp` subtitle extraction.
3. Store transcript text only when available and permitted.
4. Mark source as manual captions or auto captions when known.
5. If captions are unavailable, state that clearly; do not run ASR without approval.

### Blog series or article list

1. Fetch each URL.
2. Extract title, author/date if available, canonical URL, and headings.
3. Default granularity: one issue/workspace per post.
4. For long posts, optionally split by top-level headings if the user wants finer-grained work.
5. Store short summaries and reading notes; avoid copying full article bodies unless the license permits it.

### PDF/book/local documents

1. Load the `parse-document` skill when available.
2. Use `document_parse` for text/JSON extraction.
3. Use `document_search` for known phrases, TOC entries, citations, or page locations.
4. Use `document_screenshot` only when layout, figures, equations, or tables matter.
5. Split in this order of preference:
   - table of contents chapters
   - explicit headings
   - sections/subsections
   - page ranges only when structure is unavailable
6. For each unit, record page ranges and citation anchors.
7. Do not publish full book text by default. Publish a reading guide, summary, issue checklist, and maybe short quoted snippets if fair-use/permission is clear.

## Normalized unit schema

Convert every source item into a normalized unit before generating files/issues:

```yaml
number: "01"
slug: "short-kebab-slug"
title: "Lesson or chapter title"
source_url: "https://..."        # optional for local docs
source_path: "path/to/book.pdf"  # optional for local docs
pages: "12-34"                  # optional for books/PDFs
duration: "1h15m"               # optional for videos
summary:
  - "Key point 1"
  - "Key point 2"
deliverables:
  - "Concrete follow-along artifact"
  - "Exercise/check/output"
workspace: "coursework/01-short-kebab-slug"
notes_file: "lessons/01-short-kebab-slug.md"
transcript_or_reading_file: "video_transcripts/01-short-kebab-slug.md"
```

## Recommended repository structure

Use this structure unless the user asks otherwise:

```text
.
├── README.md
├── pyproject.toml              # if Python/uv project requested
├── uv.lock                     # if Python/uv project requested
├── .python-version             # if Python/uv project requested
├── .gitignore
├── lessons/                    # lightweight lesson/chapter note files
├── video_transcripts/          # video transcripts, if allowed/available
├── readings/                   # PDF/book/blog reading guides, summaries, citations
├── coursework/
│   ├── README.md
│   └── <nn-slug>/
│       ├── README.md
│       ├── notebooks/
│       ├── src/
│       ├── tests/
│       └── artifacts/
├── data/
│   ├── README.md
│   ├── raw/
│   ├── processed/
│   └── external/
└── artifacts/
    ├── README.md
    ├── figures/
    ├── samples/
    └── metrics/
```

For empty directories, add `.gitkeep`.

## Python/uv setup

When the course is code-heavy or the user requests Python/ML notebooks, create a uv project:

```toml
[project]
name = "<repo-name>"
version = "0.1.0"
description = "Follow-along repository for <course/title>."
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = ["ruff>=0.12"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["B", "E", "F", "I", "UP"]
```

Add dependencies requested by the user, e.g. `numpy`, `pandas`, `seaborn`, `torch`, `jupyter`, etc. Run `uv lock` or `uv sync` when appropriate.

## File templates

### Root README.md

Include:

- course title and attribution
- source links
- repo purpose
- setup commands
- lesson table with video/source, notes, transcript/reading guide, workspace, and issue links
- repository layout

### Lesson note

```markdown
# Lesson NN — Title

> ## Lesson link
> [Open source](SOURCE_URL)

- **Duration/pages:** ...
- **Course/book:** ...
- **Transcript/reading guide:** ../...
- **Workspace:** ../coursework/NN-slug/
- **GitHub issue:** #NN

## Focus

Short description.

## Learning checkpoint

What the learner should be able to do after this unit.
```

### Workspace README

```markdown
# Issue #NN — Title

- **GitHub issue:** https://github.com/OWNER/REPO/issues/NN
- **Source:** ...
- **Lesson notes:** ...
- **Transcript/reading guide:** ...

## Goal

One durable goal.

## Starter notebook

- `notebooks/NN-slug.ipynb`  # if notebooks are used

## Folder contract

- `notebooks/` — exploratory follow-along work.
- `src/` — cleaned code worth keeping.
- `tests/` — small checks and reproducibility tests.
- `artifacts/` — plots, samples, metrics, screenshots.

## Deliverables

- [ ] ...
```

### Starter notebook

If the user asks for notebooks, create one notebook per unit with exactly one intro Markdown cell unless more is requested. Include issue, source, notes, transcript/reading-guide, and workspace guidance.

### GitHub issue body

```markdown
## Source

SOURCE_URL or local document citation/page range

## Lesson note

[`lessons/NN-slug.md`](LINK)

## Transcript / reading guide

[`video_transcripts/NN-slug.md` or `readings/NN-slug.md`](LINK)

## Workspace

[`coursework/NN-slug/`](LINK)

## Summary

- Key point 1
- Key point 2
- Key point 3

## Deliverables

- [ ] Follow/watch/read the unit
- [ ] Work through examples in the workspace
- [ ] Move stable code to `src/`
- [ ] Add checks/tests for important behavior
- [ ] Save representative outputs in `artifacts/`
- [ ] Update notes with takeaways and gotchas
```

## GitHub workflow

1. Check current repo state:

   ```bash
   git status --short --branch || true
   gh auth status || true
   ```

2. If creating a new repo:

   ```bash
   git init
   git branch -M main
   gh repo create <name> --public|--private --source=. --remote=origin --push --description "..."
   ```

3. If using an existing repo, verify remote:

   ```bash
   git remote -v
   gh repo view --json name,visibility,url
   ```

4. Create or update issues:

   - Prefer `gh issue list --state all` first to avoid duplicates.
   - Use `gh issue create` for new unit issues.
   - Use `gh issue edit --body-file` to enrich existing issues.
   - Create issues in course order.

5. Commit and push after filesystem changes:

   ```bash
   git add .
   git commit -m "Create follow-along course structure"
   git push
   ```

## Validation checklist

Before reporting done:

- [ ] Root README links resolve locally.
- [ ] Every unit has a notes file.
- [ ] Every unit has a workspace folder.
- [ ] Every unit has a transcript, reading guide, or explicit unavailable note.
- [ ] Every issue links to source, notes, transcript/reading guide, and workspace.
- [ ] GitHub issues are in the intended granularity and order.
- [ ] `git status --short --branch` is clean after push.
- [ ] Mention any source limitations, gated transcripts, missing captions, or copyright constraints.

## Common task recipes

### "Make a public repo, one issue per lesson"

- Fetch source page.
- Extract lessons.
- Create root README, `lessons/`, and `coursework/`.
- Initialize git and create public GitHub repo.
- Create one GitHub issue per lesson.
- Push.

### "Add transcripts"

- For YouTube, use `yt-dlp` via `youtube-transcript-fallback`.
- Store under `video_transcripts/` if permitted.
- Update transcript index and each issue body.

### "Turn a PDF book into a study repo"

- Parse the PDF.
- Extract table of contents and page ranges.
- Create `readings/NN-chapter.md` summaries instead of full text by default.
- Create one issue/workspace per chapter or major section.
- Include citations/page ranges in issue bodies.
