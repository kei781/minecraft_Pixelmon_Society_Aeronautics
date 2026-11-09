import hashlib
import io
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

    def test_bundled_folder_zip_and_nested_jar_conflicts_are_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(alias.TARGET, b"{}")
        nested_bytes = stream.getvalue()
        cases = [{"resourcepacks/repair.zip": nested_bytes},
                 {"resourcepacks/repair/" + alias.TARGET: b"{}"},
                 {"resourcepacks/repair/" + alias.TEXTURE: b"replacement"}]
        for overrides in cases:
            before = dict(overrides)
            with self.subTest(keys=list(overrides)), self.assertRaises(ValueError):
                alias.apply(overrides, self.files)
            self.assertEqual(overrides, before)
        nested = Path(self.directory.name) / "nested.jar"
        with zipfile.ZipFile(nested, "w") as archive:
            archive.writestr("META-INF/jarjar/dependency.jar", nested_bytes)
        overrides = {}
        with self.assertRaises(ValueError):
            alias.apply(overrides, dict(self.files, nested=nested))
        self.assertEqual(overrides, {})

    def test_nonconflicting_folder_zip_and_nested_jar_preserve_inputs(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(alias.MODEL, self.model)
            archive.writestr("assets/owned/models/item/unrelated.json", b"{}")
        safe_zip = stream.getvalue()
        nested = Path(self.directory.name) / "safe-nested.jar"
        with zipfile.ZipFile(nested, "w") as archive:
            archive.writestr("META-INF/jarjar/safe.jar", safe_zip)
        overrides = {"resourcepacks/safe.zip": safe_zip,
                     "resourcepacks/safe-folder/" + alias.TEXTURE: self.texture,
                     "resourcepacks/safe-folder/assets/owned/unrelated.json": b"{}"}
        before = dict(overrides)
        alias.apply(overrides, dict(self.files, nested=nested))
        self.assertEqual({n:overrides[n] for n in before}, before)
        self.assertEqual(set(overrides) - set(before), {"kubejs/" + alias.TARGET})

    def batch_fixture(self):
        specs = []
        # Reuse the actual archive guard with two owned model names and a block-model path.
        block = "assets/decorative_blocks/models/block/owned.json"
        with zipfile.ZipFile(self.jar, "a") as archive:
            archive.writestr(block, self.model)
        jar_sha = self.sha(self.jar.read_bytes())
        for name in ("owned_first", "owned_second"):
            specs.append({"item":"decorative_blocks:"+name, "jar":alias.JAR, "jar_sha256":jar_sha,
                          "target_path":"assets/decorative_blocks/models/item/"+name+".json",
                          "parent":"decorative_blocks:block/owned", "resources":{block:self.sha(self.model)},
                          "vanilla_dependencies":[]})
        path=Path(self.directory.name)/"specs.json";path.write_text(json.dumps(specs))
        return path, specs

    def test_batch_is_atomic_if_later_target_conflicts(self):
        path,specs=self.batch_fixture()
        overrides={"kubejs/"+specs[1]["target_path"]:b"existing user resource"}
        before=dict(overrides)
        with patch.object(alias,"ADDITIONAL_ITEMS",{s["item"] for s in specs}), self.assertRaisesRegex(ValueError,"already supplied"):
            alias.apply_additional(overrides,self.files,path)
        self.assertEqual(overrides,before)

    def test_batch_applies_all_and_rejects_missing_inventory(self):
        path,specs=self.batch_fixture();overrides={"unrelated":b"preserved"}
        with patch.object(alias,"ADDITIONAL_ITEMS",{s["item"] for s in specs}):
            receipts=alias.apply_additional(overrides,self.files,path)
            self.assertEqual(len(receipts),2);self.assertEqual(overrides['unrelated'],b'preserved')
            self.assertEqual(len(overrides),3)
            path.write_text(json.dumps(specs[:1]))
            with self.assertRaisesRegex(ValueError,"inventory"):
                alias.apply_additional({},self.files,path)


if __name__ == "__main__":
    unittest.main()
