# Pass 1 / Pass 2 Ambiguity Patch Plan

**Branch:** `fix/pass1-pass2-ambiguity-patches`  
**Thread Date:** 2026-04-29  
**Goal:** All 5 patches committed, validated, and ready for local checkout by end of day.

> **Housekeeping note (2026-05-05):** File relocated from repo root to `docs/ops/` as part of Operation Tidy Commit D (OP-3-02). Content unchanged.

---

## Status Legend

| Symbol | Meaning |
|---|---|
| ⬜ | Not started |
| 🔄 | In progress |
| ✅ | Committed to branch |
| 🧪 | Locally tested by Mark |

---

## Patch Summary

| # | File | Problem | Status |
|---|---|---|---|
| P1 | `scripts/pass1_annotate.py` | CFG edges are sequential seq±1 instead of real call-graph edges | ✅ |
| P2 | `scripts/pass1_annotate.py` | Copybook fields unresolved — inventory built from CFG JSON not from `cobc -E` expanded source | ✅ |
| P3 | `scripts/pass1_annotate.py` | `pending_branch_context` bleeds past `END-IF` / `END-EVALUATE` scope | ✅ |
| P4 | `scripts/pass2_llm.py` | `max_tokens=400` truncates EVALUATE/CICS payloads causing PARTIAL loops | ✅ |
| P5 | `scripts/pass1_annotate.py` | `EXEC CICS` not in `BRANCH_VERBS` — CICS state-machine branches unannotated | ✅ |

> **Note (2026-04-30):** All 5 patches merged to `main`. Status updated to ✅ to reflect merge. See README.md → "Stage 1 — Annotation (Pass 1)" for the authoritative active-patch list.

---

## Commit Plan (one commit per patch)

```
commit 1 — fix(pass1): replace seq±1 CFG edges with real paragraph call-graph edges
commit 2 — fix(pass1): rebuild data_items_inventory from cobc -E expanded source
commit 3 — fix(pass1): track IF/EVALUATE scope depth to clear pending_branch_context
commit 4 — fix(pass2): add per-verb max_tokens map to prevent PARTIAL truncation loops
commit 5 — fix(pass1): add CICS branch command detection to BRANCH_VERBS handling
```

---

## P1 — Real CFG Edges

### Problem
`cfg_predecessors` is hardcoded `[seq - 1]` and `cfg_successors` is `[seq + 1]` — a
pure sequential walk with no knowledge of PERFORM targets, CICS XCTL/LINK destinations,
or GO TO branches. The LLM sees no cross-paragraph flow context, which is the primary
cause of semantic ambiguity in CICS pseudo-conversational programs like CardDemo.

### Root Cause (line in pass1_annotate.py)
```python
"cfg_predecessors": [seq - 1] if seq > 1 else [],
"cfg_successors": [seq + 1],
```

### Fix
After annotation loop, make a second pass over the annotation list. For each annotation
whose verb is `PERFORM` or `GO TO`, look up the target paragraph name in
`cfg["paragraphs"]` and annotate the first statement of that paragraph with a real
predecessor edge. Emit `cfg_perform_target` and `cfg_goto_target` keys on the calling
statement for Pass 2 context.

### Acceptance Criteria
- `cfg_successors` on a `PERFORM` statement contains the seq of the first statement
  of the named paragraph (if resolvable from CFG JSON).
- `cfg_predecessors` on the first statement of a called paragraph lists all PERFORM/GO TO
  statements that target it.
- Seq±1 fallback retained for statements where no CFG edge resolves.

### Status: ✅ Merged to main (2026-04-30)

---

## P2 — Copybook-Expanded Data Inventory

### Problem
`data_items_inventory` is built from `cfg["data_items"]` — the set Cobol-REKT walked.
Copybook fields that were not fully resolved by the CFG tool appear as `unresolved`
operands, which causes the LLM to lower confidence for every proposition that touches
a copybook field, even when the field name is unambiguous.

### Root Cause (line in pass1_annotate.py)
```python
data_items_inventory = {d["name"].upper() for d in cfg.get("data_items", []) if d.get("name")}
```

### Fix
After `preprocess()` runs (which already calls `cobc -E`), scan the preprocessed lines
for data-item definitions: lines in the DATA DIVISION matching the pattern
`^\s+(\d{2})\s+([A-Z0-9][A-Z0-9-]*)` (level number + name). Union this set with the
existing CFG inventory. This catches all COPY-expanded fields without requiring a
separate copybook expansion step.

### Acceptance Criteria
- Fields from COPY members (e.g. DFHCOMMAREA fields, copybook record layouts) appear
  as `working-storage` rather than `unresolved` in the annotation output.
- Zero regression on fields that were already resolved via the CFG JSON path.

### Status: ✅ Merged to main (2026-04-30)

---

## P3 — Branch Context Scope Depth

### Problem
`pending_branch_context` is set on every `IF`/`EVALUATE` and never cleared until
the next branch verb. Statements after `END-IF` or `END-EVALUATE` inherit the stale
branch context and the LLM interprets them as conditionally guarded when they are
unconditional sequential code.

### Root Cause (line in pass1_annotate.py)
```python
pending_branch_context = rec["cfg_branch_context"]  # set, never cleared by END-IF
```

### Fix
Add a `_scope_depth` counter (integer, init 0) alongside `pending_branch_context`.
On `IF` or `EVALUATE` verb: increment depth, set context.
On scope terminator tokens (`END-IF`, `END-EVALUATE`): decrement depth, and if depth
reaches 0 clear `pending_branch_context = None`.
The `SCOPE_TERMINATORS` set already exists in the code — route it through the
statement loop rather than only using it for paragraph phantom filtering.

### Acceptance Criteria
- A statement immediately following `END-IF.` has `cfg_branch_context = null`.
- Nested IF blocks (depth > 1) correctly maintain context until the outermost
  END-IF is consumed.
- Selftest passes without regression (COBSWAIT has no IF blocks, so selftest
  is unaffected; add a targeted unit assertion in validate_pass1.py).

### Status: ✅ Merged to main (2026-04-30)

---

## P4 — Per-Verb max_tokens Map

### Problem
All LLM payloads use `max_tokens=400` regardless of verb complexity. EVALUATE blocks
with multiple WHEN arms and CICS interactions with RESP/RESP2 checks regularly exceed
400 tokens in their JSON response, causing truncated JSON that the merge step rejects,
which leaves the proposition as PARTIAL and re-queues it.

### Root Cause (line in pass2_llm.py)
```python
ap.add_argument("--max-tokens", type=int, default=400)
# ... all payloads use the same args.max_tokens
```

### Fix
Add a `VERB_MAX_TOKENS` dict in `pass2_llm.py`:
```python
VERB_MAX_TOKENS = {
    "EVALUATE":         700,
    "EXEC CICS":        600,
    "EXEC SQL":         600,
    "IF":               500,
    "CALL":             500,
    "MOVE CORRESPONDING": 500,
}
DEFAULT_MAX_TOKENS = 400
```
In `build_payload()`, replace `max_tokens` with
`VERB_MAX_TOKENS.get(prop["verb"], max_tokens)` so the CLI default is still
overrideable but complex verbs get headroom automatically.

### Acceptance Criteria
- A proposition with `verb = "EVALUATE"` emits a payload with `max_tokens = 700`.
- CLI `--max-tokens` still overrides the default for all verbs (regression guard).
- No change to the wire payload structure for verbs not in `VERB_MAX_TOKENS`.

### Status: ✅ Merged to main (2026-04-30)

---

## P5 — CICS Branch Command Detection

### Problem
`EXEC CICS` is in `KNOWN_VERBS` but not in `BRANCH_VERBS`. CICS commands like
`HANDLE CONDITION`, `RETURN` with COMMAREA, and `XCTL`/`LINK` are conditional branch
points that drive the pseudo-conversational state machine in CardDemo. Without
branch annotation they are emitted to Pass 2 as unconditional `cics-interaction`,
causing the LLM to assign `sequential` or `cics-interaction` when the correct
pattern is `state-machine` or `guard-with-override`.

### Root Cause (line in pass1_annotate.py)
```python
BRANCH_VERBS = {"IF", "EVALUATE", "GO TO"}  # EXEC CICS absent
```

### Fix
Add a `CICS_BRANCH_COMMANDS` set:
```python
CICS_BRANCH_COMMANDS = {"HANDLE", "RETURN", "XCTL", "LINK", "ABEND"}
```
In the annotation loop, after detecting `EXEC CICS`, extract the first token of
the remaining text (`rest`) and check if it is in `CICS_BRANCH_COMMANDS`. If yes,
set `cfg_branch_context = f"EXEC CICS {cics_command} {rest_summary}"` and set
`is_cics_branch = True` on the annotation record. Pass 2 system prompt already
includes `state-machine` in `SEMANTIC_PATTERN_ENUM` so no Pass 2 changes needed.

### Acceptance Criteria
- An `EXEC CICS RETURN TRANSID(...)` statement has `cfg_branch_context` set and
  `is_cics_branch = True`.
- An `EXEC CICS SEND MAP(...)` (non-branch) has `cfg_branch_context = null`.
- Selftest unaffected (COBSWAIT uses `EXEC CICS` but only `ACCEPT`/`MOVE`/`CALL`/
  `STOP RUN` are annotated per the current 4-statement assertion).

### Status: ✅ Merged to main (2026-04-30)

---

## Local Checkout Instructions (for tonight)

```bash
git fetch origin
git checkout fix/pass1-pass2-ambiguity-patches
git log --oneline   # should show 5 patch commits + this plan commit

# Selftest pass1 (requires GnuCOBOL installed):
python scripts/pass1_annotate.py --selftest

# Validate pass1 on COCRDUPC:
python scripts/pass1_annotate.py \
  --src app/cbl/COCRDUPC.cbl \
  --cfg validation/structure/COCRDUPC_cfg.json \
  --program-id COCRDUPC \
  --out validation/pass1/COCRDUPC_annotations.json \
  --phantoms-out validation/pass1/COCRDUPC_phantoms.json

# Inspect unresolved count (should be lower than baseline after P2):
python -c "import json; a=json.load(open('validation/pass1/COCRDUPC_annotations.json')); print('unresolved:', sum(1 for x in a if x.get('operand_unresolved')))"

# Validate pass2 payload generation:
python scripts/pass2_llm.py \
  --propositions validation/pass2/COCRDUPC_propositions.json \
  --program-id COCRDUPC \
  --out validation/pass2/COCRDUPC_llm_requests.jsonl

# Check EVALUATE payloads have max_tokens=700 after P4:
python -c "import json; [print(l['verb'] if '_routing' not in l else l['_routing']['verb'], l.get('max_tokens')) for l in [json.loads(x) for x in open('validation/pass2/COCRDUPC_llm_requests.jsonl')]]"
```

---

## Notes / Decisions Log

| Date | Note |
|---|---|
| 2026-04-29 | Branch created from main @ cd4f747 |
| 2026-04-29 | All 5 problems identified from pass1_annotate.py + pass2_llm.py code review |
| 2026-04-30 | All 5 patches merged to main per README.md Stage 1 active-patch list |
| 2026-05-05 | File relocated from repo root to `docs/ops/` as part of Operation Tidy Commit D (OP-3-02). Content unchanged. |
