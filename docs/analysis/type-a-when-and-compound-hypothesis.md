# Type A: Compound `WHEN..AND` Clause Analysis

## Summary

This document captures the full investigation into compound `WHEN..AND` clauses
found in two CardDemo programs — **COCRDSLC** and **COCRDUPC** — that are
incompatible with the smojol COBOL-to-CFG (Control Flow Graph) tool used in
the AWS Mainframe Modernization pipeline.

---

## Problem Statement

The AWS smojol parser/CFG builder rejects or mis-models COBOL `EVALUATE`
statements that use the compound `WHEN <cond1> AND <cond2>` form. This is
valid Enterprise COBOL syntax but is a known edge case for many COBOL analysis
tools: they either fail to parse it or collapse both conditions into a single
branch, losing the semantics of one of the guards.

The specific pattern at issue is:

```cobol
    WHEN <condition-A>
     AND <condition-B>
         <shared body>
```

This **is not** the same as `WHEN <cond-A> WHEN <cond-B>` (COBOL fallthrough).
The `AND` here is a **conjunct** on a single `WHEN` — both conditions must be
true simultaneously. When two such conjunct `WHEN..AND` clauses share the same
body (fallthrough), the semantics become:

> Execute the body if **(A AND B)** OR **(C AND B)** — which simplifies to
> **B AND (A OR C)**.

The CFG tool cannot distinguish this from a plain `WHEN A WHEN C` fallthrough,
causing incorrect branch modeling.

---

## Files Investigated

### 1. `app/cbl/COCRDSLC.cbl` — Credit Card Selection

**Current state (main branch):** Already partially fixed.

The `WHEN CDEMO-PGM-ENTER AND <cond>` clause around line 339 of the *original*
file has been rewritten in the current `main` to:

```cobol
           WHEN CDEMO-PGM-ENTER
               IF CDEMO-FROM-PROGRAM EQUAL LIT-CCLISTPGM
                   SET INPUT-OK TO TRUE
                   ...
                   PERFORM COMMON-RETURN
               ELSE
                   PERFORM 1000-SEND-MAP THRU 1000-SEND-MAP-EXIT
                   PERFORM COMMON-RETURN
               END-IF
```

**Assessment:** The Type A rewrite is already applied here. ✅

However, a **residual anomaly** exists in `COCRDUPC` (see below).

---

### 2. `app/cbl/COCRDUPC.cbl` — Credit Card Update

This file contains **two distinct problems**:

#### Problem 1 — Already-Fixed Block (lines ~482–499, current main)

The original compound `WHEN..AND` fallthrough:

```cobol
    WHEN CDEMO-PGM-ENTER
     AND CDEMO-FROM-PROGRAM  EQUAL LIT-CCLISTPGM
    WHEN CCARD-AID-PFK12
     AND CDEMO-FROM-PROGRAM  EQUAL LIT-CCLISTPGM
        SET CDEMO-PGM-REENTER    TO TRUE
        ...
        GO TO COMMON-RETURN
```

Has been rewritten in `main` to:

```cobol
           WHEN CDEMO-PGM-ENTER
           WHEN CCARD-AID-PFK12
               IF CDEMO-FROM-PROGRAM  EQUAL LIT-CCLISTPGM
                      SET CDEMO-PGM-REENTER    TO TRUE
                      ...
                      GO TO COMMON-RETURN
               END-IF
```

**Assessment:** Type A rewrite is applied. ✅

However, the `GO TO COMMON-RETURN` inside the `IF` body is still present.
This is a smojol CFG concern because `GO TO` inside a nested `IF`
inside an `EVALUATE WHEN` creates an unstructured branch in the graph.

---

#### Problem 2 — Remaining Compound `WHEN..AND` (UNRESOLVED ⚠️)

Further down in the same `EVALUATE TRUE` block, two more compound
`WHEN..AND` clauses remain in current `main`:

```cobol
           WHEN CCUP-DETAILS-NOT-FETCHED
            AND CDEMO-PGM-ENTER
           WHEN CDEMO-FROM-PROGRAM   EQUAL LIT-MENUPGM
            AND NOT CDEMO-PGM-REENTER
                INITIALIZE WS-THIS-PROGCOMMAREA
                PERFORM 3000-SEND-MAP THRU 3000-SEND-MAP-EXIT
                SET CDEMO-PGM-REENTER        TO TRUE
                SET CCUP-DETAILS-NOT-FETCHED TO TRUE
                GO TO COMMON-RETURN
```

This is another **two-clause WHEN..AND fallthrough** pattern.

The semantics are:
> Enter this block if:
> - `CCUP-DETAILS-NOT-FETCHED AND CDEMO-PGM-ENTER`  
> - **OR** `CDEMO-FROM-PROGRAM = LIT-MENUPGM AND NOT CDEMO-PGM-REENTER`

This cannot be modeled as a simple OR of plain conditions because each WHEN
guards a different conjunct pair.

```cobol
           WHEN CCUP-DETAILS-FETCHED
            AND CDEMO-PGM-REENTER
```

A third compound `WHEN..AND` is also present lower in the block:

```cobol
           WHEN CCUP-DETAILS-FETCHED
            AND CDEMO-PGM-REENTER
                PERFORM 2000-PROCESS-INPUTS ...
```

This is a **single-clause** compound (no fallthrough), making it a simpler
but still problematic form for the CFG tool.

---

## Hypothesis

> The smojol CFG tool fails to correctly model COBOL `WHEN <X> AND <Y>` forms
> because the compound conjunction on a WHEN clause produces an AND-node in
> the raw AST that the CFG builder does not bifurcate into a proper guard edge.
> The result is either a parse failure or a control-flow edge that bypasses
> the `<Y>` guard entirely.

### Root Cause

The COBOL 85 / Enterprise COBOL `EVALUATE` grammar permits:

```
WHEN selection-subject [AND selection-subject]
```

Most COBOL compilers (IBM, MicroFocus) support this. However, static analysis
tools that translate COBOL to CFGs commonly model `WHEN` as a single-condition
branch and do not implement the AND-conjunct extension. The result:

| Clause Form | COBOL Compiler | smojol CFG Tool |
|---|---|---|
| `WHEN A` | ✅ Correct | ✅ Correct |
| `WHEN A AND B` | ✅ Correct | ⚠️ Drops B guard |
| `WHEN A\nWHEN B` (fallthrough) | ✅ Correct | ✅ Correct |

---

## Proposed Fix — Type A Rewrite Rules

### Rule 1: Single Compound `WHEN..AND` (no fallthrough)

```cobol
* BEFORE
    WHEN <X>
     AND <Y>
        <body>

* AFTER
    WHEN <X>
        IF <Y>
            <body>
        END-IF
```

### Rule 2: Two Compound `WHEN..AND` with Shared Body (fallthrough)

```cobol
* BEFORE
    WHEN <A>
     AND <B>
    WHEN <C>
     AND <B>        (* same guard B *)
        <body>

* AFTER
    WHEN <A>
    WHEN <C>
        IF <B>
            <body>
        END-IF
```

### Rule 3: Two Compound `WHEN..AND` with DIFFERENT Guards (fallthrough)

This is the harder case in COCRDUPC (lines ~500–509):

```cobol
* BEFORE
    WHEN <A1> AND <B1>
    WHEN <A2> AND <B2>   (* B1 != B2 *)
        <body>

* AFTER — cannot collapse guard into single IF; must use nested EVALUATE or IF/OR
    WHEN <A1>
        IF <B1> PERFORM <body-paragraph> END-IF
    WHEN <A2>
        IF <B2> PERFORM <body-paragraph> END-IF
```

When the body is non-trivial (multi-line), extract it to a named paragraph
and PERFORM from each branch to avoid duplication.

---

## Files Requiring Action

| File | Clause | Lines (current main) | Status | Rule |
|---|---|---|---|---|
| COCRDSLC.cbl | `WHEN CDEMO-PGM-ENTER` nested IF | ~197–216 | ✅ Already fixed | — |
| COCRDUPC.cbl | `WHEN CDEMO-PGM-ENTER / WHEN CCARD-AID-PFK12` + `IF FROM=CCLIST` | ~482–499 | ✅ Fixed but has `GO TO` residual | — |
| COCRDUPC.cbl | `WHEN CCUP-DETAILS-NOT-FETCHED AND CDEMO-PGM-ENTER` | ~500–509 | ⚠️ **Unresolved** | Rule 3 |
| COCRDUPC.cbl | `WHEN CCUP-DETAILS-FETCHED AND CDEMO-PGM-REENTER` | ~510–520 | ⚠️ **Unresolved** | Rule 1 |

---

## Residual Risk: `GO TO COMMON-RETURN` Inside `IF`

After the Type A rewrites are applied, several `GO TO COMMON-RETURN` calls
remain inside nested `IF` blocks within `EVALUATE WHEN` clauses. smojol CFG
builders also flag `GO TO` as an unstructured jump. A follow-on **Type B**
rewrite would replace these with structured PERFORM-to-exit patterns or
pharagraph restructuring.

This is out of scope for the current Type A pass.

---

## Next Steps

1. Review this analysis — confirm or correct the hypothesis.
2. Apply Rule 1 fix to `COCRDUPC` line ~510: `WHEN CCUP-DETAILS-FETCHED AND CDEMO-PGM-REENTER`.
3. Apply Rule 3 fix to `COCRDUPC` lines ~500–509 (the two different-guard fallthrough).
4. Validate with smojol CFG tool against the patched file.
5. Optionally, open a Type B ticket for `GO TO` elimination.
