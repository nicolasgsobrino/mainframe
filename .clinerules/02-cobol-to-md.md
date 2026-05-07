# COBOL to Markdown Translation Rules

> **Protocol Version:** `aifirst/1.0`
> **Status:** ACTIVE

## Overview

This document specifies the rules for converting COBOL source files into Markdown (`.md`) format. The primary goal is to ensure a **1:1 accurate translation** of the business logic while making the documentation "AI First" to support future knowledge graph generation.

## Translation Requirements

### 1:1 Accuracy

- The translated Markdown must capture 100% of the underlying business logic, conditions, loops, and data structures from the COBOL code.
- No logic may be abstracted away or summarized to the point of losing functional fidelity.
- The output must be verifiable against the original code to prove accurate translation (this is validated in Gate 3).

### AI First Formatting

- **YAML Frontmatter**: Every converted `.md` file MUST begin with a structured YAML header.
- **File Summary**: The document must include a concise, clear summary of what the file does. This summary will be used by downstream processes to create a knowledge graph.
- **Structure**: Use clear Markdown headings, bullet points, and code blocks where appropriate to optimize for LLM context parsing. Avoid dense, unstructured paragraphs.

## Output Schema

Every converted file must follow this structural template:

```markdown
---
file_name: "ORIGINAL_FILE.cbl"
type: "COBOL_PROGRAM" # or COPYBOOK, JCL, etc.
description: "A short, 1-2 sentence summary of the file's primary purpose."
dependencies:
  - "COPYBOOK1"
  - "COPYBOOK2"
---

# File Summary

[Provide a comprehensive summary of what the file does, suitable for ingestion into a knowledge graph. Detail the inputs, outputs, and core business function.]

## Data Structures

[Translate the WORKING-STORAGE and LINKAGE sections into logical, readable formats, noting types and hierarchies.]

## Business Logic

[Translate the PROCEDURE DIVISION logic 1:1. Use pseudocode, flow descriptions, or structured text that perfectly mirrors the COBOL execution path.]
```

## Validation

- Translations will be scored during the **G3 - VALIDATE** phase of the AiFirst protocol.
- T03 (Functional Output) will verify YAML validity and field-level matches.
- T04 (Semantic Accuracy) will use LLM-as-judge or human rubrics to verify the 1:1 faithfulness of the translated logic.
