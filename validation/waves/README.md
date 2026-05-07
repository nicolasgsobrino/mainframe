# validation/waves/ - Multi-Pass Proposition Pipeline

## Overview

The `validation/waves/` directory contains the output of the multi-pass proposition pipeline, organized by wave number. Each wave represents a distinct phase in the COBOL program analysis and proposition generation process.

## Wave Structure

### wave-1/ - Pass 1: Annotation & Pattern Analysis

**Purpose:** Initial pass that extracts patterns and generates annotations for COBOL programs.

**File Patterns:**
- `{PROG}_annotations.json` - Extracted annotations
- `{PROG}_phantoms.json` - Phantom definitions
- `byte_layouts/{PROG}.json` - Byte layout data
- `fallthrough/{PROG}.json` - Fallthrough analysis
- `file_control/{PROG}.json` - File control records
- `paragraph_io/{PROG}.json` - Paragraph I/O analysis

**File Count:** 45 files (17 root files + 28 subdirectory files)
- wave-1 root: 17 files
- wave-1/byte_layouts: 7 files
- wave-1/fallthrough: 7 files
- wave-1/file_control: 7 files
- wave-1/paragraph_io: 7 files

### wave-2/ - Pass 2: LLM Proposition Generation

**Purpose:** Secondary pass that uses LLM to generate propositions from annotations.

**File Patterns:**
- `{PROG}_llm_requests.jsonl` - LLM API requests
- `{PROG}_propositions.json` - Generated propositions
- `_dispatch_manifest.json` - Batch dispatch manifest

**File Count:** 18 files (batch dispatch + 7 programs)

### wave-3/ - Pass 3: Synthesis & Validation

**Purpose:** Final pass that synthesizes responses and validates propositions.

**File Patterns:**
- `{PROG}_synth_requests.jsonl` - Synthesis requests
- `{PROG}_responses.jsonl` - LLM responses
- `{PROG}_synthesis.jsonl` - Final synthesis output

**File Count:** 8 files (7 programs)

## Naming Conventions

- **Program ID:** 6-character uppercase alphanumeric (e.g., CBACT01C, CBCUS01C)
- **Wave Prefix:** `wave-N/` where N = 1, 2, or 3
- **JSON Files:** Standard JSON with consistent schema
- **JSONL Files:** JSON Lines format (one JSON object per line)

## Provenance

```
wave-1 → wave-2 → wave-3
   ↓         ↓         ↓
Annotations → Propositions → Synthesis
```

Each wave consumes output from the previous wave, creating a deterministic pipeline:

1. **wave-1** reads COBOL source files and produces annotations
2. **wave-2** reads wave-1 annotations and produces propositions via LLM
3. **wave-3** reads wave-2 propositions and produces validated synthesis

## Usage

- **For developers:** Review wave-N files to understand analysis pipeline output
- **For validators:** Use wave-3 synthesis as the gold standard for validation
- **For re-runs:** Re-run `scripts/run_full_batch.sh` to regenerate all waves