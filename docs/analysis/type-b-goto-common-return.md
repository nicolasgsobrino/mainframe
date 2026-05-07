# Type B: GO TO COMMON-RETURN Elimination — Hypothesis & Fix Plan

> **Status:** Analysis only. No code changes in this PR.  
> **Scope:** `app/cbl/COCRDUPC.cbl` (primary), `app/cbl/COCRDSLC.cbl` (reference/clean)

---

## Overview

| File | Total `GO TO` | Type B (inside WHEN→IF) | Type C (outside EVALUATE) | Already Clean |
|------|:---:|:---:|:---:|:---:|
| COCRDUPC.cbl | 5 | 4 | 0 | 1 |
| COCRDSLC.cbl | 0 | 0 | 0 | n/a — uses `PERFORM COMMON-RETURN` |

---

## Grep Results — All `GO TO` in Scope

### COCRDUPC.cbl (post Type-A commit 719b469)

```
Line ~246  WHEN CDEMO-PGM-ENTER / WHEN CCARD-AID-PFK12
               IF CDEMO-FROM-PROGRAM EQUAL LIT-CCLISTPGM
                   ...
                   GO TO COMMON-RETURN          ← TYPE B-1 (single nested IF)
               END-IF

Line ~271  WHEN CCUP-CHANGES-OKAYED-AND-DONE / WHEN CCUP-CHANGES-FAILED
               ...
               GO TO COMMON-RETURN              ← TYPE B-2 (bare WHEN body, no IF)
                                                  [see note below]

Line ~286  WHEN CCUP-DETAILS-FETCHED
               IF CDEMO-PGM-REENTER
                   PERFORM 2000-PROCESS-INPUTS
                   IF INPUT-ERROR
                       PERFORM 3000-SEND-MAP
                       GO TO COMMON-RETURN      ← TYPE B-1a (doubly nested IF)
                   END-IF
                   PERFORM 5000-UPDATE-RECORD
                   PERFORM 3000-SEND-MAP
                   GO TO COMMON-RETURN          ← TYPE B-1b (same outer IF)
               END-IF

Line ~296  WHEN OTHER
               ...
               GO TO COMMON-RETURN              ← TYPE B-2 (bare WHEN body)

3001-INIT-AND-SHOW-MAP.  (extracted paragraph)
               ...
               GO TO COMMON-RETURN              ← TYPE B-3 (inside extracted PERFORM para)
```

> **Note on B-2:** `WHEN CCUP-CHANGES-OKAYED-AND-DONE` and `WHEN OTHER` bodies contain `GO TO COMMON-RETURN` **not** guarded by a nested IF — they are direct paragraph exits. These are simpler replacements.

### COCRDSLC.cbl — Reference: Already Clean

COCRDSLC uses `PERFORM COMMON-RETURN` everywhere inside its EVALUATE WHEN bodies — no `GO TO` at all. This is the **target pattern** for COCRDUPC.

```cobol
* COCRDSLC — clean example (no GO TO)
WHEN CDEMO-PGM-ENTER
    IF CDEMO-FROM-PROGRAM EQUAL LIT-CCLISTPGM
        ...
        PERFORM COMMON-RETURN      ← already correct
    ELSE
        PERFORM COMMON-RETURN      ← already correct
    END-IF
WHEN OTHER
    ...
    PERFORM COMMON-RETURN          ← already correct
```

---

## What Was Already Fixed (Type A — commit 719b469)

The following Type A rewrites were applied and merged:

| Rule | Location | Change |
|------|----------|--------|
| A1 | `WHEN CCUP-DETAILS-FETCHED` | Compound `WHEN..AND` → plain `WHEN` + nested `IF/END-IF` |
| A3 | `WHEN CCUP-DETAILS-NOT-FETCHED` / `WHEN CDEMO-FROM-PROGRAM=LIT-MENUPGM` | Two compound `WHEN..AND` bodies extracted to `3001-INIT-AND-SHOW-MAP` paragraph |

These rewrites **created** new Type B instances by wrapping formerly direct `GO TO COMMON-RETURN` calls inside `IF/END-IF` blocks.

---

## Type B Fix Rules

| Rule | Pattern | Condition | Fix |
|------|---------|-----------|-----|
| **B1** | `GO TO COMMON-RETURN` inside a single nested `IF` within a `WHEN` clause | One `GO TO` in the `IF` body | Replace `GO TO COMMON-RETURN` with `PERFORM COMMON-RETURN` |
| **B1a** | `GO TO COMMON-RETURN` inside a doubly-nested `IF` (e.g., `IF INPUT-ERROR`) | `GO TO` in inner guard | Replace with `PERFORM COMMON-RETURN` |
| **B2** | `GO TO COMMON-RETURN` directly in a bare `WHEN` body (no nested IF) | Direct exit from clause | Replace with `PERFORM COMMON-RETURN` |
| **B3** | `GO TO COMMON-RETURN` inside an extracted `PERFORM` paragraph (e.g., `3001-INIT-AND-SHOW-MAP`) | Para ends with `GO TO` | Replace with `PERFORM COMMON-RETURN` |

> **Core principle:** Every `GO TO COMMON-RETURN` is a jump to a paragraph that does two things: (1) move COMMAREA, (2) EXEC CICS RETURN. Because `COMMON-RETURN` does not fall through — it ends with `EXEC CICS RETURN` which terminates the transaction — replacing `GO TO` with `PERFORM` is semantically equivalent. The `PERFORM` will return to the call site, but since `COMMON-RETURN` ends in `EXEC CICS RETURN`, the program never reaches the return point.

---

## Example Diffs (Preview — Not Applied)

### B1 — Single Nested IF (WHEN CDEMO-PGM-ENTER / WHEN CCARD-AID-PFK12)

```diff
           WHEN CDEMO-PGM-ENTER
           WHEN CCARD-AID-PFK12
               IF CDEMO-FROM-PROGRAM  EQUAL LIT-CCLISTPGM
                      ...
                      PERFORM 3000-SEND-MAP
                         THRU 3000-SEND-MAP-EXIT
-                         GO TO COMMON-RETURN
+                         PERFORM COMMON-RETURN
               END-IF
```

### B1a / B1b — Doubly-Nested IF (WHEN CCUP-DETAILS-FETCHED)

```diff
           WHEN CCUP-DETAILS-FETCHED
               IF CDEMO-PGM-REENTER
                   PERFORM 2000-PROCESS-INPUTS
                      THRU 2000-PROCESS-INPUTS-EXIT
                   IF INPUT-ERROR
                       PERFORM 3000-SEND-MAP
                          THRU 3000-SEND-MAP-EXIT
-                          GO TO COMMON-RETURN
+                          PERFORM COMMON-RETURN
                   END-IF
                   PERFORM 5000-UPDATE-RECORD
                      THRU 5000-UPDATE-RECORD-EXIT
                   PERFORM 3000-SEND-MAP
                      THRU 3000-SEND-MAP-EXIT
-                      GO TO COMMON-RETURN
+                      PERFORM COMMON-RETURN
               END-IF
```

### B2 — Bare WHEN Body (WHEN CCUP-CHANGES-OKAYED-AND-DONE)

```diff
           WHEN CCUP-CHANGES-OKAYED-AND-DONE
           WHEN CCUP-CHANGES-FAILED
                ...
                PERFORM 3000-SEND-MAP THRU 3000-SEND-MAP-EXIT
                SET CCUP-DETAILS-NOT-FETCHED TO TRUE
-               GO TO COMMON-RETURN
+               PERFORM COMMON-RETURN
```

### B2 — WHEN OTHER

```diff
           WHEN OTHER
                ...
                PERFORM 3000-SEND-MAP THRU 3000-SEND-MAP-EXIT
-               GO TO COMMON-RETURN
+               PERFORM COMMON-RETURN
```

### B3 — Extracted Paragraph (3001-INIT-AND-SHOW-MAP)

```diff
        3001-INIT-AND-SHOW-MAP.
                    INITIALIZE WS-THIS-PROGCOMMAREA
                    PERFORM 3000-SEND-MAP THRU
                            3000-SEND-MAP-EXIT
                    SET CDEMO-PGM-REENTER        TO TRUE
                    SET CCUP-DETAILS-NOT-FETCHED TO TRUE
-                   GO TO COMMON-RETURN
+                   PERFORM COMMON-RETURN
        3001-INIT-AND-SHOW-MAP-EXIT.
            EXIT.
```

---

## Semantic Safety Analysis

`COMMON-RETURN` is defined as:

```cobol
 COMMON-RETURN.
     MOVE WS-THIS-PROGCOMMAREA TO DFHCOMMAREA (1:LENGTH OF
                                  WS-THIS-PROGCOMMAREA)
     EXEC CICS RETURN
          TRANSID (LIT-THISTRANID)
          COMMAREA(CARDDEMO-COMMAREA)
     END-EXEC.
```

`EXEC CICS RETURN` terminates the CICS task. Control never returns to the caller regardless of whether `GO TO` or `PERFORM` was used. The two forms are **100% semantically equivalent** in this program.

---

## Scope: Type C (Future)

Type C would be `GO TO` statements that jump to paragraphs **other than** `COMMON-RETURN`, or `GO TO` statements that appear **outside** any `EVALUATE` block. No Type C instances were identified in COCRDUPC or COCRDSLC in this scan. Other large files (COACTUPC.cbl @ 182KB, COCRDLIC.cbl @ 118KB, CBTRN02C.cbl @ 58KB) have not been scanned — flagged for future analysis.

---

## Review Questions

1. **Hypothesis confirmed?** Is `PERFORM COMMON-RETURN` a safe 1-for-1 replacement for `GO TO COMMON-RETURN` given that `EXEC CICS RETURN` never returns?
2. **Rules correct?** Are B1/B1a/B2/B3 the right classification, or do any of these warrant a different approach?
3. **Inline vs. PERFORM preference:** For B3 (the extracted `3001-INIT-AND-SHOW-MAP` paragraph), should we keep the paragraph and just swap `GO TO` → `PERFORM`, or inline the `COMMON-RETURN` body directly into the paragraph and drop the `GO TO` entirely?
4. **Scope Type C?** Should we scan COACTUPC, COCRDLIC, CBTRN02C for `GO TO` patterns now, or keep that as a separate PR?

---

> **Code changes after approval.**
