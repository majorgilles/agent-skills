#!/bin/sh
# The accuracy gate: verify.py (words and code lines in order) and audit.py (every character, drawing, figure pixel,
# exercise number) on every content file. Prints one line per file and exits 1 if anything is unaccounted for.
# Pixel checks render SVG crops in Chromium (Playwright; CHROMIUM=/path/to/chrome to pick a binary).
fail=0
for f in content/*.html; do
  v=$(python tools/verify.py "$f" | tail -1 | sed -E 's/.*, ([0-9]+) discrepancies.*/\1/')
  a=$(python tools/audit.py "$f" | head -1)
  miss=$(echo "$a" | sed -E 's/.*\| missing ([0-9]+).*/\1/'); extra=$(echo "$a" | sed -E 's/.*\| extra ([0-9]+).*/\1/')
  draw=$(echo "$a" | sed -E 's/.*uncovered drawings ([0-9]+).*/\1/'); pix=$(echo "$a" | sed -E 's/.*pixel mismatches ([0-9]+).*/\1/')
  st=$(echo "$a" | sed -E 's/.*structure issues ([0-9]+).*/\1/'); neg=$(echo "$a" | sed -E 's/.*negations lost ([0-9]+).*/\1/'); bar=$(echo "$a" | sed -E 's/.*bars lost ([0-9]+).*/\1/')
  ok=OK; [ "$v$miss$extra$draw$pix$st$neg$bar" = "00000000" ] || { ok=CHECK; fail=1; }
  printf '%-22s %-5s verify %s | chars missing %s extra %s | drawings %s | pixels %s | structure %s | negations %s | bars %s\n' "$(basename "$f")" "$ok" "$v" "$miss" "$extra" "$draw" "$pix" "$st" "$neg" "$bar"
done
echo "details: work/audit/<file>.json (+ PNGs of anything unaccounted for)"
exit $fail
