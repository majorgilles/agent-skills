#!/usr/bin/env node
// Usage: node extract.js <page.html> <flow.json>
// Recovers the flow file embedded in a published page, so a flow can be updated without a copy on disk.
"use strict";

const fs = require("fs");

const [pagePath, outputPath] = process.argv.slice(2);
if (!pagePath || !outputPath) {
  console.error("Usage: node extract.js <page.html> <flow.json>");
  process.exit(1);
}

const page = fs.readFileSync(pagePath, "utf8");
const match = page.match(/FlowRender\.mount\((\{[\s\S]*\}), document\);/);
if (!match) {
  console.error("error: no embedded flow found. Is this a page built by visualize-flow?");
  process.exit(1);
}
fs.writeFileSync(outputPath, `${JSON.stringify(JSON.parse(match[1]), null, 2)}\n`);
console.log(`flow: ${outputPath}`);
