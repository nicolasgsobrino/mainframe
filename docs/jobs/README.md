# CardDemo Batch Jobs

Documentation for the JCL batch jobs in `app/jcl/`.

## Data File Setup

These jobs create and populate VSAM datasets from flat files.

| Job | Description |
|-----|-------------|
| [ACCTFILE](ACCTFILE.md) | Delete, define, and load the account data VSAM file |
| [CARDFILE](CARDFILE.md) | Rebuild card data VSAM with alternate index, including CICS close/reopen |
| [CUSTFILE](CUSTFILE.md) | Rebuild customer data VSAM with CICS close/reopen |
| [DEFCUST](DEFCUST.md) | Delete and redefine customer VSAM (alternate naming, no data load) |
| [DISCGRP](DISCGRP.md) | Delete, define, and load the disclosure group VSAM file |
| [DUSRSECJ](DUSRSECJ.md) | Create and populate user security VSAM from in-stream data |
| [ESDSRRDS](ESDSRRDS.md) | Define and populate ESDS and RRDS VSAM files for user security |
| [TCATBALF](TCATBALF.md) | Delete, define, and load the transaction category balance VSAM file |
| [TRANCATG](TRANCATG.md) | Delete, define, and load the transaction category type VSAM file |
| [TRANFILE](TRANFILE.md) | Rebuild transaction master VSAM with alternate index, including CICS close/reopen |
| [TRANIDX](TRANIDX.md) | Create alternate index on transaction master processed timestamp |
| [TRANTYPE](TRANTYPE.md) | Delete, define, and load the transaction type VSAM file |
| [XREFFILE](XREFFILE.md) | Rebuild card cross-reference VSAM with alternate index |

## GDG Definitions

These jobs define Generation Data Group bases for versioned datasets.

| Job | Description |
|-----|-------------|
| [DALYREJS](DALYREJS.md) | Define GDG base for daily transaction rejects (5 generations) |
| [DEFGDGB](DEFGDGB.md) | Define 6 GDG bases for transaction-related datasets |
| [DEFGDGD](DEFGDGD.md) | Define GDG bases for reference data and load first generations |
| [REPTFILE](REPTFILE.md) | Define GDG base for transaction reports (10 generations) |

## Transaction Processing

These jobs run batch programs that process transactions.

| Job | Description |
|-----|-------------|
| [COMBTRAN](COMBTRAN.md) | Sort/merge transaction backup with system transactions into VSAM master |
| [INTCALC](INTCALC.md) | Run interest calculation program (CBACT04C) |
| [POSTTRAN](POSTTRAN.md) | Run transaction posting program (CBTRN02C) |
| [TRANBKP](TRANBKP.md) | Back up transaction master to GDG, then reset VSAM file |

## Reporting

| Job | Description |
|-----|-------------|
| [PRTCATBL](PRTCATBL.md) | Unload, sort, and format transaction category balance report |
| [TRANREPT](TRANREPT.md) | Filter, sort, and format a transaction report by date range |

## Data Export / Import

| Job | Description |
|-----|-------------|
| [CBEXPORT](CBEXPORT.md) | Export multiple VSAM files into a single consolidated dataset |
| [CBIMPORT](CBIMPORT.md) | Import from consolidated export, splitting into normalized flat files |
| [READACCT](READACCT.md) | Read account master VSAM and export to flat file formats |
| [READCARD](READCARD.md) | Read and dump card master VSAM records |
| [READCUST](READCUST.md) | Read and dump customer master VSAM records |
| [READXREF](READXREF.md) | Read and dump card cross-reference VSAM records |

## CICS Administration

| Job | Description |
|-----|-------------|
| [CBADMCDJ](CBADMCDJ.md) | Define CardDemo CICS resource definitions (mapsets, programs, transactions) |
| [CLOSEFIL](CLOSEFIL.md) | Close CardDemo VSAM files in CICS region |
| [OPENFIL](OPENFIL.md) | Open CardDemo VSAM files in CICS region |

## Utility

| Job | Description |
|-----|-------------|
| [WAITSTEP](WAITSTEP.md) | Timed wait (duration in centiseconds) |
