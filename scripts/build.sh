#!/bin/bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
usage() { echo 'Usage: scripts/build.sh [options]'; common_usage; }
defaults
parse build "$@"
docker_ready
echo "Building $image from $context"
exec docker buildx build --platform "linux/$arch" --progress plain --load --tag "$image" "$context"
