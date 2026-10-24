---
name: implement-product-task-slices
description: Implement a product task from a Notion ticket ID as a series of incremental vertical slices, each on its own branch and PR. Reads the task, breaks todos into tracer-bullet slices, gets user approval on the breakdown, then implements and ships each slice via /super-commit. Requires the notionMCP MCP server. Use when user says "implement this ticket as slices", "ship GEN-1234 incrementally", "vertical slices for this ticket", or "implement product task with slices". Do NOT use when the user wants a single end-to-end PR (use /implement-product-task instead). Do NOT use for analysis only (use /analyze-notion-ticket instead).
---

# Implement a Product Task as Vertical Slices

**Input**: a Notion ticket ID (e.g., `GEN-11619`), passed as an argument.

Instead of implementing the whole ticket end-to-end on a single branch/PR, ship a series of thin **vertical slices** — each one a tracer bullet that cuts through all integration layers (schema, API, UI, tests) and is independently demoable. Each slice is its own branch and its own PR.

## Instructions

### Step 1: Read the task

Fetch the Notion ticket using `mcp__notionMCP__notion-fetch` and read the contents of the task and all of the todos.

### Step 2: Update status

Update the ticket status to `In Progress` if not already done, using `mcp__notionMCP__notion-update-page`.

### Step 3: Draft vertical slices

Group the todos into **tracer-bullet slices**. Each slice must:

- Deliver a narrow but COMPLETE path through every relevant layer (schema, API, UI, tests)
- Be demoable or verifiable on its own once merged
- Be independently shippable — a teammate could merge slice 1 without slice 2 existing
- Prefer many thin slices over few thick ones

A slice is NOT a horizontal layer (e.g. "all schema changes", "all UI changes"). It's a thin end-to-end behavior.

Slices may be **HITL** (require human interaction — design review, architectural decision) or **AFK** (can be implemented and merged without human checkpoints). Prefer AFK where possible.

### Step 4: Quiz the user on the breakdown

Present the proposed slices as a numbered list. For each:

- **Title**: short descriptive name
- **Type**: HITL / AFK
- **Branch name**: suggested branch (e.g. `<ticket-id>-<slice-slug>`)
- **Blocked by**: which earlier slices must merge first (if any)
- **Notion todos covered**: which todos from the ticket this slice closes
- **What ships**: one-line description of the demoable outcome

Then ask:

- Does the granularity feel right? (too coarse / too fine)
- Are the dependency relationships correct?
- Should any slices be merged or split further?
- Are HITL/AFK markers correct?

Iterate until the user approves the breakdown. Do NOT begin implementation before approval.

### Step 5: Implement slices one at a time

For each approved slice, in dependency order:

1. **Create a branch** for the slice from the appropriate base (usually `main`, or the previous slice's branch if stacked).
2. **Implement the slice** end-to-end. Touch every layer the slice needs — do not defer "the UI part" or "the tests part" to a later slice.
3. **Tick the Notion todos** that this slice closes (update `- [ ]` → `- [x]` for the todos listed under "Notion todos covered" using `mcp__notionMCP__notion-update-page`). Leave todos that belong to future slices unchecked.
4. **Ship the slice**: invoke `/super-commit` with the ticket ID to commit, open the PR, and notify Slack. The PR title should make clear this is a slice (e.g. `[GEN-11619] slice 2/5: <slice title>`).
5. **Checkpoint with the user** before starting the next slice:
   - For AFK slices: confirm the PR opened cleanly and ask whether to proceed to the next slice immediately or wait for review/merge.
   - For HITL slices: stop and wait for the user to drive the human checkpoint (design review, decision) before continuing.
6. **Return to step 1** for the next slice. If the previous slice has not yet merged and the next slice depends on it, branch off the previous slice's branch (stacked PR) rather than `main`.

### Step 6: Final status update

Once every slice is shipped and all Notion todos are checked, update the ticket status to `To review`.

## Common Issues

### Notion fetch fails
**Cause:** Invalid ticket ID, permissions issue, or too many hanging MCP processes.
**Solution:** Verify the ticket ID format (e.g., `GEN-12345`). If MCP is unresponsive, kill hanging processes (`pkill -f notionMCP`) and ask the user to reconnect via `/mcp` and log in through the browser popup.

### Notion update fails
**Cause:** Status property value mismatch.
**Solution:** Use exact status values: `In Progress`, `To review`.

### A slice turns out not to be a true vertical slice
**Cause:** While implementing, you discover the slice cannot ship without changes that belong to a "later" slice — i.e. the slices weren't actually independent.
**Solution:** Stop. Re-quiz the user on the breakdown (back to Step 4) with a revised slice plan rather than secretly widening the current slice.

### Stacked PR base is wrong
**Cause:** Next slice was branched off `main` but depends on an unmerged earlier slice.
**Solution:** Rebase the new branch onto the earlier slice's branch and update the PR base in GitHub before pushing further commits.

### User wants to abandon the slices approach mid-ticket
**Cause:** Slicing is producing more overhead than value for this particular ticket.
**Solution:** Stop opening new slice PRs. Ask whether to (a) finish remaining work as one consolidated PR via `/implement-product-task`, or (b) close out the already-shipped slices and continue manually.
