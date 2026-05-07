schema_version: "aifirst/1.0"
task_id: "T-2026-04-27-001"
task_name: "Demo Completion Sprint"
status: ACTIVE
author: "Mark Snow"
created: "2026-04-27T10:59:00-04:00"
last_updated: "2026-05-02T12:10:00-04:00"
target_completion: "2026-04-28T17:00:00-04:00"
budget_hours: 12
tracks:
  - code
  - language
  - rehearsal
gate_flow: "A/B (parallel) → C → D → E → F(bg) | G → H → I → J → K | L → M → N"
locked_phrases:
  - "scribe within the evidence envelope, not translator"
  - "witness-agnostic at the contract layer; each witness needs an adapter, gates and schema unchanged"
  - "deterministic substrate beneath your dashboard"
demo_success_criteria:
  - "Live walkthrough of COBSWAIT PASS case with all five tiers visible"
  - "Live walkthrough of CBACT01C pre-fix BLOCKED case"
  - "SHA provenance manifest displayed on screen"
  - "run.log scrolled live showing 84+ events"
  - "At least one partner question the substrate answers cleanly"
  - "Integration ask delivered with one named v2 pilot program"
demo_success_threshold:
  green: "6/6"
  yellow: "4-5/6 → debrief and schedule second meeting"
  red: "<4/6 → re-target audience or framing"
---

# Demo Completion Sprint — Working Plan

> **Living document.** Update checkboxes and gate statuses in real time.
> **Critical rule:** Snapshot before fix. COBSWAIT promotion is independent. Discovery before pitch. One commit window.

---

## Track 1 — Code (Day 1 Morning, ~4h)

### Gate: PRE-CODE
- [x] Repo is on `main`, clean working tree
- [x] All 6 pilot COBOL sources confirmed in `app/cbl/`
- [x] `.aifirst/runs/T-2026-04-23-001/run.log` has 84+ events (85 lines confirmed)
- [x] Validation reports exist in `validation/reports/` (125+ report files across all 6 pilot programs)

**PRE-CODE status:** `PASS`

---

### Block A — Preserve BLOCKED Headline Asset (45 min, parallel to B)

**Purpose:** The CBACT01C BLOCKED state is the #1 demo asset. Preserve before any fix work.

- [x] A.1 — Create branch `demo/blocked-cbact01c-snapshot` from current HEAD
- [x] A.2 — Create directory `demo/blocked-cbact01c-snapshot/`
- [x] A.3 — Copy into snapshot directory:
  - [x] `translations/baseline/CBACT01C.md`
  - [x] T02-R validation report (`CBACT01C_T02R.json`) from `validation/reports/`
  - [x] Additional: T01, T02, T03, T04, v12_T01, v12_T02, v12_T03, original COBOL source
- [x] A.4 — Write `demo/blocked-cbact01c-snapshot/README.md` with:
  - [x] What: the BLOCKED state
  - [x] Why: unqualified `ACCT-REISSUE-DATE` vs CFG-known qualified forms (`OUT-ACCT-REISSUE-DATE` / `WS-ACCT-REISSUE-DATE`)
  - [x] Proof: the system refused to hallucinate and halted cleanly
- [x] A.5 — Tag commit `demo-snapshot-v1` (points to `2175cf2`, pushed to remote)

**Block A validation:**
- [x] `demo/blocked-cbact01c-snapshot/` exists with 11 artifacts
- [x] README explains BLOCKED reason in ≤5 sentences (4 paragraphs, concise)
- [x] Tag `demo-snapshot-v1` exists on remote and points to `2175cf2`
- [x] Original `translations/baseline/CBACT01C.md` unchanged

**Block A status:** `PASS`

---

### Block B — Promote COBSWAIT to Gold (45 min, parallel to A)

**Purpose:** Single highest-leverage action. Unblocks Phase 4 and all downstream training.

- [x] B.1 — Created `translations/gold/` directory
- [x] B.2 — Copied `translations/gold-candidate/COBSWAIT.md` → `translations/gold/COBSWAIT.md`
- [x] B.3 — Verified tier results: T01=PASS, T02=PASS, T02-R=PASS, T03=PASS (1.0/0.95), T04=DEFERRED
- [x] B.4 — Computed SHA: `21e6845d3cfc70c1eca805f26f8f906faa42aea2`
- [x] B.5 — Committed and pushed on `feat/block-c-sha-provenance-manifest` (commit `0bffc18`); merged to main

**Block B validation:**
- [x] `translations/gold/COBSWAIT.md` exists on main (SHA `21e6845d3cfc70c1eca805f26f8f906faa42aea2`)
- [x] `translations/gold-candidate/COBSWAIT.md` still exists (preserved)
- [x] `run.log` gold_promotion event appended at line 85

**Block B status:** `PASS`

---

### Gate: POST-A/B
- [x] Block A and Block B both PASS
- [x] No uncommitted changes
- [x] `run.log` append-only integrity confirmed (85 lines, no overwrites)

**POST-A/B status:** `PASS`

---

### Block C — SHA Provenance Manifest (90 min)

**Purpose:** Cryptographic chain from source → CFG → Markdown → report. Partner compliance requirement.

- [x] C.1 — Created `.aifirst/runs/T-2026-04-23-001/provenance.md` with YAML header (7 fields)
- [x] C.2 — Populated 4-column manifest table, 6 programs, 24 SHAs
- [x] C.3 — All 24 SHAs verified via `git hash-object` (not just spot-check)
- [x] C.4 — Extended G1 scaffold template in AiFirst Protocol spec with provenance manifest section
- [x] C.5 — Committed and pushed; merged to main
- [x] C.6 — Docs consistency audit commit: table pipe syntax verified, verification example added, integrity note added

**Block C validation:**
- [x] `provenance.md` exists with valid YAML header (all 7 fields present)
- [x] All 6 rows populated, 24 non-null SHAs
- [x] Verification section includes concrete example command with expected output
- [x] Integrity note links manifest to run.log audit trail
- [x] G1 template updated

**Block C status:** `PASS`

---

### Block D — BMS Edge Declaration (15 min)

**Purpose:** Close "did you ignore the screen layer?" objection without scope expansion.

- [x] D.1 — Add `bms_maps:` block to COSGN00C YAML front-matter (map: COSGN0A, status: pending-extraction)
- [x] D.2 — Add `bms_maps:` block to COMEN01C YAML front-matter (map: COMEN01, status: pending-extraction)
- [x] D.3 — Verified YAML front-matter parses cleanly: COMEN01C T01=PASS, CBACT01C T01=PASS
- [x] D.4 — Committed `287a35b` and pushed to `feat/block-d-bms-edge-declaration`
- [x] D.5 — CBACT01C confirmed as batch program (no BMS screen layer — correct to omit)

**Block D validation:**
- [x] Both COSGN00C and COMEN01C have `bms_maps:` blocks with `translation_status: pending-extraction`
- [x] YAML front-matter parses cleanly (T01 verified for COMEN01C and CBACT01C)
- [x] CBACT01C body changes: validation section updated to `overall: PASS` — accepted as legitimate work
- [x] COMEN01C body changes: formatting/validation updates — accepted as legitimate work

**Block D status:** `PASS`

---

### Gate: PRE-FIX
- [x] CBACT01C snapshot safely tagged on remote (`demo-snapshot-v1` → `2175cf2`)
- [x] Block C merged to main ✅ AND Block D committed ✅
- [x] Safe to modify CBACT01C translation (snapshot preserved, BMS edges declared)

**PRE-FIX status:** `PASS`

---

### Block E — Fix CBACT01C (30 min)

**Purpose:** Clear the one real translation defect. Full 6-file gold set.

- [x] E.1 — Switched to `fix/cbact01c-t02r-ws-reissue-date` branch
- [x] E.2 — Located IF/EVALUATE block governing `WS-REISSUE-DATE` in `app/cbl/CBACT01C.cbl` (lines 223–224)
- [x] E.3 — CFG-known qualified field name confirmed: `WS-REISSUE-DATE`
- [x] E.4 — Updated REDEFINES interpretation condition string in `translations/baseline/CBACT01C.md` (commit `b6fb99d`)
- [x] E.5 — Re-ran T02-R validator: PASS (report `CBACT01C_baseline_v10_T02R_postfix.json`, SHA `83084442…`, exit=0)
- [x] E.6 — No FAIL encountered — proceeded
- [x] E.7 — Promoted to `translations/gold-candidate/CBACT01C.md` (commit `3ce9a609`)
- [x] E.8 — Fix event appended to `.aifirst/runs/T-CBACT01C-T02R-FIX/run.log`

**Block E validation:**
- [x] T02-R PASS for CBACT01C (SHA `83084442…`, exit=0)
- [x] Condition string uses CFG-known qualified field name (`WS-REISSUE-DATE`)
- [x] `demo/blocked-cbact01c-snapshot/` intact and unchanged
- [x] `run.log` contains fix event (`T-CBACT01C-T02R-FIX`)

**Block E status:** `PASS`

---

### Block F — T04 Judge Dispatch (background)

**Purpose:** Real semantic scores. COSGN00C is the CICS-online capability sentinel.

- [ ] F.1 — Dispatch 68-payload batch: COMEN01C → COBSWAIT → CBCUS01C → CBTRN01C → COSGN00C
- [ ] F.2 — Monitor COSGN00C — low score = model boundary, not pipeline defect
- [ ] F.3 — Log results as T04 tier events in `run.log` as they return

**Block F validation:**
- [ ] All 68 payloads dispatched
- [ ] Results logged on arrival
- [ ] COSGN00C anomalies flagged with `sentinel_note`

**Block F status:** `PENDING`

---

### Gate: CODE-COMPLETE
- [x] Blocks A–E all committed and pushed
- [ ] Block F dispatched
- [x] `run.log` append-only integrity confirmed
- [x] `translations/gold/` contains at least COBSWAIT ✅
- [x] `demo/blocked-cbact01c-snapshot/` tagged and preserved ✅
- [x] SHA provenance manifest populated ✅
- [x] BMS edges declared ✅ (Block D PASS)

**CODE-COMPLETE status:** `PENDING` (awaiting Block F dispatch)

---

## Track 2 — Language (Day 1 Afternoon, ~4h)

### Block G — README Rewrite (60 min)

**Purpose:** Partner-facing language using the three locked phrases.

**Issue found in audit:** Current README uses "translate/translation" to describe LLM action and lacks witness-layer framing. Block G must address both agent-facing and partner-facing audiences.

- [ ] G.1 — Add partner-facing intro section using locked phrases 1 and 3
- [ ] G.2 — Replace "translate/translation" with "narrate/scribe" where referring to LLM action
- [ ] G.3 — Keep "translation" for directory names and artifact references only
- [ ] G.4 — Add "Witness Layer" section with honest adapter framing (locked phrase 2)
- [ ] G.5 — Review for overclaims — no "zero redesign" language

**Block G validation:**
- [ ] All three locked phrases appear in README
- [ ] No "translates COBOL" applied to LLM action
- [ ] Witness-agnostic framing includes adapter acknowledgment
- [ ] README renders correctly in GitHub

**Block G status:** `PENDING`

---

### Block H — Partner Deck (90 min)

**Purpose:** Six-slide narrative at `docs/partner-pitch.md`.

- [ ] H.1 — Slide 1: Problem — reliable structured COBOL extraction is the upstream bottleneck
- [ ] H.2 — Slide 2: Substrate — five-gate pipeline, schema-validated, append-only audit
- [ ] H.3 — Slide 3: Headline — CBACT01C BLOCKED, system refused to hallucinate
- [ ] H.4 — Slide 4: Provenance — SHA manifest, source → CFG → MD → report chain
- [ ] H.5 — Slide 5: Dual-use — `run.log` as compliance artifact AND fine-tuning signal
- [ ] H.6 — Slide 6: Integration ask — substrate under their dashboard, one named v2 pilot program

**Block H validation:**
- [ ] Six sections in `docs/partner-pitch.md`
- [ ] Three locked phrases appear at least once each
- [ ] No "zero redesign" overclaim
- [ ] Slides 1–5 build to Slide 6 naturally

**Block H status:** `PENDING`

---

### Block I — Discovery Questions (30 min)

**Purpose:** Opens the meeting. Confirm integration shape before pitching.

- [ ] I.1 — Write `docs/discovery-questions.md` with four questions + pivot notes:
  1. What does your accuracy figure measure — structural coverage, semantic faithfulness, or task completion?
  2. Where do failures cluster — by complexity, COBOL feature, or domain?
  3. What does your DFG/PDG model — programs only, programs + screens, or programs + screens + fields?
  4. What input format does your dashboard expect, and where is the natural integration seam?

**Block I validation:**
- [ ] Four questions with pivot notes written
- [ ] Questions are open-ended, not leading
- [ ] No substrate pitch embedded

**Block I status:** `PENDING`

---

### Block J — Objection Register (45 min)

**Purpose:** Five prepared one-liners. Acknowledge limit, name path.

- [ ] J.1 — Write `docs/objections.md`:

  | # | Objection | One-liner response |
  |---|-----------|-------------------|
  | 1 | GnuCOBOL ≠ Enterprise COBOL | GnuCOBOL is the current witness, replaceable; contract layer unchanged when you swap in IBM listings |
  | 2 | Sample size is six | Six is the demo set; substrate is corpus-agnostic, per-file cost bounded by gate budget |
  | 3 | We already have static analysis | Static analysis covers structure; this adds schema-gated narration with cryptographic provenance |
  | 4 | Show me production | Production requires partner code access — that is the integration ask |
  | 5 | Why trust an LLM at all | LLM has no freedom outside the CFG envelope; here is the BLOCKED case where it hit the boundary and stopped; here is the SHA chain |

- [ ] J.2 — Read each aloud; rewrite any that sound defensive
- [ ] J.3 — Commit

**Block J validation:**
- [ ] Five entries, each ≤2 sentences
- [ ] Pattern: acknowledge limit → name path
- [ ] None defensive; all confident and honest

**Block J status:** `PENDING`

---

### Block K — Demo Success Criteria (15 min)

**Purpose:** Know whether the meeting succeeded before you walk out.

- [ ] K.1 — Write `docs/demo-success.md` with six-item checklist (from YAML above)
- [ ] K.2 — Add green/yellow/red threshold definitions
- [ ] K.3 — Commit

**Block K validation:**
- [ ] Six criteria listed as yes/no
- [ ] Three thresholds defined

**Block K status:** `PENDING`

---

### Gate: LANGUAGE-COMPLETE
- [ ] Blocks G–K all committed
- [ ] Three locked phrases in README and partner deck
- [ ] All `docs/` files render on GitHub
- [ ] No overclaims in partner-facing text

**LANGUAGE-COMPLETE status:** `PENDING`

---

## Track 3 — Rehearsal (Day 2 Morning, ~3h)

### Block L — Dry-Run Demo Walkthrough (90 min)

- [ ] L.1 — Open repo in browser, show README
- [ ] L.2 — Navigate to `translations/gold/COBSWAIT.md`, walk through YAML + body
- [ ] L.3 — Show validation reports for COBSWAIT (all tiers PASS)
- [ ] L.4 — Scroll `run.log` live, narrate event flow
- [ ] L.5 — Open `demo/blocked-cbact01c-snapshot/`, narrate BLOCKED reason (≤90 seconds)
- [ ] L.6 — Show SHA provenance manifest
- [ ] L.7 — Deliver integration ask with one named pilot program
- [ ] L.8 — Time it. Target: 12 min. Hard ceiling: 18 min.
- [ ] L.9 — If over 18 min: cut deck slides 1–2

**Block L validation:**
- [ ] Walkthrough ≤18 min
- [ ] BLOCKED narration ≤90 seconds, lands the thesis
- [ ] Integration ask specific (one named program)

**Block L status:** `PENDING`

---

### Block M — Objection Stress-Test (60 min)

- [ ] M.1 — Read five one-liners aloud; rewrite any that feel wrong
- [ ] M.2 — Collaborator plays skeptical enterprise architect for 20 min
- [ ] M.3 — Log every question NOT on the register
- [ ] M.4 — Add one-liners for top 3 new questions
- [ ] M.5 — Update `docs/objections.md`

**Block M status:** `PENDING`

---

### Block N — Final Commit and Tag (30 min)

- [ ] N.1 — Verify Blocks A–M all PASS
- [ ] N.2 — Single squash commit if needed
- [ ] N.3 — Tag `demo-ready-v1`
- [ ] N.4 — Push to `main`
- [ ] N.5 — Verify GitHub renders all docs correctly

**Block N status:** `PENDING`

---

### Gate: DEMO-READY
- [ ] CODE-COMPLETE gate PASS
- [ ] LANGUAGE-COMPLETE gate PASS
- [ ] Dry-run ≤18 min
- [ ] Objection register stress-tested
- [ ] Tag `demo-ready-v1` on remote
- [ ] Demo success criteria accessible for meeting

**DEMO-READY status:** `PENDING`

---

## Quick Reference

| Gate | Depends On | Pass Condition |
|------|-----------|----------------|
| PRE-CODE | — | Clean repo, run.log integrity, sources present |
| POST-A/B | PRE-CODE | Snapshot tagged, COBSWAIT promoted, no uncommitted changes |
| PRE-FIX | POST-A/B + C + D | Snapshot safe, SHA manifest done, BMS edges declared |
| CODE-COMPLETE | PRE-FIX + E + F dispatched | All code committed, provenance populated, gold ≥1 file |
| LANGUAGE-COMPLETE | G + H + I + J + K | All docs committed, locked phrases present, no overclaims |
| DEMO-READY | CODE-COMPLETE + LANGUAGE-COMPLETE + L + M + N | Tagged, rehearsed, stress-tested, ≤18 min |

---

## Changelog

| Timestamp | Block | Update |
|-----------|-------|--------|
| 2026-04-27T10:59 | — | Initial plan created |
| 2026-04-27T11:42 | PRE-CODE / Block A | PRE-CODE gate PASS. Branch `demo/blocked-cbact01c-snapshot` created, 11 artifacts snapshotted, tag `demo-snapshot-v1` on `2175cf2`, README explains BLOCKED reason, original baseline unchanged |
| 2026-04-27T12:46 | Block B | COBSWAIT promoted to gold (commit `0bffc18`). T01=PASS, T02=PASS, T02-R=PASS, T03=PASS, T04=DEFERRED. SHA `21e6845d`. POST-A/B gate PASS |
| 2026-04-27T13:05 | Block C | `provenance.md` with 24 SHAs (6×4). All SHAs verified. G1 spec extended |
| 2026-04-27T13:45 | Docs audit | `fix/docs-consistency-audit` PR merged: provenance.md verification example, integrity note, DEMO-SPRINT-PLAN.md synced |
| 2026-04-27T14:20 | Block D | BMS edge declarations committed (`287a35b`): COSGN00C (COSGN0A) and COMEN01C (COMEN01) both pending-extraction. CBACT01C confirmed batch — no BMS. T01 PASS both files |
| 2026-04-27T14:27 | Block D / PRE-FIX | DEMO-SPRINT-PLAN.md cleanup: Block D → PASS, PRE-FIX → PASS, duplicate section removed, all checkboxes reconciled |
| 2026-04-27T17:55 | Block E | CBACT01C T02-R defect fixed (commit `b6fb99d`): condition `ACCT-REISSUE-DATE` → `WS-REISSUE-DATE` (CFG-known, CBACT01C.cbl lines 223–224). T01/T02/T02-R/T03 all PASS post-fix. Promoted to `translations/gold-candidate/CBACT01C.md` (commit `3ce9a609`). Fix event in `.aifirst/runs/T-CBACT01C-T02R-FIX/run.log`. Block E → PASS. CODE-COMPLETE gate: Blocks A–E ✅, awaiting Block F dispatch only. D.2 map name corrected: COMEN01A → COMEN01 (matches committed YAML). |
| 2026-05-02T12:10 | Gate fixes (branch `fix/gate-failures-cbact01c-02c-03c`) | Structural gate raised from 5/8 to **8/8 PASS**. Root causes: (1) `extract_cfg_summary.py` L01 data-item parser added — `01`-level `data_items` now written to `_cfg.json`, eliminating false hallucination flags on all data fields; (2) `is_paragraph_node()` tightened to reject Cobol-REKT synthetic verb-prefixed CFG labels. MD content fixes: CBACT01C — removed hallucinated paragraphs `END-IF`, `END-PERFORM`, `GOBACK`, `VB2-ACCT-ID`, `WS-REISSUE-DATE`; CBACT02C — fixed missing YAML frontmatter `---` block, removed `END-PERFORM` paragraph and `CARD-RECORD` data item; CBACT03C — removed `CARD-XREF-RECORD` data item. Gate result confirmed locally before push. Ready for Mark's review and merge. |
| 2026-05-05T10:34 | Housekeeping | File relocated from repo root to `docs/ops/` as part of Operation Tidy Commit D (OP-3-01). Content unchanged. |
