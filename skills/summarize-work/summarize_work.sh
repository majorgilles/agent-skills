#!/usr/bin/env bash
# Usage: summarize_work.sh [YYYY-MM-DD]   (default: the previous working day, in the local time zone)
# Prints, for each Claude Code session with prompts on that day: its folder, prompt count, time span,
# the first prompts, the links it mentioned, and the end of its last reply.
set -euo pipefail

days_back=$([ "$(date +%u)" = 1 ] && echo 3 || echo 1)  # Monday reaches back to Friday
day="${1:-$(date -v-"${days_back}"d +%Y-%m-%d)}"
projects="$HOME/.claude/projects"

local_day='(.timestamp // "")[0:19] + "Z" | fromdateiso8601 | localtime | strftime("%Y-%m-%d")'
local_time='(.timestamp // "")[0:19] + "Z" | fromdateiso8601 | localtime | strftime("%H:%M")'

find "$projects" -maxdepth 2 -name '*.jsonl' -newermt "$day 00:00" -print0 |
  while IFS= read -r -d '' file; do
    prompts=$(jq -r --arg day "$day" "
      select(.type == \"user\" and (.timestamp // \"\") != \"\")
      | select(($local_day) == \$day)
      | ($local_time) as \$time
      | (if (.message.content | type) == \"string\" then .message.content
         else ([.message.content[]? | select(.type == \"text\") | .text] | join(\" \")) end) as \$text
      | select(\$text != \"\")
      | (\$text | capture(\"^<bash-input>(?<command>[^<]*)</bash-input>\").command | \"$ \" + .) // \$text
      | \"\(\$time) \(gsub(\"\\n\"; \" \"))\"" "$file" 2>/dev/null |
      grep -vE '^[0-9:]+ *(<|$|Base directory for this skill:|\[Request interrupted|This session is being continued|\(Re-invocation of|Skill /)' || true)
    [ -n "$prompts" ] || continue

    folder=$(basename "$(dirname "$file")" | sed 's/^-Users-[^-]*-//; s/^-herdr-worktrees-//')
    count=$(printf '%s\n' "$prompts" | wc -l | tr -d ' ')
    first=$(printf '%s\n' "$prompts" | head -1 | cut -c1-5)
    last=$(printf '%s\n' "$prompts" | tail -1 | cut -c1-5)

    replies=$(jq -r --arg day "$day" "
      select(.type == \"assistant\" and (.timestamp // \"\") != \"\")
      | select(($local_day) == \$day)
      | .message.content[]? | select(.type == \"text\") | .text" "$file" 2>/dev/null || true)

    echo "=== $folder  ($(basename "$file" | cut -c1-8))  $count prompts  $first-$last"
    printf '%s\n' "$prompts" | head -12 | cut -c1-200 | sed 's/^/  > /'
    links=$(printf '%s\n' "$prompts" "$replies" |
      grep -oE 'https://github\.com/[^ )>]+/pull/[0-9]+|GEN-[0-9]+|INIT-[0-9]+' | sort -u | tr '\n' ' ' || true)
    [ -n "$links" ] && echo "  links: $links"
    echo "  last reply: $(printf '%s' "$replies" | tail -c 500 | tr '\n' ' ' | LC_ALL=C tr -cd '[:print:]')"
    echo
  done
