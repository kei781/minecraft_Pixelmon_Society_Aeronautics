import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("tmux") and shutil.which("sha256sum"), "Linux tmux control test")
class ServerControlTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="psa-control-test-")
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name)
        shutil.copyfile(ROOT / "server-control.sh", self.profile / "server-control.sh")
        for name in [".psa-forge-candidate.json", ".psa-owned-smoke-test"]:
            (self.profile / name).write_text("isolated test fixture\n")
        (self.profile / "eula.txt").write_text("eula=false\n")
        self.tmux = ["tmux", "-L", "psa-forge-" + hashlib.sha256(str(self.profile.resolve()).encode()).hexdigest()[:16], "-f", "/dev/null"]

    def control(self, action):
        return subprocess.run(["bash", "server-control.sh", action], cwd=self.profile, capture_output=True, text=True, timeout=10)

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
