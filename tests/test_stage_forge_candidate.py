import importlib.util
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("stage_forge", ROOT / "tools/stage_forge_candidate.py")
stage_forge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_forge)


class StageForgeTest(unittest.TestCase):
    def prepare_stage_inputs(self, root, resource=True):
        # Archive/file fixtures only; never installed or launched as game content.
        helper = stage_forge.forge_datapack_compat
        target_data = b"original serializer target fixture, never executed"
        original = b'{"forge:conditions":[{"type":"forge:false"}]}'
        server, pixelmon, port, module = [root/name for name in ["server.zip", "pixelmon.jar", "port.jar", "module.jar"]]
        with zipfile.ZipFile(server, "w") as archive:
            for number in range(310): archive.writestr("mods/fixture%d.jar" % number, b"not a game mod")
            archive.writestr(helper.TARGET_PATH, target_data)
            if resource: archive.writestr(helper.RESOURCE, original if resource is True else resource)
        with zipfile.ZipFile(pixelmon, "w") as archive:
            for number in range(68): archive.writestr("data/pixelmon/spawn_replacement/fixture%d.json" % number, "{}")
        port.write_bytes(b"port fixture never executed"); module.write_bytes(b"module fixture never executed")
        lock = root/"lock.json"
        lock.write_text(json.dumps({"artifacts": {role: {
            "source_page": "https://example.test/fixture", "size": path.stat().st_size,
            "upstream_hashes": {"sha1": stage_forge.digest(path, "sha1")}}
            for role,path in [("society_server", server), ("pixelmon", pixelmon)]}}))
        contexts = ExitStack(); self.addCleanup(contexts.close)
        contexts.enter_context(patch.multiple(stage_forge, LOCK=lock,
            SERVER_SHA1=stage_forge.digest(server,"sha1"), PIXELMON_SHA256=stage_forge.digest(pixelmon),
            PORT_SHA256=stage_forge.digest(port)))
        contexts.enter_context(patch.multiple(helper, RESOURCE_SHA256=hashlib.sha256(original).hexdigest(),
            TARGET_SHA256=hashlib.sha256(target_data).hexdigest(), MODULE_SHA256=stage_forge.digest(module)))
        return server, pixelmon, port, module, original

    def test_stage_normalizes_resource_and_records_optional_module_contract(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch); server,pixelmon,port,module,original=self.prepare_stage_inputs(root)
            helper=stage_forge.forge_datapack_compat
            for enabled in [False,True]:
                with self.subTest(module=enabled):
                    destination=root/("with-module" if enabled else "legacy")
                    receipt=stage_forge.stage(server,pixelmon,port,destination,"player",module if enabled else None)
                    self.assertEqual((destination/helper.RESOURCE).read_bytes(),helper.normalize_resource(original)[0])
                    self.assertEqual(receipt,json.loads((destination/".psa-forge-candidate.json").read_text()))
                    self.assertEqual(receipt["top_level_mod_jars"],314 if enabled else 313)
                    declaration=helper.module_receipt() if enabled else None
                    self.assertEqual(receipt["datapack_sync_compatibility"],declaration)
                    self.assertEqual(helper.verify_staged_module(destination,declaration),declaration)
                    hashes=(destination/".psa-mods.sha256").read_text().splitlines()
                    self.assertEqual(len(hashes),314 if enabled else 313)
                    self.assertEqual(any(line.endswith("  "+helper.MODULE_PATH) for line in hashes),enabled)
                    self.assertEqual((destination/"eula.txt").read_text(),"eula=false\n")

    def test_stage_missing_or_changed_loot_list_fails_before_destination_creation(self):
        for resource in [False,b"{}"]:
            with self.subTest(resource=resource),tempfile.TemporaryDirectory() as scratch:
                root=Path(scratch);server,pixelmon,port,module,_=self.prepare_stage_inputs(root,resource)
                destination=root/"must-not-exist"
                with self.assertRaisesRegex(ValueError,"global loot modifier"):
                    stage_forge.stage(server,pixelmon,port,destination,datapack_fix=module)
                self.assertFalse(destination.exists())

    def test_stage_changed_optional_module_fails_before_destination_creation(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);server,pixelmon,port,module,_=self.prepare_stage_inputs(root)
            module.write_bytes(b"changed fixture")
            destination=root/"must-not-exist"
            with self.assertRaisesRegex(ValueError,"server datapack module"):
                stage_forge.stage(server,pixelmon,port,destination,datapack_fix=module)
            self.assertFalse(destination.exists())

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
