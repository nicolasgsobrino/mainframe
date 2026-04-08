# DUSRSECJ

**Source:** [app/jcl/DUSRSECJ.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/DUSRSECJ.jcl)

Creates and populates the User Security VSAM KSDS file. Generates a flat file from in-stream user data (admin and regular user records), defines the VSAM cluster, and loads the data into it.

## Steps

- **PREDEL** -- Executes IEFBR14 to delete the existing USRSEC.PS flat file if present (disposition MOD,DELETE,DELETE).
- **STEP01** -- Executes IEBGENER to write in-stream user security records (5 admin users and 5 regular users with IDs, names, and passwords) to a new flat file (USRSEC.PS) with LRECL=80, RECFM=FB.
- **STEP02** -- Executes IDCAMS to delete any existing USRSEC.VSAM.KSDS cluster and define a new one with 8-byte keys at offset 0, 80-byte fixed records, REUSE, FREESPACE(10,15), and CISZ(8192).
- **STEP03** -- Executes IDCAMS REPRO to copy user security data from the flat file (USRSEC.PS) into the VSAM KSDS cluster.
