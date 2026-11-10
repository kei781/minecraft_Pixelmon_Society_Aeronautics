import hashlib
import json
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
        (self.profile / ".psa-forge-candidate.json").write_text("{}\n")
        (self.profile / ".psa-owned-smoke-test").write_text("isolated test fixture\n")
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

    def prepare_optional_module_fixture(self, module_bytes, target_bytes):
        # Process-control fixture only: this executable is a shell, never Minecraft.
        java = self.profile/"runtime/java/bin/java"; java.parent.mkdir(parents=True)
        java.write_text('#!/usr/bin/env bash\necho fixture-started\nwhile read -r line; do [[ "$line" == stop ]] && exit 0; done\n')
        java.chmod(0o755)
        args = self.profile/"libraries/net/minecraftforge/forge/1.20.1-47.4.20/unix_args.txt"
        args.parent.mkdir(parents=True); args.write_text("")
        mods = self.profile/"mods"; mods.mkdir()
        for number in range(312): (mods/("fixture-%d.jar" % number)).write_bytes(b"shell fixture only")
        (mods/"serializer_debug-1.0.1.jar").write_bytes(target_bytes)
        (mods/"PSA-Datapack-Sync-Compat-0.1.jar").write_bytes(module_bytes)
        declaration = {"path":"mods/PSA-Datapack-Sync-Compat-0.1.jar",
            "sha256":hashlib.sha256(module_bytes).hexdigest(),"server_only":True,"source":"compat/datapack-sync",
            "target_sha256":hashlib.sha256(target_bytes).hexdigest()}
        (self.profile/".psa-forge-candidate.json").write_text(json.dumps({
            "top_level_mod_jars":314,"datapack_sync_compatibility":declaration}))
        (self.profile/".psa-mods.sha256").write_text("".join(
            hashlib.sha256(p.read_bytes()).hexdigest()+"  mods/"+p.name+"\n" for p in sorted(mods.glob("*.jar"))))
        (self.profile/"server.properties").write_text("online-mode=true\n")
        (self.profile/"eula.txt").write_text("eula=true\n")

    def test_relocked_but_unpinned_optional_module_is_not_started(self):
        self.prepare_optional_module_fixture(b"not the pinned module", b"not the pinned target")
        result = self.control("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("declaration required", result.stderr)
        self.assertNotEqual(subprocess.run(self.tmux+["has-session","-t","server"],capture_output=True).returncode,0)

    def test_declared_module_removed_and_relocked_does_not_downgrade_to_313(self):
        self.prepare_optional_module_fixture(b"not executed", b"not executed")
        (self.profile/"mods/PSA-Datapack-Sync-Compat-0.1.jar").unlink()
        (self.profile/".psa-mods.sha256").write_text("".join(
            hashlib.sha256(p.read_bytes()).hexdigest()+"  mods/"+p.name+"\n"
            for p in sorted((self.profile/"mods").glob("*.jar"))))
        result = self.control("start")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(subprocess.run(self.tmux+["has-session","-t","server"],capture_output=True).returncode,0)

    def test_pinned_optional_module_fixture_starts_and_stops(self):
        module = os.environ.get("PSA_QA_DATAPACK_MODULE")
        target = os.environ.get("PSA_QA_SERIALIZER_TARGET")
        if not module or not target: self.skipTest("Pinned optional artifact inputs not provided")
        self.prepare_optional_module_fixture(Path(module).read_bytes(), Path(target).read_bytes())
        self.addCleanup(lambda: subprocess.run(self.tmux+["kill-server"],capture_output=True))
        result = self.control("start")
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(self.control("status").stdout.strip(),"Running")
        stopped = self.control("stop")
        self.assertEqual(stopped.returncode, 0, stopped.stdout+stopped.stderr)
        self.assertEqual(self.control("status").stdout.strip(),"Stopped")
