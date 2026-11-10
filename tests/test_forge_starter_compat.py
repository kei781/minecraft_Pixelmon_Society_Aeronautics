"""Packaging guard fixtures only; none of these fake class bytes are launched."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import forge_starter_compat as compat


class StarterOverlayTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base, self.patchjar, self.pixelmon = [self.root / n for n in ("base.jar", "patch.jar", "pixelmon.jar")]
        self.output = self.root / "result.jar"
        self.config, self.source, self.manifest = [self.root / n for n in ("starter.mixins.json", "Source.java", "pins.json")]
        self.source.write_text("authored fixture")
        self.pixelmon.write_bytes(b"opaque upstream fixture")
        self.original = {
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\r\nMixinConfigs: existing-a.json,\r\n existing-b.json\r\nKeep: unchanged\r\n\r\n",
            "existing-a.json": b'{"mixins":["Existing"]}',
            "existing-b.json": b'{"client":["Retained"]}',
            "PSA_PROVENANCE.txt": b"original provenance\n",
            "upstream/Untouched.class": b"opaque upstream bytes"}
        self.write_zip(self.base, self.original)
        self.base_bytes = self.base.read_bytes()
        self.compiled = b"authored compiled fixture only"
        self.config.write_text(json.dumps({"required": True, "minVersion": "0.8", "package": "dev.psa.startercompat.mixin",
            "compatibilityLevel": "JAVA_17", "mixins": ["PixelmonStarterRecipientMixin"], "injectors": {"defaultRequire": 1}}))
        self.patchfiles = {compat.CLASS: self.compiled, self.config.name: self.config.read_bytes(),
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\r\nMixinConfigs: starter.mixins.json\r\n\r\n"}
        self.write_zip(self.patchjar, self.patchfiles)
        self.pins = {key: compat.digest(path) for path, key in [(self.base, "base_common_sha256"),
            (self.patchjar, "tested_patch_sha256"), (self.pixelmon, "pixelmon_sha256"),
            (self.config, "config_sha256"), (self.source, "source_sha256")]}
        self.pins["class_sha256"] = hashlib.sha256(self.compiled).hexdigest()
        self.save_pins()
        for name, path in (("MANIFEST", self.manifest), ("SOURCE", self.source), ("CONFIG", self.config)):
            replacement = patch.object(compat, name, path); replacement.start(); self.addCleanup(replacement.stop)

    @staticmethod
    def write_zip(path, files):
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in files.items(): archive.writestr(name, data)

    def save_pins(self):
        self.manifest.write_text(json.dumps(self.pins))

    def build(self):
        return compat.build(self.base, self.patchjar, self.pixelmon, self.output)

    def repin_patch(self):
        self.write_zip(self.patchjar, self.patchfiles)
        self.pins["tested_patch_sha256"] = compat.digest(self.patchjar); self.save_pins()

    def test_payload_preservation_folded_manifest_and_reproducibility(self):
        self.build()
        with zipfile.ZipFile(self.output) as result:
            for name, data in self.original.items():
                if name not in ("META-INF/MANIFEST.MF", "PSA_PROVENANCE.txt"):
                    self.assertEqual(result.read(name), data)
            manifest = result.read("META-INF/MANIFEST.MF")
            self.assertEqual(compat.mixin_header(manifest)[4], ["existing-a.json", "existing-b.json", self.config.name])
            self.assertIn(b"Keep: unchanged\r\n\r\n", manifest)
            self.assertTrue(all(len(line) <= 70 for line in manifest.splitlines()))
            self.assertEqual(result.read(compat.CLASS), self.compiled)
        second = self.root / "second.jar"
        compat.build(self.base, self.patchjar, self.pixelmon, second)
        self.assertEqual(self.output.read_bytes(), second.read_bytes())

    def test_wrong_compiled_class_and_wrong_registration_are_refused(self):
        for field, content, error in [(compat.CLASS, b"wrong class", "Compiled"),
                ("META-INF/MANIFEST.MF", b"MixinConfigs: starter.mixins.json,extra.json\r\n", "registration")]:
            with self.subTest(field=field):
                original = self.patchfiles[field]; self.patchfiles[field] = content; self.repin_patch()
                with self.assertRaisesRegex(ValueError, error): self.build()
                self.assertFalse(self.output.exists())
                self.patchfiles[field] = original; self.repin_patch()

    def test_additional_mixin_configuration_is_refused(self):
        document = json.loads(self.config.read_text()); document["client"] = ["Unexpected"]
        self.config.write_text(json.dumps(document)); self.pins["config_sha256"] = compat.digest(self.config); self.save_pins()
        with self.assertRaisesRegex(ValueError, "Only the authored"): self.build()
        self.assertFalse(self.output.exists())

    def test_outputs_cannot_overwrite_or_target_mods_even_via_alias(self):
        self.output.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "Fresh"): self.build()
        self.assertEqual(self.output.read_bytes(), b"preserve")
        mods = self.root / "mods"; mods.mkdir()
        alias = self.root / "alias"; alias.symlink_to(mods, target_is_directory=True)
        for folder in (mods, alias):
            with self.assertRaisesRegex(ValueError, "non-mods"):
                compat.build(self.base, self.patchjar, self.pixelmon, folder / "new.jar")
        self.assertEqual(list(mods.iterdir()), [])

    def test_mutated_input_and_symlink_are_refused(self):
        self.base.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "base_common"): self.build()
        self.base.write_bytes(self.base_bytes)
        self.assertEqual(compat.digest(self.base), self.pins["base_common_sha256"])
        link = self.root / "alias.jar"; link.symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, "base_common"):
            compat.build(link, self.patchjar, self.pixelmon, self.output)
        self.assertFalse(self.output.exists())

    def test_manifest_duplicate_header_and_duplicate_configs_are_refused(self):
        for data in (b"MixinConfigs: a.json\nMixinConfigs: b.json\n", b"MixinConfigs: a.json,a.json\n"):
            with self.assertRaises(ValueError): compat.append_config(data, "new.json")


if __name__ == "__main__":
    unittest.main()
