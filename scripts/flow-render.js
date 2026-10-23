// Renders a flow file as an EventStorming board and a BPMN 2.0 diagram.
// The same file runs in Node (build.js uses it to write the .bpmn) and in the browser (the page inlines it).
(function (root) {
  "use strict";

  const STICKY_KINDS = {
    event: "Domain event",
    command: "Command",
    aggregate: "Aggregate",
    actor: "Actor",
    policy: "Policy",
    external: "External system",
    readmodel: "Read model",
    hotspot: "Hotspot",
  };

  const LAYOUT = {
    columnWidth: 160,
    rowHeight: 130,
    lanePadding: 15,
    laneLabelWidth: 30,
    poolX: 40,
    externalY: 30,
    externalHeight: 60,
    externalGap: 60,
    subProcessPadding: { top: 24, side: 15, bottom: 15 },
  };
  const FIRST_COLUMN_X = LAYOUT.poolX + LAYOUT.laneLabelWidth + 20;

  const SIZES = { task: [100, 80], event: [36, 36], gateway: [50, 50], annotation: [140, 64] };
  const EVENT_TYPES = new Set(["startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent"]);
  const GATEWAY_TYPES = new Set(["exclusiveGateway", "parallelGateway", "inclusiveGateway", "eventBasedGateway"]);
  const TASK_TYPES = new Set(["task", "serviceTask", "userTask", "manualTask", "sendTask", "receiveTask", "scriptTask", "businessRuleTask"]);
  const EVENT_DEFINITIONS = new Set(["message", "timer", "error", "link", "conditional", "signal", "escalation"]);

  function shapeKind(type) {
    if (EVENT_TYPES.has(type)) return "event";
    if (GATEWAY_TYPES.has(type)) return "gateway";
    return "task";
  }

  function isInteger(value) {
    return Number.isInteger(value) && value >= 0;
  }

  // ---------- validation ----------

  function validateBoard(board, errors) {
    const phaseIds = new Set((board.phases || []).map(phase => phase.id));
    const laneIds = new Set((board.lanes || []).map(lane => lane.id));
    if (!phaseIds.size) errors.push("board.phases is empty.");
    if (!laneIds.size) errors.push("board.lanes is empty.");
    (board.cells || []).forEach((cell, cellIndex) => {
      const where = `board.cells[${cellIndex}]`;
      if (!laneIds.has(cell.lane)) errors.push(`${where}: unknown lane "${cell.lane}".`);
      if (!phaseIds.has(cell.phase)) errors.push(`${where}: unknown phase "${cell.phase}".`);
      (cell.chains || []).forEach((chain, chainIndex) => chain.forEach((sticky, stickyIndex) => {
        const stickyWhere = `${where}.chains[${chainIndex}][${stickyIndex}]`;
        if (!STICKY_KINDS[sticky.kind]) errors.push(`${stickyWhere}: unknown kind "${sticky.kind}".`);
        if (!sticky.text) errors.push(`${stickyWhere}: missing text.`);
      }));
    });
  }

  function validateNodes(bpmn, errors) {
    const laneIds = new Set((bpmn.lanes || []).map(lane => lane.id));
    const nodesById = {};
    for (const node of bpmn.nodes || []) {
      if (nodesById[node.id]) errors.push(`Duplicate node id "${node.id}".`);
      nodesById[node.id] = node;
    }
    for (const node of bpmn.nodes || []) {
      const where = `node "${node.id}"`;
      const known = node.type === "subProcess" || EVENT_TYPES.has(node.type) || GATEWAY_TYPES.has(node.type) || TASK_TYPES.has(node.type);
      if (!known) errors.push(`${where}: unknown type "${node.type}".`);
      if (node.def && !EVENT_DEFINITIONS.has(node.def)) errors.push(`${where}: unknown def "${node.def}".`);
      if (node.type === "boundaryEvent") {
        if (!nodesById[node.attachedTo]) errors.push(`${where}: attachedTo "${node.attachedTo}" does not exist.`);
        continue;
      }
      if (node.parent) {
        if (nodesById[node.parent]?.type !== "subProcess") errors.push(`${where}: parent "${node.parent}" is not a subProcess.`);
      } else if (!laneIds.has(node.lane)) {
        errors.push(`${where}: unknown lane "${node.lane}".`);
      }
      if (node.type !== "subProcess" && !(isInteger(node.column) && isInteger(node.row))) {
        errors.push(`${where}: column and row must be integers from 0.`);
      }
    }
    return nodesById;
  }

  function validate(model) {
    const errors = [];
    if (!model.title) errors.push("Missing title.");
    if (model.story && !(model.story.text && Array.isArray(model.story.steps) && model.story.steps.length)) {
      errors.push("story needs a text and at least one step.");
    }
    if (!model.board && !model.bpmn) errors.push("A flow needs a board, a bpmn section, or both.");
    if (model.board) validateBoard(model.board, errors);
    if (!model.bpmn) return { errors, warnings: model.story ? [] : ["No story. Add one: it is the first thing a reader sees."] };

    const bpmn = model.bpmn;
    const errorsBeforeBpmn = errors.length;
    const nodesById = validateNodes(bpmn, errors);
    const externalIds = new Set((bpmn.externals || []).map(external => external.id));
    (bpmn.flows || []).forEach(([from, to], index) => {
      if (!nodesById[from]) errors.push(`flows[${index}]: unknown source "${from}".`);
      if (!nodesById[to]) errors.push(`flows[${index}]: unknown target "${to}".`);
    });
    (bpmn.messages || []).forEach((message, index) => {
      if (!nodesById[message.task]) errors.push(`messages[${index}]: unknown task "${message.task}".`);
      if (!externalIds.has(message.external)) errors.push(`messages[${index}]: unknown external "${message.external}".`);
    });
    (bpmn.annotations || []).forEach((annotation, index) => {
      if (!nodesById[annotation.target]) errors.push(`annotations[${index}]: unknown target "${annotation.target}".`);
    });
    if (errors.length > errorsBeforeBpmn) return { errors, warnings: [] };

    const warnings = [];
    if (!model.story) warnings.push("No story. Add one: it is the first thing a reader sees.");
    const placed = layout(bpmn);
    const cells = {};
    for (const node of bpmn.nodes) {
      if (node.type === "subProcess" || node.type === "boundaryEvent") continue;
      const key = `${laneOf(node, nodesById)}/${node.column}/${node.row}`;
      if (cells[key]) errors.push(`Nodes "${cells[key]}" and "${node.id}" share lane, column and row.`);
      cells[key] = node.id;
    }
    bpmn.flows.forEach(([from, to]) => {
      const source = placed.boxes[from];
      const target = placed.boxes[to];
      if (center(target).x < center(source).x - 1) {
        warnings.push(`Flow ${from} -> ${to} goes backwards. Use a pair of link events instead.`);
      }
    });
    for (const message of bpmn.messages || []) {
      const task = placed.boxes[message.task];
      const external = placed.externals.find(candidate => candidate.id === message.external);
      if (center(task).x < external.x || center(task).x > external.x + external.width) {
        warnings.push(`External "${message.external}" does not sit above task "${message.task}". Set its column.`);
      }
    }
    return { errors, warnings };
  }

  // ---------- layout ----------

  function laneOf(node, nodesById) {
    if (node.lane) return node.lane;
    if (node.parent) return laneOf(nodesById[node.parent], nodesById);
    if (node.attachedTo) return laneOf(nodesById[node.attachedTo], nodesById);
    return undefined;
  }

  function center(box) {
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  }

  function boxAround(centerPoint, [width, height]) {
    return { x: centerPoint.x - width / 2, y: centerPoint.y - height / 2, width, height };
  }

  function layout(bpmn) {
    const nodesById = Object.fromEntries(bpmn.nodes.map(node => [node.id, node]));
    const externals = bpmn.externals || [];
    const poolY = externals.length ? LAYOUT.externalY + LAYOUT.externalHeight + LAYOUT.externalGap : LAYOUT.externalY;

    const lanes = [];
    let laneTop = poolY;
    for (const lane of bpmn.lanes) {
      const rowsUsed = [...bpmn.nodes, ...(bpmn.annotations || [])]
        .filter(item => isInteger(item.row) && (item.lane || laneOf(item, nodesById)) === lane.id)
        .map(item => item.row + 1);
      const rows = Math.max(1, lane.rows || 0, ...rowsUsed);
      const height = rows * LAYOUT.rowHeight + 2 * LAYOUT.lanePadding;
      lanes.push({ id: lane.id, name: lane.name, y: laneTop, height });
      laneTop += height;
    }
    const lanesById = Object.fromEntries(lanes.map(lane => [lane.id, lane]));

    function cellCenter(laneId, column, row) {
      return {
        x: FIRST_COLUMN_X + column * LAYOUT.columnWidth + LAYOUT.columnWidth / 2,
        y: lanesById[laneId].y + LAYOUT.lanePadding + row * LAYOUT.rowHeight + LAYOUT.rowHeight / 2,
      };
    }

    const boxes = {};
    for (const node of bpmn.nodes) {
      if (node.type === "subProcess" || node.type === "boundaryEvent") continue;
      boxes[node.id] = boxAround(cellCenter(laneOf(node, nodesById), node.column, node.row), SIZES[shapeKind(node.type)]);
    }
    for (const node of bpmn.nodes.filter(candidate => candidate.type === "subProcess")) {
      const children = bpmn.nodes.filter(child => child.parent === node.id).map(child => boxes[child.id]);
      const padding = LAYOUT.subProcessPadding;
      const left = Math.min(...children.map(box => box.x)) - padding.side;
      const top = Math.min(...children.map(box => box.y)) - padding.top;
      const right = Math.max(...children.map(box => box.x + box.width)) + padding.side;
      const bottom = Math.max(...children.map(box => box.y + box.height)) + padding.bottom;
      boxes[node.id] = { x: left, y: top, width: right - left, height: bottom - top };
    }
    for (const node of bpmn.nodes.filter(candidate => candidate.type === "boundaryEvent")) {
      const host = boxes[node.attachedTo];
      const x = isInteger(node.column) ? cellCenter(laneOf(node, nodesById), node.column, 0).x : center(host).x;
      boxes[node.id] = boxAround({ x, y: host.y + host.height }, SIZES.event);
    }

    const annotationBoxes = {};
    (bpmn.annotations || []).forEach((annotation, index) => {
      annotationBoxes[annotation.id || `annotation_${index + 1}`] = boxAround(cellCenter(annotation.lane, annotation.column, annotation.row), SIZES.annotation);
    });

    const placedExternals = externals.map(external => ({
      id: external.id,
      name: external.name,
      x: FIRST_COLUMN_X + external.column * LAYOUT.columnWidth + 5,
      y: LAYOUT.externalY,
      width: (external.span || 1) * LAYOUT.columnWidth - 10,
      height: LAYOUT.externalHeight,
    }));

    const rightEdge = Math.max(...[...Object.values(boxes), ...Object.values(annotationBoxes), ...placedExternals].map(box => box.x + box.width));
    const pool = { x: LAYOUT.poolX, y: poolY, width: rightEdge + 40 - LAYOUT.poolX, height: laneTop - poolY };
    return { boxes, annotationBoxes, lanes, pool, externals: placedExternals };
  }

  function route(source, target) {
    const sourceCenter = center(source);
    const targetCenter = center(target);
    if (Math.abs(sourceCenter.x - targetCenter.x) < 1) {
      return targetCenter.y > sourceCenter.y
        ? [{ x: sourceCenter.x, y: source.y + source.height }, { x: targetCenter.x, y: target.y }]
        : [{ x: sourceCenter.x, y: source.y }, { x: targetCenter.x, y: target.y + target.height }];
    }
    if (targetCenter.x > sourceCenter.x) {
      const start = { x: source.x + source.width, y: sourceCenter.y };
      const end = { x: target.x, y: targetCenter.y };
      if (Math.abs(start.y - end.y) < 1) return [start, end];
      const middle = (start.x + end.x) / 2;
      return [start, { x: middle, y: start.y }, { x: middle, y: end.y }, end];
    }
    return [{ x: source.x, y: sourceCenter.y }, { x: target.x + target.width, y: targetCenter.y }];
  }

  // ---------- BPMN XML ----------

  function escapeXml(value) {
    return String(value).replace(/[&<>"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);
  }

  function eventDefinitionXml(node) {
    if (!node.def) return "";
    if (node.def === "link") return `<bpmn:linkEventDefinition name="${escapeXml(node.name || node.id)}"/>`;
    if (node.def === "conditional") {
      return '<bpmn:conditionalEventDefinition><bpmn:condition xsi:type="bpmn:tFormalExpression"/></bpmn:conditionalEventDefinition>';
    }
    return `<bpmn:${node.def}EventDefinition/>`;
  }

  function nodeXml(node, bpmn, flowsByParent) {
    const name = node.name ? ` name="${escapeXml(node.name)}"` : "";
    const attached = node.attachedTo ? ` attachedToRef="${node.attachedTo}"` : "";
    const body = node.type === "subProcess"
      ? bpmn.nodes.filter(child => child.parent === node.id).map(child => nodeXml(child, bpmn, flowsByParent)).join("") + (flowsByParent[node.id] || []).join("")
      : eventDefinitionXml(node);
    return `<bpmn:${node.type} id="${node.id}"${name}${attached}>${body}</bpmn:${node.type}>`;
  }

  function labelXml(node, box) {
    const label = node.label;
    if (!label) return "";
    const bounds = {
      right: { x: box.x + box.width + 6, y: box.y + 4, width: 100, height: 28 },
      left: { x: box.x - 106, y: box.y + 4, width: 100, height: 28 },
      above: { x: box.x - 35, y: box.y - 38, width: box.width + 70, height: 32 },
    }[label];
    if (!bounds) return "";
    return `<bpmndi:BPMNLabel><dc:Bounds x="${bounds.x}" y="${bounds.y}" width="${bounds.width}" height="${bounds.height}"/></bpmndi:BPMNLabel>`;
  }

  function boundsXml(box) {
    return `<dc:Bounds x="${box.x}" y="${box.y}" width="${box.width}" height="${box.height}"/>`;
  }

  function waypointsXml(points) {
    return points.map(point => `<di:waypoint x="${point.x}" y="${point.y}"/>`).join("");
  }

  function annotationLink(targetBox, noteBox) {
    const targetCenter = center(targetBox);
    const noteCenter = center(noteBox);
    if (Math.abs(targetCenter.x - noteCenter.x) < 1) {
      return noteCenter.y < targetCenter.y
        ? [{ x: targetCenter.x, y: targetBox.y }, { x: noteCenter.x, y: noteBox.y + noteBox.height }]
        : [{ x: targetCenter.x, y: targetBox.y + targetBox.height }, { x: noteCenter.x, y: noteBox.y }];
    }
    return noteCenter.x > targetCenter.x
      ? [{ x: targetBox.x + targetBox.width, y: targetCenter.y }, { x: noteBox.x, y: noteCenter.y }]
      : [{ x: targetBox.x, y: targetCenter.y }, { x: noteBox.x + noteBox.width, y: noteCenter.y }];
  }

  function buildBpmnXml(bpmn) {
    const placed = layout(bpmn);
    const nodesById = Object.fromEntries(bpmn.nodes.map(node => [node.id, node]));
    const flowsByParent = {};
    const edges = [];

    (bpmn.flows || []).forEach(([from, to, name], index) => {
      const id = `flow_${index + 1}`;
      const parent = nodesById[from].parent || "process";
      const nameAttribute = name ? ` name="${escapeXml(name)}"` : "";
      (flowsByParent[parent] ||= []).push(`<bpmn:sequenceFlow id="${id}" sourceRef="${from}" targetRef="${to}"${nameAttribute}/>`);
      edges.push(`<bpmndi:BPMNEdge id="${id}_di" bpmnElement="${id}">${waypointsXml(route(placed.boxes[from], placed.boxes[to]))}</bpmndi:BPMNEdge>`);
    });

    const messageFlows = [];
    (bpmn.messages || []).forEach((message, index) => {
      const task = placed.boxes[message.task];
      const external = placed.externals.find(candidate => candidate.id === message.external);
      const bottom = external.y + external.height;
      const directions = message.direction === "out" ? ["out"] : message.direction === "in" ? ["in"] : ["out", "in"];
      for (const direction of directions) {
        const id = `message_${index + 1}_${direction}`;
        const x = center(task).x + (directions.length === 2 ? (direction === "out" ? -15 : 15) : 0);
        const [source, target, points] = direction === "out"
          ? [message.task, message.external, [{ x, y: task.y }, { x, y: bottom }]]
          : [message.external, message.task, [{ x, y: bottom }, { x, y: task.y }]];
        const name = message.name && direction === "out" ? ` name="${escapeXml(message.name)}"` : "";
        messageFlows.push(`<bpmn:messageFlow id="${id}" sourceRef="${source}" targetRef="${target}"${name}/>`);
        edges.push(`<bpmndi:BPMNEdge id="${id}_di" bpmnElement="${id}">${waypointsXml(points)}</bpmndi:BPMNEdge>`);
      }
    });

    const annotationsXml = (bpmn.annotations || []).map((annotation, index) => {
      const id = annotation.id || `annotation_${index + 1}`;
      edges.push(`<bpmndi:BPMNEdge id="${id}_link_di" bpmnElement="${id}_link">${waypointsXml(annotationLink(placed.boxes[annotation.target], placed.annotationBoxes[id]))}</bpmndi:BPMNEdge>`);
      return `<bpmn:textAnnotation id="${id}"><bpmn:text>${escapeXml(annotation.text)}</bpmn:text></bpmn:textAnnotation>` +
        `<bpmn:association id="${id}_link" sourceRef="${annotation.target}" targetRef="${id}"/>`;
    }).join("");

    const lanesXml = bpmn.lanes.map(lane => {
      const references = bpmn.nodes.filter(node => !node.parent && laneOf(node, nodesById) === lane.id)
        .map(node => `<bpmn:flowNodeRef>${node.id}</bpmn:flowNodeRef>`).join("");
      return `<bpmn:lane id="${lane.id}" name="${escapeXml(lane.name)}">${references}</bpmn:lane>`;
    }).join("");

    const shapes = [
      `<bpmndi:BPMNShape id="pool_di" bpmnElement="pool" isHorizontal="true">${boundsXml(placed.pool)}</bpmndi:BPMNShape>`,
      ...placed.lanes.map(lane => `<bpmndi:BPMNShape id="${lane.id}_di" bpmnElement="${lane.id}" isHorizontal="true">${boundsXml({
        x: placed.pool.x + LAYOUT.laneLabelWidth, y: lane.y, width: placed.pool.width - LAYOUT.laneLabelWidth, height: lane.height,
      })}</bpmndi:BPMNShape>`),
      ...placed.externals.map(external => `<bpmndi:BPMNShape id="${external.id}_di" bpmnElement="${external.id}" isHorizontal="true">${boundsXml(external)}</bpmndi:BPMNShape>`),
      ...bpmn.nodes.map(node => {
        const box = placed.boxes[node.id];
        const expanded = node.type === "subProcess" ? ' isExpanded="true"' : "";
        const marker = node.type === "exclusiveGateway" ? ' isMarkerVisible="true"' : "";
        return `<bpmndi:BPMNShape id="${node.id}_di" bpmnElement="${node.id}"${expanded}${marker}>${boundsXml(box)}${labelXml(node, box)}</bpmndi:BPMNShape>`;
      }),
      ...Object.entries(placed.annotationBoxes).map(([id, box]) => `<bpmndi:BPMNShape id="${id}_di" bpmnElement="${id}">${boundsXml(box)}</bpmndi:BPMNShape>`),
    ];

    const topLevel = bpmn.nodes.filter(node => !node.parent).map(node => nodeXml(node, bpmn, flowsByParent)).join("\n");
    return `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" id="definitions" targetNamespace="https://github.com/majorgilles/visualize-flow">
<bpmn:collaboration id="collaboration">
<bpmn:participant id="pool" name="${escapeXml(bpmn.pool || "Process")}" processRef="process"/>
${placed.externals.map(external => `<bpmn:participant id="${external.id}" name="${escapeXml(external.name)}"/>`).join("\n")}
${messageFlows.join("\n")}
</bpmn:collaboration>
<bpmn:process id="process" isExecutable="false">
<bpmn:laneSet id="lane_set">${lanesXml}</bpmn:laneSet>
${topLevel}
${(flowsByParent.process || []).join("\n")}
${annotationsXml}
</bpmn:process>
<bpmndi:BPMNDiagram id="diagram"><bpmndi:BPMNPlane id="plane" bpmnElement="collaboration">
${shapes.join("\n")}
${edges.join("\n")}
</bpmndi:BPMNPlane></bpmndi:BPMNDiagram>
</bpmn:definitions>
`;
  }

  // ---------- browser page ----------

  function element(document, tag, className, text) {
    const created = document.createElement(tag);
    if (className) created.className = className;
    if (text !== undefined) created.textContent = text;
    return created;
  }

  function renderLegend(document, legendElement) {
    for (const [kind, label] of Object.entries(STICKY_KINDS)) {
      const item = element(document, "span");
      const swatch = element(document, "i");
      swatch.style.background = `var(--${kind})`;
      item.append(swatch, label);
      legendElement.append(item);
    }
  }

  function showDetail(document, detailElement, sticky, button) {
    document.querySelectorAll(".sticky[aria-pressed]").forEach(other => other.setAttribute("aria-pressed", "false"));
    if (button) button.setAttribute("aria-pressed", "true");
    const kind = element(document, "div", "kind");
    const swatch = element(document, "i");
    swatch.style.background = `var(--${sticky.kind})`;
    kind.append(swatch, STICKY_KINDS[sticky.kind]);
    detailElement.replaceChildren(kind, element(document, "h3", "", sticky.text));
    for (const text of [sticky.sub, sticky.detail].filter(Boolean)) detailElement.append(element(document, "p", "", text));
    if (sticky.ref) detailElement.append(element(document, "div", "ref", sticky.ref));
  }

  function makeSticky(document, detailElement, sticky) {
    const classes = ["sticky", sticky.kind, sticky.timer && "timer", sticky.loop && "loop"].filter(Boolean);
    const button = element(document, "button", classes.join(" "), sticky.text);
    button.type = "button";
    button.setAttribute("aria-pressed", "false");
    if (sticky.sub) button.append(element(document, "small", "", sticky.sub));
    button.addEventListener("click", () => showDetail(document, detailElement, sticky, button));
    return button;
  }

  function renderBoard(document, board, boardElement, detailElement) {
    boardElement.style.gridTemplateColumns = `112px repeat(${board.phases.length}, minmax(200px, 1fr))`;
    boardElement.style.minWidth = `${112 + board.phases.length * 215}px`;
    boardElement.append(element(document, "div"));
    board.phases.forEach((phase, index) => {
      const header = element(document, "div", "phase", `Step ${index + 1}`);
      header.append(element(document, "b", "", phase.name));
      boardElement.append(header);
    });

    let first = null;
    board.lanes.forEach((lane, laneIndex) => {
      if (laneIndex > 0) boardElement.append(element(document, "div", "lane-sep"));
      boardElement.append(element(document, "div", "lane-label", lane.name));
      for (const phase of board.phases) {
        const chains = board.cells.filter(cell => cell.lane === lane.id && cell.phase === phase.id).flatMap(cell => cell.chains);
        const cellElement = element(document, "div", chains.length ? "cell" : "cell empty");
        for (const chain of chains) {
          const chainElement = element(document, "div", "chain");
          chain.forEach((sticky, position) => {
            if (position > 0) chainElement.append(element(document, "div", "arrow"));
            const button = makeSticky(document, detailElement, sticky);
            if (!first && sticky.detail) first = [sticky, button];
            chainElement.append(button);
          });
          cellElement.append(chainElement);
        }
        boardElement.append(cellElement);
      }
    });
    if (first) showDetail(document, detailElement, first[0], first[1]);
  }

  async function renderBpmn(document, xml, canvasElement) {
    const BpmnJS = root.BpmnJS;
    if (typeof BpmnJS === "undefined") {
      canvasElement.replaceChildren(element(document, "p", "bpmn-fallback", "The BPMN viewer could not load. The XML below still opens in Camunda Modeler or demo.bpmn.io."));
      return null;
    }
    const tokens = root.getComputedStyle(document.documentElement);
    canvasElement.replaceChildren();
    const viewer = new BpmnJS({
      container: canvasElement,
      bpmnRenderer: {
        defaultFillColor: tokens.getPropertyValue("--panel").trim(),
        defaultStrokeColor: tokens.getPropertyValue("--fg").trim(),
        defaultLabelColor: tokens.getPropertyValue("--fg").trim(),
      },
    });
    try {
      await viewer.importXML(xml);
      viewer.get("canvas").zoom("fit-viewport");
    } catch (error) {
      canvasElement.replaceChildren(element(document, "p", "bpmn-fallback", `The BPMN XML did not render: ${error.message}`));
    }
    return viewer;
  }

  function renderTableOfContents(document, tocElement) {
    for (const section of document.querySelectorAll("section[id$='-section']")) {
      if (section.hidden) continue;
      const heading = section.querySelector("h2");
      const link = element(document, "a", "", heading.textContent);
      link.href = `#${section.id}`;
      tocElement.append(link);
    }
  }

  function mount(model, document) {
    const byId = id => document.getElementById(id);
    byId("flow-title").textContent = model.title;
    byId("flow-summary").textContent = model.summary || "";
    const provenance = [model.source && `Source: ${model.source}`, model.read_on && `Read from the code on ${model.read_on}`].filter(Boolean);
    byId("flow-provenance").textContent = provenance.join(" · ");

    if (model.story) {
      byId("story-text").textContent = model.story.text;
      for (const step of model.story.steps) byId("story-steps").append(element(document, "li", "", step));
    } else {
      byId("story-section").hidden = true;
    }

    if (root.DddViews) root.DddViews.render(model, document);

    if (model.board) {
      renderLegend(document, byId("legend"));
      renderBoard(document, model.board, byId("board"), byId("detail"));
    } else {
      byId("board-section").hidden = true;
    }

    if (!model.bpmn) byId("bpmn-section").hidden = true;
    renderTableOfContents(document, byId("toc"));
    if (!model.bpmn) return;
    const xml = buildBpmnXml(model.bpmn);
    byId("bpmn-xml").value = xml;
    let viewer = null;
    renderBpmn(document, xml, byId("bpmn-canvas")).then(created => { viewer = created; });
    byId("bpmn-fit").addEventListener("click", () => viewer?.get("canvas").zoom("fit-viewport"));
    byId("bpmn-copy").addEventListener("click", event => {
      const button = event.currentTarget;
      root.navigator.clipboard.writeText(xml).then(
        () => { button.textContent = "Copied"; root.setTimeout(() => { button.textContent = "Copy BPMN XML"; }, 1600); },
        () => { byId("bpmn-xml-box").open = true; byId("bpmn-xml").focus(); byId("bpmn-xml").select(); },
      );
    });
  }

  const api = { STICKY_KINDS, validate, layout, buildBpmnXml, mount };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FlowRender = api;
})(typeof window !== "undefined" ? window : globalThis);
