# Visualize Flow Skill

An agent skill that reads a flow in your codebase (a lambda chain, an event flow, a cron, a sync) and draws it two ways:

- an **EventStorming board**: colored sticky notes on a timeline, with events, commands, policies, external systems and hotspots;
- a **BPMN 2.0 diagram**: lanes, gateways, message flows to external systems. The `.bpmn` file opens in Camunda Modeler or demo.bpmn.io.

Both views come from one JSON **flow file** that you keep in the repo, next to the feature docs. Edit the file, rebuild, and both views change together.

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

This writes `examples/order-checkout.bpmn` and a self-contained HTML page. The page loads fonts from Google Fonts and the BPMN viewer ([bpmn-js](https://github.com/bpmn-io/bpmn-js)) from jsDelivr.

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | The steps the agent follows. |
| `FORMAT.md` | The flow file format. |
| `scripts/flow-render.js` | Validation, grid layout, BPMN XML and the page renderer. Runs in Node and in the browser. |
| `scripts/build.js` | Command line: validates a flow file, writes the `.bpmn` and the HTML page. |
| `scripts/template.html` | The page design. |
| `examples/order-checkout.flow.json` | A small complete example. |

## License

MIT. See [LICENSE](LICENSE).
