#!/bin/bash
# Link every skill in skills/ into ~/.agents/skills and ~/.claude/skills. A skill already installed under the same
# name as a real folder (not a link) is moved to ~/.agents/skills-backup/ first, never deleted.
set -euo pipefail
repo=$(cd "$(dirname "$0")" && pwd)
backup=~/.agents/skills-backup/$(date +%Y%m%d-%H%M%S)

for target in ~/.agents/skills ~/.claude/skills; do
  mkdir -p "$target"
  for skill in "$repo"/skills/*/; do
    name=$(basename "$skill")
    if [ -e "$target/$name" ] && [ ! -L "$target/$name" ]; then
      where="$backup/$(basename "$(dirname "$target")")"
      mkdir -p "$where" && mv "$target/$name" "$where/$name"
      echo "backed up $target/$name to $where/$name"
    fi
    ln -sfn "${skill%/}" "$target/$name"
  done
done
echo "Linked $(ls -d "$repo"/skills/*/ | wc -l) skills into ~/.agents/skills and ~/.claude/skills."
