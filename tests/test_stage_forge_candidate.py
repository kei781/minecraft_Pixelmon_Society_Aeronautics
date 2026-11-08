import importlib.util
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stage_forge", ROOT / "tools/stage_forge_candidate.py")
stage_forge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_forge)


class StageForgeTest(unittest.TestCase):
    def test_published_hashes_verify_both_metadata_shapes(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source, lock = root / "mod.jar", root / "lock.json"
            source.write_bytes(b"upstream mod")
            hashes = {"sha1": hashlib.sha1(source.read_bytes()).hexdigest(),
                      "sha512": hashlib.sha512(source.read_bytes()).hexdigest()}
            for metadata in [{"size": source.stat().st_size, "upstream_hashes": hashes},
                             {"file": {"size": source.stat().st_size, "hashes": hashes}}]:
                metadata["source_page"] = "https://example.test/official"
                lock.write_text(json.dumps({"artifacts": {"test": metadata}}))
                with patch.object(stage_forge, "LOCK", lock):
                    self.assertTrue(stage_forge.verify_published(source, "test")["verified"])

    def test_published_verification_rejects_missing_hashes_and_tampering(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source, lock = root / "mod.jar", root / "lock.json"
            source.write_bytes(b"upstream mod")
            correct = hashlib.sha1(source.read_bytes()).hexdigest()
            cases = [(999, {"sha1": correct}), (source.stat().st_size, {"sha1": "0" * 40}),
                     (source.stat().st_size, {}), (source.stat().st_size, None),
                     (source.stat().st_size, {"sha1": "wrong"})]
            for size, hashes in cases:
                lock.write_text(json.dumps({"artifacts": {"test": {"source_page": "https://example.test/official",
                    "size": size, "upstream_hashes": hashes}}}))
                with self.subTest(size=size, hashes=hashes), patch.object(stage_forge, "LOCK", lock):
                    with self.assertRaises(ValueError):
                        stage_forge.verify_published(source, "test")

    def archive(self, extra):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for number in range(311):
                archive.writestr("mods/example%d.jar" % number, b"test")
            for name, content in extra:
                archive.writestr(name, content)
        data.seek(0)
        return zipfile.ZipFile(data)

    def test_server_scripts_are_not_extracted(self):
        with self.archive([("start.sh", b"not copied"), ("config/test.toml", b"included")]) as archive:
            entries = stage_forge.selected_entries(archive)
            self.assertEqual(len(entries), 312)
            self.assertNotIn("start.sh", [i.filename for i in entries])

    def test_unsafe_paths_case_collisions_and_symlinks_fail(self):
        link = zipfile.ZipInfo("mods/link.jar")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for extra in [[("mods/../../outside", b"x")], [("/outside", b"x")],
                      [("mods/EXAMPLE0.jar", b"x")], [(link, b"/outside")]]:
            with self.subTest(extra=extra), self.archive(extra) as archive:
                with self.assertRaises(ValueError):
                    stage_forge.selected_entries(archive)

    def test_bad_input_or_existing_destination_never_overwrites(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source, output = root / "bad.zip", root / "out"
            source.write_bytes(b"wrong input")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                stage_forge.stage(source, source, source, output)
            self.assertFalse(output.exists())
            output.mkdir()
            sentinel = output / "world-data"
            sentinel.write_text("preserve")
            with self.assertRaisesRegex(ValueError, "fresh"):
                stage_forge.stage(source, source, source, output)
            self.assertEqual(sentinel.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
