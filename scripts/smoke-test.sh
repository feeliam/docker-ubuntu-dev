#!/bin/bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
usage() {
    echo 'Usage: scripts/smoke-test.sh [options]'
    common_usage
    echo '  --all          build/test all 24 combinations (overrides selectors)'
    echo '  --skip-build   use existing local images'
    echo 'Requires host Python 3, OpenSSH client and Docker. Results: .test-results/'
}
defaults
parse smoke "$@"
docker_ready
args=(--ubuntu "$ubuntu" --variant "$variant" --arch "$arch")
[[ $all == 0 ]] || args+=(--all)
[[ $skip_build == 0 ]] || args+=(--skip-build)
exec python3 "$SCRIPT_DIR/smoke.py" "${args[@]}"
