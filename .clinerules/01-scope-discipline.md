# Cline Agent Discipline Rules

## Rule 1 — Read BRANCH-SCOPE.md first, always
Before reading any plan file, scratchpad, or memory bank, read
/BRANCH-SCOPE.md and apply its current-branch rules. If BRANCH-SCOPE.md
is missing, halt and ask for human input.

## Rule 2 — Plan files are advisory, not authoritative
DEMO-SPRINT-PLAN.md, PATCH-PLAN.md, .clinerules/scratchpad.md, and any
other plan or tracker are ADVISORY. They describe what might be done.
They do NOT describe what THIS branch is doing. If a plan file block
conflicts with BRANCH-SCOPE.md, BRANCH-SCOPE.md wins.

## Rule 3 — No autonomous pipeline execution
Never execute any of these without explicit human instruction in the
current turn:
- Block F T04 judge dispatch (or any 60+ payload batch)
- extract_cfg_summary.py --all --force
- Any git push
- Any git merge
- Any rm / Remove-Item on validation/ content

## Rule 4 — Read-only review by default
When asked to "review" or "check" anything, perform read-only analysis.
Do not write files, do not modify rules, do not update scratchpads.
End with a decision prompt for the human.

## Rule 5 — Scratchpads are ephemeral
.clinerules/scratchpad.md is read-once, written-once per session. Never
anchor work on a prior session's scratchpad. If a prior scratchpad
exists, treat it as stale context and overwrite after reading
BRANCH-SCOPE.md.

## Rule 6 — Evidence over memory
When reporting status, cite evidence from the filesystem or git, not
from any in-memory plan. Quote the exact command and output that proves
each claim.
