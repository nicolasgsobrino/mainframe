#!/usr/bin/env python3
"""
extract_ground_truth.py -- normalize CFG JSON into gate-comparable ground truth.

Reads:  validation/structure/{PROGRAM}_cfg.json  (produced by extract_cfg_local.py)
Writes: validation/ground_truth/{PROGRAM}_gt.json
        validation/logs/gt_{TIMESTAMP}.log        (append-only run log)

No LLM. No external dependencies beyond stdlib + json/pathlib.
Runnable on any machine with Python 3.8+.

Cobol-REKT RC8 known issue: scope terminators (END-IF, END-EXEC,
END-PERFORM, END-EVALUATE, END-READ, END-WRITE, END-STRING,
END-UNSTRING, END-MULTIPLY, END-DIVIDE, END-ADD, END-SUBTRACT,
END-COMPUTE, END-SEARCH) are misidentified as paragraph names and
reported as BOTH dead code AND reachable paragraphs in some programs.
These are filtered from both lists before gate comparison.

Usage:
    python validation/extract_ground_truth.py              # all programs (auto-discovered)
    python validation/extract_ground_truth.py CBACT01C     # single program
    python validation/extract_ground_truth.py CBACT01C COBSWAIT  # subset
"""
import io
import json
import sys
import hashlib
import datetime
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except AttributeError:
    pass

try:
    from validation.cobol_vocab import COBOL_SCOPE_TERMINATORS
except ImportError:
    try:
        from cobol_vocab import COBOL_SCOPE_TERMINATORS
    except ImportError:
        # Hard-coded fallback -- keep in sync with cobol_vocab.py
        COBOL_SCOPE_TERMINATORS = frozenset({
            "END-EXEC", "END-IF", "END-PERFORM", "END-EVALUATE",
            "END-READ", "END-WRITE", "END-STRING", "END-UNSTRING",
            "END-MULTIPLY", "END-DIVIDE", "END-ADD", "END-SUBTRACT",
            "END-COMPUTE", "END-SEARCH", "END-CALL", "END-REWRITE",
            "END-DELETE", "END-START", "END-RETURN",
        })


def _discover_programs() -> list[str]:
    """Auto-discover programs that have a cfg JSON in validation/structure/."""
    structure_dir = Path("validation/structure")
    if not structure_dir.exists():
        return []
    return sorted(
        p.stem.replace("_cfg", "")
        for p in structure_dir.glob("*_cfg.json")
    )


def log(run_id: str, lines: list, log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"gt_{run_id}.log"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return log_path


def extract(program_id: str) -> dict:
    cfg_path = Path(f"validation/structure/{program_id}_cfg.json")
    if not cfg_path.exists():
        print(f"[GT] ERROR: {cfg_path} not found -- skipping {program_id}")
        return {}

    raw = cfg_path.read_bytes()
    cfg = json.loads(raw)

    # Filter Cobol-REKT RC8 false-positive scope terminators from dead list
    raw_dead = cfg.get("dead_code_paragraphs", [])
    filtered_dead = [p for p in raw_dead if p not in COBOL_SCOPE_TERMINATORS]
    suppressed_dead = set(p for p in raw_dead if p in COBOL_SCOPE_TERMINATORS)

    # Filter Cobol-REKT RC8 false-positive scope terminators from reachable list.
    raw_reachable = [
        p["name"] for p in cfg.get("paragraphs", []) if p.get("reachable", False)
    ]
    filtered_reachable = [p for p in raw_reachable if p not in COBOL_SCOPE_TERMINATORS]
    suppressed_reachable = set(p for p in raw_reachable if p in COBOL_SCOPE_TERMINATORS)

    suppressed_all = sorted(suppressed_dead | suppressed_reachable)

    gt = {
        "program_id": program_id,
        "source_sha": cfg.get("source_sha", "unknown"),
        "cfg_sha": hashlib.sha256(raw).hexdigest()[:12],
        "extracted_at": datetime.datetime.utcnow().isoformat() + "Z",
        "paragraphs_reachable": sorted(set(filtered_reachable)),
        "paragraphs_dead": sorted(filtered_dead),
        "scope_terminators_suppressed": suppressed_all,
        "data_items_level01": sorted({
            d["name"] for d in cfg.get("data_items", []) if d.get("level") == 1
        }),
        "redefines_pairs": sorted([
            [r["name"], r["redefines"]]
            for r in cfg.get("redefines_clauses", [])
        ]),
        "calls_to": sorted(cfg.get("calls_to", [])),
        "copybooks": sorted(cfg.get("copybooks_used", [])),
        "cics_commands": cfg.get("cics_commands", []),
    }

    out_path = Path(f"validation/ground_truth/{program_id}_gt.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(gt, indent=2), encoding="utf-8")

    suppressed_note = f", {len(suppressed_all)} terminators suppressed" if suppressed_all else ""
    line = (
        f"[GT] {program_id}: "
        f"{len(gt['paragraphs_reachable'])} reachable, "
        f"{len(gt['paragraphs_dead'])} dead{suppressed_note}, "
        f"{len(gt['data_items_level01'])} L01 items, "
        f"{len(gt['redefines_pairs'])} redefines"
    )
    print(line)
    return gt, line


if __name__ == "__main__":
    run_id = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    log_dir = Path("validation/logs")

    # Auto-discover all programs with a CFG file; explicit args override
    discovered = _discover_programs()
    targets = sys.argv[1:] if sys.argv[1:] else discovered

    # Warn only for programs that have no cfg file
    unknown = [p for p in targets
               if not Path(f"validation/structure/{p}_cfg.json").exists()]
    run_lines = [f"# extract_ground_truth run {run_id}", f"# targets: {targets}"]
    if unknown:
        warn = f"[GT] WARNING: no cfg file found for: {unknown}"
        print(warn)
        run_lines.append(warn)

    for p in targets:
        if Path(f"validation/structure/{p}_cfg.json").exists():
            result = extract(p)
            if result:
                _, line = result
                run_lines.append(line)

    log(run_id, run_lines, log_dir)
    print(f"[GT] log written: validation/logs/gt_{run_id}.log")
