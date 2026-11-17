"""Packaging guard fixtures only; none of these fake class bytes are launched."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import forge_pcsync_compat as compat
from forge_starter_compat import digest, mixin_header


class PcResendOverlayTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base, self.patchjar, self.output = [self.root / name for name in ("base.jar", "patch.jar", "result.jar")]
        self.config, self.manifest = self.root / "psa-pc-resync.mixins.json", self.root / "pins.json"
        self.sources = {name: self.root / (name + ".java") for name in compat.NAMES}
        for name, path in self.sources.items():
            path.write_text("authored fixture " + name)
        self.original = {
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\r\nMixinConfigs: existing-a.json,\r\n existing-b.json\r\nKeep: unchanged\r\n\r\n",
            "existing-a.json": b'{"mixins":["Existing"]}', "PSA_PROVENANCE.txt": b"original provenance\n",
            "upstream/Untouched.class": b"opaque upstream bytes"}
        self.write_zip(self.base, self.original)
        self.compiled = {name: ("compiled fixture " + name).encode() for name in compat.NAMES}
        self.config.write_text(json.dumps(compat.EXPECTED_CONFIG))
        self.patchfiles = {compat.CLASSES[name]: data for name, data in self.compiled.items()}
        self.patchfiles[self.config.name] = self.config.read_bytes()
        self.patchfiles["META-INF/MANIFEST.MF"] = b"Manifest-Version: 1.0\r\nMixinConfigs: psa-pc-resync.mixins.json\r\n\r\n"
        self.write_zip(self.patchjar, self.patchfiles)
        self.pins = {"base_common_sha256": digest(self.base), "tested_patch_sha256": digest(self.patchjar),
                     "config_sha256": digest(self.config),
                     "source_sha256": {name: digest(path) for name, path in self.sources.items()},
                     "class_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in self.compiled.items()}}
        self.save_pins()
        for name, value in (("MANIFEST", self.manifest), ("SOURCES", self.sources), ("CONFIG", self.config)):
            replacement = patch.object(compat, name, value); replacement.start(); self.addCleanup(replacement.stop)

    @staticmethod
    def write_zip(path, files):
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)

    def save_pins(self):
        self.manifest.write_text(json.dumps(self.pins))

    def refused(self, message):
        with self.assertRaisesRegex(ValueError, message):
            compat.build(self.base, self.patchjar, self.output)
        self.assertFalse(self.output.exists())

    def test_only_the_class_and_its_registration_are_added(self):
        receipt = compat.build(self.base, self.patchjar, self.output)
        with zipfile.ZipFile(self.output) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        added = {compat.CLASSES["PixelmonPcResyncMixin"], self.config.name}
        self.assertEqual(set(files) - set(self.original), added)
        self.assertEqual(sorted(receipt["added"]), sorted(added))
        self.assertEqual(files[compat.CLASSES["PixelmonPcResyncMixin"]], self.compiled["PixelmonPcResyncMixin"])
        self.assertEqual(files[self.config.name], self.config.read_bytes())
        for name in ("existing-a.json", "upstream/Untouched.class"):
            self.assertEqual(files[name], self.original[name])
        self.assertEqual(mixin_header(files["META-INF/MANIFEST.MF"])[4],
                         ["existing-a.json", "existing-b.json", self.config.name])
        self.assertTrue(files["PSA_PROVENANCE.txt"].startswith(b"original provenance\n"))
        self.assertIn(b"Pixelmon PC resend", files["PSA_PROVENANCE.txt"])

    def test_other_base_patch_source_or_class_is_refused(self):
        self.pins["base_common_sha256"] = "0" * 64; self.save_pins()
        self.refused("Pinned input differs: base_common_sha256")
        self.pins["base_common_sha256"] = digest(self.base)
        self.sources["PixelmonPcResyncMixin"].write_text("edited"); self.save_pins()
        self.refused("Pinned input differs: source_sha256")
        self.pins["source_sha256"]["PixelmonPcResyncMixin"] = digest(self.sources["PixelmonPcResyncMixin"])
        self.pins["class_sha256"]["PixelmonPcResyncMixin"] = "0" * 64; self.save_pins()
        self.refused("Compiled repair class differs")

    def test_configuration_that_registers_anything_else_is_refused(self):
        self.config.write_text(json.dumps(dict(compat.EXPECTED_CONFIG, mixins=["PixelmonPcResyncMixin", "Other"])))
        self.pins["config_sha256"] = digest(self.config); self.save_pins()
        self.refused("Only the authored classes of this step may be registered")

    def test_base_that_already_holds_the_class_is_refused(self):
        self.write_zip(self.base, dict(self.original, **{compat.CLASSES["PixelmonPcResyncMixin"]: b"present"}))
        self.pins["base_common_sha256"] = digest(self.base); self.save_pins()
        self.refused("Unexpected base inventory")


class TrackedResendTest(unittest.TestCase):
    """The tracked source and configuration against the tracked pins."""

    def test_shipped_pins_match_the_shipped_source_and_configuration(self):
        pins = json.loads(compat.MANIFEST.read_text())
        self.assertEqual(pins["source_sha256"], {name: digest(path) for name, path in compat.SOURCES.items()})
        self.assertEqual(pins["config_sha256"], digest(compat.CONFIG))
        self.assertEqual(json.loads(compat.CONFIG.read_text()), compat.EXPECTED_CONFIG)
        self.assertEqual(sorted(pins["class_sha256"]), sorted(compat.NAMES))

    @unittest.skipUnless((ROOT / "cache/research/psa-common-portfix-r1.jar").is_file()
                         and (ROOT / "cache/research/psa-pc-resync-canonical-r1.jar").is_file(), "pinned private inputs not present")
    def test_pinned_inputs_give_the_common_jar_the_staging_tool_expects(self):
        import stage_forge_candidate
        with tempfile.TemporaryDirectory() as folder:
            receipt = compat.build(ROOT / "cache/research/psa-common-portfix-r1.jar",
                                   ROOT / "cache/research/psa-pc-resync-canonical-r1.jar", Path(folder) / "common.jar")
        self.assertEqual(receipt["sha256"], stage_forge_candidate.PORT_SHA256)


if __name__ == "__main__":
    unittest.main()
