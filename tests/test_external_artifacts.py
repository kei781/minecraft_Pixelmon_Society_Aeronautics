"""Verify that source candidates never bypass the remaining artifact gates."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare", ROOT / "tools/prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class ExternalArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        (self.root / "inputs").mkdir()
        self.items = []
        for name in ["society", "sunrisegardening", "orchard", "plentifulponds"]:
            data = ("original " + name).encode()
            item = {"filename": name + ".jar", "mod_id": name, "sha1": hashlib.sha1(data).hexdigest()}
            if name in {"orchard", "plentifulponds"}:
                candidate = ("candidate " + name).encode()
                item["source_build"] = {"sha256": hashlib.sha256(candidate).hexdigest(), "size": len(candidate), "commit": "1" * 40}
            self.items.append(item)
            (self.root / "inputs" / item["filename"]).write_bytes(data)
        self.save_manifest()
        self.root_patch = patch.object(prepare, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def save_manifest(self):
        (self.root / "external-artifacts.json").write_text(json.dumps({"artifacts": self.items}))

    def test_originals_remain_accepted(self):
        accepted = prepare.external_artifacts()
        self.assertEqual([item["sha1"] for item in accepted], [item["sha1"] for item in self.items])
        self.assertEqual([item["accepted_as"] for item in accepted], ["original"] * 4)

    def test_pinned_candidates_are_accepted_without_changing_original_hashes(self):
        before = [item["sha1"] for item in self.items]
        for name in ["orchard", "plentifulponds"]:
            (self.root / "inputs" / (name + ".jar")).write_bytes(("candidate " + name).encode())
        accepted = prepare.external_artifacts()
        self.assertEqual([item["sha1"] for item in accepted], before)
        self.assertEqual([item["accepted_as"] for item in accepted], ["original", "original", "source_candidate", "source_candidate"])

    def test_candidate_byte_tampering_is_rejected(self):
        (self.root / "inputs/orchard.jar").write_bytes(b"candidate orchare")
        with self.assertRaisesRegex(ValueError, "orchard.jar"):
            prepare.external_artifacts()

    def test_candidates_do_not_hide_missing_society(self):
        (self.root / "inputs/society.jar").unlink()
        for name in ["orchard", "plentifulponds"]:
            (self.root / "inputs" / (name + ".jar")).write_bytes(("candidate " + name).encode())
        with self.assertRaisesRegex(ValueError, "society.jar"):
            prepare.external_artifacts()

    def test_stage_records_actual_candidate_hash_and_commit(self):
        (self.root / "inputs/orchard.jar").write_bytes(b"candidate orchard")
        for folder in ["config", "defaultconfigs", "kubejs"]:
            (self.root / "upstream/society" / folder).mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.root / "upstream/society")], check=True)
        # One already-cached file exercises real staging without network access.
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("data/pixelmon/pixelmon/spawn_replacement/cow.json", "{}")
        data = archive_bytes.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        cached = self.root / "cache" / digest / "pixelmon.jar"
        cached.parent.mkdir(parents=True)
        cached.write_bytes(data)
        (self.root / "integration-lock.json").write_text(json.dumps({"files": [
            {"project": "pixelmon", "side": "both", "path": "mods/pixelmon.jar", "url": "https://example.invalid/pixelmon.jar",
             "hashes": {"sha256": digest}, "size": len(data)}]}))
        core = self.root / "compat/creativecore/CreativeCore_NEOFORGE_v2.13.51_mc1.21.1-psa-codec1.jar"
        core.parent.mkdir(parents=True)
        core.write_bytes(b"fixture core")
        (self.root / "evidence").mkdir()
        (self.root / "evidence/creativecore-patch.json").write_text(json.dumps(
            {"patched_sha256": hashlib.sha256(core.read_bytes()).hexdigest()}))
        with patch.object(prepare, "verify_upstream"):
            prepare.stage("server")
        receipt = json.loads((self.root / "server/.integration-staging.json").read_text())
        actual = next(item for item in receipt["external_artifacts"] if item["mod_id"] == "orchard")
        self.assertEqual(actual["accepted_as"], "source_candidate")
        self.assertEqual(actual["sha256"], hashlib.sha256((self.root / "server/mods/orchard.jar").read_bytes()).hexdigest())
        self.assertEqual(actual["source_commit"], "1" * 40)
        original = next(item for item in receipt["external_artifacts"] if item["mod_id"] == "society")
        self.assertEqual(original["accepted_as"], "original")
        self.assertIsNone(original["source_commit"])
        overrides = receipt["mob_compatibility_overrides"]
        self.assertEqual(len(overrides), 2)
        for override in overrides:
            staged = self.root / "server" / override["path"]
            self.assertEqual(override["sha256"], hashlib.sha256(staged.read_bytes()).hexdigest())
        cow = json.loads((self.root / "server/kubejs/data/pixelmon/pixelmon/spawn_replacement/cow.json").read_text())
        self.assertEqual(cow["detection"]["types"], [])
        self.assertIn("allow-vanilla-mobs: true", (self.root / "server/config/pixelmon/entity.yml").read_text())


if __name__ == "__main__":
    unittest.main()
