---
name: double-loop-tdd
description: Double-loop test-driven development. An outer acceptance test (BDD feature, end-to-end or API-level) states the behavior and stays red, while inner unit-test red → green cycles drive the implementation until it passes. Use when the user wants to build features or fix bugs test-first, mentions "TDD", "double loop", "outside-in", "acceptance test", "BDD", "red-green-refactor", or wants integration tests.
---

# Double-Loop Test-Driven Development

Double-loop TDD runs two red → green loops, one inside the other:

- **Outer loop (acceptance):** one test that states a user-visible behavior from the spec, written first, at the outermost seam (a BDD scenario, an end-to-end or API-level test). It stays red while the feature is being built. It is cross-validation: it checks the work, it does not drive it.
- **Inner loop (unit):** plain unit tests at agreed seams, one red → green cycle at a time. These drive every line of the implementation.

The feature is done when the outer test goes green. That is the default for this skill; drop to the inner loop alone only when there is no user-visible behavior to state (a pure refactor-safe utility, say), and say so.

This skill is the reference that makes both loops produce tests worth keeping: what a good test is, where tests go, the anti-patterns, and the rules of the loops. Every section applies on every cycle — consult them before and during the loops, not after.

When exploring the codebase, read `CONTEXT.md` (if it exists) so test names and interface vocabulary match the project's domain language, and respect ADRs in the area you're touching.

## The two loops

```
write ONE failing acceptance test (outer, red) ───────────────┐
  │                                                           │
  ├─► inner: write one failing unit test at an agreed seam    │
  │     ► write only enough code to pass it (green)           │
  │     ► re-run the acceptance test: still red? loop again   │
  │                                                           │
  └─► acceptance test green ─► next acceptance test ◄─────────┘
```

1. **Pick one behavior** from the spec and write its acceptance test. A parametrized scenario (a BDD Scenario Outline with an Examples table, a table-driven test) counts as one. Run it and confirm it fails.
2. **Read the failure.** It tells you the first missing piece. That piece is the next inner-loop slice.
3. **Inner loop.** One unit test, red, then the minimum code, green. Repeat, one slice at a time.
4. **After each inner green, re-run the acceptance test.** A new failure message means progress; it points at the next slice.
5. **Outer green.** The behavior is done. Only then write the next acceptance test.

Never write the implementation to satisfy the acceptance test directly. If a change has no unit test making it necessary, it is not yet justified.

## What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't. A good test reads like a specification — "user can checkout with valid cart" tells you exactly what capability exists — and survives refactors because it doesn't care about internal structure.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

An acceptance test additionally reads in the domain's language, so a non-developer can check it against the spec. When the spec's acceptance criteria are already Given/When/Then, the acceptance test should read as those criteria.

## Seams — where tests go

A **seam** is the public boundary you test at: the interface where you observe behavior without reaching inside. Tests live at seams, never against internals.

**Test only at pre-agreed seams.** Before writing any test, write down the seams under test and confirm them with the user. No test is written at an unconfirmed seam. You can't test everything — agreeing the seams up front is how testing effort lands on the critical paths and complex logic instead of every edge case.

Agree both loops' seams:

- **The acceptance seam** — the outermost interface a caller uses (the endpoint, the tool, the command). Usually one.
- **The unit seams** — the inner interfaces whose logic is complex or risky enough to deserve their own tests (a parser, a permission gate, a security check). List them in the order you intend to build them.

Ask: "What's the public interface, and which seams should we test?"

## Anti-patterns

- **Implementation-coupled** — mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological** — the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`, a snapshot derived by hand the same way, a constant asserted equal to itself), so it passes by construction and can never disagree with the code. Expected values must come from an independent source of truth — a known-good literal, a worked example, the spec.
- **Horizontal slicing** — writing all tests first, then all implementation. Bulk tests verify _imagined_ behavior: you test the _shape_ of things rather than user-facing behavior, the tests go insensitive to real changes, and you commit to test structure before understanding the implementation. Work in **vertical slices** instead — one test → one implementation → repeat, each test a **tracer bullet** that responds to what the last cycle taught you. This holds in both loops: one acceptance test at a time, one unit test at a time.
- **Acceptance-driven implementation** — skipping the inner loop and coding straight at the acceptance test. The code passes the scenario but nothing pins down its edge cases, and every failure has to be diagnosed through the whole stack.
- **Duplicated edge cases** — pushing every edge case through the acceptance test. Edge cases belong in the inner loop, where each one costs a few lines; the outer test covers the behaviors the spec names.

## Rules of the loops

- **Red before green, in both loops.** Write the failing test first, then only enough code to pass it. Don't anticipate future tests or add speculative features.
- **One slice at a time.** One seam, one test, one minimal implementation per inner cycle; one behavior per outer cycle.
- **The outer test stays red until the inner loops have built the behavior.** A red acceptance test mid-feature is expected, not a failure to fix.
- **Refactoring is not part of the loop.** It belongs to the review stage (see the `code-review` skill), not the red → green implementation cycle.

## Attribution

Adapted from the [`tdd` skill](https://github.com/mattpocock/skills/blob/321658273cb1d20b76026717d027d505790106d4/skills/engineering/tdd/SKILL.md) by [Matt Pocock](https://github.com/mattpocock), MIT licensed. `tests.md` and `mocking.md` are his, unchanged. The double-loop structure follows *Growing Object-Oriented Software, Guided by Tests* by Steve Freeman and Nat Pryce.
