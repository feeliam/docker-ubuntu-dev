#!/bin/bash
# Shared host-side argument handling; compatible with macOS Bash 3.2.
set -Eeuo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
fail() { echo "Error: $*" >&2; exit 1; }
need_value() { [[ $# -ge 2 && -n $2 && $2 != --* ]] || fail "$1 requires a value"; }
host_arch() {
    case $(uname -m) in
        arm64|aarch64) echo arm64 ;;
        amd64|x86_64) echo amd64 ;;
        *) fail 'Cannot detect architecture; specify --arch amd64 or --arch arm64.' ;;
    esac
}
defaults() {
    ubuntu=22.04; variant=base; arch=$(host_arch)
    name=''; ssh_port=2222; web_port=6080; bind=127.0.0.1
    workspace=''; home_volume=''; all=0; skip_build=0
}
common_usage() {
    cat <<'HELP'
  --ubuntu 18.04|20.04|22.04      default: 22.04
  --variant base|desktop|ros|desktop-ros   default: base
  --arch amd64|arm64             default: host architecture
  -h, --help
HELP
}
parse() {
    local mode=$1; shift
    while [[ $# -gt 0 ]]; do
        case $1 in
            --ubuntu) need_value "$@"; ubuntu=$2; shift 2 ;;
            --variant) need_value "$@"; variant=$2; shift 2 ;;
            --arch) need_value "$@"; arch=$2; shift 2 ;;
            --name|--ssh-port|--web-port|--bind|--workspace|--home-volume)
                [[ $mode == run ]] || fail "$1 is only supported by run.sh"
                need_value "$@"
                case $1 in
                    --name) name=$2 ;; --ssh-port) ssh_port=$2 ;; --web-port) web_port=$2 ;;
                    --bind) bind=$2 ;; --workspace) workspace=$2 ;; --home-volume) home_volume=$2 ;;
                esac
                shift 2 ;;
            --all) [[ $mode == smoke ]] || fail '--all is only supported by smoke-test.sh'; all=1; shift ;;
            --skip-build) [[ $mode == smoke ]] || fail '--skip-build is only supported by smoke-test.sh'; skip_build=1; shift ;;
            -h|--help) usage; exit 0 ;;
            *) fail "Unknown argument: $1 (see --help)" ;;
        esac
    done
    case $ubuntu in 18.04|20.04|22.04) ;; *) fail 'Unsupported --ubuntu' ;; esac
    case $variant in base|desktop|ros|desktop-ros) ;; *) fail 'Unsupported --variant' ;; esac
    case $arch in amd64|arm64) ;; *) fail 'Unsupported --arch' ;; esac
    local suffix=''
    [[ $variant == base ]] || suffix="-$variant"
    context="$REPO_ROOT/ubuntu${ubuntu/./}$suffix/$arch"
    image="ubuntu-dev:$ubuntu-$variant-$arch"
    name=${name:-ubuntu-dev-${ubuntu/./}-$variant-$arch}
}
docker_ready() {
    command -v docker >/dev/null || fail 'Install Docker with Buildx first.'
    docker info >/dev/null 2>&1 || fail 'Docker is unavailable. Start Docker Desktop/Engine and check docker context ls.'
}
