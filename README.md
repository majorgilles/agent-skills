# Visualize Flow Skill

An agent skill that reads a flow in your codebase (a lambda chain, an event flow, a cron, a sync) and draws it as one page with every view Domain-Driven Design uses:

- a short **story** of the flow;
- a **core domain chart** and a **context map**, with upstream, downstream and integration roles;
- **bounded context canvases** and **aggregate design canvases**, with each aggregate's lifecycle;
- a **domain story** and a **domain message flow**;
- an **EventStorming board**: colored sticky notes on a timeline, with hotspots;
- a **BPMN 2.0 diagram**, exportable to Camunda Modeler or demo.bpmn.io.

Every view comes from one JSON **flow file**. The skill keeps it outside your repo and embeds it in the page, so `scripts/extract.js` recovers it from a saved page.

## Install

```bash
git clone https://github.com/majorgilles/visualize-flow.git ~/.agents/skills/visualize-flow
```

Then ask the agent to "visualize the pricing flow", or invoke `/visualize-flow`.

## Build by hand

The build needs Node 18 or later, and nothing else.

```bash
node scripts/build.js examples/order-checkout.flow.json --html /tmp/order-checkout.html
```

This writes a self-contained HTML page. Add `--bpmn <path>` to also write the `.bpmn` file. The page loads fonts from Google Fonts and the BPMN viewer ([bpmn-js](https://github.com/bpmn-io/bpmn-js)) from jsDelivr.

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | The steps the agent follows. |
| `FORMAT.md` | The flow file format. |
| `scripts/flow-render.js` | Story, board and BPMN: validation, grid layout, BPMN XML and page wiring. Runs in Node and in the browser. |
| `scripts/ddd-views.js` | Core domain chart, context map, canvases, domain story and message flow. Runs in Node and in the browser. |
| `scripts/build.js` | Command line: validates a flow file and writes the HTML page, and the `.bpmn` on request. |
| `scripts/extract.js` | Command line: recovers the flow file from a page built by the skill. |
| `scripts/template.html` | The page design. |
| `examples/order-checkout.flow.json` | A small complete example. |

## License

MIT. See [LICENSE](LICENSE).
