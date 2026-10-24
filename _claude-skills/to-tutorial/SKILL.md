---
name: to-tutorial
description: Write a content-driven tutorial for the current project, using git history as a hidden scaffold for the order of ideas — not as the structure the reader sees. Use when the user wants a tutorial, walkthrough, or "explain how this project came together" doc.
---

Goal: produce a tutorial that teaches the *concepts* behind the code, in an order that builds understanding. Use the commit history privately, as a research tool, to recover the order in which the author actually solved problems — but the final document must read as a content-organized teaching piece, not a changelog.

A reader should never think "this is a list of commits." They should think "this person walked me through the ideas."

## Process

1. **Read the commit history end-to-end.** `git log --reverse --oneline` for shape, then expand individual commits with `git show <hash>` when you need to know what was actually added. You're looking for the *thinking*: what problem did each commit solve? What did the author have to learn or decide?

2. **Read the current code.** The tutorial is grounded in what exists *now*, not in intermediate states. Read README, top-level config, the main source files. Cross-reference against commits so you understand which pieces were hard-won vs. obvious.

3. **Cluster commits into conceptual parts.** Many commits collapse into one teaching beat. Some single commits split into two. Reorder freely. Drop commits that are noise (typo fixes, formatting) unless they illustrate a pitfall worth teaching. The output is a list of *parts*, each with a clear concept and a "why this matters" hook.

4. **Confirm the outline with the user before writing prose.** Show the part titles and one-line summaries. Let them reorder, drop, or add. Don't write the full tutorial against a wrong skeleton.

5. **Write the tutorial.** Save as `TUTORIAL.md` at the repo root unless the user asks otherwise.

## Style rules (non-negotiable)

- **Content-driven headings.** "Part 3 — Pinning Rust nightly", not "Commit abc123: bump toolchain". Never reference commit hashes, PR numbers, or "in this commit we…".
- **Lead with the why.** Each part opens with the problem the reader would hit if this piece weren't there. Code comes after motivation, not before.
- **Show real code from the repo**, but trim it to the teaching essentials. Full files belong in the repo; the tutorial shows the lines that carry the lesson.
- **Name the surprises.** Where the author got stuck, where a magic number bit them, where the obvious approach didn't work — these are the highest-value paragraphs. Mine the commit history specifically for these (look for "fix", "revert", commits that undo previous ones, long messages).
- **Second person, conversational.** "You'll notice…", "Here's the awkward part…". Not academic. Not a README.
- **Tight prose.** No filler. If a sentence doesn't add information or motivation, cut it.
- **End with what's next.** A short "where to go from here" pointing at natural follow-on work — not a recap.

## Anti-patterns to avoid

- A part-per-commit structure (dead giveaway it's commit-driven).
- Chronological framing ("First we added X, then we added Y…"). Teach in the order that builds understanding, which is often *not* the order things were built.
- Restating what code does instead of why it exists.
- Skipping the painful bits. The pitfalls are the tutorial.
