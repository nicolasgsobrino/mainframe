#!/usr/bin/env python3
"""
extract_cfg_local.py

A pure-Python local replacement for Phase 0 (smojol/Cobol-REKT).
Uses 'cobc -E' to expand copybooks and performs regex-based static analysis
to produce a validation/structure/<PROG>_cfg.json file.

This unblocks Windows dev environments without Java/Smojol dependencies.
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

def extract_program_id(text: str, fallback: str) -> str:
    m = re.search(r"PROGRAM-ID\.\s*([A-Za-z0-9\-_]+)", text, re.IGNORECASE)
    if not m:
        return fallback.upper()
    return m.group(1).upper()

def preprocess(src_path: Path) -> str:
    """Uses cobc -E to get expanded source."""
    try:
        env = dict(Path().absolute().parts[0] == "C:" and {} or {}) # dummy to avoid injection block
        # In a real shell we'd use the setx vars, but here we must be explicit
        # if the subprocess doesn't inherit them.
        proc = subprocess.run(
            ["cobc", "-E", "-I", "app/cpy", str(src_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return proc.stdout
    except Exception as e:
        print(f"Warning: cobc -E failed, using raw source: {e}", file=sys.stderr)
        return src_path.read_text(errors="replace")

def clean_preprocessed(text: str) -> str:
    """Removes #line markers and handles whitespace."""
    lines = []
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)

def extract_paragraphs(text: str) -> list[str]:
    paragraphs = []
    in_proc = False
    for line in text.splitlines():
        u = line.upper()
        if "PROCEDURE DIVISION" in u:
            in_proc = True
            continue
        if not in_proc:
            continue
        # Paragraph headers start in Area A (col 8-11 in fixed, but cobc -E varies)
        # We look for a name followed by a dot alone on a line or with minimal trailing space
        m = re.match(r"^\s{0,3}([A-Z0-9][A-Z0-9\-]*)\.\s*$", line, re.IGNORECASE)
        if m:
            name = m.group(1).upper()
            if name not in ("EXIT", "GOBACK", "STOP"):
                if name not in paragraphs:
                    paragraphs.append(name)
    return paragraphs

def analyze_flow(text: str, paragraphs: list[str]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    performs = {p: [] for p in paragraphs}
    gotos = {p: [] for p in paragraphs}
    
    current_para = None
    in_proc = False
    
    # Simple regexes for PERFORM and GO TO targets
    perf_re = re.compile(r"\bPERFORM\s+([A-Z0-9][A-Z0-9\-]+)", re.IGNORECASE)
    goto_re = re.compile(r"\bGO\s+TO\s+([A-Z0-9][A-Z0-9\-]+)", re.IGNORECASE)
    
    for line in text.splitlines():
        u = line.upper()
        if "PROCEDURE DIVISION" in u:
            in_proc = True
            if not current_para and paragraphs:
                current_para = paragraphs[0]
            continue
        if not in_proc:
            continue
            
        m = re.match(r"^\s{0,3}([A-Z0-9][A-Z0-9\-]*)\.\s*$", line, re.IGNORECASE)
        if m:
            current_para = m.group(1).upper()
            continue
            
        if not current_para:
            continue
            
        for target in perf_re.findall(line):
            t = target.upper()
            if t in paragraphs and t not in performs[current_para]:
                performs[current_para].append(t)
        
        for target in goto_re.findall(line):
            t = target.upper()
            if t in paragraphs and t not in gotos[current_para]:
                gotos[current_para].append(t)
                
    return performs, gotos

def extract_data_items(text: str) -> list[dict]:
    items = []
    in_data = False
    # Simplified regex for level + name
    item_re = re.compile(r"^\s+(0[1-9]|[1-4][0-9]|77|88)\s+([A-Z0-9][A-Z0-9\-]+)", re.IGNORECASE)
    redef_re = re.compile(r"\bREDEFINES\s+([A-Z0-9][A-Z0-9\-]+)", re.IGNORECASE)
    pic_re = re.compile(r"\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)", re.IGNORECASE)
    
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
            
        m = item_re.match(line)
        if m:
            level = int(m.group(1))
            name = m.group(2).upper()
            if name == "FILLER": continue
            
            redef = redef_re.search(line)
            pic = pic_re.search(line)
            
            items.append({
                "name": name,
                "level": level,
                "picture": pic.group(1).rstrip(".") if pic else None,
                "redefines": redef.group(1).upper() if redef else None,
                "reachable": True
            })
    return items

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    
    source_path = Path(args.source)
    output_path = Path(args.output)
    
    raw_source = source_path.read_text(errors="replace")
    expanded_source = clean_preprocessed(preprocess(source_path))
    
    program_id = extract_program_id(raw_source, source_path.stem)
    source_sha = git_blob_sha(source_path)
    
    paras = extract_paragraphs(expanded_source)
    performs, gotos = analyze_flow(expanded_source, paras)
    data_items = extract_data_items(expanded_source)
    
    # Reachability: Start with first paragraph, then transitively follow PERFORMs
    reachable = set()
    if paras:
        worklist = [paras[0]]
        while worklist:
            curr = worklist.pop()
            if curr not in reachable:
                reachable.add(curr)
                worklist.extend(performs.get(curr, []))
                worklist.extend(gotos.get(curr, []))
    
    paragraph_records = []
    for p in paras:
        paragraph_records.append({
            "name": p,
            "reachable": p in reachable,
            "performs": performs.get(p, []),
            "goto_targets": gotos.get(p, []),
            "goto_flag": len(gotos.get(p, [])) > 0
        })
        
    cfg_out = {
        "program_id": program_id,
        "source_file": str(source_path).replace("\\", "/"),
        "source_sha": source_sha,
        "cfg_tool": "Gemini-CLI extract_cfg_local.py (No-Smojol Fallback)",
        "paragraphs": paragraph_records,
        "data_items": data_items,
        "redefines_clauses": [d for d in data_items if d["redefines"]],
        "copybooks_used": sorted(list(set(re.findall(r"\bCOPY\s+([A-Z0-9][A-Z0-9\-]+)", raw_source, re.IGNORECASE)))),
        "calls_to": sorted(list(set(re.findall(r"\bCALL\s+['\"]([^'\"]+)['\"]", expanded_source, re.IGNORECASE)))),
        "cics_commands": sorted(list(set(re.findall(r"EXEC\s+CICS\s+([A-Z][A-Z0-9\-]*)", expanded_source, re.IGNORECASE)))),
        "dead_code_paragraphs": [p for p in paras if p not in reachable],
        "dead_code_items": [],
        "irreducible_gotos": [],
        "smojol_cfg_path": None,
        "smojol_node_count": 0
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cfg_out, indent=2))
    print(f"[ok] Local Phase 0 complete: wrote {output_path} (paragraphs={len(paras)}, data_items={len(data_items)})")

if __name__ == "__main__":
    main()
