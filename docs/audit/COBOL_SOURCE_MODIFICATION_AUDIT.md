# COBOL Source Modification Audit Trail

> **Purpose:** Production-grade record of every `.cbl` / `.CBL` file in `app/cbl/` that has been modified from the upstream AWS source. Required before any GnuCOBOL compilation or production deployment to establish a clean diff baseline.

---

## Audit Metadata

| Field | Value |
|---|---|
| **Upstream repo** | [aws-samples/aws-mainframe-modernization-carddemo](https://github.com/aws-samples/aws-mainframe-modernization-carddemo) |
| **Fork repo** | [MrSnowNB/aws-mainframe-modernization-carddemo](https://github.com/MrSnowNB/aws-mainframe-modernization-carddemo) |
| **Upstream ref** | `main` @ commit `59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e` |
| **Fork ref** | `main` @ commit `f4d602e5aeb21d22322361f6e605a1f37513d0fe` |
| **Diff method** | Git blob SHA comparison (identical SHA = bit-for-bit identical file) |
| **Audit date** | 2026-05-02 |
| **Auditor** | Perplexity AI (automated SHA diff) + MrSnowNB (human review) |
| **Total files audited** | 31 |

---

## Executive Summary

| Category | Count | Files |
|---|---|---|
| ✅ **Pristine** (identical to upstream) | 30 | See table below |
| ⚠️ **Modified** (diverges from upstream) | 1 | `COCRDLIC.cbl` |
| ➕ **Fork-only** (not in upstream) | 0 | — |

**Only one COBOL source file has been changed from the original AWS codebase.** All 30 other files are bit-for-bit identical to the upstream `aws-samples` repo and are safe to compile with GnuCOBOL without any pre-processing.

---

## Modified Files — Full Detail

### `app/cbl/COCRDLIC.cbl` ⚠️ MODIFIED

| Field | Value |
|---|---|
| **Upstream blob SHA** | `d49ce3fdce5d18d49da44690ab944422c21770a7` |
| **Fork blob SHA** | `bf18933337604df3ab15c4a8a8e6b9af3c263e02` |
| **Upstream size** | 117,376 bytes |
| **Fork size** | 118,186 bytes (+810 bytes) |
| **Modification type** | **Syntactic rewrite — functionally identical COBOL** |
| **Safe to compile?** | ✅ Yes — logic is unchanged |

#### Why it was modified

smojol-cli (the static CFG analysis tool used in this project) contains a bug in `ConditionVisitor.java:28` / `IfFlowNode.java:93` and `EvaluateBreaker.java:77` / `AdditionalConditionVisitor.java:50`. The visitor crashes with a `NullPointerException` whenever it encounters a COBOL `IF` or `WHEN` clause that mixes a **boolean condition-name** with a **relational comparison** via `AND` on the same line:

```cobol
* This pattern crashes smojol-cli:
IF  VIEW-REQUESTED-ON(I-SELECTED)
AND CDEMO-FROM-PROGRAM EQUAL LIT-THISPGM
```

Root cause: the visitor resolves `VIEW-REQUESTED-ON` as a boolean condition-name, then calls `.getRelationalOperation()` on the `AND` operand — which returns `null` for mixed boolean+relational compounds — causing the NPE.

#### What was changed

Two `IF..AND` compound clauses inside `EVALUATE TRUE` were decomposed into two separate nested `IF` statements. The Java smojol-cli source was **not touched**.

**Pattern applied (both occurrences):**

```cobol
* BEFORE (crashes smojol-cli):
WHEN CCARD-AID-ENTER
    IF  VIEW-REQUESTED-ON(I-SELECTED)
    AND CDEMO-FROM-PROGRAM EQUAL LIT-THISPGM
        EXEC CICS XCTL ...
    END-IF

* AFTER (smojol-cli compatible, functionally identical):
WHEN CCARD-AID-ENTER
    IF VIEW-REQUESTED-ON(I-SELECTED)
        IF CDEMO-FROM-PROGRAM EQUAL LIT-THISPGM
            EXEC CICS XCTL ...
        END-IF
    END-IF
```

#### Change history (PRs)

| PR | Branch | Description |
|---|---|---|
| [#27](https://github.com/MrSnowNB/aws-mainframe-modernization-carddemo/pull/27) | `fix/cocrdlic-evaluate-compound-when-v2` | Split `WHEN..AND` compound in EVALUATE block |
| [#28](https://github.com/MrSnowNB/aws-mainframe-modernization-carddemo/pull/28) | `fix/cocrdlic-split-compound-if-v3` | Split remaining `IF..AND` compound inside the WHEN block |

#### GnuCOBOL diff command

To verify the change is purely syntactic before compiling:
```bash
# Fetch the upstream original
curl -s https://raw.githubusercontent.com/aws-samples/aws-mainframe-modernization-carddemo/main/app/cbl/COCRDLIC.cbl \
  -o /tmp/COCRDLIC_upstream.cbl

# Diff against fork version
diff --unified /tmp/COCRDLIC_upstream.cbl app/cbl/COCRDLIC.cbl
```

Expected: Only the two `IF..AND` decompositions appear in the diff. No logic, data structures, file I/O, or CICS calls are different.

---

## Pristine Files — SHA Verification Table

All 30 files below have **identical blob SHAs** in the fork and upstream. They require no diff before GnuCOBOL compilation.

| File | Blob SHA (identical in both) | Size |
|---|---|---|
| `CBACT01C.cbl` | `a9a14e021e6fe1c14caa544213d938abd15b6681` | 17,450 B |
| `CBACT02C.cbl` | `1b9b9af16d07320ab7b1dedf0d780f409f6878ed` | 14,096 B |
| `CBACT03C.cbl` | `aebb60c1118f8679810a0e3fa802465c7cfdf83f` | 14,101 B |
| `CBACT04C.cbl` | `1da48c0015ca11995d2c02d8ece3fcbc63b84ec1` | 52,479 B |
| `CBCUS01C.cbl` | `88a99d7fc534579e538c438a4860e72ec068730c` | 6,914 B |
| `CBEXPORT.cbl` | `4fcf13c1c36fa4f2c3ebe6401c23a5562f122be4` | 24,197 B |
| `CBIMPORT.cbl` | `39b243598d7296ed4c370d793f8e571d954e3f93` | 20,239 B |
| `CBSTM03A.CBL` | `60f3d4811d9037bc1a778dd5b677d318fc04dc78` | 35,574 B |
| `CBSTM03B.CBL` | `d076c44dffe71113e3bc5acf3dda68a14e1c54b2` | 6,983 B |
| `CBTRN01C.cbl` | `6494be3b695bd33f27b39f8d13dc5b510f92b7ed` | 17,967 B |
| `CBTRN02C.cbl` | `ee606affbec764cb9c428a6cd43880d2072ffce3` | 58,890 B |
| `CBTRN03C.cbl` | `4d77c6d1678ef01ef2d03e4ad5dc8770f947adf6` | 52,239 B |
| `COACTUPC.cbl` | `d66944150c9ad91fe0459ef304cc536b651b9a42` | 182,463 B |
| `COACTVWC.cbl` | `9e3a27d87110c7023b0f7e295f5e4a0ca5c60472` | 74,764 B |
| `COADM01C.cbl` | `1212a66d5979213bbbe0ebe75ca11eb056866aab` | 22,736 B |
| `COBIL00C.cbl` | `6c0ed9af223d0b2bee0aebbbf691769f2c07e457` | 23,426 B |
| `COBSWAIT.cbl` | `7957347717cf04be2dc4f5be24aa94668cf780ab` | 2,020 B |
| `COCRDSLC.cbl` | `c62ebd0e3f7a8e566ffaee9a5af0701abc3278f2` | 71,308 B |
| `COCRDUPC.cbl` | `9eb519c94f13ac0db659193c6c70e7846e859cc5` | 125,961 B |
| `COMEN01C.cbl` | `a404313748b0715a306336ac599b3e585697c05c` | 12,461 B |
| `CORPT00C.cbl` | `ed3660b37c8f1cd00c0b3ab323d7eae7eb933207` | 28,302 B |
| `COSGN00C.cbl` | `c3e7f8e4fb96466d3822ad82ceda8a96fb555d78` | 10,288 B |
| `COTRN00C.cbl` | `a5f92db9aa5a275c7942498d7abc9d08579957e8` | 29,270 B |
| `COTRN01C.cbl` | `c4d95b61ba73552b3c421e16d6eb5def5821bd7c` | 14,244 B |
| `COTRN02C.cbl` | `2491849ee9d6840655b020fc1f34b22b9f1667aa` | 33,665 B |
| `COUSR00C.cbl` | `8f2fae8667585ee58a720df8b14bac06d256414f` | 29,285 B |
| `COUSR01C.cbl` | `1ac1b78d11bc552b2a35abee504f73a74b3dfcb3` | 12,571 B |
| `COUSR02C.cbl` | `1588889bf6a4595cc73492bbaed3d1a18dd60330` | 17,611 B |
| `COUSR03C.cbl` | `b0b2b5e699ad362b09d12ff1b2608d60a0823105` | 15,038 B |
| `CSUTLDTC.cbl` | `20671f0edd440eb9d194c28176fdfce8481228b7` | 11,608 B |

---

## Production Grade Notes

### Rule: Modification Categories for Future Projects

When using analysis tools that cannot handle all valid COBOL syntax, modifications must be classified:

| Category | Definition | GnuCOBOL Safe? | Requires Re-diff Before Deploy? |
|---|---|---|---|
| **Type A — Syntactic Workaround** | Restructured syntax, identical semantics (e.g., split compound IF) | ✅ Yes | ✅ Yes — verify no semantic drift |
| **Type B — Bug Fix** | Corrects actual logic error in the original source | ✅ Yes | ✅ Yes — document the defect |
| **Type C — Tool Stub** | Adds stub paragraphs/sections for analysis tool compatibility only | ⚠️ Strip before compile | ✅ Yes — must be removed |
| **Type D — Annotation** | Comments only, no executable code changed | ✅ Yes | ✅ Yes — low risk |

The `COCRDLIC.cbl` change in this project is **Type A — Syntactic Workaround**.

### How to Re-verify This Audit

```bash
# Add upstream as a remote (one-time)
git remote add upstream https://github.com/aws-samples/aws-mainframe-modernization-carddemo.git
git fetch upstream

# Diff all CBL files between upstream main and our main
git diff upstream/main main -- app/cbl/

# Verify a specific file is pristine
git diff upstream/main main -- app/cbl/CBACT01C.cbl
# (should produce no output if pristine)
```
