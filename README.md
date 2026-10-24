# Agent skills

My skills for coding agents (Claude Code, Codex, pi and others that read `SKILL.md` skills). One folder per skill
in `skills/`.

| Skill | What it does |
| --- | --- |
| [`coding-tutor`](skills/coding-tutor) | Act as a hands-on coding tutor — the student types every line. You instruct and explain why; never edit or run files yourself |
| [`course-creator`](skills/course-creator) | Turn a course page, playlist, blog series, syllabus, local PDF/book, or similar learning source into a structured follow-along GitHub repository with lesson notes, transcripts/extracts when appropriate, workspaces, uv/Python scaffolding when requested, and one GitHub issue per lesson/chapter/unit |
| [`double-loop-tdd`](skills/double-loop-tdd) | Double-loop test-driven development. An outer acceptance test (BDD feature, end-to-end or API-level) states the behavior and stays red, while inner unit-test red → green cycles drive the implementation until it passes |
| [`exercise-tutor`](skills/exercise-tutor) | Act as a hands-on coding tutor who assigns exercises with the recipe spelled out — student writes every line themselves. You set the task and list the ingredients up front; never edit or run files yourself |
| [`implement-product-task-slices`](skills/implement-product-task-slices) | Implement a product task from a Notion ticket ID as a series of incremental vertical slices, each on its own branch and PR. Reads the task, breaks todos into tracer-bullet slices, gets user approval on the breakdown, then implements and ships each slice via /super-commit. Requires the notionMCP MCP server |
| [`notebook-docs`](skills/notebook-docs) | Rewrite notebook Markdown, comments, docstrings, types, and tensor-shape explanations. Optionally commit and push the checked changes |
| [`pdf-book-to-study-site`](skills/pdf-book-to-study-site) | Turn a PDF textbook (math or coding) into a verbatim, readable HTML study site with exact figures, real math, runnable Python/JavaScript code, themes and text size, Khan-style mastery tracking and automatic exercise checking via the reader's own LLM key plus real code execution. Openly licensed books can be published on GitHub Pages; books the user has purchased are built as a private personal study copy (local or access-controlled hosting) |
| [`to-issues`](skills/to-issues) | Break a plan, spec, or PRD into independently-grabbable GitHub issues using tracer-bullet vertical slices |
| [`to-prd`](skills/to-prd) | Turn the current conversation context into a PRD and submit it as a GitHub issue |
| [`to-tutorial`](skills/to-tutorial) | Write a content-driven tutorial for the current project, using git history as a hidden scaffold for the order of ideas — not as the structure the reader sees |
| [`visualize-flow`](skills/visualize-flow) | Draw a flow from the code (a lambda chain, an event flow, a cron, a sync, a use case) as one page with a core domain chart, a context map, a domain story, an EventStorming board and a BPMN diagram, all built from one flow JSON file |

## Install

```bash
git clone git@github.com:majorgilles/agent-skills.git ~/dev/agent-skills
~/dev/agent-skills/install.sh
```

`install.sh` links every skill into `~/.agents/skills` and `~/.claude/skills`, so edits in this repo apply right
away. Run it again after adding a skill. To use a single skill without cloning, copy its folder into one of those
two directories.

## History

This repo replaced the separate `claude-skills`, `course-creator`, `double-loop-tdd`, `pdf-book-to-study-site` and
`visualize-flow` repos; their commit history is kept here.
