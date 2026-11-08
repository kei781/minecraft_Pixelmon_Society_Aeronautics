import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forge_resources", ROOT / "tools/forge_resources.py")
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)


class GeneratedResourceTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.source = self.root / "raw"
        self.destination = self.root / "merged"
        self.source.mkdir()

    def write(self, path, document):
        target = self.source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document))

    def test_shared_minecraft_tag_retains_every_mods_values(self):
        path = "data/minecraft/tags/blocks/mineable/pickaxe.json"
        self.write("aeronautics/" + path, {"values": ["aeronautics:levitite", "minecraft:stone"]})
        self.write("simulated/" + path, {"replace": False, "values": ["simulated:assembler", "minecraft:stone"]})
        self.write("offroad/assets/offroad/models/item/wheel.json", {"parent": "offroad:block/wheel"})
        self.write("aeronautics/.cache/provider.json", {"private_cache": True})
        report = resources.flatten(self.source, self.destination)
        merged = json.loads((self.destination / path).read_text())
        self.assertEqual(merged["values"], ["aeronautics:levitite", "minecraft:stone", "simulated:assembler"])
        self.assertEqual(report["merged_tags"], [path])
        self.assertEqual(len(report["files"]), 2)
        self.assertFalse(any(".cache" in str(p) for p in self.destination.rglob("*")))

    def test_different_non_tag_resources_fail_without_output(self):
        path = "assets/minecraft/models/item/shared.json"
        self.write("aeronautics/" + path, {"parent": "a"})
        self.write("simulated/" + path, {"parent": "b"})
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            resources.flatten(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_replacing_tag_is_not_silently_combined(self):
        path = "data/minecraft/tags/blocks/test.json"
        self.write("aeronautics/" + path, {"values": ["aeronautics:a"]})
        self.write("simulated/" + path, {"replace": True, "values": ["simulated:b"]})
        with self.assertRaisesRegex(ValueError, "safely merge"):
            resources.flatten(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_forge_removals_are_preserved(self):
        merged = resources.merge_tag(b'{"values":["a:a"],"remove":["#a:old"]}',
                                     b'{"values":["b:b"],"remove":["#a:old","b:old"]}', "test")
        self.assertEqual(json.loads(merged), {"replace": False, "values": ["a:a", "b:b"],
                                             "remove": ["#a:old", "b:old"]})

    def test_symlinks_and_existing_output_are_rejected(self):
        self.write("aeronautics/data/aeronautics/tags/blocks/test.json", {"values": ["aeronautics:a"]})
        link = self.source / "simulated"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            resources.flatten(self.source, self.destination)
        link.unlink()
        resources.flatten(self.source, self.destination)
        sentinel = self.destination / "sentinel"
        sentinel.write_text("existing output")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            resources.flatten(self.source, self.destination)
        self.assertEqual(sentinel.read_text(), "existing output")

    def test_combination_keeps_tags_translations_and_backported_sound(self):
        main = self.root / "main"
        generated = self.root / "generated"
        for root, values in [(main, {"tag": ["a:a"], "lang": {"old": "authored", "shared": "authored"},
                                    "sounds": {"gust": {"name": "minecraft:entity.wind_charge.wind_burst"}}}),
                             (generated, {"tag": ["b:b"], "lang": {"new": "generated", "shared": "generated"},
                                         "sounds": {"gust": {"name": "minecraft:entity.generic.explode"}}})]:
            for path, data in [("data/minecraft/tags/blocks/example.json", {"values": values["tag"]}),
                               ("assets/aeronautics/lang/en_us.json", values["lang"]),
                               ("assets/aeronautics/sounds.json", values["sounds"])]:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(data))
        report = resources.combine(main, generated, self.destination)
        self.assertEqual(len(report["merged_resources"]), 3)
        self.assertEqual(json.loads((self.destination / "data/minecraft/tags/blocks/example.json").read_text())["values"], ["a:a", "b:b"])
        self.assertEqual(json.loads((self.destination / "assets/aeronautics/lang/en_us.json").read_text()),
                         {"old": "authored", "new": "generated", "shared": "authored"})
        self.assertEqual(json.loads((self.destination / "assets/aeronautics/sounds.json").read_text())["gust"]["name"],
                         "minecraft:entity.generic.explode")

    def test_cli_supports_flatten_then_combine(self):
        self.write("aeronautics/data/aeronautics/tags/blocks/test.json", {"values": ["aeronautics:a"]})
        script = str(ROOT / "tools/forge_resources.py")
        flattened = subprocess.run([sys.executable, script, "flatten", str(self.source), str(self.destination)],
                                   check=True, text=True, capture_output=True)
        self.assertEqual(json.loads(flattened.stdout)["files"], 1)
        main, complete = self.root / "authored", self.root / "complete"
        main.mkdir()
        (main / "notice.txt").write_text("authored")
        combined = subprocess.run([sys.executable, script, "combine", str(main), str(self.destination), str(complete)],
                                  check=True, text=True, capture_output=True)
        self.assertEqual(json.loads(combined.stdout)["files"], 2)
        self.assertEqual((complete / "notice.txt").read_text(), "authored")

    def test_jar_normalization_preserves_bytes_and_removes_metadata_variation(self):
        outputs = []
        for number, year in enumerate([2025, 2026]):
            source, output = self.root / (str(number) + '.jar'), self.root / (str(number) + '-out.jar')
            with zipfile.ZipFile(source, 'w') as archive:
                for name, data in [('META-INF/MANIFEST.MF', b'Manifest-Version: 1.0\n'), ('a.class', b'class bytes')]:
                    info = zipfile.ZipInfo(name, (year, 1, 1, 0, 0, 0))
                    archive.writestr(info, data)
            resources.canonical_jar(source, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read('a.class'), b'class bytes')
            outputs.append(output.read_bytes())
            with self.assertRaises(FileExistsError):
                resources.canonical_jar(source, output)
        self.assertEqual(*outputs)


if __name__ == "__main__":
    unittest.main()
