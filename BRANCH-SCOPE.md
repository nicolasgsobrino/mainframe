# Branch Scope (authoritative)

Every agent working on this repo MUST read this file first, before
DEMO-SPRINT-PLAN.md, PATCH-PLAN.md, .clinerules/scratchpad.md, or any
other plan document.

## Current Branch Rules
- If the branch name starts with `wave<N>/<program>`, the ONLY
  deliverable is:
    translations/gold-candidate/<PROGRAM>.md  AND
    validation/structure/<PROGRAM>_cfg.json   AND
    gate_compare.py 11/11 PASS                AND
    lint_cobol 62/0/2 baseline preserved
  Everything else is out of scope.

- If the branch name starts with `fix/<topic>`, the scope is a SINGLE
  file or a SINGLE bug class. No unrelated edits.

- If the branch name starts with `chore/<topic>`, the scope is
  infrastructure/docs/rules only. No pipeline code changes.

## Forbidden without explicit human approval
- Running any dispatch that spends tokens/$ (Block F T04 judge, batch
  LLM runs, etc.)
- Squashing commits that contain audit trail
- Editing validators (extract_cfg_summary.py, gate_compare.py,
  extract_ground_truth.py, extract_md_claims.py, lint_cobol.py)
- Hand-editing anything under validation/structure/ or validation/rekt/
- Merging PRs (human-only action)

## Mandatory pre-commit checklist (every agent, every commit)
1. `git status -sb` — show current branch + clean tree
2. Confirm branch name matches a scope rule above
3. Confirm files being committed are in scope for that branch
4. For any `.md` change: `py validation/extract_md_claims.py <PROG>` must
   PASS
5. For any validation/ change: `py validation/gate_compare.py` must
   return 11/11 (or whatever the current corpus count is)
6. For any lint change: `py validation/lint_cobol/lint_cobol.py
   --fail-on-error` must match committed baseline exactly

## Handoff requirement
End every agent turn with:
- Current branch
- Files changed (git diff --stat)
- Exit codes of any validators run
- Explicit next action requested OR "awaiting human instruction"
