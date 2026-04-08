# ESDSRRDS

**Source:** [app/jcl/ESDSRRDS.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/ESDSRRDS.jcl)

Defines and populates ESDS (Entry-Sequenced) and RRDS (Relative Record) VSAM files for user security data. Creates a flat file from in-stream data, then loads it into both an ESDS and an RRDS cluster.

## Steps

- **PREDEL** -- Executes IEFBR14 to delete the existing ESDSRRDS.PS flat file if present (disposition MOD,DELETE,DELETE).
- **STEP01** -- Executes IEBGENER to write in-stream user security records (5 admin users and 5 regular users) to a new flat file (ESDSRRDS.PS) with LRECL=80, RECFM=FB.
- **STEP02** -- Executes IDCAMS to delete any existing USRSEC.VSAM.ESDS cluster and define a new ESDS (NONINDEXED) cluster with 80-byte records, REUSE, FREESPACE(10,15), and CISZ(8192).
- **STEP03** -- Executes IDCAMS REPRO to copy data from the flat file (ESDSRRDS.PS) into the ESDS cluster.
- **STEP04** -- Executes IDCAMS to delete any existing USRSEC.VSAM.RRDS cluster and define a new RRDS (NUMBERED) cluster with 80-byte records, REUSE, FREESPACE(10,15), and CISZ(8192).
- **STEP05** -- Executes IDCAMS REPRO to copy data from the flat file (ESDSRRDS.PS) into the RRDS cluster.
