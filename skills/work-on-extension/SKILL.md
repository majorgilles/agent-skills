---
name: work-on-extension
description: Create or update a pi extension from a user prompt, implement and test it, set up git if needed, work on a dedicated branch, bump package.json, update README.md, commit/push, and open a GitHub PR for review. Use when the user asks to build, modify, package, or PR a pi extension; also when they say work_on_extension.
---

# Work on Extension

Build or modify a pi extension end-to-end from the user's prompt and prepare it for review as a GitHub PR.

> Naming note: pi skill names must use lowercase letters, numbers, and hyphens, so this skill is `work-on-extension` even if the user says `work_on_extension`.

## Primary outcome

At the end of this workflow, the target repo should have:

- A created or updated pi extension that implements the user's request
- A git repository if one did not already exist
- A dedicated feature branch
- An updated `package.json` version
- An updated `README.md`
- Relevant tests/checks run, with results reported
- A pushed branch and an opened GitHub PR for review, when a remote is available

## Required pi docs

Before implementing extension code, read the pi docs needed for the task:

- `C:\Users\giloz\AppData\Roaming\npm\node_modules\@earendil-works\pi-coding-agent\docs\extensions.md`
- `C:\Users\giloz\AppData\Roaming\npm\node_modules\@earendil-works\pi-coding-agent\docs\packages.md`

If the extension uses custom TUI components, themes, keybindings, SDK APIs, providers, or other specialized features, also read the linked docs referenced from those files before coding.

Use working examples from:

- `C:\Users\giloz\AppData\Roaming\npm\node_modules\@earendil-works\pi-coding-agent\examples\extensions\`

## Workflow

### 1. Understand the request

Extract from the user prompt:

- Extension purpose and user-facing behavior
- Whether this is a new extension or an update to an existing one
- Desired location/repo/package name, if provided
- Required extension capabilities: tool, command, event hook, UI, provider, autocomplete, etc.
- Acceptance criteria and test expectations

Ask a brief clarification only if the request is ambiguous enough that implementation would likely go in the wrong repo, wrong extension, or require credentials/remotes you do not have.

### 2. Inspect the workspace

Use file and git inspection commands to determine:

- Current directory and repository root (`git rev-parse --show-toplevel`)
- Existing extension files in common locations:
  - `extensions/`
  - `.pi/extensions/`
  - `~/.pi/agent/extensions/`
  - paths declared under `package.json` `pi.extensions`
- Existing `package.json`, lockfile, `tsconfig.json`, tests, lint scripts, and `README.md`
- Whether the requested extension already exists by name, package manifest, command/tool names, README mentions, or file names

If no suitable repo exists, create or use a dedicated package directory for the extension rather than scattering files in the agent working directory.

### 3. Set up git and branch

Before editing implementation files:

1. If not inside a git repo, run `git init` in the target package/repo directory.
2. Ensure `main` exists and treat it as the destination/base branch for the PR. If the repo is new, create `main` and make an initial commit with the existing scaffold before feature work when useful.
3. Create a dedicated branch from `main` with a descriptive slug, for example:
   - `feature/pi-<extension-name>` for new extensions
   - `fix/pi-<extension-name>-<short-change>` for updates/fixes
4. Do not commit unrelated dirty changes. If unrelated changes already exist, ask the user how to proceed before overwriting, staging, or committing them.

If no remote exists, you cannot open a PR yet. Ask the user for a GitHub remote URL or permission to create one with `gh repo create`, then continue.

### 4. Implement the extension

Follow pi extension conventions:

- Single-file extensions may live in `extensions/<name>.ts` or `.pi/extensions/<name>.ts`.
- Multi-file or package extensions should use a directory with `index.ts` or a package manifest declaring `pi.extensions`.
- Extension modules export a default function receiving `ExtensionAPI`.
- Runtime dependencies go in `dependencies`; pi core packages imported by extensions should be `peerDependencies` with `"*"` range when packaged (`@earendil-works/pi-coding-agent`, `@earendil-works/pi-ai`, `@earendil-works/pi-tui`, `typebox`).
- Use `typebox` schemas for tools; use `StringEnum` from `@earendil-works/pi-ai` for string enums.
- If a custom tool mutates files, use `withFileMutationQueue()` around the full read-modify-write window.
- Tools must truncate large outputs and report where full output can be found.
- In non-interactive modes, check `ctx.hasUI` before relying on dialogs or TUI-only behavior.
- Prefer small, testable helper functions for non-trivial logic.

If updating an existing extension, preserve existing behavior unless the user explicitly asks to change it.

### 5. Package metadata and version bump

Update or create `package.json` as appropriate:

- Ensure the package includes `"keywords": ["pi-package", ...]` when it is intended to be shareable.
- Ensure `pi.extensions` points to the extension entry file(s), unless conventional `extensions/` discovery is sufficient and already used.
- Bump the version exactly once per workflow:
  - Default to patch bump for implementation updates.
  - Use minor bump for new user-visible capabilities.
  - Use major bump only for breaking changes.
- Preserve existing package manager and lockfile style. Run install only when dependencies changed.

### 6. README update

Update or create `README.md` with:

- What the extension does
- Installation or local usage instructions (`pi install ...` or `pi -e ...` / local package path)
- Commands/tools/events registered by the extension
- Configuration, environment variables, and permissions/security notes
- Basic examples
- Testing/checking instructions

Keep the README accurate for the current package structure.

### 7. Validate

Run the most relevant checks available in the repo, for example:

- `npm test`
- `npm run test`
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- Direct smoke test with `pi -e <extension-path>` when practical

If a command is missing, do not invent it; report that it is not available. If a check fails, fix the implementation or clearly report the blocker.

### 8. Commit, push, and open PR

After validation:

1. Review the diff (`git status`, `git diff`).
2. Stage only relevant files.
3. Commit with a concise message, for example `feat: add <extension-name> pi extension`.
4. Push the feature branch.
5. Open a PR with `gh pr create --base main` so the destination branch is always `main`.

PR body should include:

- Summary of the extension/change
- Key files changed
- Tests/checks run and their results
- Any limitations, follow-up work, or manual review notes

If `gh` is unavailable, not authenticated, or no remote exists, provide exact next commands for the user to run, using `--base main` for PR creation.

## Output format

When finished, respond with:

- Branch name
- PR URL, or why a PR could not be opened
- Summary of implementation
- Version bump performed
- Tests/checks run
- Any caveats or follow-ups

## Safety and quality rules

- Do not overwrite unrelated user changes.
- Do not commit secrets, `.env` files, generated `node_modules`, or unrelated artifacts.
- Do not force-push unless the user explicitly requests it.
- Do not open a PR from a branch with known failing checks unless the user explicitly approves.
- Prefer minimal, maintainable extension code over large frameworks.
- Cite file paths clearly in status updates and summaries.
