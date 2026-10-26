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
| [`omnibook-converter`](skills/omnibook-converter) | Convert a PDF book (text or scanned, with OCR) into a verbatim, audited `.omnibook` package for Gilles's Omnibook Reader (`omarchy-apps/omnibook_reader`): every word, character, drawing and figure pixel accounted for |
| [`simplified-technical-english`](skills/simplified-technical-english) | Rewrite text in ASD-STE100 Simplified Technical English: a chat answer, a Notion page, a Slack message, a GitHub PR or issue, or a doc file |
| [`summarize-work`](skills/summarize-work) | Summarize the work done through Claude Code on one day, across every session and repo, as standup notes: releases, PRs, production work and the next steps left open |
| [`to-tutorial`](skills/to-tutorial) | Write a content-driven tutorial for the current project, using git history as a hidden scaffold for the order of ideas — not as the structure the reader sees |
| [`trace-flow`](skills/trace-flow) | Trace an architectural flow hop by hop, with the trigger of every hop (emitter and route) proven by a `file:line` in the code |
| [`visualize-flow`](skills/visualize-flow) | Draw a flow from the code (a lambda chain, an event flow, a cron, a sync, a use case) as one page with a core domain chart, a context map, a domain story, an EventStorming board and a BPMN diagram, all built from one flow JSON file |
| [`work-on-extension`](skills/work-on-extension) | Create or update a pi extension from a prompt: implement and test it, work on a branch, bump the version, update the README, and open a PR |

## Install

```bash
git clone git@github.com:majorgilles/agent-skills.git ~/dev/agent-skills
~/dev/agent-skills/install.sh
```

`install.sh` links every skill into `~/.agents/skills`, `~/.claude/skills` and, when pi is installed,
`~/.pi/agent/skills`, so edits in this repo apply right away. It also turns on the repo's git hooks in `.githooks/`,
so every later `git pull` runs `install.sh` again by itself. Run it by hand after adding a skill locally. To use a
single skill without cloning, copy its folder into one of those directories.

## History

This repo replaced the separate `claude-skills`, `course-creator`, `double-loop-tdd`, `pdf-book-to-study-site` and
`visualize-flow` repos; their commit history is kept here.
