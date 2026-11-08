"""Verify that source candidates never bypass the remaining artifact gates."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
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
                item["source_build"] = {"sha256": hashlib.sha256(candidate).hexdigest(), "size": len(candidate)}
            self.items.append(item)
            (self.root / "inputs" / item["filename"]).write_bytes(data)
        self.save_manifest()
        self.root_patch = patch.object(prepare, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def save_manifest(self):
        (self.root / "external-artifacts.json").write_text(json.dumps({"artifacts": self.items}))

    def test_originals_remain_accepted(self):
        self.assertEqual(prepare.external_artifacts(), self.items)

    def test_pinned_candidates_are_accepted_without_changing_original_hashes(self):
        before = [item["sha1"] for item in self.items]
        for name in ["orchard", "plentifulponds"]:
            (self.root / "inputs" / (name + ".jar")).write_bytes(("candidate " + name).encode())
        self.assertEqual([item["sha1"] for item in prepare.external_artifacts()], before)

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


if __name__ == "__main__":
    unittest.main()
