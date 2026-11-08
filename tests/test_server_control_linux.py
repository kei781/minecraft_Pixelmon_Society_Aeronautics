import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith("linux") and all(shutil.which(p) for p in ["tmux", "sha256sum", "flock"]), "Linux tmux control test")
class ServerControlTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="psa-control-test-")
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name)
        self.env = os.environ.copy()
        shutil.copyfile(ROOT / "server-control.sh", self.profile / "server-control.sh")
        for name in [".psa-forge-candidate.json", ".psa-owned-smoke-test"]:
            (self.profile / name).write_text("isolated test fixture\n")
        (self.profile / "eula.txt").write_text("eula=false\n")
        self.tmux = ["tmux", "-L", "psa-forge-" + hashlib.sha256(str(self.profile.resolve()).encode()).hexdigest()[:16], "-f", "/dev/null"]

    def control(self, action):
        return subprocess.run(["bash", "server-control.sh", action], cwd=self.profile, env=self.env, capture_output=True, text=True, timeout=10)

    def test_concurrent_start_preserves_live_console_and_releases_lock(self):
        # Shell-only fixture, never a Minecraft process or real mod JAR.
        java = self.profile / "runtime/java/bin/java"
        java.parent.mkdir(parents=True)
        java.write_text('#!/usr/bin/env bash\necho fixture-started\nwhile read -r line; do [[ "$line" == stop ]] && exit 0; done\n')
        java.chmod(0o755)
        args = self.profile / "libraries/net/minecraftforge/forge/1.20.1-47.4.20/unix_args.txt"
        args.parent.mkdir(parents=True); args.write_text("")
        mods = self.profile / "mods"; mods.mkdir()
        hashes = []
        for n in range(313):
            name = "mods/fixture-%d.jar" % n
            (self.profile / name).write_bytes(b"shell fixture only")
            hashes.append(hashlib.sha256(b"shell fixture only").hexdigest() + "  " + name)
        (self.profile / ".psa-mods.sha256").write_text("\n".join(hashes) + "\n")
        (self.profile / "server.properties").write_text("online-mode=true\n")
        (self.profile / "eula.txt").write_text("eula=true\n")
        (self.profile / "console.log").write_text("previous-console\n")
        gate, release = self.profile / "gate", self.profile / "release"
        binary = self.profile / "test-bin"; binary.mkdir()
        wrapper = binary / "sha256sum"
        wrapper.write_text('#!/usr/bin/env bash\n'
            'if [[ "${1:-}" == --check && ! -e %s ]]; then\n' % shlex.quote(str(gate))
            + '  touch %s\n  while [[ ! -e %s ]]; do sleep 0.01; done\nfi\n' % (shlex.quote(str(gate)), shlex.quote(str(release)))
            + 'exec %s "$@"\n' % shlex.quote(shutil.which("sha256sum")))
        wrapper.chmod(0o755)
        self.env["PATH"] = str(binary) + os.pathsep + self.env["PATH"]
        self.addCleanup(lambda: subprocess.run(self.tmux + ["kill-server"], capture_output=True))
        first = subprocess.Popen(["bash", "server-control.sh", "start"], cwd=self.profile,
                env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not gate.exists() and time.monotonic() < deadline: time.sleep(0.01)
            self.assertTrue(gate.exists(), "first start did not reach the controlled barrier")
            second = self.control("start")
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("operation is in progress", second.stderr)
        finally:
            release.touch()
            out, err = first.communicate(timeout=10)
        self.assertEqual(first.returncode, 0, out + err)
        deadline = time.monotonic() + 5
        console = self.profile / "console.log"
        while (not console.exists() or "fixture-started" not in console.read_text()) and time.monotonic() < deadline: time.sleep(0.01)
        self.assertIn("fixture-started", console.read_text())
        self.assertEqual(self.control("start").stdout.strip(), "Already running")
        self.assertIn("fixture-started", console.read_text())
        backups = list((self.profile / "logs").glob("console-previous-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "previous-console\n")

    def test_start_does_not_accept_eula_implicitly(self):
        result = self.control("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--accept-eula", result.stderr)
        self.assertEqual((self.profile / "eula.txt").read_text(), "eula=false\n")
        self.assertNotEqual(subprocess.run(self.tmux + ["has-session", "-t", "server"], capture_output=True).returncode, 0)

    def test_foreign_session_is_not_stopped(self):
        subprocess.run(self.tmux + ["new-session", "-d", "-s", "server", "sleep 120"], check=True)
        self.addCleanup(lambda: subprocess.run(self.tmux + ["kill-server"], capture_output=True))
        subprocess.run(self.tmux + ["set-option", "-t", "server", "@psa-root", "different-root"], check=True)
        result = self.control("stop")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized tmux session", result.stderr)
        self.assertEqual(subprocess.run(self.tmux + ["has-session", "-t", "server"], capture_output=True).returncode, 0)
