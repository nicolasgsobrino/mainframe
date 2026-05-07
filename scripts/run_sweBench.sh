#!/usr/bin/env bash
# T05 — SWE-bench Lite regression harness.
# This sandbox has no SWE-bench environment; exit with a clear DEFERRED signal
# so validators can record t05_regression_pass=null.
set -euo pipefail
cat <<'EOF'
{"tier":"T05","status":"DEFERRED","reason":"SWE-bench Lite environment not available in sandbox","pass":null}
EOF
exit 2
