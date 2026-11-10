"""Recovery must preserve other worlds and refuse unidentified or live targets."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec("fcntl") is not None, "QA controller uses Unix file locks")
class RecoveryBoundaries(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parent / "forge-render-probe/render-qa-control.py"
        spec = importlib.util.spec_from_file_location("render_qa_test_controller", path)
        self.control = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.control)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.control.ROOT = self.root
        self.control.running = lambda: False
        # Actual313/hash/auth checks are separately tested on N100; these tests
        # exercise archive identity and data preservation without game binaries.
        self.control.inventory = lambda receipt: None
        self.receipt = {"owner": "psa-render-qa-v1", "profile": self.root.name,
                        "world_generation": "00000000-0000-0000-0000-000000000001"}
        (self.root / ".psa-disposable-qa").touch()
        (self.root / ".psa-render-qa.json").write_text(json.dumps(self.receipt))
        self.world = self.root / "world-render-qa"
        self.world.mkdir()
        (self.world / "owned-data.bin").write_bytes(b"preserve crashed data exactly")
        self.marker = {"owner": "psa-render-world-v1", "profile": self.root.name, "generation": "00000000-0000-0000-0000-000000000001"}
        (self.world / ".psa-render-world-owner.json").write_text(json.dumps(self.marker))
        self.other = self.root / "other-world"
        self.other.mkdir()
        (self.other / "unrelated.bin").write_bytes(b"never modify another world")
        (self.root / "psa-validation").mkdir()

    def test_live_process_cannot_recover(self):
        self.control.running = lambda: True
        with self.assertRaisesRegex(RuntimeError, "fully stopped"):
            self.control.recover(self.receipt)
        self.assertTrue((self.world / "owned-data.bin").exists())
        self.assertFalse((self.root / "qa-crash-history").exists())

    def test_marker_or_generation_mismatch_preserves_all_data(self):
        (self.world / ".psa-render-world-owner.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "no owned QA marker"):
            self.control.recover(self.receipt)
        (self.world / ".psa-render-world-owner.json").write_text(json.dumps(self.marker))
        for changed in [{"profile": "another-profile"}, {"generation": "another-generation"}]:
            (self.world / ".psa-render-world-owner.json").write_text(json.dumps({**self.marker, **changed}))
            with self.assertRaisesRegex(RuntimeError, "QA world generation mismatch"):
                self.control.recover(self.receipt)
            self.assertFalse((self.root / "qa-crash-history").exists())
        (self.world / ".psa-render-world-owner.json").write_text(json.dumps(self.marker))
        bad_receipt = {**self.receipt, "world_generation": "x/../../outside"}
        with self.assertRaisesRegex(RuntimeError, "Invalid QA world generation"):
            self.control.recover(bad_receipt)
        state = {"active": True, "world_generation": "other-generation"}
        (self.root / "psa-validation/render-server-current.json").write_text(json.dumps(state))
        with self.assertRaisesRegex(RuntimeError, "another QA world"):
            self.control.recover(self.receipt)
        self.assertEqual((self.world / "owned-data.bin").read_bytes(), b"preserve crashed data exactly")
        self.assertFalse((self.root / "qa-crash-history").exists())

    def test_recovery_archives_exact_world_and_checkpoint_only(self):
        state = {"active": True, "world_generation": "00000000-0000-0000-0000-000000000001", "owned_entities": ["fixture"]}
        (self.root / "psa-validation/render-server-current.json").write_text(json.dumps(state))
        self.control.recover(self.receipt)
        archives = list((self.root / "qa-crash-history").iterdir())
        self.assertEqual(len(archives), 1)
        old = archives[0] / "world-render-qa"
        self.assertEqual((old / "owned-data.bin").read_bytes(), b"preserve crashed data exactly")
        self.assertEqual(json.loads((archives[0] / "render-server-current.json").read_text()), state)
        self.assertEqual((self.other / "unrelated.bin").read_bytes(), b"never modify another world")
        self.assertFalse((self.world / "owned-data.bin").exists())
        receipt = json.loads((self.root / ".psa-render-qa.json").read_text())
        self.assertNotEqual(receipt["world_generation"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(json.loads((self.world / ".psa-render-world-owner.json").read_text())["generation"], receipt["world_generation"])

    def test_dirty_or_invalid_checkpoint_refuses_start(self):
        old = sys.argv
        try:
            sys.argv = ["render-qa-control.py", "start"]
            for text in [json.dumps({"active": True}), "incomplete json"]:
                (self.root / "psa-validation/render-server-current.json").write_text(text)
                with self.assertRaisesRegex(RuntimeError, "Unresolved prior QA run"):
                    self.control.main()
                self.assertEqual((self.world / "owned-data.bin").read_bytes(), b"preserve crashed data exactly")
        finally:
            sys.argv = old

    def test_permanent_cleanup_failure_refuses_contradictory_complete_flag(self):
        state = {"active": False, "cleanup_complete": True, "cleanup_failed": True}
        (self.root / "psa-validation/render-server-current.json").write_text(json.dumps(state))
        old = sys.argv
        try:
            sys.argv = ["render-qa-control.py", "start"]
            with self.assertRaisesRegex(RuntimeError, "Unresolved prior QA run"):
                self.control.main()
        finally:
            sys.argv = old


if __name__ == "__main__":
    unittest.main()
