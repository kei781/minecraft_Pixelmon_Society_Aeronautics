"""Exercise real archive contents, staging gates and Windows import paths."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import export_client as exporter
import prepare


class ClientExportTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.output = self.root / "out/client.mrpack"
        for module in [exporter, prepare]:
            patcher = patch.object(module, "ROOT", self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.lock = {"minecraft": "1.21.1", "neoforge": "21.1.262", "files": []}
        for project in sorted(exporter.DIAGNOSTIC | {"creativecore"}):
            data = project.encode()
            if project == "pixelmon":
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, "w") as archive:
                    archive.writestr("data/pixelmon/pixelmon/spawn_replacement/cow.json", "{}")
                data = stream.getvalue()
            hashes = {name: hashlib.new(name, data).hexdigest() for name in ["sha1", "sha512"]}
            file = {"project": project, "path": "mods/" + project + ".jar", "side": "both",
                    "url": "https://example.invalid/" + project + ".jar", "hashes": hashes, "size": len(data)}
            self.lock["files"].append(file)
            cached = self.root / "cache" / hashes["sha512"] / (project + ".jar")
            cached.parent.mkdir(parents=True)
            cached.write_bytes(data)
        (self.root / "integration-lock.json").write_text(json.dumps(self.lock))
        (self.root / "inputs").mkdir()
        artifacts = []
        for project in ["society", "sunrisegardening", "orchard", "plentifulponds"]:
            data = ("UNIT TEST FIXTURE ONLY " + project).encode()
            (self.root / "inputs" / (project + ".jar")).write_bytes(data)
            artifacts.append({"filename": project + ".jar", "mod_id": project, "sha1": hashlib.sha1(data).hexdigest()})
        (self.root / "external-artifacts.json").write_text(json.dumps({"artifacts": artifacts}))
        core = self.root / "compat/creativecore/CreativeCore_NEOFORGE_v2.13.51_mc1.21.1-psa-codec1.jar"
        core.parent.mkdir(parents=True)
        core.write_bytes(b"UNIT TEST PATCH FIXTURE")
        (self.root / "evidence").mkdir()
        (self.root / "evidence/creativecore-patch.json").write_text(json.dumps({
            "patched_sha256": hashlib.sha256(core.read_bytes()).hexdigest(),
            "original_sha512": next(file["hashes"]["sha512"] for file in self.lock["files"] if file["project"] == "creativecore")}))
        for folder in ["config", "defaultconfigs", "kubejs", exporter.RESOURCE_SOURCE]:
            (self.root / "upstream/society" / folder).mkdir(parents=True)
        (self.root / "upstream/society/config/fixture.json").write_text("{}")
        resource = self.root / "upstream/society" / exporter.RESOURCE_SOURCE
        (resource / "pack.mcmeta").write_text('{"pack":{"pack_format":43,"description":"fixture"}}')
        upstream = self.root / "upstream/society"
        (upstream / ".gitignore").write_text("ignored-local.*\n")
        self.git("init", "-q")
        self.git("add", ".")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root / "upstream/society"), *args])

    def test_diagnostic_has_exact_six_downloads_and_preservation_overrides(self):
        report = exporter.build("diagnostic", self.output)
        with zipfile.ZipFile(self.output) as archive:
            index = json.loads(archive.read("modrinth.index.json"))
            metadata = json.loads(archive.read("overrides/psa-client-profile.json"))
            self.assertEqual({Path(file["path"]).stem for file in index["files"]}, exporter.DIAGNOSTIC)
            for file in index["files"]:
                original = next(item for item in self.lock["files"] if item["path"] == file["path"])
                self.assertEqual(file["hashes"], original["hashes"])
                self.assertEqual(file["fileSize"], original["size"])
            self.assertEqual(index["dependencies"], {"minecraft": "1.21.1", "neoforge": "21.1.262"})
            self.assertIn("NO Society", index["name"])
            self.assertFalse(metadata["complete_integration"])
            cow = json.loads(archive.read("overrides/kubejs/data/pixelmon/pixelmon/spawn_replacement/cow.json"))
            self.assertEqual(cow["detection"]["types"], [])
            for name, digest in metadata["overrides"].items():
                self.assertEqual(hashlib.sha256(archive.read("overrides/" + name)).hexdigest(), digest)
        self.assertEqual(report["sha256"], hashlib.sha256(self.output.read_bytes()).hexdigest())

    def test_missing_society_prevents_full_export_and_output_directory(self):
        (self.root / "inputs/society.jar").unlink()
        with patch.object(prepare, "verify_upstream"), self.assertRaisesRegex(ValueError, "society.jar"):
            exporter.build("integration", self.output)
        self.assertFalse(self.output.parent.exists())

    def test_bundled_import_keeps_sources_and_includes_verified_bytes(self):
        report = exporter.build("diagnostic", self.output, bundle_downloads=True)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(json.loads(archive.read("modrinth.index.json"))["files"], [])
            metadata = json.loads(archive.read("overrides/psa-client-profile.json"))
            self.assertTrue(metadata["bundled_downloads"])
            self.assertEqual(len(metadata["source_downloads"]), 6)
            for file in metadata["source_downloads"]:
                data = archive.read("overrides/" + file["path"])
                self.assertEqual(hashlib.sha512(data).hexdigest(), file["hashes"]["sha512"])
                self.assertEqual(len(data), file["fileSize"])
        self.assertEqual(report["downloads"], 0)

    def test_full_fixture_contains_one_patched_core_all_externals_and_rebuilt_resource(self):
        with patch.object(prepare, "verify_upstream"):
            exporter.build("integration", self.output)
        with zipfile.ZipFile(self.output) as archive:
            index = json.loads(archive.read("modrinth.index.json"))
            self.assertNotIn("mods/creativecore.jar", [file["path"] for file in index["files"]])
            names = archive.namelist()
            self.assertEqual(len([name for name in names if "CreativeCore" in name]), 1)
            self.assertNotIn("overrides/mods/creativecore.jar", names)
            for project in ["society", "sunrisegardening", "orchard", "plentifulponds"]:
                self.assertEqual(archive.read("overrides/mods/" + project + ".jar"), (self.root / "inputs" / (project + ".jar")).read_bytes())
            with zipfile.ZipFile(io.BytesIO(archive.read("overrides/resourcepacks/sunlit_overrides.zip"))) as resource:
                self.assertEqual(resource.namelist(), ["pack.mcmeta"])
            self.assertFalse(json.loads(archive.read("overrides/psa-client-profile.json"))["complete_integration"])

    def test_ignored_files_and_ignored_external_symlinks_are_not_packaged(self):
        config = self.root / "upstream/society/config"
        outside = self.root / "private-fixture.txt"
        outside.write_text("UNIT TEST PRIVATE MARKER")
        (config / "ignored-local.json").write_text("UNIT TEST PRIVATE MARKER")
        (config / "ignored-local.link").symlink_to(outside)
        with patch.object(prepare, "verify_upstream"):
            exporter.build("integration", self.output)
        with zipfile.ZipFile(self.output) as archive:
            self.assertIn("overrides/config/fixture.json", archive.namelist())
            self.assertFalse(any("ignored-local" in name for name in archive.namelist()))
            self.assertFalse(any(b"UNIT TEST PRIVATE MARKER" in archive.read(name) for name in archive.namelist()))

    def test_tracked_external_symlink_is_rejected_before_output(self):
        link = self.root / "upstream/society/config/external.json"
        outside = self.root / "private-fixture.txt"
        outside.write_text("UNIT TEST PRIVATE MARKER")
        link.symlink_to(outside)
        self.git("add", "config/external.json")
        with patch.object(prepare, "verify_upstream"), self.assertRaisesRegex(ValueError, "regular file"):
            exporter.build("integration", self.output)
        self.assertFalse(self.output.parent.exists())

    def test_parent_directory_symlink_is_rejected(self):
        nested = self.root / "upstream/society/config/nested"
        nested.mkdir()
        (nested / "file.json").write_text("{}")
        self.git("add", "config/nested/file.json")
        (nested / "file.json").unlink()
        nested.rmdir()
        nested.symlink_to(self.root, target_is_directory=True)
        (self.root / "file.json").write_text("UNIT TEST PRIVATE MARKER")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            prepare.tracked_files(self.root / "upstream/society", ["config"])

    def test_deterministic_archives_and_exclusive_output(self):
        exporter.build("diagnostic", self.output)
        original = self.output.read_bytes()
        second = self.root / "out/second.mrpack"
        exporter.build("diagnostic", second)
        self.assertEqual(original, second.read_bytes())
        with self.assertRaisesRegex(ValueError, "overwrite"):
            exporter.build("diagnostic", self.output)
        self.assertEqual(original, self.output.read_bytes())

    def test_windows_paths_and_metadata_collisions_are_rejected(self):
        for name in [".", "../escape", "/absolute", "mods\\a.jar", "mods/NUL.jar", "mods/a:", "mods/a.", "mods/a\n.jar"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                exporter.safe_path(name)
        for overrides in [{"mods/A.jar": b"a", "mods/a.jar": b"b"}, {"PSA-client-profile.json": b"x"}]:
            with self.assertRaises(ValueError):
                exporter.write_pack(self.output, "diagnostic", self.lock, [], overrides)
        self.assertFalse(self.output.parent.exists())


if __name__ == "__main__":
    unittest.main()
