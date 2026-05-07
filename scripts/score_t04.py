#!/usr/bin/env python3
"""T04 — Semantic Accuracy scorer scaffold.

A real run requires an LLM-as-judge endpoint. This scaffold:
  - loads CFG paragraph list + MD procedure_paragraphs[] and business_rules[]
  - emits a judging request payload per paragraph at --out-requests
  - if --judgments is supplied (JSON list of {paragraph, score, reason}), computes weighted mean
  - threshold ≥ 0.85; dead-code paragraphs weighted at 0.1×

Do NOT invent scores. When no --judgments file is supplied, T04 remains PENDING
and the tier status is logged as DEFERRED with reason="no judge endpoint".
"""
import argparse
import json
import sys
from pathlib import Path
import yaml


def load_md(md_path: Path):
    content = md_path.read_text()
    parts = content.split("---", 2)
    front = yaml.safe_load(parts[1]) or {}
    body = parts[2] if len(parts) >= 3 else ""
    return front, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--judgments", default=None,
                    help="JSON file: [{paragraph, score 0-5, reason}, ...]")
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-requests", default=None)
    args = ap.parse_args()

    cfg = json.loads(Path(args.cfg).read_text())
    front, body = load_md(Path(args.md))

    cfg_paragraphs = cfg.get("paragraphs", [])
    requests = []
    for p in cfg_paragraphs:
        requests.append({
            "paragraph": p["name"],
            "reachable": p.get("reachable", True),
            "judge_prompt": (
                "Score 0-5 for this paragraph's English translation vs COBOL source. "
                "5=complete, 4=minor imprecision, 3=some implicit logic missing, "
                "2=significant rule absent/wrong, 1=semantically incorrect, 0=missing/gibberish. "
                "Return JSON: {\"paragraph\":\"<name>\",\"score\":<int>,\"reason\":\"<sentence>\"}."
            ),
        })
    if args.out_requests:
        Path(args.out_requests).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_requests).write_text(json.dumps(requests, indent=2))

    result = {
        "tier": "T04",
        "file": str(args.md),
        "threshold": 0.85,
        "paragraph_count": len(cfg_paragraphs),
    }

    if not args.judgments:
        result["status"] = "DEFERRED"
        result["reason"] = "no judge endpoint configured; judge invocation must be performed separately"
        result["pass"] = None
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
        sys.exit(0)

    judgments = json.loads(Path(args.judgments).read_text())
    by_name = {j["paragraph"].upper(): j for j in judgments}
    reach_map = {p["name"].upper(): p.get("reachable", True) for p in cfg_paragraphs}

    total_weight = 0.0
    weighted_sum = 0.0
    per_para = []
    low = []
    for name, reachable in reach_map.items():
        j = by_name.get(name)
        if j is None:
            per_para.append({"paragraph": name, "score": 0, "note": "no judgment"})
            weight = 1.0 if reachable else 0.1
            total_weight += weight
            continue
        s = int(j.get("score", 0))
        weight = 1.0 if reachable else 0.1
        total_weight += weight
        weighted_sum += weight * (s / 5.0)
        per_para.append({"paragraph": name, "score": s, "reason": j.get("reason", "")})
        if s < 3:
            low.append({"paragraph": name, "score": s, "reason": j.get("reason", "")})

    score = weighted_sum / total_weight if total_weight else 0.0
    result.update({
        "score": round(score, 4),
        "pass": score >= 0.85,
        "per_paragraph": per_para,
        "low_scoring": low,
        "status": "PASS" if score >= 0.85 else "FAIL",
    })
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps({"tier": "T04", "file": args.md, "score": result["score"], "pass": result["pass"]}))
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
