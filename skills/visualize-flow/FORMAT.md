# Flow file format

A flow file is JSON. `examples/order-checkout.flow.json` is a complete small example: copy its shape.

```json
{
  "title": "Order checkout",
  "summary": "One or two sentences: what the flow does and who it is for.",
  "read_on": "2026-10-23",
  "story": { ... },
  "board": { ... },
  "bpmn": { ... }
}
```

`read_on` is the date you read the code. Every section is optional; the page hides a missing one. The page shows them in this order:

| Key | View | Answers |
|---|---|---|
| `story` | In short | What the flow does, in 30 seconds. |
| `core_domain_chart` | Core domain chart | Which subdomains set the business apart. |
| `context_map` | Context map | Which bounded contexts the flow crosses, and who depends on whom. |
| `domain_story` | Domain story | Who does what with which work object, in business words. |
| `board` | EventStorming board | Events, commands, policies and hotspots on a timeline. |
| `bpmn` | BPMN 2.0 | The precise process, for review. |

## `core_domain_chart`

```json
"core_domain_chart": {
  "subdomains": [
    { "name": "Invoicing", "differentiation": 3.5, "complexity": 6.5, "in_flow": true, "note": "Optional line under the chart." }
  ]
}
```

Both axes run from 0 to 10. Differentiation above 6.67 is core, between 3.33 and 6.67 supporting, below that generic. These are estimates: say so in a `note` when it matters. Keep points at least 1.5 apart on one axis, or their labels overlap.

## `context_map`

```json
"context_map": {
  "contexts": [
    { "id": "contract", "name": "Contract", "kind": "core", "in_flow": true, "column": 1, "row": 1, "note": "Optional." }
  ],
  "relationships": [
    { "upstream": "twikey", "downstream": "contract", "kind": "upstream-downstream",
      "upstream_roles": ["OHS"], "downstream_roles": ["ACL"], "label": "twikey_integration" }
  ]
}
```

- `kind` of a context: `core`, `supporting`, `generic`, `external` or `legacy`.
- `kind` of a relationship: `upstream-downstream`, `customer-supplier`, `partnership`, `shared-kernel` or `separate-ways`.
- Roles: `OHS` (Open Host Service), `PL` (Published Language), `ACL` (Anticorruption Layer), `CF` (Conformist).
- Put the context at the center of the flow in the middle of the grid, its partners around it. Keep diagonal neighbours: straight vertical lines between adjacent rows leave little room for labels.
- `"in_flow": false` on a relationship draws it faded.

## `domain_story`

Numbered sentences of the form actor, activity, work object, and optionally a target actor.

```json
"domain_story": {
  "actors": [{ "id": "lizy", "name": "Lizy platform", "kind": "system" }],
  "sentences": [{ "actor": "lizy", "activity": "books", "object": "Invoice", "preposition": "in", "target": "exact", "note": "Optional." }]
}
```

Actor `kind` is `person`, `group` or `system`. `preposition` defaults to "to". Write activities in business words, not code names.

## `board`: the EventStorming view

```json
"board": {
  "phases": [{ "id": "trigger", "name": "Something asks for a price" }],
  "lanes": [{ "id": "main", "name": "Main flow" }, { "id": "failure", "name": "Failure and retry" }],
  "cells": [
    { "lane": "main", "phase": "trigger", "chains": [[ sticky, sticky ], [ sticky ]] }
  ]
}
```

- **Phases** are the columns, left to right in time. Use 4 to 7.
- **Lanes** are the rows. Usual pair: the main flow and the failure path.
- A **chain** is a vertical stack of stickies joined by arrows: one cause-and-effect sequence. A cell holds several chains, one under the other.

A sticky:

```json
{ "kind": "policy", "text": "Every month, reprice published vehicles", "sub": "last price older than 1 month",
  "detail": "Shown in the side panel when the sticky is selected.", "ref": "path/to/handler.py", "timer": true }
```

| `kind` | Color | Holds |
|---|---|---|
| `event` | orange | Something that happened, in the past tense, with its code name in `sub`. |
| `command` | blue | A request to do something, in the imperative. |
| `aggregate` | yellow | The aggregate or entity that handles a command. |
| `actor` | pale yellow | A person or team that issues a command. Keep it to one or two words. |
| `policy` | lilac | A reaction rule: "Whenever X, do Y". Crons and retries are policies. |
| `external` | pink | A system outside the codebase. |
| `readmodel` | green | Data that someone reads to decide: a table, a report, a screen. |
| `hotspot` | red | A question, a risk, or a surprise found in the code. |

Optional flags: `timer: true` adds a clock (a scheduled policy), `loop: true` marks a sticky that sends the flow back to an earlier step.

## `bpmn`: the BPMN 2.0 view

The layout is a grid. Every node sits in a cell named by its lane, `column` (0 = left) and `row` (0 = top of the lane). The build computes all coordinates, so the file holds no pixels.

```json
"bpmn": {
  "pool": "my-service: order checkout",
  "lanes": [{ "id": "lane_api", "name": "API" }, { "id": "lane_worker", "name": "Worker" }],
  "externals": [{ "id": "ext_stripe", "name": "Stripe", "column": 4, "span": 1 }],
  "nodes": [
    { "id": "start", "type": "startEvent", "def": "message", "name": "Order placed", "lane": "lane_api", "column": 0, "row": 0 },
    { "id": "pay", "type": "serviceTask", "name": "Charge card", "lane": "lane_worker", "column": 4, "row": 0 }
  ],
  "flows": [["start", "pay"], ["check", "pay", "Yes"]],
  "messages": [{ "task": "pay", "external": "ext_stripe", "direction": "both" }],
  "annotations": [{ "text": "Retries are not idempotent.", "target": "pay", "lane": "lane_worker", "column": 5, "row": 1 }]
}
```

### Nodes

| Field | Values |
|---|---|
| `type` | `startEvent`, `endEvent`, `intermediateCatchEvent`, `intermediateThrowEvent`, `boundaryEvent`, `serviceTask`, `userTask`, `task`, `sendTask`, `receiveTask`, `manualTask`, `scriptTask`, `businessRuleTask`, `exclusiveGateway`, `parallelGateway`, `inclusiveGateway`, `eventBasedGateway`, `subProcess` |
| `def` | Events only: `message`, `timer`, `error`, `conditional`, `link`, `signal`, `escalation`. Leave it out for a plain event. |
| `label` | Where the label goes: `right`, `left` or `above`. Default is the BPMN default (below events and gateways). |
| `parent` | The id of a `subProcess`. Children take the lane of their parent. |
| `attachedTo` | Boundary events only: the id of the host task or sub-process. Optional `column` moves it along the host. |

A `subProcess` has no `column` or `row`: it wraps its children. A gateway has no `name` when it only splits or joins.

### Layout rules

- Flows go left to right or straight up and down. Keep columns increasing along the flow.
- For a loop back to an earlier step, use two link events with the same `name`: an `intermediateThrowEvent` with `"def": "link"` where the loop starts, and an `intermediateCatchEvent` with `"def": "link"` before the step it returns to.
- Put an `external` in the same column as the task that calls it, so its message flows run straight up. Leave the cells between that task and the top of the pool empty.
- An event label set to `right` fills the start of the next column. Keep that cell empty.
- Annotations take a cell. Put them in the same column as their target (vertical link) or in the same row (horizontal link).
- One node per cell: the build fails when two nodes share a cell.
