#!/bin/sh
# Full rebuild from the PDF: convert every chapter -> swap checked LaTeX into math crops -> audit -> package.
set -e
rm -rf site/figs            # crops are regenerated; never package stale ones
sh tools/convert_all.sh
python tools/crops.py apply
for f in content/*.html; do python tools/audit.py "$f" --no-pixels > /dev/null || true; done   # summaries for book.json
python tools/package.py
