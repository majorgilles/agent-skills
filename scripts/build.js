#!/usr/bin/env node
// Usage: node build.js <flow.json> [--html <page.html>] [--bpmn <diagram.bpmn>]
// Validates the flow, writes the .bpmn next to the JSON, and writes the HTML page (default: a temp folder).
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const FlowRender = require("./flow-render.js");

function parseArguments(argv) {
  const options = { input: null, html: null, bpmn: null };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--html") options.html = argv[++index];
    else if (argument === "--bpmn") options.bpmn = argv[++index];
    else if (!options.input) options.input = argument;
    else throw new Error(`Unexpected argument: ${argument}`);
  }
  if (!options.input) throw new Error("Usage: node build.js <flow.json> [--html <page.html>] [--bpmn <diagram.bpmn>]");
  return options;
}

function baseName(input) {
  return path.basename(input).replace(/\.flow\.json$|\.json$/, "");
}

function main() {
  const options = parseArguments(process.argv.slice(2));
  const model = JSON.parse(fs.readFileSync(options.input, "utf8"));
  model.source = model.source || path.relative(process.cwd(), path.resolve(options.input));

  const { errors, warnings } = FlowRender.validate(model);
  warnings.forEach(warning => console.warn(`warning: ${warning}`));
  if (errors.length) {
    errors.forEach(error => console.error(`error: ${error}`));
    process.exit(1);
  }

  const name = baseName(options.input);
  if (model.bpmn) {
    const bpmnPath = options.bpmn || path.join(path.dirname(options.input), `${name}.bpmn`);
    fs.writeFileSync(bpmnPath, FlowRender.buildBpmnXml(model.bpmn));
    console.log(`bpmn: ${bpmnPath}`);
  }

  const htmlPath = options.html || path.join(os.tmpdir(), "visualize-flow", `${name}.html`);
  fs.mkdirSync(path.dirname(htmlPath), { recursive: true });
  const template = fs.readFileSync(path.join(__dirname, "template.html"), "utf8");
  const renderer = fs.readFileSync(path.join(__dirname, "flow-render.js"), "utf8");
  const safeJson = JSON.stringify(model).replace(/</g, "\\u003c");
  const page = template
    .replace("{{TITLE}}", () => model.title.replace(/[&<>]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[character]))
    .replace("{{RENDERER}}", () => renderer)
    .replace("{{MODEL}}", () => safeJson);
  fs.writeFileSync(htmlPath, page);
  console.log(`html: ${htmlPath}`);
}

try {
  main();
} catch (error) {
  console.error(`error: ${error.message}`);
  process.exit(1);
}
