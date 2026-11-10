import hashlib
import io
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import export_forge_client as client
import install_forge_runtime as runtime


class ForgeClientAndRuntimeTest(unittest.TestCase):
    def test_resource_zip_cannot_be_classified_as_a_mod(self):
        for kind, name in [("mod", "resource.zip"), ("resourcepack", "mod.jar"),
                           ("unknown", "mod.jar"), ("mod", "../mod.jar")]:
            with self.subTest(kind=kind, name=name), self.assertRaises(ValueError):
                client.target_path(kind, name)

    def test_unexpected_private_overrides_and_symlinks_fail(self):
        link = zipfile.ZipInfo("overrides/config/link.txt")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for name in ["overrides/accounts.json", "overrides/config/../../outside", link]:
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as archive:
                archive.writestr(name, b"test")
            data.seek(0)
            with zipfile.ZipFile(data) as archive, self.assertRaises(ValueError):
                client.overrides_from(archive)

    def test_windows_case_collision_in_overrides_fails(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("overrides/config/Example.txt", b"a")
            archive.writestr("overrides/config/example.txt", b"b")
        data.seek(0)
        with zipfile.ZipFile(data) as archive, self.assertRaises(ValueError):
            client.overrides_from(archive)

    def test_corrupt_existing_runtime_cache_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            source = root / "runtime.tar.gz"
            source.write_bytes(b"corrupt")
            item = {"filename": source.name, "size": 7, "hashes": {"sha256": hashlib.sha256(b"correct").hexdigest()}}
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                runtime.download(item, root)
            self.assertEqual(source.read_bytes(), b"corrupt")
            item["hashes"] = {}
            with self.assertRaisesRegex(ValueError, "hashes are required"):
                runtime.verify(source, item)


if __name__ == "__main__":
    unittest.main()
