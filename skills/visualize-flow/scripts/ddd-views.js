// The DDD views of a flow file (core domain chart, context map, domain story); validates in Node, renders in the page.
(function (root) {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const CONTEXT_KINDS = ["core", "supporting", "generic", "external", "legacy"];
  const RELATIONSHIP_KINDS = ["upstream-downstream", "customer-supplier", "partnership", "shared-kernel", "separate-ways"];
  const ROLE_NAMES = {
    OHS: "Open Host Service",
    PL: "Published Language",
    ACL: "Anticorruption Layer",
    CF: "Conformist",
  };

  // ---------- validation ----------

  function validateContextMap(contextMap, errors) {
    const ids = new Set();
    for (const context of contextMap.contexts || []) {
      if (ids.has(context.id)) errors.push(`context_map: duplicate context id "${context.id}".`);
      ids.add(context.id);
      if (!CONTEXT_KINDS.includes(context.kind)) errors.push(`context_map: context "${context.id}" has unknown kind "${context.kind}".`);
      if (!(Number.isInteger(context.column) && Number.isInteger(context.row))) {
        errors.push(`context_map: context "${context.id}" needs an integer column and row.`);
      }
    }
    for (const [index, relationship] of (contextMap.relationships || []).entries()) {
      if (!ids.has(relationship.upstream)) errors.push(`context_map.relationships[${index}]: unknown upstream "${relationship.upstream}".`);
      if (!ids.has(relationship.downstream)) errors.push(`context_map.relationships[${index}]: unknown downstream "${relationship.downstream}".`);
      if (!RELATIONSHIP_KINDS.includes(relationship.kind)) errors.push(`context_map.relationships[${index}]: unknown kind "${relationship.kind}".`);
      for (const role of [...(relationship.upstream_roles || []), ...(relationship.downstream_roles || [])]) {
        if (!ROLE_NAMES[role]) errors.push(`context_map.relationships[${index}]: unknown role "${role}".`);
      }
    }
    return ids;
  }

  function validate(model) {
    const errors = [];
    if (model.context_map) validateContextMap(model.context_map, errors);

    for (const [index, subdomain] of (model.core_domain_chart?.subdomains || []).entries()) {
      for (const axis of ["differentiation", "complexity"]) {
        const value = subdomain[axis];
        if (typeof value !== "number" || value < 0 || value > 10) errors.push(`core_domain_chart.subdomains[${index}]: ${axis} must be a number from 0 to 10.`);
      }
    }
    if (model.domain_story) {
      const actorIds = new Set((model.domain_story.actors || []).map(actor => actor.id));
      for (const [index, sentence] of (model.domain_story.sentences || []).entries()) {
        if (!actorIds.has(sentence.actor)) errors.push(`domain_story.sentences[${index}]: unknown actor "${sentence.actor}".`);
        if (sentence.target && !actorIds.has(sentence.target)) errors.push(`domain_story.sentences[${index}]: unknown target "${sentence.target}".`);
      }
    }
    return errors;
  }

  // ---------- small DOM and SVG helpers ----------

  function element(document, tag, className, text) {
    const created = document.createElement(tag);
    if (className) created.className = className;
    if (text !== undefined) created.textContent = text;
    return created;
  }

  function svgElement(document, tag, attributes = {}, text) {
    const created = document.createElementNS(SVG_NS, tag);
    for (const [name, value] of Object.entries(attributes)) created.setAttribute(name, value);
    if (text !== undefined) created.textContent = text;
    return created;
  }

  function wrapWords(text, maxCharacters) {
    const lines = [];
    let line = "";
    for (const word of String(text).split(/\s+/)) {
      if (line && (line + " " + word).length > maxCharacters) {
        lines.push(line);
        line = word;
      } else {
        line = line ? `${line} ${word}` : word;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  function multilineText(document, lines, x, y, attributes = {}, lineHeight = 15) {
    const text = svgElement(document, "text", { x, y: y - ((lines.length - 1) * lineHeight) / 2, ...attributes });
    lines.forEach((line, index) => {
      text.append(svgElement(document, "tspan", { x, dy: index === 0 ? 0 : lineHeight }, line));
    });
    return text;
  }

  function borderPoint(box, toward) {
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;
    const deltaX = toward.x - centerX;
    const deltaY = toward.y - centerY;
    if (deltaX === 0 && deltaY === 0) return { x: centerX, y: centerY };
    const scale = Math.min(
      deltaX === 0 ? Infinity : (box.width / 2) / Math.abs(deltaX),
      deltaY === 0 ? Infinity : (box.height / 2) / Math.abs(deltaY),
    );
    return { x: centerX + deltaX * scale, y: centerY + deltaY * scale };
  }

  function scrollable(document, svg) {
    const wrapper = element(document, "div", "diagram-scroll");
    wrapper.append(svg);
    return wrapper;
  }

  function list(document, items, emptyText = "None recorded.") {
    if (!items || !items.length) return element(document, "p", "muted", emptyText);
    const listElement = element(document, "ul");
    for (const item of items) listElement.append(element(document, "li", "", item));
    return listElement;
  }

  // ---------- core domain chart ----------

  function renderCoreDomainChart(document, chart) {
    const width = 640;
    const height = 440;
    const plot = { left: 70, top: 20, right: width - 20, bottom: height - 60 };
    const scaleX = value => plot.left + (value / 10) * (plot.right - plot.left);
    const scaleY = value => plot.bottom - (value / 10) * (plot.bottom - plot.top);
    const svg = svgElement(document, "svg", { viewBox: `0 0 ${width} ${height}`, class: "diagram", role: "img", "aria-label": "Core domain chart" });

    const bands = [
      { from: 6.67, to: 10, name: "Core", token: "--core" },
      { from: 3.33, to: 6.67, name: "Supporting", token: "--supporting" },
      { from: 0, to: 3.33, name: "Generic", token: "--generic" },
    ];
    for (const band of bands) {
      svg.append(svgElement(document, "rect", {
        x: plot.left, y: scaleY(band.to), width: plot.right - plot.left, height: scaleY(band.from) - scaleY(band.to),
        fill: `var(${band.token})`, opacity: 0.35,
      }));
      svg.append(svgElement(document, "text", { x: plot.right - 8, y: scaleY(band.to) + 18, "text-anchor": "end", class: "band-label" }, band.name));
    }
    svg.append(svgElement(document, "line", { x1: plot.left, y1: plot.bottom, x2: plot.right, y2: plot.bottom, class: "axis" }));
    svg.append(svgElement(document, "line", { x1: plot.left, y1: plot.top, x2: plot.left, y2: plot.bottom, class: "axis" }));
    svg.append(svgElement(document, "text", { x: (plot.left + plot.right) / 2, y: height - 18, "text-anchor": "middle", class: "axis-label" }, "Model complexity →"));
    svg.append(svgElement(document, "text", {
      x: 20, y: (plot.top + plot.bottom) / 2, "text-anchor": "middle", class: "axis-label",
      transform: `rotate(-90 20 ${(plot.top + plot.bottom) / 2})`,
    }, "Business differentiation →"));
    for (const tick of [0, 5, 10]) {
      svg.append(svgElement(document, "text", { x: scaleX(tick), y: plot.bottom + 18, "text-anchor": "middle", class: "tick" }, String(tick)));
      svg.append(svgElement(document, "text", { x: plot.left - 10, y: scaleY(tick) + 4, "text-anchor": "end", class: "tick" }, String(tick)));
    }
    for (const subdomain of chart.subdomains) {
      const x = scaleX(subdomain.complexity);
      const y = scaleY(subdomain.differentiation);
      svg.append(svgElement(document, "circle", { cx: x, cy: y, r: 8, class: subdomain.in_flow ? "point in-flow" : "point" }));
      const labelOnLeft = subdomain.complexity > 7;
      svg.append(svgElement(document, "text", {
        x: labelOnLeft ? x - 13 : x + 13, y: y + 4, "text-anchor": labelOnLeft ? "end" : "start", class: subdomain.in_flow ? "point-label strong" : "point-label",
      }, subdomain.name));
    }
    const wrapper = element(document, "div");
    wrapper.append(scrollable(document, svg));
    const notes = chart.subdomains.filter(subdomain => subdomain.note);
    if (notes.length) wrapper.append(list(document, notes.map(subdomain => `${subdomain.name}: ${subdomain.note}`)));
    return wrapper;
  }

  // ---------- context map ----------

  function renderContextMap(document, contextMap) {
    const cell = { width: 320, height: 220 };
    const box = { width: 180, height: 76 };
    const columns = Math.max(...contextMap.contexts.map(context => context.column)) + 1;
    const rows = Math.max(...contextMap.contexts.map(context => context.row)) + 1;
    const width = columns * cell.width;
    const height = rows * cell.height;
    const svg = svgElement(document, "svg", { viewBox: `0 0 ${width} ${height}`, class: "diagram", style: `min-width:${Math.min(width, 900)}px`, role: "img", "aria-label": "Context map" });

    const boxes = {};
    for (const context of contextMap.contexts) {
      boxes[context.id] = {
        x: context.column * cell.width + (cell.width - box.width) / 2,
        y: context.row * cell.height + (cell.height - box.height) / 2,
        width: box.width,
        height: box.height,
      };
    }

    for (const relationship of contextMap.relationships || []) {
      const upstreamBox = boxes[relationship.upstream];
      const downstreamBox = boxes[relationship.downstream];
      const upstreamCenter = { x: upstreamBox.x + box.width / 2, y: upstreamBox.y + box.height / 2 };
      const downstreamCenter = { x: downstreamBox.x + box.width / 2, y: downstreamBox.y + box.height / 2 };
      const start = borderPoint(upstreamBox, downstreamCenter);
      const end = borderPoint(downstreamBox, upstreamCenter);
      const inFlow = relationship.in_flow !== false;
      svg.append(svgElement(document, "line", {
        x1: start.x, y1: start.y, x2: end.x, y2: end.y,
        class: `relation ${relationship.kind}${inFlow ? "" : " dim"}`,
      }));

      const directed = relationship.kind === "upstream-downstream" || relationship.kind === "customer-supplier";
      const length = Math.hypot(end.x - start.x, end.y - start.y) || 1;
      const unit = { x: (end.x - start.x) / length, y: (end.y - start.y) / length };
      const badgeAt = (point, direction) => ({ x: point.x + unit.x * 18 * direction, y: point.y + unit.y * 18 * direction });
      if (directed) {
        const ends = [
          { point: badgeAt(start, 1), letter: "U", roles: relationship.upstream_roles || [] },
          { point: badgeAt(end, -1), letter: "D", roles: relationship.downstream_roles || [] },
        ];
        for (const { point, letter, roles } of ends) {
          svg.append(svgElement(document, "circle", { cx: point.x, cy: point.y, r: 10, class: "badge" }));
          svg.append(svgElement(document, "text", { x: point.x, y: point.y + 4, "text-anchor": "middle", class: "badge-text" }, letter));
          if (roles.length) {
            svg.append(svgElement(document, "text", { x: point.x + 14, y: point.y - 8, class: "role-text" }, roles.join(", ")));
          }
        }
      }
      const kindLabel = { "customer-supplier": "Customer / Supplier", partnership: "Partnership", "shared-kernel": "Shared Kernel", "separate-ways": "Separate Ways" }[relationship.kind];
      const labelLines = [kindLabel, ...wrapWords(relationship.label || "", 24)].filter(Boolean);
      if (labelLines.length) {
        const normal = { x: -unit.y, y: unit.x };
        if (normal.x < 0 || (normal.x === 0 && normal.y > 0)) { normal.x = -normal.x; normal.y = -normal.y; }
        const isVertical = Math.abs(unit.x) < 0.3;
        const isHorizontal = Math.abs(unit.y) < 0.3;
        const middle = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
        const anchor = isHorizontal ? "middle" : "start";
        const position = isHorizontal
          ? { x: middle.x, y: middle.y - 10 - (labelLines.length - 1) * 6.5 }
          : { x: middle.x + normal.x * (isVertical ? 14 : 12), y: middle.y + normal.y * 12 };
        svg.append(multilineText(document, labelLines, position.x, position.y, { "text-anchor": anchor, class: "relation-label" }, 13));
      }
    }

    for (const context of contextMap.contexts) {
      const contextBox = boxes[context.id];
      svg.append(svgElement(document, "rect", {
        x: contextBox.x, y: contextBox.y, width: contextBox.width, height: contextBox.height, rx: 38,
        class: `context ${context.kind}${context.in_flow ? " in-flow" : ""}`,
      }));
      const lines = wrapWords(context.name, 20);
      svg.append(multilineText(document, lines, contextBox.x + box.width / 2, contextBox.y + box.height / 2 - 6, { "text-anchor": "middle", class: "context-name" }));
      svg.append(svgElement(document, "text", {
        x: contextBox.x + box.width / 2, y: contextBox.y + box.height - 10, "text-anchor": "middle", class: "context-kind",
      }, context.kind));
    }

    const wrapper = element(document, "div");
    wrapper.append(scrollable(document, svg));
    const roles = new Set((contextMap.relationships || []).flatMap(relationship => [...(relationship.upstream_roles || []), ...(relationship.downstream_roles || [])]));
    const legend = element(document, "p", "muted", "U = upstream, D = downstream. ");
    legend.append([...roles].map(role => `${role} = ${ROLE_NAMES[role]}`).join(", ") + (roles.size ? "." : ""));
    wrapper.append(legend);
    const notes = contextMap.contexts.filter(context => context.note);
    if (notes.length) wrapper.append(list(document, notes.map(context => `${context.name}: ${context.note}`)));
    return wrapper;
  }

  // ---------- domain story ----------

  const ICONS = {
    person: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 9a7 7 0 0 1 14 0z",
    group: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20a6 6 0 0 1 12 0zm8 0a6 6 0 0 1 12 0z",
    system: "M3 4h18v12H3zM8 20h8M12 16v4",
    object: "M6 2h9l5 5v15H6zM15 2v5h5",
  };

  function icon(document, name) {
    const svg = svgElement(document, "svg", { viewBox: "0 0 24 24", class: "icon", "aria-hidden": "true" });
    const filled = name === "person" || name === "group";
    svg.append(svgElement(document, "path", { d: ICONS[name], fill: filled ? "currentColor" : "none", stroke: "currentColor", "stroke-width": 1.8 }));
    return svg;
  }

  function renderDomainStory(document, story) {
    const actors = Object.fromEntries(story.actors.map(actor => [actor.id, actor]));
    const wrapper = element(document, "div", "story-board");
    story.sentences.forEach((sentence, index) => {
      const row = element(document, "div", "story-sentence");
      row.append(element(document, "span", "story-number", String(index + 1)));
      const actor = actors[sentence.actor];
      const actorChip = element(document, "span", "story-actor");
      actorChip.append(icon(document, actor.kind || "person"), actor.name);
      row.append(actorChip, element(document, "span", "story-activity", `${sentence.activity} →`));
      const objectChip = element(document, "span", "story-object");
      objectChip.append(icon(document, "object"), sentence.object);
      row.append(objectChip);
      if (sentence.target) {
        const target = actors[sentence.target];
        row.append(element(document, "span", "story-activity", sentence.preposition || "to"));
        const targetChip = element(document, "span", "story-actor");
        targetChip.append(icon(document, target.kind || "person"), target.name);
        row.append(targetChip);
      }
      if (sentence.note) row.append(element(document, "span", "story-note", sentence.note));
      wrapper.append(row);
    });
    return wrapper;
  }

  // ---------- page wiring ----------

  const SECTIONS = [
    { key: "core_domain_chart", id: "core-domain", render: (document, model) => renderCoreDomainChart(document, model.core_domain_chart) },
    { key: "context_map", id: "context-map", render: (document, model) => renderContextMap(document, model.context_map) },
    { key: "domain_story", id: "domain-story", render: (document, model) => renderDomainStory(document, model.domain_story) },
  ];

  function render(model, document) {
    for (const section of SECTIONS) {
      const sectionElement = document.getElementById(`${section.id}-section`);
      if (!sectionElement) continue;
      const value = model[section.key];
      if (!value || (Array.isArray(value) && !value.length)) {
        sectionElement.hidden = true;
        continue;
      }
      document.getElementById(`${section.id}-body`).append(section.render(document, model));
    }
  }

  const api = { validate, render };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DddViews = api;
})(typeof window !== "undefined" ? window : globalThis);
