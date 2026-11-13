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
import forge_portfix_compat as compat

PORT_CLASS = "dev/port/Repaired.class"


class PortRepairOverlayTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base, self.patchjar, self.output = [self.root / name for name in ("base.jar", "patch.jar", "result.jar")]
        self.config, self.manifest = self.root / "psa-port-fix.mixins.json", self.root / "pins.json"
        self.sources = {name: self.root / (name + ".java") for name in compat.NAMES}
        for name, path in self.sources.items():
            path.write_text("authored fixture " + name)
        self.original = {
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\r\nMixinConfigs: existing-a.json,\r\n existing-b.json\r\nKeep: unchanged\r\n\r\n",
            "existing-a.json": b'{"mixins":["Existing"]}', "PSA_PROVENANCE.txt": b"original provenance\n",
            PORT_CLASS: b"opaque port class", "upstream/Untouched.class": b"opaque upstream bytes"}
        self.write_zip(self.base, self.original)
        self.compiled = {name: ("compiled fixture " + name).encode() for name in compat.NAMES}
        self.config.write_text(json.dumps(compat.EXPECTED_CONFIG))
        self.patchfiles = {compat.CLASSES[name]: data for name, data in self.compiled.items()}
        self.patchfiles[self.config.name] = self.config.read_bytes()
        self.patchfiles["META-INF/MANIFEST.MF"] = b"Manifest-Version: 1.0\r\nMixinConfigs: psa-port-fix.mixins.json\r\n\r\n"
        self.write_zip(self.patchjar, self.patchfiles)
        self.pins = {"base_common_sha256": compat.digest(self.base), "tested_patch_sha256": compat.digest(self.patchjar),
                     "config_sha256": compat.digest(self.config),
                     "source_sha256": {name: compat.digest(path) for name, path in self.sources.items()},
                     "class_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in self.compiled.items()},
                     "port_class_sha256": {PORT_CLASS: hashlib.sha256(self.original[PORT_CLASS]).hexdigest()}}
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

    def build(self):
        return compat.build(self.base, self.patchjar, self.output)

    def test_only_the_two_classes_and_their_registration_are_added(self):
        receipt = self.build()
        with zipfile.ZipFile(self.output) as result:
            for name, data in self.original.items():
                if name not in ("META-INF/MANIFEST.MF", "PSA_PROVENANCE.txt"):
                    self.assertEqual(result.read(name), data)
            manifest = result.read("META-INF/MANIFEST.MF")
            self.assertEqual(compat.mixin_header(manifest)[4], ["existing-a.json", "existing-b.json", self.config.name])
            self.assertIn(b"Keep: unchanged\r\n\r\n", manifest)
            for name in compat.NAMES:
                self.assertEqual(result.read(compat.CLASSES[name]), self.compiled[name])
            self.assertTrue(result.read("PSA_PROVENANCE.txt").startswith(b"original provenance\n"))
            self.assertEqual(len(result.namelist()), len(self.original) + 3)
        self.assertEqual(receipt["unchanged_entries"], 3)
        second = self.root / "second.jar"
        compat.build(self.base, self.patchjar, second)
        self.assertEqual(self.output.read_bytes(), second.read_bytes())

    def test_changed_inputs_are_refused_before_anything_is_written(self):
        def repin_patch():
            self.write_zip(self.patchjar, self.patchfiles)
            self.pins["tested_patch_sha256"] = compat.digest(self.patchjar)
            self.save_pins()

        with self.assertRaisesRegex(ValueError, "base_common_sha256"):
            self.write_zip(self.base, dict(self.original, **{"upstream/Untouched.class": b"changed"}))
            self.build()
        self.write_zip(self.base, self.original)
        self.sources[compat.NAMES[0]].write_text("edited source")
        with self.assertRaisesRegex(ValueError, "source_sha256"):
            self.build()
        self.sources[compat.NAMES[0]].write_text("authored fixture " + compat.NAMES[0])
        saved = self.patchfiles[compat.CLASSES[compat.NAMES[1]]]
        self.patchfiles[compat.CLASSES[compat.NAMES[1]]] = b"another class"
        repin_patch()
        with self.assertRaisesRegex(ValueError, "Compiled repair class differs"):
            self.build()
        self.patchfiles[compat.CLASSES[compat.NAMES[1]]] = saved
        self.patchfiles["META-INF/MANIFEST.MF"] = b"MixinConfigs: psa-port-fix.mixins.json,extra.json\r\n"
        repin_patch()
        with self.assertRaisesRegex(ValueError, "registration"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_a_different_port_class_or_an_already_repaired_base_is_refused(self):
        self.pins["port_class_sha256"][PORT_CLASS] = "0" * 64
        self.save_pins()
        with self.assertRaisesRegex(ValueError, "Repaired port class differs"):
            self.build()
        self.pins["port_class_sha256"][PORT_CLASS] = hashlib.sha256(self.original[PORT_CLASS]).hexdigest()
        self.write_zip(self.base, dict(self.original, **{self.config.name: b"{}"}))
        self.pins["base_common_sha256"] = compat.digest(self.base)
        self.save_pins()
        with self.assertRaisesRegex(ValueError, "Unexpected base inventory"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_output_must_be_a_fresh_jar_outside_any_mods_folder(self):
        for target in (self.root / "mods" / "result.jar", self.root / "result.zip", self.base):
            with self.subTest(target=target.name), self.assertRaisesRegex(ValueError, "Fresh non-mods output"):
                compat.build(self.base, self.patchjar, target)


class TrackedRepairTest(unittest.TestCase):
    """The tracked sources and configuration against the tracked pins; no private input is read."""

    def test_tracked_sources_and_configuration_match_the_pins(self):
        lock = json.loads(compat.MANIFEST.read_text())
        self.assertEqual(json.loads(compat.CONFIG.read_text()), compat.EXPECTED_CONFIG)
        self.assertEqual(lock["config_sha256"], compat.digest(compat.CONFIG))
        self.assertEqual(lock["source_sha256"], {name: compat.digest(path) for name, path in compat.SOURCES.items()})
        self.assertEqual(sorted(lock["class_sha256"]), sorted(compat.NAMES))

    @unittest.skipUnless((ROOT / "cache/research/psa-common-portfix-r1.jar").is_file()
                         and (ROOT / "cache/research/psa-port-fix-0.1-canonical.jar").is_file(), "pinned private inputs not present")
    def test_pinned_inputs_give_the_common_jar_the_staging_tool_expects(self):
        import stage_forge_candidate
        with tempfile.TemporaryDirectory() as folder:
            receipt = compat.build(ROOT / "cache/research/psa-player-v18-staged/mods/psa-aeronautics-experimental-forge-1.20.1.jar",
                                   ROOT / "cache/research/psa-port-fix-0.1-canonical.jar", Path(folder) / "common.jar")
        self.assertEqual(receipt["sha256"], stage_forge_candidate.PORT_SHA256)
        self.assertEqual(receipt["sha256"], compat.digest(ROOT / "cache/research/psa-common-portfix-r1.jar"))


if __name__ == "__main__":
    unittest.main()
