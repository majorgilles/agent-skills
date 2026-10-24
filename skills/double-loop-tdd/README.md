# Double-Loop TDD Skill

An agent skill for test-driven development with two loops:

- an **outer acceptance test** (a BDD scenario, end-to-end or API-level test) that states one behavior from the spec and stays red while it is built;
- **inner unit-test red → green cycles** at agreed seams, which drive the implementation until the acceptance test passes.

The acceptance test checks the work. The unit tests drive it.

## Credit

This is an adaptation of the [`tdd` skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/tdd) by [Matt Pocock](https://github.com/mattpocock), from [mattpocock/skills](https://github.com/mattpocock/skills), MIT licensed. His sections (what a good test is, seams, anti-patterns, rules of the loop) are kept as written, and `tests.md` and `mocking.md` are his files, unchanged.

What this version adds:

- double-loop is the default, not an option;
- seams are agreed for both loops (one acceptance seam, an ordered list of unit seams);
- two extra anti-patterns: coding straight at the acceptance test, and pushing every edge case through it.

The double-loop idea itself comes from *Growing Object-Oriented Software, Guided by Tests* by Steve Freeman and Nat Pryce.

## Install

Clone this repository into a skill search path:

```bash
git clone https://github.com/majorgilles/double-loop-tdd.git ~/.agents/skills/double-loop-tdd
```

Then invoke it as `/double-loop-tdd`, or let the agent pick it up when you ask for test-first work.

## License

MIT. See [LICENSE](LICENSE), which keeps the original copyright notice.
