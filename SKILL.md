---
name: visualize-flow
description: Draw a flow from the code (a lambda chain, an event flow, a cron, a sync, a use case) as one page with every DDD view (core domain chart, context map, bounded context canvases, domain story, EventStorming board, domain message flow, aggregate design canvases) plus BPMN, all built from one flow JSON file. Use when the user wants a flow visualized, mapped, or drawn as EventStorming, BPMN or a context map.
---

One **flow file** (`<flow>.flow.json`) is the single source of truth. `scripts/build.js` turns it into one self-contained HTML page with every view. The format is in [FORMAT.md](FORMAT.md); read it before writing the file.

**Write nothing into the repo.** The flow file and the page live in the scratch directory. The published page embeds the flow file, so it can always be recovered with `scripts/extract.js`.

## Steps

1. **Pin the flow.** Name its entry points and its last observable effect. Ask the user only when the code offers several flows that match the request.

2. **Trace it in the code.** Start at every entry point: handlers, admin actions, crons, signals, queue and event consumers. Follow each one through services and aggregates until the flow ends. Done when you can name, with a file path, every:
   - trigger (who or what starts the flow);
   - command and the aggregate that handles it;
   - domain event, with its real name from the code;
   - policy ("whenever X, do Y"), including retries and scheduled jobs;
   - external system called;
   - bounded context crossed, and which side depends on which;
   - state each aggregate moves through;
   - failure path, from the error to whatever reacts to it.

   Collect **hotspots** as you go: a behavior that surprised you, a silent skip, a flag that changes the path, an inconsistency. These are the most valuable stickies on the board.

3. **Write the flow file** at `<scratch-dir>/flows/<flow>.flow.json`. Write the `story` first: if you cannot tell the flow in a paragraph and six steps, go back to step 2. Then fill every section in FORMAT.md. Every sticky with a code counterpart carries `ref`, the repo-relative file path. Use the names from the repo's glossary when it has one. Mark judgment calls (core domain chart positions, strategic classification) as estimates in the text.

4. **Build.** Run:

   ```bash
   node <skill-dir>/scripts/build.js <scratch-dir>/flows/<flow>.flow.json --html <scratch-dir>/<flow>.html
   ```

   Fix every `error` and rerun. A `warning` about a backward flow means a loop: replace it with a pair of link events (a throw and a catch with the same `name`). Add `--bpmn <path>` only when the user asks for a `.bpmn` file.

5. **Publish.** When an Artifact tool is available, publish the HTML page and give the user the link. Otherwise give the path of the HTML file.

6. **Report.** Give the user the link and list the hotspots in one line each.

## Updating a flow

Edit the flow file in the scratch directory and rerun step 4. When it is gone, read the published page (with the Artifact tool's `read` action) and run `node <skill-dir>/scripts/extract.js <saved-page.html> <scratch-dir>/flows/<flow>.flow.json` to get it back.
