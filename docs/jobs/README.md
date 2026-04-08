# CardDemo Batch Jobs

Documentation for the JCL batch jobs in `app/jcl/`.

**Tags:** `VSAM` `CICS` `COBOL` `SORT` `GDG` `AIX`

## Data File Setup

These jobs create and populate VSAM datasets from flat files.

| Job | Tags | Description |
|-----|------|-------------|
| [ACCTFILE](ACCTFILE.md) | `VSAM` | Delete, define, and load the account data VSAM file |
| [CARDFILE](CARDFILE.md) | `VSAM` `AIX` `CICS` | Rebuild card data VSAM with alternate index, including CICS close/reopen |
| [CUSTFILE](CUSTFILE.md) | `VSAM` `CICS` | Rebuild customer data VSAM with CICS close/reopen |
| [DEFCUST](DEFCUST.md) | `VSAM` | Delete and redefine customer VSAM (alternate naming, no data load) |
| [DISCGRP](DISCGRP.md) | `VSAM` | Delete, define, and load the disclosure group VSAM file |
| [DUSRSECJ](DUSRSECJ.md) | `VSAM` | Create and populate user security VSAM from in-stream data |
| [ESDSRRDS](ESDSRRDS.md) | `VSAM` | Define and populate ESDS and RRDS VSAM files for user security |
| [TCATBALF](TCATBALF.md) | `VSAM` | Delete, define, and load the transaction category balance VSAM file |
| [TRANCATG](TRANCATG.md) | `VSAM` | Delete, define, and load the transaction category type VSAM file |
| [TRANFILE](TRANFILE.md) | `VSAM` `AIX` `CICS` | Rebuild transaction master VSAM with alternate index, including CICS close/reopen |
| [TRANIDX](TRANIDX.md) | `AIX` | Create alternate index on transaction master processed timestamp |
| [TRANTYPE](TRANTYPE.md) | `VSAM` | Delete, define, and load the transaction type VSAM file |
| [XREFFILE](XREFFILE.md) | `VSAM` `AIX` | Rebuild card cross-reference VSAM with alternate index |

## GDG Definitions

These jobs define Generation Data Group bases for versioned datasets.

| Job | Tags | Description |
|-----|------|-------------|
| [DALYREJS](DALYREJS.md) | `GDG` | Define GDG base for daily transaction rejects (5 generations) |
| [DEFGDGB](DEFGDGB.md) | `GDG` | Define 6 GDG bases for transaction-related datasets |
| [DEFGDGD](DEFGDGD.md) | `GDG` | Define GDG bases for reference data and load first generations |
| [REPTFILE](REPTFILE.md) | `GDG` | Define GDG base for transaction reports (10 generations) |

## Transaction Processing

These jobs run batch programs that process transactions.

| Job | Tags | Description |
|-----|------|-------------|
| [COMBTRAN](COMBTRAN.md) | `VSAM` `SORT` `GDG` | Sort/merge transaction backup with system transactions into VSAM master |
| [INTCALC](INTCALC.md) | `COBOL` `GDG` | Run interest calculation program (CBACT04C) |
| [POSTTRAN](POSTTRAN.md) | `COBOL` `GDG` | Run transaction posting program (CBTRN02C) |
| [TRANBKP](TRANBKP.md) | `VSAM` `AIX` `GDG` | Back up transaction master to GDG, then reset VSAM file |

## Reporting

| Job | Tags | Description |
|-----|------|-------------|
| [PRTCATBL](PRTCATBL.md) | `SORT` `GDG` | Unload, sort, and format transaction category balance report |
| [TRANREPT](TRANREPT.md) | `COBOL` `SORT` `GDG` | Filter, sort, and format a transaction report by date range |

## Data Export / Import

| Job | Tags | Description |
|-----|------|-------------|
| [CBEXPORT](CBEXPORT.md) | `COBOL` `VSAM` | Export multiple VSAM files into a single consolidated dataset |
| [CBIMPORT](CBIMPORT.md) | `COBOL` | Import from consolidated export, splitting into normalized flat files |
| [READACCT](READACCT.md) | `COBOL` | Read account master VSAM and export to flat file formats |
| [READCARD](READCARD.md) | `COBOL` | Read and dump card master VSAM records |
| [READCUST](READCUST.md) | `COBOL` | Read and dump customer master VSAM records |
| [READXREF](READXREF.md) | `COBOL` | Read and dump card cross-reference VSAM records |

## CICS Administration

| Job | Tags | Description |
|-----|------|-------------|
| [CBADMCDJ](CBADMCDJ.md) | `CICS` | Define CardDemo CICS resource definitions (mapsets, programs, transactions) |
| [CLOSEFIL](CLOSEFIL.md) | `CICS` | Close CardDemo VSAM files in CICS region |
| [OPENFIL](OPENFIL.md) | `CICS` | Open CardDemo VSAM files in CICS region |

## Utility

| Job | Tags | Description |
|-----|------|-------------|
| [WAITSTEP](WAITSTEP.md) | `COBOL` | Timed wait (duration in centiseconds) |
