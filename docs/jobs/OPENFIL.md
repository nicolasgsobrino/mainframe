# OPENFIL

**Source:** [app/jcl/OPENFIL.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/OPENFIL.jcl)

Opens VSAM files in the CICS region (CICSAWSA) by issuing CEMT SET FILE OPEN commands through SDSF.

## Steps

- **OPCIFIL** -- Executes SDSF to issue five CEMT commands to the CICSAWSA CICS region, opening the following files: TRANSACT (transactions), CCXREF (card cross-reference), ACCTDAT (account data), CXACAIX (cross-reference AIX), and USRSEC (user security).
