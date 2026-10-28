#!/usr/bin/env python3
"""Real Docker integration checks. Only containers/volumes owned by this run are deleted."""
import argparse
import base64
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / ".test-results"


def run(*args, **kwargs):
    return subprocess.run(list(args), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True, timeout=kwargs.pop("timeout", 180), **kwargs).stdout.strip()


def wait_for(check, timeout=120):
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        try:
            result = check()
            if result:
                return result
        except Exception as exc:
            last = exc
        time.sleep(1)
    raise AssertionError("Readiness timeout: %s" % last)


def port(name, container_port):
    return int(run("docker", "port", name, str(container_port)).split(":")[-1])


def ssh(name, user, password, command, directory):
    askpass = directory / "askpass.sh"
    askpass.write_text('#!/bin/sh\nprintf "%s\\n" "$SMOKE_SSH_PASSWORD"\n')
    askpass.chmod(0o700)
    env = dict(os.environ, SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE="force",
               SMOKE_SSH_PASSWORD=password, DISPLAY=":99")
    return run("ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
               "-o", "ConnectTimeout=5", "-o", "PreferredAuthentications=password",
               "-o", "PubkeyAuthentication=no", "-o", "NumberOfPasswordPrompts=1",
               "-p", str(port(name, 22)), user + "@127.0.0.1", command,
               stdin=subprocess.DEVNULL, start_new_session=True, env=env, timeout=30)


VNC_CHECK = r'''
import ctypes, ctypes.util, socket, struct
def read(n):
    data = b''
    while len(data) < n:
        part = s.recv(n-len(data))
        if not part: raise RuntimeError('VNC closed connection')
        data += part
    return data
with socket.create_connection(('127.0.0.1', 5901), 5) as s:
    assert read(12).startswith(b'RFB ')
    s.sendall(b'RFB 003.008\n')
    types = read(read(1)[0])
    assert 2 in types, types
    s.sendall(b'\x02')
    challenge = read(16)
    key = bytes(int(format(c, '08b')[::-1], 2) for c in b'ubuntu'.ljust(8, b'\0'))
    lib = ctypes.CDLL(ctypes.util.find_library('crypto'))
    schedule = ctypes.create_string_buffer(128)
    lib.DES_set_key_unchecked(ctypes.c_char_p(key), ctypes.byref(schedule))
    response = b''
    for offset in (0, 8):
        out = ctypes.create_string_buffer(8)
        lib.DES_ecb_encrypt(ctypes.c_char_p(challenge[offset:offset+8]), out, ctypes.byref(schedule), 1)
        response += out.raw
    s.sendall(response)
    assert read(4) == b'\0\0\0\0', 'VNC authentication failed'
    s.sendall(b'\x01')
    width, height = struct.unpack('!HH', read(4))
    assert (width, height) == (1920, 1080), (width, height)
    print('VNC password authentication OK', width, height)
'''


def check_ros(name, distro):
    prefix = ("docker", "exec", "--user", "ubuntu", "-e", "HOME=/home/ubuntu", name, "bash", "-lc")
    if distro == "humble":
        command = r'''set -eo pipefail
test "$ROS_DISTRO" = humble
mkdir -p ~/smoke_ws/src
cd ~/smoke_ws/src
ros2 pkg create --build-type ament_cmake smoke_pkg
cd ..
colcon build --executor sequential
source install/setup.bash
timeout 25 ros2 topic pub /smoke std_msgs/msg/String "data: smoke_ok" -r 2 > /tmp/pub.log 2>&1 &
publisher=$!
trap 'kill "$publisher" 2>/dev/null || true' EXIT
sleep 3
timeout 20 ros2 topic echo /smoke std_msgs/msg/String --once | grep smoke_ok
'''
    else:
        command = r'''set -eo pipefail
mkdir -p ~/smoke_ws/src
cd ~/smoke_ws/src
catkin_create_pkg smoke_pkg roscpp rospy std_msgs
cd ..
catkin_make -j2
source devel/setup.bash
roscore > /tmp/roscore.log 2>&1 &
master=$!
trap 'kill "$master" "${publisher:-}" 2>/dev/null || true' EXIT
for i in $(seq 1 30); do rosparam list >/dev/null 2>&1 && break; sleep 1; done
rostopic pub -r 2 /smoke std_msgs/String 'data: smoke_ok' > /tmp/pub.log 2>&1 &
publisher=$!
timeout 20 rostopic echo -n 1 /smoke | grep smoke_ok
'''
    run(*prefix, command, timeout=240)


def test_one(version, variant, arch, build):
    tag = f"ubuntu-dev:{version}-{variant}-{arch}"
    key = f"{version}-{variant}-{arch}"
    log = RESULTS / (key + ".log")
    result = {"image": tag, "status": "FAIL", "checks": [], "log": str(log.relative_to(ROOT))}
    names = []
    volumes = []
    desktop, ros = "desktop" in variant, "ros" in variant
    distro = {"18.04": "melodic", "20.04": "noetic", "22.04": "humble"}[version]
    try:
        if build:
            with log.open("w") as stream:
                subprocess.run([str(ROOT / "scripts/build.sh"), "--ubuntu", version, "--variant", variant,
                                "--arch", arch], stdout=stream, stderr=subprocess.STDOUT,
                               check=True, timeout=3600)
            result["checks"].append("build")
        else:
            log.write_text("Using local image: " + tag + "\n")
        inspect = json.loads(run("docker", "image", "inspect", tag))[0]
        assert inspect["Architecture"] == arch, inspect["Architecture"]
        result["checks"].append("architecture")
        with tempfile.TemporaryDirectory(prefix="ubuntu-dev-smoke-") as temp:
            directory = Path(temp)
            name = "ubuntu-dev-smoke-" + uuid.uuid4().hex[:12]
            names.append(name)
            volume = name + "-home"
            volumes.append(volume)
            args = ["docker", "run", "-d", "--name", name, "--platform", "linux/" + arch,
                    "--mount", "type=volume,source=" + volume + ",target=/home/ubuntu",
                    "-p", "127.0.0.1::22"]
            if desktop:
                args += ["-p", "127.0.0.1::80", "--shm-size=512m"]
            run(*(args + [tag]))
            wait_for(lambda: ssh(name, "ubuntu", "ubuntu", "id -un", directory) == "ubuntu")
            result["checks"].append("default-password-ssh")
            expected_major = 2 if ros and distro == "melodic" else 3
            check = f'''set -e
test "$(. /etc/os-release; echo "$VERSION_ID")" = '{version}'
test "$(dpkg --print-architecture)" = '{arch}'
for command in gcc g++ gdb vim python python3 sshd; do command -v "$command"; done
python -c 'import sys; assert sys.version_info[0] == {expected_major}'
python3 -m pip --version
printf '#include <stdio.h>\\nint main(void) {{ puts("compile_ok"); return 0; }}\\n' > /tmp/hello.c
gcc -g /tmp/hello.c -o /tmp/hello
/tmp/hello | grep compile_ok
printf '#include <iostream>\\nint main() {{ std::cout << "cpp_ok"; }}\\n' > /tmp/hello.cpp
g++ -g /tmp/hello.cpp -o /tmp/hello-cpp
/tmp/hello-cpp | grep cpp_ok
test "$(id -u)" != 0
touch ~/persistent-marker
'''
            ssh(name, "ubuntu", "ubuntu", "bash -lc " + shlex.quote(check), directory)
            result["checks"].append("toolchain-and-python")
            sudo_check = "printf '%s\\n' ubuntu | sudo -S -p '' id -u"
            assert ssh(name, "ubuntu", "ubuntu", sudo_check, directory) == "0"
            run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(directory / "id_ed25519"))
            public_key = (directory / "id_ed25519.pub").read_text()
            run("docker", "exec", "-i", name, "bash", "-c",
                "install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh; "
                "cat > /home/ubuntu/.ssh/authorized_keys; "
                "chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys; chmod 600 /home/ubuntu/.ssh/authorized_keys",
                input=public_key)
            assert run("ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
                "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-i", str(directory / "id_ed25519"),
                "-p", str(port(name, 22)), "ubuntu@127.0.0.1", "id -un") == "ubuntu"
            assert "permitrootlogin no" in run("docker", "exec", name, "sshd", "-T")
            result["checks"].append("sudo-public-key-and-root-login-policy")
            if ros:
                assert ssh(name, "ubuntu", "ubuntu", "echo $ROS_DISTRO", directory) == distro
                check_ros(name, distro)
                result["checks"].append("ros-environment-build-pubsub")
            if desktop:
                web_port = port(name, 80)
                url = f"http://127.0.0.1:{web_port}/vnc.html"
                wait_for(lambda: urllib.request.urlopen(url, timeout=3).status == 200)
                # Check the actual websocket upgrade, not merely the static noVNC HTML.
                with socket.create_connection(("127.0.0.1", web_port), timeout=5) as sock:
                    request = ("GET /websockify HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                               "Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: "
                               + base64.b64encode(os.urandom(16)).decode() + "\r\n\r\n")
                    sock.sendall(request.encode())
                    assert b"101" in sock.recv(4096).split(b"\r\n")[0]
                wait_for(lambda: "mate-session" in run("docker", "exec", name, "pgrep", "-a", "mate-session"))
                run("docker", "exec", "-i", name, "python3", "-", input=VNC_CHECK)
                result["checks"].append("mate-novnc-websocket-vnc-auth")
                run("docker", "exec", "-d", "--user", "ubuntu", "-e", "HOME=/home/ubuntu", "-e", "DISPLAY=:1",
                    name, "firefox", "--no-remote", "--new-window", "data:text/html,<title>Ubuntu browser smoke</title><h1>OK</h1>")
                wait_for(lambda: "Ubuntu browser smoke" in run("docker", "exec", "--user", "ubuntu",
                    "-e", "HOME=/home/ubuntu", "-e", "DISPLAY=:1", name, "xwininfo", "-root", "-tree"), timeout=120)
                result["checks"].append("firefox-window")
                if ros:
                    executable = "rviz2" if distro == "humble" else "rviz"
                    run("docker", "exec", "-d", "--user", "ubuntu", "-e", "HOME=/home/ubuntu", "-e", "DISPLAY=:1", name,
                        "bash", "-lc", executable + " >/tmp/rviz-smoke.log 2>&1")
                    wait_for(lambda: "rviz" in run("docker", "exec", "--user", "ubuntu", "-e", "HOME=/home/ubuntu",
                        "-e", "DISPLAY=:1", name, "xwininfo", "-root", "-tree").lower(), timeout=120)
                    result["checks"].append("rviz-window")
            hostkey = run("docker", "exec", name, "cat", "/etc/ssh/ssh_host_ed25519_key.pub")
            run("docker", "stop", "-t", "20", name)
            run("docker", "start", name)
            wait_for(lambda: ssh(name, "ubuntu", "ubuntu", "test -f ~/persistent-marker && echo restart_ok", directory) == "restart_ok")
            assert hostkey == run("docker", "exec", name, "cat", "/etc/ssh/ssh_host_ed25519_key.pub")
            if desktop:
                url = f"http://127.0.0.1:{port(name, 80)}/vnc.html"
                wait_for(lambda: urllib.request.urlopen(url, timeout=3).status == 200)
                wait_for(lambda: "mate-session" in run("docker", "exec", name, "pgrep", "-a", "mate-session"))
            result["checks"].append("restart-and-persistence")
            custom = name + "-custom"
            names.append(custom)
            # A bind mount exercises user writable host data without changing host ownership.
            run("docker", "run", "-d", "--name", custom, "--platform", "linux/" + arch,
                "-e", "USER=developer", "-e", "PASSWORD=testpassword", "-p", "127.0.0.1::22",
                "--mount", "type=bind,source=" + temp + ",target=/workspace", tag)
            wait_for(lambda: ssh(custom, "developer", "testpassword", "id -un", directory) == "developer")
            assert hostkey != run("docker", "exec", custom, "cat", "/etc/ssh/ssh_host_ed25519_key.pub")
            ssh(custom, "developer", "testpassword", "echo bind_ok > /workspace/bind-marker", directory)
            assert (directory / "bind-marker").read_text().strip() == "bind_ok"
            result["checks"].append("custom-user-password-bind-mount-unique-host-key")
            completed = subprocess.run(["docker", "run", "--rm", "--platform", "linux/" + arch, tag,
                "bash", "-c", 'test "$(id -un)" = ubuntu && exit 17'], capture_output=True, text=True, timeout=60)
            assert completed.returncode == 17, completed.stderr
            result["checks"].append("custom-command-exit-code")
        result["status"] = "PASS"
    except Exception as exc:
        result["error"] = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            result["error"] += "\n" + (exc.stderr or "") + "\n" + (exc.stdout or "")
    finally:
        with log.open("a") as stream:
            for name in names:
                stream.write("\n=== " + name + " ===\n")
                subprocess.run(["docker", "logs", name], stdout=stream, stderr=subprocess.STDOUT, timeout=30)
                subprocess.run(["docker", "rm", "-f", name], stdout=stream, stderr=subprocess.STDOUT, timeout=30)
            for volume in volumes:
                subprocess.run(["docker", "volume", "rm", volume], stdout=stream, stderr=subprocess.STDOUT, timeout=30)
            stream.write("\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ubuntu", default="22.04", choices=["18.04", "20.04", "22.04"])
    parser.add_argument("--variant", default="base", choices=["base", "desktop", "ros", "desktop-ros"])
    parser.add_argument("--arch", default="arm64" if os.uname().machine in ("arm64", "aarch64") else "amd64", choices=["amd64", "arm64"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    matrix = ([(v, kind, arch) for v in ("22.04", "20.04", "18.04")
               for arch in ("arm64", "amd64") for kind in ("base", "desktop", "ros", "desktop-ros")]
              if args.all else [(args.ubuntu, args.variant, args.arch)])
    results = []
    for version, variant, arch in matrix:
        print(f"Testing {version} {variant} {arch} ...", flush=True)
        result = test_one(version, variant, arch, not args.skip_build)
        results.append(result)
        print(result["status"] + " " + result["image"] + (": " + result.get("error", "")[-1000:] if result["status"] != "PASS" else ""), flush=True)
        (RESULTS / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(0 if all(result["status"] == "PASS" for result in results) else 1)


if __name__ == "__main__":
    main()
