# Course Creator Skill

Agent skill for turning a course page, playlist, blog series, syllabus, PDF/book, or hand-written outline into a structured follow-along GitHub repository.

## What it creates

- source-attributed lesson/chapter/unit index
- one GitHub issue per lesson/chapter/unit
- lesson notes and transcript/reading-guide files
- follow-along `coursework/` workspaces
- optional `uv`/Python project scaffolding
- optional starter notebooks
- validation checklist for links, issues, commits, and pushes

## Install

Clone this repository into a skill search path:

```bash
git clone https://github.com/majorgilles/course-creator.git ~/.agents/skills/course-creator
```

Restart pi, then invoke:

```text
/skill:course-creator
```

## Example prompts

```text
Create a public repo from https://karpathy.ai/zero-to-hero.html with one issue per lesson.
```

```text
Turn this PDF book into a study repo, one issue per chapter, summaries only.
```

```text
Build a follow-along repository for this blog series and create GitHub issues for each post.
```

## Notes

- The skill preserves source attribution and links back to originals.
- For YouTube transcripts, it delegates to a `yt-dlp`-based transcript workflow when available.
- For copyrighted books/articles, it defaults to summaries, reading guides, citations, and issue checklists rather than republishing full text.
