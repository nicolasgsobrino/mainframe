# DEFGDGD

**Source:** [app/jcl/DEFGDGD.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/DEFGDGD.jcl)

Defines GDG bases for transaction reference data and loads their first generation. Covers transaction type, transaction category type, and disclosure group datasets.

## Steps

- **STEP10** -- Executes IDCAMS to define the GDG base for transaction type (TRANTYPE.BKUP) with LIMIT(5) and SCRATCH.
- **STEP20** -- Executes IEBGENER to copy the transaction type flat file (TRANTYPE.PS) into the first generation of the TRANTYPE.BKUP GDG. Conditional on prior step success.
- **STEP30** -- Executes IDCAMS to define the GDG base for transaction category type (TRANCATG.PS.BKUP) with LIMIT(5) and SCRATCH. Conditional on prior step success.
- **STEP40** -- Executes IEBGENER to copy the transaction category flat file (TRANCATG.PS) into the first generation of the TRANCATG.PS.BKUP GDG. Conditional on prior step success.
- **STEP50** -- Executes IDCAMS to define the GDG base for disclosure group (DISCGRP.BKUP) with LIMIT(5) and SCRATCH.
- **STEP60** -- Executes IEBGENER to copy the disclosure group flat file (DISCGRP.PS) into the first generation of the DISCGRP.BKUP GDG. Conditional on prior step success.
