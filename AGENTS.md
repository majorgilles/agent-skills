# agent-skills

This repo holds the user's own skills for coding agents, one folder per skill in `skills/`. Each folder has a
`SKILL.md`. Agents find the skills through links in `~/.agents/skills`, `~/.claude/skills` and, when pi is installed,
`~/.pi/agent/skills`. The links point back to this repo, so an edit here applies at once.

## Install the skills for the user

When the user asks to install, link or set up these skills:

1. Clone the repo to `~/dev/agent-skills` if it is not there yet:

   ```bash
   git clone git@github.com:majorgilles/agent-skills.git ~/dev/agent-skills
   ```

2. Run the install script:

   ```bash
   ~/dev/agent-skills/install.sh
   ```

   For each folder in `skills/`, it creates a link with the same name in `~/.agents/skills`, in
   `~/.claude/skills` and, when `~/.pi/agent` exists, in `~/.pi/agent/skills`. A real folder with that name is
   moved to `~/.agents/skills-backup/<timestamp>/` first. A link to a skill that this repo no longer has is
   removed. The script never deletes a skill folder.

3. Check the links. This prints nothing when every skill is linked correctly:

   ```bash
   repo=~/dev/agent-skills
   targets=(~/.agents/skills ~/.claude/skills)
   [ -d ~/.pi/agent ] && targets+=(~/.pi/agent/skills)
   for target in "${targets[@]}"; do
     for skill in "$repo"/skills/*/; do
       name=$(basename "$skill")
       [ "$(readlink "$target/$name")" = "${skill%/}" ] && [ -f "$target/$name/SKILL.md" ] \
         || echo "not linked: $target/$name"
     done
     find "$target" -maxdepth 1 -type l ! -exec test -e {} \; -print | sed 's/^/dangling: /'
   done
   ```

4. Tell the user how many skills are linked, and list any folder that the script moved to the backup.

Run the script again after you pull new skills or add one. It is safe to run any number of times.

## Add a skill

1. Create `skills/<name>/SKILL.md`. Its front matter needs `name` (the folder name) and `description` (what the
   skill does, then when to use it).
2. Add a row for it to the table in `README.md`, in alphabetical order.
3. Run `install.sh`, then the check above.
4. Commit and push.

This repo is public. Do not add company code, internal paths, customer data or secrets to a skill. Rewrite a skill
from work as generic guidance first.

## Leave alone

`~/.agents/skills` and `~/.claude/skills` also hold skills that this repo does not own: skills installed by the
`skills` CLI (listed in `~/.agents/.skill-lock.json`), skills installed by their own tool (such as `notebooklm`),
and `~/.claude/skills/synced`, which claude.ai manages. Do not move, link or delete them.
