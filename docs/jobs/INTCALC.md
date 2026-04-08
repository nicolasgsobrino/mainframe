# INTCALC

**Source:** [app/jcl/INTCALC.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/INTCALC.jcl)

Runs the interest calculation batch program (CBACT04C) to process the transaction category balance file and compute interest and fees. Reads account, card cross-reference, and disclosure group data, then writes system transaction records to a new GDG generation.

## Steps

- **STEP15** -- Executes program CBACT04C with PARM='2022071800'. Reads from TCATBALF (transaction category balance), XREFFILE and XREFFIL1 (card cross-reference and its AIX path), ACCTFILE (account data), and DISCGRP (disclosure group) VSAM files. Writes output to a new generation of the SYSTRAN GDG with LRECL=350, RECFM=F.
