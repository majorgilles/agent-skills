# omnibook-converter

An agent skill that converts a PDF book (text or scanned) into a verbatim **.omnibook** package for
[Gilles's Omnibook Reader](https://github.com/majorgilles/omarchy-apps/tree/main/omnibook_reader):

- text copied by script from the PDF text layer (scans: Tesseract OCR, doubtful words settled by a vote with another
  OCR layer and blind model reads, a human review page for the rest), never retyped by a model
- figures as exact crops (vector SVG, or PNG for raster art and scans); tables, code listings with cueball annotations,
  notes, sidebars, captions and exercise blocks as real HTML
- a gate that proves it: every word in order, every character, every drawing and every figure's pixels accounted for
- one profile per book (`profile.json`), with a Manning MEAP profile included

The reader adds themes and fonts, bookmarks, highlights and notes, search, exercise checking with your own LLM key,
proof maps, runnable Python/JavaScript and Google Drive sync.

## Install

```sh
git clone https://github.com/majorgilles/agent-skills ~/dev/agent-skills && ~/dev/agent-skills/install.sh
```

Then ask your agent to "convert this PDF book for the Omnibook reader". `SKILL.md` has the procedure.

## Rights

Purchased books are personal study copies: keep the package in your own library (local folder or your Google Drive).
Use DRM-free PDFs you legitimately own; the skill does not remove DRM. Openly licensed books keep their attribution.
