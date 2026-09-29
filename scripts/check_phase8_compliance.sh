#!/usr/bin/env bash
set -euo pipefail

minimum_commits=35
commit_count=$(git rev-list --all --count)
if (( commit_count < minimum_commits )); then
  echo "Expected at least ${minimum_commits} commits across all branches; found ${commit_count}" >&2
  exit 1
fi

echo "Commit count across all branches: ${commit_count}"
echo "Partner contribution breakdown:"
git shortlog -sn --all

required_files=(
  docs/evidence/01_branch_protection.png
  docs/evidence/01_branch_protection.md
  docs/evidence/02_ci_pipeline_red.png
  docs/evidence/02_ci_pipeline_green.png
  docs/evidence/02_red_green_ci_notes.md
  docs/evidence/03_merge_conflict_markers.png
  docs/evidence/03_merge_conflict_resolved.png
  docs/evidence/03_conflict_notes.md
)

missing=0
for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing evidence file: ${file}" >&2
    missing=1
  fi
done

if (( missing != 0 )); then
  exit 1
fi

echo "Phase 8 evidence files: complete"