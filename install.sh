#!/bin/bash
# Link every skill in skills/ into ~/.agents/skills, ~/.claude/skills and ~/.pi/agent/skills (if pi is installed).
# A real folder with the same name is moved to ~/.agents/skills-backup/, and links to removed skills are deleted.
set -euo pipefail
repo=$(cd "$(dirname "$0")" && pwd)
backup=~/.agents/skills-backup/$(date +%Y%m%d-%H%M%S)

git -C "$repo" config core.hooksPath .githooks

targets=(~/.agents/skills ~/.claude/skills)
[ -d ~/.pi/agent ] && targets+=(~/.pi/agent/skills)

for target in "${targets[@]}"; do
  mkdir -p "$target"
  for skill in "$repo"/skills/*/; do
    name=$(basename "$skill")
    if [ -e "$target/$name" ] && [ ! -L "$target/$name" ]; then
      where="$backup${target#"$HOME"}"
      mkdir -p "$where" && mv "$target/$name" "$where/$name"
      echo "backed up $target/$name to $where/$name"
    fi
    ln -sfn "${skill%/}" "$target/$name"
  done
  for link in "$target"/*; do
    if [ -L "$link" ] && [ ! -e "$link" ] && [[ "$(readlink "$link")" == "$repo/skills/"* ]]; then
      rm "$link" && echo "removed $link: its skill is no longer in this repo"
    fi
  done
done
echo "Linked $(ls -d "$repo"/skills/*/ | wc -l | tr -d ' ') skills into ${targets[*]/#$HOME/~}."
