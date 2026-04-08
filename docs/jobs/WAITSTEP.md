# WAITSTEP

**Source:** [app/jcl/WAITSTEP.jcl](https://github.com/mechanical-orchard/aws-mainframe-modernization-carddemo/blob/main/app/jcl/WAITSTEP.jcl)

Executes a timed wait using program COBSWAIT. The wait duration is specified in centiseconds via SYSIN input (default value 00003600 = 36 seconds).

## Steps

- **WAIT** -- Executes program COBSWAIT with a SYSIN parameter of 00003600 centiseconds (36 seconds), causing the job to pause for the specified duration.
