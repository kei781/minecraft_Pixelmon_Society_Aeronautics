import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import forge_datapack_compat as compat


class DatapackCompatibilityTest(unittest.TestCase):
    """Metadata/file fixtures only; no fixture is launched as Minecraft content or a mod."""
    def setUp(self):
        self.original = b'{"forge:conditions":[{"type":"forge:false"}]}'
        context = patch.object(compat, "RESOURCE_SHA256", hashlib.sha256(self.original).hexdigest())
        context.start(); self.addCleanup(context.stop)

    def test_only_invalid_noop_list_changes_and_conditions_survive(self):
        files = {compat.RESOURCE: self.original, "kubejs/data/other/loot_modifiers/real.json": b"preserve other list"}
        receipt = compat.apply_overrides(files)
        self.assertEqual(json.loads(files[compat.RESOURCE]), {
            "forge:conditions": [{"type": "forge:false"}], "replace": False, "entries": []})
        self.assertEqual(files["kubejs/data/other/loot_modifiers/real.json"], b"preserve other list")
        self.assertEqual(receipt["sha256"], hashlib.sha256(files[compat.RESOURCE]).hexdigest())

    def test_changed_or_missing_input_does_not_mutate_mapping(self):
        for data in [None, b"{}", self.original + b" "]:
            files = {"keep": b"untouched"}
            if data is not None: files[compat.RESOURCE] = data
            before = dict(files)
            with self.subTest(data=data), self.assertRaises(ValueError): compat.apply_overrides(files)
            self.assertEqual(files, before)

    def test_hash_allowance_does_not_normalize_unrecognized_schema(self):
        different = b'{"replace":true,"entries":["example:real_modifier"]}'
        with patch.object(compat, "RESOURCE_SHA256", hashlib.sha256(different).hexdigest()), self.assertRaises(ValueError):
            compat.normalize_resource(different)

    def test_symlink_directory_never_changes_external_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); outside = root/"outside"
            target = outside/"data/forge/loot_modifiers/global_loot_modifiers.json"
            target.parent.mkdir(parents=True); target.write_bytes(self.original)
            staged = root/"staged"; staged.mkdir(); (staged/"kubejs").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError): compat.apply_directory(staged)
            self.assertEqual(target.read_bytes(), self.original)

    def test_module_install_and_exact_declaration_preserve_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root/"authored-fixture.jar"; source.write_bytes(b"module fixture never executed")
            staged = root/"staged"; target = staged/compat.TARGET_PATH
            target.parent.mkdir(parents=True); target.write_bytes(b"original target fixture never executed")
            with patch.multiple(compat, MODULE_SHA256=compat.digest(source), TARGET_SHA256=compat.digest(target)):
                before = target.read_bytes(); declaration = compat.install_module(staged, source)
                self.assertEqual(compat.verify_staged_module(staged, declaration), declaration)
                self.assertEqual(target.read_bytes(), before)
                with self.assertRaises(ValueError): compat.verify_staged_module(staged, {})
                with self.assertRaises(ValueError): compat.install_module(staged, source)

    def test_declared_missing_module_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIsNone(compat.verify_staged_module(root, None))
            with self.assertRaises(ValueError): compat.verify_staged_module(root, compat.module_receipt())


if __name__ == "__main__": unittest.main()
