#!/usr/bin/env python3
"""
gate_compare.py -- diff ground truth vs MD claims, emit gate report.

Reads:  validation/ground_truth/{PROGRAM}_gt.json
        validation/claims/{PROGRAM}_claims.json
Writes: validation/reports/{PROGRAM}_gate.json
        validation/logs/gate_{TIMESTAMP}.log     (append-only run log)

No LLM. Purely set-difference logic.
Runnable on any machine with Python 3.8+ stdlib only.

Exit codes:
    0 = all tested programs PASS
    1 = one or more programs FAIL

Usage:
    python validation/gate_compare.py              # all known programs
    python validation/gate_compare.py CBACT01C     # single program
    python validation/gate_compare.py --all        # all gold-candidates in translations/

Run AFTER extract_ground_truth.py and extract_md_claims.py.
"""
import io
import json
import sys
import datetime
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except AttributeError:
    pass

try:
    from validation.cobol_vocab import INVALID_PARAGRAPH_NAMES
except ImportError:
    try:
        from cobol_vocab import INVALID_PARAGRAPH_NAMES
    except ImportError:
        INVALID_PARAGRAPH_NAMES = frozenset({
            "END-EXEC", "END-IF", "END-PERFORM", "END-EVALUATE",
            "END-READ", "END-WRITE", "END-STRING", "END-UNSTRING",
            "END-MULTIPLY", "END-DIVIDE", "END-ADD", "END-SUBTRACT",
            "END-COMPUTE", "END-SEARCH", "END-CALL", "END-REWRITE",
            "END-DELETE", "END-START", "END-RETURN",
        })

# ---------------------------------------------------------------------------
# PROGRAMS registry — auto-discovers any program that has both a
# ground_truth JSON and a claims JSON, so new programs never need to be
# manually added here.  The explicit list is kept as a fallback and for
# documentation purposes.
# ---------------------------------------------------------------------------
_EXPLICIT_PROGRAMS = [
    "CBACT01C", "CBACT02C", "CBCUS01C", "CBTRN01C",
    "COBSWAIT", "COMEN01C", "COSGN00C",
]

def _discover_programs() -> list:
    """Return union of explicit list + any program with both gt and claims files."""
    gt_dir = Path("validation/ground_truth")
    cl_dir = Path("validation/claims")
    discovered = set(_EXPLICIT_PROGRAMS)
    if gt_dir.exists() and cl_dir.exists():
        gt_ids = {p.stem.replace("_gt", "") for p in gt_dir.glob("*_gt.json")}
        cl_ids = {p.stem.replace("_claims", "") for p in cl_dir.glob("*_claims.json")}
        discovered |= (gt_ids & cl_ids)
    return sorted(discovered)

PROGRAMS = _discover_programs()


def log(run_id: str, lines: list, log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"gate_{run_id}.log"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return log_path


def compare(program_id: str) -> tuple:
    gt_path = Path(f"validation/ground_truth/{program_id}_gt.json")
    cl_path = Path(f"validation/claims/{program_id}_claims.json")
    log_lines = []

    if not gt_path.exists():
        msg = f"[GATE] {program_id}: SKIP -- ground truth not found (run extract_ground_truth.py first)"
        print(msg)
        return False, [msg]
    if not cl_path.exists():
        msg = f"[GATE] {program_id}: SKIP -- claims not found (run extract_md_claims.py first)"
        print(msg)
        return False, [msg]

    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    cl = json.loads(cl_path.read_text(encoding="utf-8"))

    failures = []
    warnings = []

    # -- Check 1: No reachable paragraph missing from MD ----------------------
    gt_reachable = set(gt["paragraphs_reachable"])
    cl_paragraphs = set(cl["paragraphs_claimed"])
    cl_synthetic = set(cl.get("synthetic_paragraphs", []))

    missing_paras = sorted(gt_reachable - cl_paragraphs)
    if missing_paras:
        failures.append({"check": "paragraphs_missing_from_md",
                         "detail": "Reachable paragraphs in source not found in MD",
                         "items": missing_paras})

    # -- Check 2: Extra paragraphs in MD must be dead OR synthetic ------------
    extra_paras = cl_paragraphs - gt_reachable
    gt_dead = set(gt["paragraphs_dead"])
    cl_dead = set(cl["dead_declared_in_md"])
    unexplained = sorted(extra_paras - gt_dead - cl_synthetic)
    if unexplained:
        failures.append({"check": "hallucinated_paragraphs",
                         "detail": "MD claims paragraphs not in source, not dead-code, and not synthetic",
                         "items": unexplained})

    # -- Check 2c: Dedicated invalid_paragraph_names check -------------------
    invalid_names = sorted(
        name for name in cl_paragraphs
        if name.upper() in INVALID_PARAGRAPH_NAMES
    )
    if invalid_names:
        failures.append({"check": "invalid_paragraph_names",
                         "detail": (
                             "MD procedure_paragraphs contains COBOL scope terminators "
                             "or reserved words that are never valid paragraph names. "
                             "These are Cobol-REKT RC8 false positives inherited by the "
                             "translation agent. Remove them from the MD."
                         ),
                         "items": invalid_names})

    if cl_synthetic and gt_reachable == set():
        warnings.append({"check": "synthetic_paragraphs_accepted",
                         "detail": "Source has no named paragraphs; MD synthetic labels accepted",
                         "items": sorted(cl_synthetic)})

    # -- Check 2b: Dead code in GT not declared in MD (warning only) ----------
    undeclared_dead = sorted(gt_dead - cl_dead)
    if undeclared_dead:
        warnings.append({"check": "dead_code_not_declared_in_md",
                         "detail": "CFG dead paragraphs not explicitly marked reachable:false in MD",
                         "items": undeclared_dead})

    # -- Check 3: Level-01 data items -----------------------------------------
    gt_items = set(gt["data_items_level01"])
    cl_items = set(cl["data_items_level01"])
    missing_items = sorted(gt_items - cl_items)
    extra_items = sorted(cl_items - gt_items)
    if missing_items:
        failures.append({"check": "data_items_missing",
                         "detail": "Level-01 data items in source not found in MD",
                         "items": missing_items})
    if extra_items:
        failures.append({"check": "data_items_hallucinated",
                         "detail": "Level-01 data items in MD not found in source",
                         "items": extra_items})

    # -- Check 4: REDEFINES pairs ---------------------------------------------
    gt_red = set(map(tuple, gt["redefines_pairs"]))
    cl_red = set(map(tuple, cl["redefines_pairs"]))
    missing_red = [list(r) for r in sorted(gt_red - cl_red)]
    if missing_red:
        failures.append({"check": "redefines_missing",
                         "detail": "REDEFINES clauses in source not declared in MD",
                         "items": missing_red})

    # -- Check 5: Calls -------------------------------------------------------
    missing_calls = sorted(set(gt["calls_to"]) - set(cl["calls_to"]))
    if missing_calls:
        failures.append({"check": "calls_missing",
                         "detail": "CALL targets in source not listed in MD calls_to",
                         "items": missing_calls})

    # -- Check 6: Copybooks ---------------------------------------------------
    missing_cpyb = sorted(set(gt["copybooks"]) - set(cl["copybooks"]))
    if missing_cpyb:
        failures.append({"check": "copybooks_missing",
                         "detail": "COPY statements in source not listed in MD copybooks_used",
                         "items": missing_cpyb})

    # -- Check 7: No fabricated T04 score -------------------------------------
    if not cl["t04_score_is_null"]:
        failures.append({"check": "fabricated_t04_score",
                         "detail": "t04_semantic_score is non-null with no judge report present",
                         "value": cl["t04_score_in_md"]})

    # -- Check 8: Propagated lint_warnings ------------------------------------
    lint_warns = cl.get("lint_warnings", [])
    if lint_warns:
        warnings.append({"check": "lint_warnings_in_claims",
                         "detail": "Claims JSON carries lint warnings -- run lint_md.py and fix before resubmitting",
                         "items": lint_warns})

    # -- Emit report ----------------------------------------------------------
    gate_pass = len(failures) == 0
    report = {
        "program_id": program_id,
        "gate_run_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source_sha": gt["source_sha"],
        "md_sha": cl["md_sha"],
        "gate_pass": gate_pass,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "scope_terminators_suppressed": gt.get("scope_terminators_suppressed", []),
    }

    out_path = Path(f"validation/reports/{program_id}_gate.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    status = "PASS [OK]" if gate_pass else f"FAIL [{len(failures)} failures, {len(warnings)} warnings]"
    line = f"[GATE] {program_id}: {status}"
    print(line)
    log_lines.append(line)
    for f in failures:
        detail = f"  X {f['check']}: {str(f.get('items', f.get('value', '')))}"
        print(detail)
        log_lines.append(detail)
    for w in warnings:
        detail = f"  ~ {w['check']}: {w.get('items', '')}"
        print(detail)
        log_lines.append(detail)
    if gt.get("scope_terminators_suppressed"):
        note = f"  [suppressed] scope terminators (Cobol-REKT RC8): {gt['scope_terminators_suppressed']}"
        print(note)
        log_lines.append(note)

    return gate_pass, log_lines


if __name__ == "__main__":
    run_id = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    log_dir = Path("validation/logs")

    args = sys.argv[1:]
    if "--all" in args:
        targets = PROGRAMS
    elif args:
        targets = args
    else:
        targets = PROGRAMS

    unknown = [p for p in targets if p not in PROGRAMS]
    all_log_lines = [f"# gate_compare run {run_id}", f"# targets: {targets}"]
    if unknown:
        warn = f"[GATE] WARNING: unknown program(s): {unknown} -- no ground_truth/claims files found"
        print(warn)
        all_log_lines.append(warn)

    results = {}
    for p in targets:
        if p in PROGRAMS or p not in unknown:
            passed, lines = compare(p)
            results[p] = passed
            all_log_lines.extend(lines)

    summary_lines = [
        "",
        "-- Gate Summary ------------------------------------------------",
    ]
    for prog, passed in results.items():
        summary_lines.append(f"  {'PASS' if passed else 'FAIL'}  {prog}")
    total = len(results)
    passed_count = sum(results.values())
    summary_lines.append(f"  {passed_count}/{total} programs passed")
    summary_lines.append("----------------------------------------------------------------")

    for line in summary_lines:
        print(line)
    all_log_lines.extend(summary_lines)

    log(run_id, all_log_lines, log_dir)
    print(f"[GATE] log written: validation/logs/gate_{run_id}.log")

    sys.exit(0 if all(results.values()) else 1)
