"""Validate executable documentation and CLI selection without a Docker daemon."""
import importlib.util
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("generate", ROOT / "scripts/generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


class MatrixContracts(unittest.TestCase):
    def test_all_contexts_are_current_and_independent(self):
        files, _ = generate.outputs()
        contexts = {name.rsplit("/", 1)[0] for name in files if name.endswith("/Dockerfile")}
        self.assertEqual(len(contexts), 24)
        for name, expected in files.items():
            with self.subTest(path=name):
                self.assertEqual((ROOT / name).read_text(), expected)
        for context in contexts:
            dockerfile = (ROOT / context / "Dockerfile").read_text()
            self.assertEqual(re.findall(r"^COPY (.+)$", dockerfile, re.M), ["entrypoint.sh /entrypoint.sh"])
            self.assertTrue(os.access(ROOT / context / "entrypoint.sh", os.X_OK))

    def test_documentation_links_and_bash_syntax(self):
        for path in ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            for target in re.findall(r"\]\(([^ )]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(document=str(path), link=target):
                    self.assertTrue((path.parent / target.split("#")[0]).exists())
            for block in re.findall(r"```bash\n(.*?)```", path.read_text(), re.S):
                completed = subprocess.run(["bash", "-n"], input=block, text=True, capture_output=True)
                self.assertEqual(completed.returncode, 0, (str(path), completed.stderr))
        for path in list((ROOT / "scripts").glob("*.sh")) + [ROOT / "scripts/templates/entrypoint.sh"]:
            subprocess.run(["bash", "-n", str(path)], check=True)

    def test_python_exception_and_ros_versions(self):
        for version, (_, distro) in generate.VERSIONS.items():
            for variant in generate.VARIANTS:
                dockerfile = generate.dockerfile(version, variant, "arm64")
                if "ros" in variant:
                    self.assertIn("ENV ROS_DISTRO=" + distro, dockerfile)
                    self.assertIn("ROS_PYTHON_VERSION=" + ("2" if distro == "melodic" else "3"), dockerfile)
                else:
                    self.assertNotIn("ENV ROS_DISTRO=", dockerfile)
                    if version == "18.04":
                        self.assertIn("ln -s /usr/bin/python3 /usr/local/bin/python", dockerfile)


class CliContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ubuntu-dev-cli-")
        self.directory = Path(self.temp.name)
        self.log = self.directory / "docker-calls"
        docker = self.directory / "docker"
        docker.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$MOCK_DOCKER_LOG"
case "$1 $2" in
  'container inspect') exit "${MOCK_EXISTS:-1}" ;;
  'create '*) echo smoke-created-id ;;
  'start '*) exit "${MOCK_START_FAIL:-0}" ;;
esac
''')
        docker.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.directory) + ":" + os.environ["PATH"],
                        MOCK_DOCKER_LOG=str(self.log), CONTAINER_USER="ubuntu")

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, script, *args):
        return subprocess.run([str(ROOT / "scripts" / script), *args], env=self.env,
                              capture_output=True, text=True)

    def test_build_selection_for_all_24_images(self):
        for version in generate.VERSIONS:
            for variant in generate.VARIANTS:
                for arch in generate.ARCHES:
                    result = self.invoke("build.sh", "--ubuntu", version, "--variant", variant, "--arch", arch)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    calls = self.log.read_text()
                    self.assertIn(f"--platform linux/{arch}", calls)
                    self.assertIn(f"ubuntu-dev:{version}-{variant}-{arch}", calls)
                    suffix = "" if variant == "base" else "-" + variant
                    self.assertIn(f"ubuntu{version.replace('.', '')}{suffix}/{arch}", calls)

    def test_invalid_input_and_help_do_not_call_docker(self):
        for script in ("build.sh", "run.sh", "smoke-test.sh"):
            for args in (("--ubuntu", "24.04"), ("--arch", "x86"), ("--variant", "oops"), ("--ubuntu",), ("--unknown",)):
                with self.subTest(script=script, args=args):
                    self.assertNotEqual(self.invoke(script, *args).returncode, 0)
            self.assertEqual(self.invoke(script, "--help").returncode, 0)
        self.assertFalse(self.log.exists())

    def test_occupied_and_duplicate_ports_do_not_create_container(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen()
            port = str(sock.getsockname()[1])
            result = self.invoke("run.sh", "--ssh-port", port)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Port check failed", result.stderr)
        result = self.invoke("run.sh", "--variant", "desktop", "--ssh-port", "44444", "--web-port", "44444")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def free_port(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return str(sock.getsockname()[1])

    def test_existing_container_is_never_removed(self):
        self.env["MOCK_EXISTS"] = "0"
        result = self.invoke("run.sh", "--ssh-port", self.free_port(), "--name", "already-exists")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("docker start already-exists", result.stderr)
        self.assertNotIn("create", self.log.read_text())
        self.assertNotIn("rm ", self.log.read_text())

    def test_host_user_is_not_forwarded_and_failed_start_cleans_only_new_id(self):
        self.env.pop("CONTAINER_USER")
        self.env["USER"] = "hostuser"
        self.env["MOCK_START_FAIL"] = "1"
        result = self.invoke("run.sh", "--ssh-port", self.free_port())
        self.assertNotEqual(result.returncode, 0)
        calls = self.log.read_text()
        self.assertIn("-e USER=ubuntu", calls)
        self.assertNotIn("hostuser", calls)
        self.assertIn("rm smoke-created-id", calls)


if __name__ == "__main__":
    unittest.main()
