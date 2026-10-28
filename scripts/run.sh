#!/bin/bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
usage() {
    echo 'Usage: scripts/run.sh [options]'
    common_usage
    cat <<'HELP'
  --name NAME              default: ubuntu-dev-VERSION-VARIANT-ARCH
  --ssh-port PORT          default: 2222
  --web-port PORT          desktop only, default: 6080
  --bind IPv4              default: 127.0.0.1; use 0.0.0.0 for LAN access
  --workspace DIRECTORY    bind an existing host directory to /workspace
  --home-volume NAME       named volume mounted at /home/CONTAINER_USER
Environment: CONTAINER_USER=ubuntu CONTAINER_PASSWORD=ubuntu
             VNC_PASSWORD=<container password> VNC_GEOMETRY=1920x1080
Requires Docker and host Python 3 (port checks).
HELP
}
defaults
parse run "$@"
command -v python3 >/dev/null || fail 'run.sh requires host Python 3 for port checks.'
[[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || fail 'Invalid container name.'
container_user=${CONTAINER_USER:-ubuntu}
container_password=${CONTAINER_PASSWORD:-ubuntu}
[[ $container_user =~ ^[a-z_][a-z0-9_-]{0,31}$ && $container_user != root ]] || fail 'CONTAINER_USER must be a valid non-root username.'
if [[ -n $home_volume ]]; then
    [[ $home_volume =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]+$ ]] || fail 'Invalid named volume.'
fi
if [[ -n $workspace ]]; then
    [[ -d $workspace ]] || fail '--workspace must point to an existing directory.'
    workspace=$(cd -- "$workspace" && pwd)
    [[ $workspace != *,* ]] || fail '--workspace must not contain commas.'
fi
ports=("$ssh_port")
[[ $variant != *desktop* ]] || ports+=("$web_port")
python3 - "$bind" "${ports[@]}" <<'PY'
import ipaddress, socket, sys
try:
    ipaddress.IPv4Address(sys.argv[1])
    ports = [int(p) for p in sys.argv[2:] if p and all('0' <= c <= '9' for c in p)]
    if len(ports) != len(sys.argv[2:]) or any(not 1 <= p <= 65535 for p in ports):
        raise ValueError('Ports must be integers between 1 and 65535')
    if len(set(ports)) != len(ports):
        raise ValueError('SSH and web ports must differ')
    for port in ports:
        with socket.socket() as sock:
            sock.bind((sys.argv[1], port))
except (ValueError, OSError) as exc:
    sys.exit('Port check failed: %s. Choose --ssh-port/--web-port or --bind; inspect docker ps.' % exc)
PY
docker_ready
if docker container inspect "$name" >/dev/null 2>&1; then
    fail "Container $name already exists. Reuse it with: docker start $name; or choose --name ANOTHER_NAME."
fi
docker image inspect "$image" >/dev/null 2>&1 || fail "Image $image is missing. Run scripts/build.sh --ubuntu $ubuntu --variant $variant --arch $arch"
args=(--platform "linux/$arch" --name "$name" --label ubuntu-dev.managed=true
      -p "$bind:$ssh_port:22" -e "USER=$container_user" -e "PASSWORD=$container_password")
if [[ $variant == *desktop* ]]; then
    args+=(-p "$bind:$web_port:80" --shm-size=512m
           -e "VNC_PASSWORD=${VNC_PASSWORD:-$container_password}" -e "VNC_GEOMETRY=${VNC_GEOMETRY:-1920x1080}")
fi
[[ -z $workspace ]] || args+=(--mount "type=bind,source=$workspace,target=/workspace")
[[ -z $home_volume ]] || args+=(--mount "type=volume,source=$home_volume,target=/home/$container_user")
# Only remove a container we have just created if Docker cannot start it.
cid=$(docker create "${args[@]}" "$image")
if ! docker start "$cid" >/dev/null; then
    docker rm "$cid" >/dev/null
    fail 'Docker could not start the new container. Check ports and Docker logs.'
fi
echo "Started $name ($cid)"
echo "SSH: ssh $container_user@${bind/0.0.0.0/127.0.0.1} -p $ssh_port"
[[ $variant != *desktop* ]] || echo "Desktop: http://${bind/0.0.0.0/127.0.0.1}:$web_port/vnc.html?resize=remote"
echo "Logs: docker logs -f $name"
