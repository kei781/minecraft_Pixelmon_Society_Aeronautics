"""Packaging guard fixtures only; fake bytes are never launched as game mods."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import forge_hitpoint_compat as compat


class HitpointOverlayTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base, self.patchjar, self.pixelmon = [self.root / n for n in ("base.jar", "patch.jar", "pixelmon.jar")]
        self.output = self.root / "result.jar"
        self.config, self.source, self.manifest = [self.root / n for n in ("mixins.json", "Source.java", "pins.json")]
        self.source.write_text("authored fixture")
        self.pixelmon.write_bytes(b"upstream fixture")
        self.original = {"META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\n\n",
            "psa-forge.mixins.json": b'{"mixins":["Existing"],"client":["Retained"]}',
            "PSA_PROVENANCE.txt": b"original provenance\n", "upstream/Untouched.class": b"opaque upstream bytes"}
        self.write_zip(self.base, self.original)
        self.compiled = b"authored compiled fixture only"
        self.write_zip(self.patchjar, {compat.CLASS: self.compiled})
        self.config.write_text(json.dumps({"mixins": ["Existing", "PixelmonDynamaxHitpointsMixin"], "client": ["Retained"]}))
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

    def test_overlay_preserves_opaque_upstream_and_is_deterministic(self):
        self.build()
        with zipfile.ZipFile(self.output) as result:
            self.assertEqual(result.read("upstream/Untouched.class"), self.original["upstream/Untouched.class"])
            self.assertEqual(result.read("META-INF/MANIFEST.MF"), self.original["META-INF/MANIFEST.MF"])
            self.assertEqual(result.read(compat.CLASS), self.compiled)
        second = self.root / "second.jar"
        compat.build(self.base, self.patchjar, self.pixelmon, second)
        self.assertEqual(self.output.read_bytes(), second.read_bytes())

    def test_rebuilt_patch_with_wrong_class_is_refused_without_output(self):
        self.write_zip(self.patchjar, {compat.CLASS: b"unexpected class"})
        self.pins["tested_patch_sha256"] = compat.digest(self.patchjar); self.save_pins()
        with self.assertRaisesRegex(ValueError, "Compiled mixin differs"): self.build()
        self.assertFalse(self.output.exists())

    def test_extra_registration_is_refused_even_with_updated_source_hash(self):
        document = json.loads(self.config.read_text()); document["client"].append("Unexpected")
        self.config.write_text(json.dumps(document)); self.pins["config_sha256"] = compat.digest(self.config); self.save_pins()
        with self.assertRaisesRegex(ValueError, "single authored"): self.build()
        self.assertFalse(self.output.exists())

    def test_existing_output_and_mods_destination_are_preserved(self):
        self.output.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "Fresh"): self.build()
        self.assertEqual(self.output.read_bytes(), b"keep")
        self.output = self.root / "mods/new.jar"
        with self.assertRaisesRegex(ValueError, "non-mods"): self.build()

    def test_mutated_original_and_symlink_are_refused(self):
        self.base.write_bytes(b"wrong original")
        with self.assertRaisesRegex(ValueError, "base_common"): self.build()
        self.write_zip(self.base, self.original)
        link = self.root / "linked.jar"; link.symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, "base_common"):
            compat.build(link, self.patchjar, self.pixelmon, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
