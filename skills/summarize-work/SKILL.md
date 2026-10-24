---
name: summarize-work
description: Summarize all the work the user did through Claude Code on one day, across every session and repo, as grouped bullet points. Use when the user asks "what did I do today/yesterday", "summarize my work", "recap my sessions", "daily recap", "sum up yesterday for my standup", "standup notes", or "/summarize-work [date]".
---

# Summarize work

This skill reads the local Claude Code transcripts of one day and turns them into a short list of what the user did. The transcripts are in `~/.claude/projects/<folder>/<session-id>.jsonl`, one file per session.

## 1. Find the day

- No date, "yesterday", or a standup: use the previous working day. On a Monday, that is the Friday before.
- "today": use today's date.
- A date: use it as `YYYY-MM-DD`.

The day is the local calendar day, not the UTC day. If the previous working day has no session, say so and use the last day that has one.

## 2. Collect the sessions

Run:

```bash
~/.claude/skills/summarize-work/summarize_work.sh <YYYY-MM-DD>
```

For each session with prompts on that day, the script prints:
- the folder (the repo or the worktree), the session id, the prompt count and the time span;
- the first 12 prompts (`$ ...` is a shell command the user ran with `!`);
- the PR links and the ticket ids (`GEN-`, `INIT-`) in the prompts and the replies;
- the end of the last reply.

If a session has more than 12 prompts, or its result is not clear, read more of its transcript with `jq`. Only read the entries of that day.

## 3. Check the outcomes

For each PR link, get its real state:

```bash
gh pr view <number> -R <owner>/<repo> --json number,title,state -q '"#\(.number) \(.state) \(.title)"'
```

The transcript shows what a session said. `gh` shows what is true now. If they differ, use `gh`.

## 4. List the releases

Always do this step, also when no session mentions a release. Run:

```bash
~/.claude/skills/summarize-work/list_releases.sh <YYYY-MM-DD> <owner/repo> [<owner/repo> ...]
```

Pass every GitHub repo that a session of the day worked in. A session folder that is a git checkout gives its repo with `gh repo view --json nameWithOwner -q .nameWithOwner`. The script prints only the releases of that day that contain the user's own commits, and only those commits. It finds them by the author's GitHub login. Tags released together, such as `common-v*` with `backend-v*`, appear once.

## 5. Write the summary

The summary is what the user reads out at the standup. Start with one bold line: the weekday, the date, the number of sessions, and the time span. Example: **Monday 19 October 2026: 12 sessions, 09:10 to 18:04**.

Group the bullets under these headings, in this order. Leave out a heading that has no item.

1. **Released**: one sub-list for each release from step 4, in time order, with its tag and local time. List only the user's commits. Do not list the work of other people. For each commit, give the PR number, the ticket id, and the effect in one plain sentence. Add what the user did on it that day, such as review comments answered or a test fixed.
2. **Merged, not yet released**: the user's merged PRs that no release of the day contains. Say when they merged if that was after the day.
3. **Open PRs**: PRs that are still open, with what they change.
4. **Production**: scripts run in prod, repricings, backfills, retries, alert triage. Give the counts: how many rows or vehicles, how many failed.
5. **Specifications**: work on tickets, acceptance criteria, flow maps and pages.
6. **Investigations**: what was investigated and the cause found, or "cause not found".
7. **Tooling**: editor, local setup, skills and scripts. Group the small items in one bullet.
8. **Still waiting on you**: a numbered list of the next steps that the sessions left open. Put the decision with the largest impact first, with its numbers. Check each item against `gh` or the repo first: leave out what is already done.

Rules:
- Stay short enough to read out in two minutes: one or two sentences per bullet.
- One bullet for each piece of work, not for each session. Merge two sessions that worked on the same ticket.
- Only write facts that are in the transcripts or in `gh`. Do not guess an outcome.
- If a session ended on an error or with no answer, say so at the end.
- Leave out the user's swearing and jokes. Keep the work.
- Use Simplified Technical English: short sentences, active voice, one idea per sentence.

Give the summary in the chat. Do not write a file unless the user asks for one.
