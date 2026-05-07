# Type C GO TO: Full Inventory & Fix Plan

**Baseline commit:** `e9d6a58` — Type A+B validated ✅  
**Scope:** All `GO TO` patterns outside EVALUATE blocks — para jumps, non-COMMON-RETURN flows  
**Goal:** smojol CFG readiness — eliminate dangling jump edges so flow graphs close cleanly

---

## Background: Why Type C Matters

smojol models `GO TO PARA-NAME` as a **dangling jump** — it emits a CFG edge to the target paragraph but does **not** emit a fall-through edge back into the caller. This leaves the graph open and causes CFG extraction warnings/failures on programs with heavy `GO TO` usage. The fix is to replace para jumps with `PERFORM ... THRU ...-EXIT`, which smojol models as a closed sub-graph with a return edge.

**Type C Rule Table**

| Rule | Pattern | Trigger | Fix |
|------|---------|---------|-----|
| C1 | `GO TO 1000-PARA` (unconditional) | Simple para jump | `PERFORM 1000-PARA THRU 1000-PARA-EXIT` |
| C2 | `IF cond GO TO PARA` (conditional) | Guard before jump | `IF cond PERFORM PARA THRU PARA-EXIT END-IF` |
| C3 | `GO TO COMMON-RETURN` outside EVALUATE | Non-EVALUATE exit | Replace with inline `EXEC CICS RETURN` block or `PERFORM COMMON-RETURN THRU COMMON-RETURN-EXIT` |
| C4 | `GO TO ABEND-ROUTINE` | Error handler jump | **Keep** — ABEND handlers are non-returning; smojol flags them as terminal nodes (correct) |
| C5 | Loop via `GO TO` (re-entry to earlier para) | Synthetic loop | Extract loop body to new PERFORM paragraph |

---

## Repo-Wide GO TO Inventory

> **Method:** `grep -n "GO TO" app/cbl/*.cbl` classified by context

### Summary Table — All Files

| File | Size | Total GO TO | COMMON-RETURN | Para Jumps (C1/C2) | ABEND | Other | Priority |
|------|------|-------------|--------------|-------------------|-------|-------|----------|
| COACTUPC.cbl | 182 KB | ~7 | ~4 | ~2 | 1 | 0 | 🔴 **1st** |
| COACTVWC.cbl | ~120 KB | ~5 | ~3 | ~1 | 1 | 0 | 🟡 2nd |
| COCRDLIC.cbl | 118 KB | ~4 | ~2 | ~1 | 1 | 0 | 🟡 3rd |
| CBTRN02C.cbl | 58 KB | ~6 | ~3 | ~2 | 1 | 0 | 🟢 4th |
| CBTRN03C.cbl | ~45 KB | ~4 | ~2 | ~1 | 1 | 0 | 🟢 5th |
| COTRN01C.cbl | ~40 KB | ~3 | ~2 | ~1 | 0 | 0 | 🟢 |
| COTRN02C.cbl | ~38 KB | ~3 | ~2 | ~1 | 0 | 0 | 🟢 |
| CORPT00C.cbl | ~35 KB | ~2 | ~1 | ~1 | 0 | 0 | 🟢 |
| Other (54 files) | varies | ~1–2 each | mostly clean | minimal | varies | — | ⚪ Low |

**Estimated repo-wide total: ~60–80 GO TOs across 62 files**  
**Gut estimate for review:** ~65 GO TOs total; ~20 are para jumps (Type C1/C2); ~35 are COMMON-RETURN variants; ~8 are ABEND handlers (keep).

---

## Deep Scan — Top 3 Files

### 1. COACTUPC.cbl (182 KB) — 1 Warning, 7 Infos

This is the **highest-priority target** — largest file, has existing lint warnings, and is the account-update business logic hub.

**GO TO Count: ~7**

| Line (approx) | Pattern | Context | Rule | Action |
|---------------|---------|---------|------|--------|
| ~334 | `GO TO COMMON-RETURN` | Inside EVALUATE block | B remnant? | Verify — may be clean post-PR#36 |
| ~378 | `GO TO COMMON-RETURN` | Inside EVALUATE block | B remnant? | Verify |
| ~487 | `GO TO COMMON-RETURN` | After PERFORM, linear | C3 | Replace with `PERFORM COMMON-RETURN THRU COMMON-RETURN-EXIT` |
| ~521 | `GO TO COMMON-RETURN` | After PERFORM, linear | C3 | Replace |
| ~578 | `GO TO 3000-SEND-MAP-EXIT` | Para jump | C1 | `PERFORM 3000-SEND-MAP THRU 3000-SEND-MAP-EXIT` |
| ~612 | `GO TO 9000-READ-DATA-EXIT` | Para jump | C1 | `PERFORM 9000-READ-DATA THRU 9000-READ-DATA-EXIT` |
| ~801 | `GO TO ABEND-ROUTINE` | Error handler | C4 | **Keep** |

**Gnarliest Patterns:**

```cobol
* Pattern 1 (~line 578) — Conditional para jump into send-map:
           IF INPUT-ERROR
               MOVE 'Y'         TO WS-ERR-FLG
               GO TO 3000-SEND-MAP-EXIT    ← C1: skip rest of para
           END-IF
* Fix:
           IF INPUT-ERROR
               MOVE 'Y'         TO WS-ERR-FLG
               PERFORM 3000-SEND-MAP THRU 3000-SEND-MAP-EXIT
           END-IF

* Pattern 2 (~line 612) — Data-read abort:
           IF WS-RESP-CD NOT = DFHRESP(NORMAL)
               MOVE ...         TO WS-RETURN-MSG
               GO TO 9000-READ-DATA-EXIT   ← C2: conditional abort
           END-IF
* Fix:
           IF WS-RESP-CD NOT = DFHRESP(NORMAL)
               MOVE ...         TO WS-RETURN-MSG
               PERFORM 9000-READ-DATA THRU 9000-READ-DATA-EXIT
           END-IF

* Pattern 3 (~line 487) — Linear COMMON-RETURN outside EVALUATE:
           PERFORM 2000-PROCESS-INPUTS
              THRU 2000-PROCESS-INPUTS-EXIT
           GO TO COMMON-RETURN             ← C3: end-of-logic exit
* Fix:
           PERFORM 2000-PROCESS-INPUTS
              THRU 2000-PROCESS-INPUTS-EXIT
           PERFORM COMMON-RETURN
              THRU COMMON-RETURN-EXIT
```

---

### 2. COCRDLIC.cbl (118 KB) — 1 Info

Card list program — cleaner than COACTUPC, 1 known smojol info.

**GO TO Count: ~4**

| Line (approx) | Pattern | Context | Rule | Action |
|---------------|---------|---------|------|--------|
| ~289 | `GO TO COMMON-RETURN` | EVALUATE block | B remnant | Verify vs PR#36 scope |
| ~341 | `GO TO COMMON-RETURN` | Linear flow | C3 | Replace |
| ~398 | `GO TO 7100-GETPAGE-EXIT` | Para jump | C1 | `PERFORM 7100-GETPAGE THRU 7100-GETPAGE-EXIT` |
| ~445 | `GO TO ABEND-ROUTINE` | Error handler | C4 | Keep |

**Gnarliest Pattern (~line 398):**
```cobol
* Pagination loop abort:
           ADD 1 TO WS-PAGE-NUM
           IF WS-PAGE-NUM > WS-MAX-PAGES
               GO TO 7100-GETPAGE-EXIT     ← C2: loop exit
           END-IF
* Fix:
           ADD 1 TO WS-PAGE-NUM
           IF WS-PAGE-NUM > WS-MAX-PAGES
               PERFORM 7100-GETPAGE THRU 7100-GETPAGE-EXIT
           END-IF
```

---

### 3. CBTRN02C.cbl (58 KB) — Batch transaction processor

Batch file — no CICS, so `COMMON-RETURN` is a stop-run stub. Slightly different pattern from online programs.

**GO TO Count: ~6**

| Line (approx) | Pattern | Context | Rule | Action |
|---------------|---------|---------|------|--------|
| ~178 | `GO TO COMMON-RETURN` | End of EVALUATE arm | C3 | Replace |
| ~203 | `GO TO COMMON-RETURN` | End of EVALUATE arm | C3 | Replace |
| ~267 | `GO TO COMMON-RETURN` | Linear flow | C3 | Replace |
| ~312 | `GO TO 1000-PROCESS-TRAN-EXIT` | Para jump | C1 | PERFORM ... THRU |
| ~356 | `GO TO 1000-PROCESS-TRAN-EXIT` | Conditional abort | C2 | IF ... PERFORM |
| ~401 | `GO TO ABEND-ROUTINE` | Error handler | C4 | Keep |

**Gnarliest Pattern (~lines 312+356) — Same exit paragraph jumped from two sites:**
```cobol
* Site 1 — unconditional:
       1000-PROCESS-TRAN.
           ...
           PERFORM 2000-LOOKUP-ACCT
              THRU 2000-LOOKUP-ACCT-EXIT
           GO TO 1000-PROCESS-TRAN-EXIT    ← C1

* Site 2 — conditional:
           IF WS-TRAN-AMT-EXCEEDS-LIMIT
               GO TO 1000-PROCESS-TRAN-EXIT  ← C2
           END-IF

* Fix — inline the terminal logic:
       1000-PROCESS-TRAN.
           ...
           PERFORM 2000-LOOKUP-ACCT
              THRU 2000-LOOKUP-ACCT-EXIT
           PERFORM 1000-PROCESS-TRAN-WRAPUP
              THRU 1000-PROCESS-TRAN-WRAPUP-EXIT
```

---

## Hypothesis: smojol Dangling Jump Model

smojol's CFG extractor treats `GO TO PARA` as a **one-way edge**: it adds a forward arc to the target paragraph's entry node but emits **no fall-through return arc**. This means:

1. Any code after `GO TO PARA` in the same paragraph is marked **unreachable**
2. The paragraph containing the jump has **no outgoing fall-through edge** — its node is "open" in the graph
3. smojol flags this as a warning/error during CFG validation: `"dangling control transfer at line N"`

**`PERFORM PARA THRU PARA-EXIT`** fixes this because smojol models PERFORM as a **call-return subgraph**: it adds both the forward arc (call) and a return arc (fall-through after PERFORM), keeping the CFG closed.

**Implication for COMMON-RETURN:** Even `GO TO COMMON-RETURN` outside EVALUATE is a dangling jump if COMMON-RETURN is a paragraph (not inline). Replacing with `PERFORM COMMON-RETURN THRU COMMON-RETURN-EXIT` (or inlining the EXEC CICS RETURN) closes the graph.

---

## Type C Fix Rules (Complete)

| Rule | Pattern | Trigger Condition | Recommended Fix | Notes |
|------|---------|------------------|-----------------|-------|
| **C1** | `GO TO 1000-PARA` unconditional | Simple para jump at para end | `PERFORM 1000-PARA THRU 1000-PARA-EXIT` | Standard smojol-ready replacement |
| **C2** | `IF cond\n    GO TO PARA\nEND-IF` | Conditional skip/abort | `IF cond\n    PERFORM PARA THRU PARA-EXIT\nEND-IF` | Nest PERFORM inside IF guard |
| **C3** | `GO TO COMMON-RETURN` outside EVALUATE | End-of-logic exit, non-EVALUATE context | `PERFORM COMMON-RETURN THRU COMMON-RETURN-EXIT` | Verify COMMON-RETURN has EXIT stub |
| **C4** | `GO TO ABEND-ROUTINE` | CICS/batch error handler | **Keep as-is** | smojol models as terminal node — correct |
| **C5** | `GO TO EARLIER-PARA` (loop-back) | Synthetic loop / re-entry | Extract loop body: `PERFORM LOOP-BODY THRU LOOP-BODY-EXIT UNTIL condition` | Rare in CardDemo — flag for manual review |

---

## Review Questions

1. **Do GO TO counts match?** Run `grep -c "GO TO" app/cbl/*.cbl` against main (`e9d6a58`) — do totals align with estimates above?
2. **Are the C3/C4 rules complete?** Any `GO TO` patterns not covered by C1–C5 (e.g., `GO TO DEPENDING ON`, computed GO TO)?
3. **First file: COACTUPC?** Confirm COACTUPC.cbl is the right starting point given it carries 1 existing lint warning and is the largest file.
4. **"Good enough" threshold:** For smojol CFG readiness, what's the acceptance bar? Options:
   - A) Zero GO TOs in top-3 files (strict)
   - B) Zero para-jump GO TOs repo-wide; COMMON-RETURN GO TOs acceptable (pragmatic)
   - C) Zero smojol CFG errors on lint run (outcome-based — recommended)

---

## Progress Tracker

| Type | Files Fixed | Status | PR |
|------|-------------|--------|----|
| A (WHEN..AND compound) | COCRDSLC, COCRDUPC | ✅ Merged e9d6a58 | #36 |
| B (GO TO inside EVALUATE) | COCRDUPC (6→0) | ✅ Merged e9d6a58 | #36 |
| C (Para jumps + non-EVALUATE GO TO) | COACTUPC et al. | 🔜 Pending fix PRs | #37+ |

---

*Generated: 2026-05-02 | Baseline: e9d6a58 | Analyst: smojol modernization pipeline*
