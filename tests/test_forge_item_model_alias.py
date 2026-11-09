import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import forge_item_model_alias as alias


class ItemModelAliasTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.jar = Path(self.directory.name) / "original.jar"
        self.model = b'{"parent":"minecraft:item/generated","textures":{"layer0":"decorative_blocks:item/blockstate_copy_tool"}}'
        self.texture = b"owned test fixture, never loaded in game"
        with zipfile.ZipFile(self.jar, "w") as archive:
            archive.writestr(alias.MODEL, self.model)
            archive.writestr(alias.TEXTURE, self.texture)
        self.guard = patch.multiple(alias, JAR_SHA256=self.sha(self.jar.read_bytes()),
                                    MODEL_SHA256=self.sha(self.model), TEXTURE_SHA256=self.sha(self.texture))
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.files = {alias.JAR: self.jar}

    @staticmethod
    def sha(data):
        return hashlib.sha256(data).hexdigest()

    def test_alias_reuses_original_model_without_changing_input_jar_or_other_overrides(self):
        original = self.jar.read_bytes()
        overrides = {"kubejs/client_scripts/example.js": b"original script"}
        receipt = alias.apply(overrides, self.files)
        self.assertEqual(json.loads(overrides["kubejs/" + alias.TARGET]), {"parent": alias.PARENT})
        self.assertEqual(overrides["kubejs/client_scripts/example.js"], b"original script")
        self.assertEqual(self.jar.read_bytes(), original)
        self.assertEqual(receipt["sha256"], self.sha(overrides["kubejs/" + alias.TARGET]))

    def test_identity_change_and_existing_model_fail_before_mutating(self):
        with patch.object(alias, "JAR_SHA256", "0" * 64):
            with self.assertRaisesRegex(ValueError, "identity"):
                alias.apply({}, self.files)
        overrides = {("kubejs/" + alias.TARGET).upper(): b"original"}
        before = dict(overrides)
        with self.assertRaisesRegex(ValueError, "already supplied"):
            alias.apply(overrides, self.files)
        self.assertEqual(overrides, before)

    def test_pack_repair_parent_replacement_and_kubejs_replacement_are_rejected(self):
        other = Path(self.directory.name) / "other.zip"
        for name, data in [(alias.TARGET, b"{}"), (alias.MODEL, b"{}"), (alias.TEXTURE.upper(), self.texture)]:
            with self.subTest(name=name), zipfile.ZipFile(other, "w") as archive:
                archive.writestr(name, data)
            overrides = {}
            with self.assertRaises(ValueError):
                alias.apply(overrides, dict(self.files, other=other))
            self.assertEqual(overrides, {})
        with self.assertRaisesRegex(ValueError, "KubeJS"):
            alias.apply({"kubejs/" + alias.MODEL: b"{}"}, self.files)


if __name__ == "__main__":
    unittest.main()
