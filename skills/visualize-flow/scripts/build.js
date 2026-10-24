#!/usr/bin/env node
// Usage: node build.js <flow.json> [--html <page.html>] [--bpmn <diagram.bpmn>]
// Validates the flow and writes the HTML page (default: a temp folder); writes a .bpmn only when asked.
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const FlowRender = require("./flow-render.js");
const DddViews = require("./ddd-views.js");

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

function escapeHtml(text) {
  return text.replace(/[&<>]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[character]);
}

function main() {
  const options = parseArguments(process.argv.slice(2));
  const model = JSON.parse(fs.readFileSync(options.input, "utf8"));

  const { errors, warnings } = FlowRender.validate(model);
  errors.push(...DddViews.validate(model));
  warnings.forEach(warning => console.warn(`warning: ${warning}`));
  if (errors.length) {
    errors.forEach(error => console.error(`error: ${error}`));
    process.exit(1);
  }

  if (options.bpmn) {
    if (!model.bpmn) throw new Error("--bpmn asked, but the flow has no bpmn section.");
    fs.writeFileSync(options.bpmn, FlowRender.buildBpmnXml(model.bpmn));
    console.log(`bpmn: ${options.bpmn}`);
  }

  const htmlPath = options.html || path.join(os.tmpdir(), "visualize-flow", `${baseName(options.input)}.html`);
  fs.mkdirSync(path.dirname(htmlPath), { recursive: true });
  const read = name => fs.readFileSync(path.join(__dirname, name), "utf8");
  const page = read("template.html")
    .replace("{{TITLE}}", () => escapeHtml(model.title))
    .replace("{{RENDERER}}", () => read("flow-render.js"))
    .replace("{{DDD_VIEWS}}", () => read("ddd-views.js"))
    .replace("{{MODEL}}", () => JSON.stringify(model).replace(/</g, "\\u003c"));
  fs.writeFileSync(htmlPath, page);
  console.log(`html: ${htmlPath}`);
}

try {
  main();
} catch (error) {
  console.error(`error: ${error.message}`);
  process.exit(1);
}
