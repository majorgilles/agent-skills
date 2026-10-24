---
name: notebook-docs
description: Rewrite notebook Markdown, comments, docstrings, types, and tensor-shape explanations. Optionally commit and push the checked changes.
disable-model-invocation: true
---

# Notebook documentation

Use this skill to document newly added code or revise existing notebook documentation.

Examples:

- `/skill:notebook-docs` — document new code in the modified notebook.
- `/skill:notebook-docs notebooks/chapter.ipynb` — document the selected notebook.
- `/skill:notebook-docs all` — revise documentation in all project notebooks.
- `/skill:notebook-docs push` — document new code, validate it, commit, and push.
- `/skill:notebook-docs notebooks/chapter.ipynb push` — select a notebook and push.

## Select the work

1. Read the applicable `AGENTS.md` files and the project's `glossary.md`.
2. Run `git status --short`. Inspect the latest notebook contents and diff.
   Read them again on each invocation; the user may have added code since the last run.
3. Use the requested path or scope. Without a path, select the modified notebook if there
   is exactly one. If several notebooks have new code and the target is unclear, ask which one.
4. Record the existing cell IDs, outputs, execution counts, and metadata before editing.
   Inspect imported definitions when their behavior or tensor shapes are unclear.

## Rewrite the documentation

- Use Simplified Technical English principles: short sentences, simple words, active voice,
  and direct instructions. Preserve precise technical terms and identifiers.
- Follow the project's glossary. Add definitions for new terms when needed.
- Place a Markdown cell before each new concept. State its purpose, inputs, outputs,
  expected shapes, and assumptions. Keep distinct concepts in separate cells.
- Use sentence-case headings and short paragraphs. Use fenced blocks only for code or commands.
- Add precise Python annotations to parameters, return values, and important variables.
  Prefer built-in generics and stable library types. Use `Any` only at an untyped third-party
  boundary when no useful type is available.
- Use Google-style docstrings with `Args:`, `Returns:` or `Yields:`, and `Raises:` as applicable.
  Document actual exceptions and existing behavior rather than a proposed implementation.
- Write concise comments that explain intent, indexing, or non-obvious operations.
- Keep Python lines within the project's limit, or 100 characters if no limit is specified.
- Keep the notebook as one continuous chapter. Move and update its single final summary
  after new cells. Correct older statements made obsolete by those cells.
- Describe saved results as observations. Separate mathematical correctness from model output.
  Explain limits without inventing causes, measurements, or results.

## Explain tensor shapes

Use the project's glossary as the source of truth. If it has no shape conventions, establish:

- `batch_size`: number of sequences.
- `sequence_length`: number of token positions.
- `d_model`: embedding or hidden-state width.
- `vocab_size`: number of vocabulary entries.

Use these common shapes:

- Token IDs: `(batch_size, sequence_length)`.
- Hidden states: `(batch_size, sequence_length, d_model)`.
- Full logits: `(batch_size, sequence_length, vocab_size)`.
- Next-token logits: `(batch_size, vocab_size)`.
- One generated token: `(batch_size, 1)`.
- Unbatched vocabulary vector: `(vocab_size,)`.
- Scalar tensor: `()`.

State concrete values separately, such as `batch_size = 1`. Explain when indexing removes
an axis and when slicing preserves it. A vocabulary slice is not a sequence axis.
Use `d_k`, `d_v`, and `d_ff` for attention dimensions when relevant. Distinguish the paper's
notation from project-specific names. Preserve executable identifiers even if an older name
remains in code; use canonical dimension names in its explanation.

## Preserve behavior

- Keep algorithms, prompts, seeds, thresholds, device choices, imports, and call order unchanged.
- Preserve saved outputs, execution metadata, and existing cell IDs. Add unique IDs to new cells.
- Annotations and documentation do not authorize unrelated bug fixes. If a validation rule
  or behavior change is needed, explain it and obtain authorization before implementing it.
- Document quirks accurately. For example, a top-p fallback is not strict input validation.
- Treat notebooks as the source of truth for reusable code. Follow the project's export setup.
  Run `uv run nbdev-export` when exported definitions or their docstrings change.
  Edit generated package modules only through notebook exports.

## Validate before completion

1. Validate notebook JSON and schema. Check unique cell IDs.
2. Parse all Python code cells. Account for notebook magics when present.
3. Run the project's lint and format checks for the modified notebooks.
4. Check that prose, types, shapes, and executable code agree.
5. Compare outputs and metadata with the recorded originals. Check that runtime code changed
   only where annotations or an explicitly authorized correction required it.
6. Run small helper smoke tests where practical. Use a toy model or tensor rather than loading
   large weights. Do not rerun expensive inference or overwrite saved results for prose-only work.
7. State which checks passed and which could not run. Completion requires accurate documentation
   and no unexplained behavior or result changes.

## Commit and push when requested

The `push` argument or an explicit user request authorizes a normal commit and push for this work.

1. Inspect the full diff and status after validation.
2. Stage the selected notebooks, their glossary updates, and necessary generated exports.
   Include user-added code in those notebooks. Keep unrelated changes unstaged.
3. Commit with a concise description. Push the current branch to its configured remote.
   If the remote or branch is unclear, ask before choosing one. Use a normal push, not force.
4. Check the final status. Report the commit ID, remote branch, checks, and remaining changes.

Without a push request, leave the edits local and say that they were not committed or pushed.
