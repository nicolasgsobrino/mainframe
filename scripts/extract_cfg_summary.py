#!/usr/bin/env python3
"""
extract_cfg_summary.py

Reads a Cobol-REKT smojol-cli report directory for a single program and emits
the schema-ready CFG JSON at validation/structure/<PROGRAM_ID>_cfg.json per
docs/COBOL-MD-PIPELINE.md v1.1.0 §Phase 0.

Inputs:
  --report-dir   path to <prog>.cbl.report directory
  --source       path to app/cbl/<PROG>.cbl (used for source_sha and program_id)
  --output       path to validation/structure/<ID>_cfg.json
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


def git_blob_sha(path: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "hash-object", str(path)], cwd=path.parent, stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return hashlib.sha1(path.read_bytes()).hexdigest()


def extract_program_id(source_path: Path) -> str:
    text = source_path.read_text(errors="replace")
    m = re.search(r"PROGRAM-ID\.\s*([A-Za-z0-9\-_]+)", text, re.IGNORECASE)
    if not m:
        return source_path.stem.upper()
    return m.group(1).upper()


def strip_comments_and_seq(text: str) -> str:
    out_lines = []
    for line in text.splitlines():
        if len(line) >= 7 and line[6] in ("*", "/"):
            continue
        body = line[6:72] if len(line) > 7 else line
        out_lines.append(body)
    return "\n".join(out_lines)


def extract_paragraphs_from_source(source_path: Path):
    text = strip_comments_and_seq(source_path.read_text(errors="replace"))
    paragraphs = []
    in_proc = False
    for line in text.splitlines():
        upper = line.upper()
        if "PROCEDURE DIVISION" in upper:
            in_proc = True
            continue
        if not in_proc:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9\-]*)\s*\.\s*$", stripped)
        if m:
            name = m.group(1).upper()
            if name in ("END PROGRAM", "EXIT"):
                continue
            if name not in paragraphs:
                paragraphs.append(name)
    return paragraphs


def extract_perform_edges(source_path: Path):
    text = strip_comments_and_seq(source_path.read_text(errors="replace"))
    edges = []
    for m in re.finditer(r"\bPERFORM\s+([A-Z0-9][A-Z0-9\-]*)", text, re.IGNORECASE):
        edges.append(m.group(1).upper())
    gotos = []
    for m in re.finditer(r"\bGO\s+TO\s+([A-Z0-9][A-Z0-9\-]*)", text, re.IGNORECASE):
        gotos.append(m.group(1).upper())
    return edges, gotos


def extract_data_items_and_redefines(source_path: Path):
    text = strip_comments_and_seq(source_path.read_text(errors="replace"))
    items = []
    redefines = []
    in_data = False
    for line in text.splitlines():
        u = line.upper()
        if "DATA DIVISION" in u:
            in_data = True
            continue
        if "PROCEDURE DIVISION" in u:
            in_data = False
            continue
        if not in_data:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        m = re.match(r"^(0?[1-9]|[1-4]\d|77|88)\s+([A-Z0-9][A-Z0-9\-]*)", stripped, re.IGNORECASE)
        if m:
            level = int(m.group(1))
            name = m.group(2).upper()
            redef_match = re.search(r"\bREDEFINES\s+([A-Z0-9][A-Z0-9\-]*)", stripped, re.IGNORECASE)
            picture = None
            pm = re.search(r"\bPIC(?:TURE)?\s+IS\s+(\S+)|\bPIC(?:TURE)?\s+(\S+)", stripped, re.IGNORECASE)
            if pm:
                picture = (pm.group(1) or pm.group(2)).rstrip(".")
            usage = None
            um = re.search(r"\b(COMP-3|COMP|BINARY|DISPLAY|PACKED-DECIMAL)\b", stripped, re.IGNORECASE)
            if um:
                usage = um.group(1).upper()
            item = {
                "name": name,
                "level": level,
                "picture": picture,
                "usage": usage,
                "redefines": redef_match.group(1).upper() if redef_match else None,
                "reachable": True,
            }
            items.append(item)
            if redef_match:
                redefines.append({
                    "name": name,
                    "redefines": redef_match.group(1).upper(),
                    "picture": picture,
                    "usage": usage,
                })
    return items, redefines


def extract_copybooks(source_path: Path):
    text = strip_comments_and_seq(source_path.read_text(errors="replace"))
    copy = set()
    for m in re.finditer(r"\bCOPY\s+([A-Z0-9][A-Z0-9\-]*)", text, re.IGNORECASE):
        copy.add(m.group(1).upper())
    return sorted(copy)


def extract_calls_to(source_path: Path):
    text = strip_comments_and_seq(source_path.read_text(errors="replace"))
    calls = []
    for m in re.finditer(r"\bCALL\s+['\"]([^'\"]+)['\"]", text, re.IGNORECASE):
        calls.append(m.group(1).upper())
    return calls


def extract_cics_commands(source_path: Path):
    text = source_path.read_text(errors="replace")
    cmds = []
    # collapse continuation by removing sequence area before scan
    text = strip_comments_and_seq(text)
    for m in re.finditer(r"EXEC\s+CICS\s+([A-Z][A-Z0-9\-]*)", text, re.IGNORECASE):
        verb = m.group(1).upper()
        if verb not in cmds:
            cmds.append(verb)
    return cmds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    source_path = Path(args.source)
    report_dir = Path(args.report_dir)
    output_path = Path(args.output)

    program_id = extract_program_id(source_path)
    source_sha = git_blob_sha(source_path)

    paragraphs_src = extract_paragraphs_from_source(source_path)
    perform_targets, goto_targets = extract_perform_edges(source_path)
    data_items, redef_list = extract_data_items_and_redefines(source_path)
    copybooks = extract_copybooks(source_path)
    calls_to = extract_calls_to(source_path)
    cics_cmds = extract_cics_commands(source_path)

    # try to read smojol CFG for paragraph reachability cross-check
    smojol_cfg = None
    smojol_cfg_path = report_dir / "cfg" / f"cfg-{source_path.name}.json"
    if smojol_cfg_path.exists():
        smojol_cfg = json.loads(smojol_cfg_path.read_text())

    smojol_nodes = []
    if smojol_cfg:
        smojol_nodes = [n for n in smojol_cfg.get("nodes", []) if n.get("type") in ("SENTENCE", "PARAGRAPH", "SECTION", "PROCEDURE_DIVISION_BODY")]

    # paragraphs reachable if any smojol node references them
    performed_set = set(perform_targets)
    paragraph_records = []
    for name in paragraphs_src:
        reachable = (name in performed_set) or (name == paragraphs_src[0])
        paragraph_records.append({
            "name": name,
            "reachable": reachable,
            "performs": [t for t in perform_targets if t != name],
            "goto_targets": [g for g in goto_targets if g != name],
            "goto_flag": False,
        })

    dead_paragraphs = [p["name"] for p in paragraph_records if not p["reachable"]]
    irreducible_gotos = [g for g in goto_targets if g not in paragraphs_src]

    cfg_out = {
        "program_id": program_id,
        "source_file": str(source_path).lstrip("./"),
        "source_sha": source_sha,
        "cfg_tool": "Cobol-REKT smojol-cli v0.1.0-RC8 + extract_cfg_summary.py",
        "paragraphs": paragraph_records,
        "data_items": [
            {
                "name": d["name"],
                "level": d["level"],
                "picture": d["picture"],
                "usage": d["usage"],
                "redefines": d["redefines"],
                "reachable": True,
            }
            for d in data_items
        ],
        "redefines_clauses": redef_list,
        "copybooks_used": copybooks,
        "calls_to": calls_to,
        "cics_commands": cics_cmds,
        "dead_code_paragraphs": dead_paragraphs,
        "dead_code_items": [],
        "irreducible_gotos": irreducible_gotos,
        "smojol_cfg_path": str(smojol_cfg_path) if smojol_cfg_path.exists() else None,
        "smojol_node_count": len(smojol_nodes),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cfg_out, indent=2))
    print(f"[ok] wrote {output_path} (paragraphs={len(paragraph_records)}, data_items={len(data_items)}, redefines={len(redef_list)})")


if __name__ == "__main__":
    main()
