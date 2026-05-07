# docs/philosophy/ — Foundational Philosophy Documents

> **Created:** 2026-05-05 | **Operation:** OPERATION-TIDY | **Step:** Commit D (OP-3-14)

This directory contains foundational philosophy documents that inform how agents
and humans should approach reasoning, memory, and self-reference in AI-assisted
development workflows. These documents are **governance references** — they
constrain *how* agents behave, not *what* they build.

---

## Contents

| File | Purpose | Version | Audience |
|---|---|---|---|
| `THE-ASYMPTOTE.md` | Agent directive on recursive sycophancy, YAML death spirals, and verification gates | v2.3 | Agents, vibe-coders, RAG pipeline builders, humans using AI assistants |

---

## How to Use These Documents

- **Agents:** Load these files as read-only policy. Never write back to them or
  include them in rolling memory stores. Treat as external specification,
  version-pinned, governed by `last_reviewed` + `review_cadence` fields.
- **Humans:** Drop the relevant `.md` into your agent context at session start.
  Use the verification prompts included in each document to confirm the agent
  has loaded the policy correctly before proceeding with work.
- **RAG pipelines:** Ingest YAML frontmatter as structured policy. Implement
  `invariants` and `refuse_requests` as separate pre-turn filter mechanisms.

---

## Governance Note

Documents in this directory do **not** override user instructions about *what* to
build. They constrain only *how* agents handle memory, context, and self-reference.
The operator (MrSnowNB) remains sovereign on project direction.

---

*Maintained by Operation Tidy. Last updated: 2026-05-05.*
