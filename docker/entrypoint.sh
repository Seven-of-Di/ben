#!/bin/bash --login

set -euo pipefail
# ... Run whatever commands ...
# ... TODO: Add your entrypoint wrapper commands ...

set +euo pipefail

conda activate ben

# Re-enable strict mode:
set -euo pipefail

# exec the final command:
exec python $@
