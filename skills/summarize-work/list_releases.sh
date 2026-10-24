#!/usr/bin/env bash
# Usage: list_releases.sh YYYY-MM-DD owner/repo [owner/repo ...]
# Prints each release published on that local day that contains commits of the current GitHub user,
# with those commits only. A release counts its commits since the previous release of the same
# component (the tag prefix before "-v", for example "backend" or "bot").
set -euo pipefail

day="$1"
shift
me=$(gh api user -q .login)

for repo in "$@"; do
  releases=$(gh release list -R "$repo" --limit 100 --json tagName,publishedAt,isDraft \
    -q '.[] | select(.isDraft | not) | "\(.publishedAt) \(.tagName)"' | sort -t' ' -k1.1,1.16r -k2,2)
  previous_commits=""
  printf '%s\n' "$releases" | while read -r published tag; do
    [ -n "$tag" ] || continue
    local_day=$(jq -rn --arg time "$published" '$time[0:19] + "Z" | fromdateiso8601 | localtime | strftime("%Y-%m-%d")')
    [ "$local_day" = "$day" ] || continue
    local_time=$(jq -rn --arg time "$published" '$time[0:19] + "Z" | fromdateiso8601 | localtime | strftime("%H:%M")')
    # A plain "v1.2.3" tag has no component: its previous release is the previous plain tag.
    if [[ "$tag" == v[0-9]* ]]; then tag_pattern='^v[0-9]'; else tag_pattern="^${tag%-v*}-v[0-9]"; fi
    previous=$(printf '%s\n' "$releases" | awk -v tag="$tag" -v pattern="$tag_pattern" '
      found && $2 ~ pattern { print $2; exit }
      $2 == tag { found = 1 }')
    # The first release of a component compares with the release just before it, whatever its prefix.
    [ -n "$previous" ] || previous=$(printf '%s\n' "$releases" | awk -v tag="$tag" 'found { print $2; exit } $2 == tag { found = 1 }')
    [ -n "$previous" ] || continue
    commits=$(gh api "repos/$repo/compare/$previous...$tag" -q ".commits[]
      | select(.author.login == \"$me\")
      | .commit.message | split(\"\n\")[0]
      | select((startswith(\"chore: release\") or contains(\"release-please--branches\")) | not)")
    [ -n "$commits" ] || continue
    # Tags released together (common with backend) carry the same commits: print them once.
    [ "$commits" != "$previous_commits" ] || continue
    echo "=== $repo $tag ($local_time), since $previous"
    printf '%s\n' "$commits" | sed 's/^/  - /'
    echo
    previous_commits="$commits"
  done
done
