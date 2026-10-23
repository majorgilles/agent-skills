---
name: visualize-flow
description: Draw a flow from the code (a lambda chain, an event flow, a cron, a sync, a use case) as an EventStorming board and a BPMN diagram, both built from one flow JSON file kept in the repo. Use when the user wants a flow visualized, mapped, or drawn as EventStorming or BPMN.
---

One **flow file** (`<flow>.flow.json`) is the single source of truth. `scripts/build.js` turns it into a `.bpmn` file and a self-contained HTML page with both views. The format is in [FORMAT.md](FORMAT.md); read it before writing the file.

## Steps

1. **Pin the flow.** Name its entry points and its last observable effect. Ask the user only when the code offers several flows that match the request.

2. **Trace it in the code.** Start at every entry point: handlers, admin actions, crons, signals, queue and event consumers. Follow each one through services and aggregates until the flow ends. Done when you can name, with a file path, every:
   - trigger (who or what starts the flow);
   - command and the aggregate that handles it;
   - domain event, with its real name from the code;
   - policy ("whenever X, do Y"), including retries and scheduled jobs;
   - external system called;
   - failure path, from the error to whatever reacts to it.

   Collect **hotspots** as you go: a behavior that surprised you, a silent skip, a flag that changes the path, an inconsistency. These are the most valuable stickies on the board.

3. **Write the flow file.** Save it next to the docs of the feature, for example `docs/features/<feature>/<flow>.flow.json`. If the repo has no `docs/` folder, ask the user where it goes. Write the `story` first: if you cannot tell the flow in a paragraph and six steps, go back to step 2. Then fill the `board` and the `bpmn` sections. Every sticky with a code counterpart carries `ref`, the repo-relative file path. Use the names from the repo's glossary when it has one.

4. **Build.** Run:

   ```bash
   node <skill-dir>/scripts/build.js docs/features/<feature>/<flow>.flow.json --html <scratch-dir>/<flow>.html
   ```

   The `.bpmn` lands next to the JSON. Fix every `error` and rerun. A `warning` about a backward flow means a loop: replace it with a pair of link events (a throw and a catch with the same `name`).

5. **Publish.** When an Artifact tool is available, publish the HTML page and give the user the link. Otherwise give the path of the HTML file.

6. **Report.** Give the user the paths of the `.flow.json` and the `.bpmn` and the link. List the hotspots in one line each. Leave the files uncommitted: the user commits them.

## Updating a flow

Edit the existing `.flow.json`, then rerun step 4. The board and the BPMN both come from that file, so one edit updates both.
