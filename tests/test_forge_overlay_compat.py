import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import forge_overlay_compat as compat

MODS_TOML = '''[[mods]]
modId = "simulated"

["lithium:options"]
"mixin.entity.collisions.unpushable_cramming" = false
"mixin.world.chunk_access" = false
"mixin.world.chunk_ticking" = false
"mixin.world.tick_scheduler" = false

[[mixins]]
config = "sable.mixins.json"
'''


def jar_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return stream.getvalue()


class OverlayCompatibilityTest(unittest.TestCase):
    """Small authored fixtures only; nothing here is loaded by a game."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        overlay = self.root / "overlay"
        self.tracked = {"kubejs/data/c/tags/items/stones.json": b'{"replace": false, "values": ["#forge:stone"]}\n',
                        "kubejs/server_scripts/psa_fixture.js": b"// overlay script fixture\n"}
        for path, data in self.tracked.items():
            (overlay / path).parent.mkdir(parents=True, exist_ok=True)
            (overlay / path).write_bytes(data)
        self.pixelmon, self.port = self.root / "pixelmon.jar", self.root / "port.jar"
        self.pixelmon.write_bytes(jar_bytes({"data/pixelmon/present.json": "{}"}))
        self.port.write_bytes(jar_bytes({compat.PORT_MODS_TOML: MODS_TOML,
                                         "data/simulated/tags/blocks/non_movable.json": '{"values": []}'}))
        self.radium = b"# Radium fixture\r\nmixin.block.moving_block_shapes=false"
        society_script = b"// Society tag script fixture"
        self.society = {compat.LITHIUM_PATH: self.radium, "kubejs/server_scripts/tags/society.js": society_script,
                        "mods/other.jar": jar_bytes({"data/other/recipes/shelf.json": '{"result": 2}'})}
        facts = [{"jar": "pixelmon", "entry": "data/pixelmon/missing_pool.json", "absent": True},
                 {"jar": "pixelmon", "entry": "data/pixelmon/present.json", "sha256": compat.sha256(b"{}")},
                 {"jar": "port", "entry": "data/simulated/tags/blocks/non_movable.json", "contains": ['"values": []']},
                 {"jar": "mods/other.jar", "entry": "data/other/recipes/shelf.json", "sha256": compat.sha256(b'{"result": 2}')},
                 {"file": "kubejs/server_scripts/tags/society.js", "sha256": compat.sha256(society_script)}]
        self.facts = self.root / "preconditions.json"
        self.facts.write_text(json.dumps(facts))
        context = patch.multiple(compat, OVERLAY=overlay, PRECONDITIONS=self.facts, LITHIUM_SHA256=compat.sha256(self.radium))
        context.start()
        self.addCleanup(context.stop)

    def plan(self, society=None):
        return compat.plan(self.pixelmon, self.port, (society or self.society).get)

    def test_overlay_is_added_verbatim_and_radium_only_gains_the_port_options(self):
        outputs, receipt = self.plan()
        for path, data in self.tracked.items():
            self.assertEqual(outputs[path], data)
        self.assertEqual(outputs[compat.LITHIUM_PATH], self.radium + b"".join(
            b"\r\n" + option.encode() + b"=false" for option in compat.LITHIUM_OPTIONS))
        self.assertEqual(sorted(outputs), sorted(list(self.tracked) + [compat.LITHIUM_PATH]))
        self.assertEqual([entry["path"] for entry in receipt["files"]], sorted(self.tracked))
        self.assertEqual(receipt["preconditions_checked"], 5)
        self.assertEqual(receipt["radium_config"]["sha256"], compat.sha256(outputs[compat.LITHIUM_PATH]))
        self.assertEqual(self.plan(), (outputs, receipt))

    def test_every_failed_precondition_stops_the_plan(self):
        broken = {
            "pool appeared upstream": lambda: self.pixelmon.write_bytes(jar_bytes(
                {"data/pixelmon/present.json": "{}", "data/pixelmon/missing_pool.json": "{}"})),
            "entry changed": lambda: self.pixelmon.write_bytes(jar_bytes({"data/pixelmon/present.json": "{ }"})),
            "port tag filled": lambda: self.port.write_bytes(jar_bytes({
                compat.PORT_MODS_TOML: MODS_TOML, "data/simulated/tags/blocks/non_movable.json": '{"values": ["a:b"]}'})),
            "other mod changed": lambda: self.society.__setitem__("mods/other.jar", jar_bytes({"data/other/recipes/shelf.json": "{}"})),
            "other mod missing": lambda: self.society.pop("mods/other.jar"),
            "society script changed": lambda: self.society.__setitem__("kubejs/server_scripts/tags/society.js", b"// edited"),
        }
        originals = (self.pixelmon.read_bytes(), self.port.read_bytes(), dict(self.society))
        for name, change in broken.items():
            self.pixelmon.write_bytes(originals[0]); self.port.write_bytes(originals[1]); self.society = dict(originals[2])
            change()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "precondition failed"):
                self.plan()
        self.pixelmon.write_bytes(originals[0]); self.port.write_bytes(originals[1]); self.society = dict(originals[2])
        self.facts.write_text(json.dumps([{"jar": "pixelmon", "entry": "x"}]))
        with self.assertRaisesRegex(ValueError, "without a test"):
            self.plan()
        self.facts.write_text("[]")
        with self.assertRaisesRegex(ValueError, "preconditions required"):
            self.plan()

    def test_radium_options_must_be_the_ones_the_port_declares(self):
        for text in [MODS_TOML.replace('"mixin.world.chunk_access" = false\n', ""),
                     MODS_TOML.replace('["lithium:options"]', '["other:options"]'),
                     MODS_TOML.replace('"mixin.world.tick_scheduler" = false', '"mixin.world.tick_scheduler" = true')]:
            self.port.write_bytes(jar_bytes({compat.PORT_MODS_TOML: text,
                                             "data/simulated/tags/blocks/non_movable.json": '{"values": []}'}))
            with self.subTest(text=text[-60:]), self.assertRaisesRegex(ValueError, "Lithium options"):
                self.plan()
        self.port.write_bytes(jar_bytes({compat.PORT_MODS_TOML: MODS_TOML,
                                         "data/simulated/tags/blocks/non_movable.json": '{"values": []}'}))
        with self.assertRaisesRegex(ValueError, "Radium configuration"):
            self.plan(dict(self.society, **{compat.LITHIUM_PATH: self.radium + b"\r\n"}))

    def test_collisions_bad_overlay_files_and_atomic_mapping(self):
        path = "kubejs/server_scripts/psa_fixture.js"
        files = dict(self.society, **{path: b"// Society already has this name"})
        before = dict(files)
        with self.assertRaisesRegex(ValueError, "already used"):
            compat.apply_overrides(files, self.pixelmon, self.port)
        self.assertEqual(files, before)
        (compat.OVERLAY / "kubejs/data/c/tags/items/broken.json").write_text("{not json")
        with self.assertRaises(ValueError):
            self.plan()
        (compat.OVERLAY / "kubejs/data/c/tags/items/broken.json").unlink()
        (compat.OVERLAY / "config").mkdir()
        (compat.OVERLAY / "config/other.toml").write_text("x = 1")
        with self.assertRaisesRegex(ValueError, "belong under kubejs"):
            self.plan()

    def test_client_mapping_reads_mods_through_the_given_reader(self):
        files = {key: value for key, value in self.society.items() if not key.startswith("mods/")}
        with self.assertRaisesRegex(ValueError, "missing mods/other.jar"):
            compat.apply_overrides(dict(files), self.pixelmon, self.port)
        receipt = compat.apply_overrides(files, self.pixelmon, self.port, self.society.get)
        self.assertEqual(files[compat.LITHIUM_PATH][-len(b"mixin.world.tick_scheduler=false"):], b"mixin.world.tick_scheduler=false")
        self.assertEqual(len(receipt["files"]), 2)

    def test_directory_application_declaration_and_symlink_refusal(self):
        staged = self.root / "staged"
        for path, data in self.society.items():
            (staged / path).parent.mkdir(parents=True, exist_ok=True)
            (staged / path).write_bytes(data)
        self.assertIsNone(compat.verify_staged(staged, None))
        receipt = compat.apply_directory(staged, self.pixelmon, self.port)
        self.assertEqual(compat.verify_staged(staged, receipt), receipt)
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            compat.verify_staged(staged, None)
        with self.assertRaises(ValueError):  # a second application finds its own files and the edited config
            compat.apply_directory(staged, self.pixelmon, self.port)
        (staged / "kubejs/server_scripts/psa_fixture.js").write_bytes(b"// changed")
        with self.assertRaisesRegex(ValueError, "differs"):
            compat.verify_staged(staged, receipt)
        linked, outside = self.root / "linked", self.root / "outside"
        outside.mkdir(); linked.mkdir()
        (linked / "kubejs").symlink_to(outside, target_is_directory=True)
        for path in (compat.LITHIUM_PATH, "mods/other.jar"):
            (linked / path).parent.mkdir(parents=True, exist_ok=True)
            (linked / path).write_bytes(self.society[path])
        with self.assertRaisesRegex(ValueError, "Regular staged overlay path"):
            compat.apply_directory(linked, self.pixelmon, self.port)
        self.assertEqual(list(outside.iterdir()), [])


class TrackedOverlayTest(unittest.TestCase):
    """The tracked overlay against the tracked records of the game runs; no private input is read."""
    TAG = compat.OVERLAY / "kubejs/data/sable/tags/blocks/silent_assembly_removal.json"

    def tagged(self):
        tag = json.loads(self.TAG.read_text())
        self.assertFalse(tag["replace"])
        return [value["id"] for value in tag["values"]]

    def test_every_block_seen_duplicating_its_contents_is_removed_silently(self):
        tagged = self.tagged()
        self.assertEqual(tagged, sorted(set(tagged)))
        before = json.loads((ROOT / "evidence/assembly-inventory-sweep-baseline.json").read_text())["summary"]
        self.assertGreater(len(before["duplicated"]), 0)
        self.assertEqual(sorted(set(before["duplicated"]) - set(tagged)), [])
        after = json.loads((ROOT / "evidence/assembly-inventory-sweep-fixed.json").read_text())["summary"]
        self.assertEqual(after["tested"], before["tested"])
        self.assertIsNone(after["failed"])
        self.assertEqual([after["duplicated"], after["lost"], after["server crash"]], [[], [], []])

    def test_the_game_check_expects_the_whole_tag(self):
        checks = json.loads((ROOT / "tests/forge-coexistence-checks.json").read_text())
        expected = [check["expect_contains"] for check in checks["tags"] if check["tag"] == "sable:silent_assembly_removal"]
        self.assertEqual(expected, [self.tagged()])

    def test_the_redstone_contact_guard_is_tied_to_the_unrepaired_port_class(self):
        # A repaired port JAR changes this class; staging then stops until the guard is taken out.
        self.assertTrue((compat.OVERLAY / "kubejs/server_scripts/psa_redstone_contact_guard.js").is_file())
        facts = json.loads(compat.PRECONDITIONS.read_text())
        self.assertIn(("port", "dev/ryanhcode/sable/forge/mixin/compatibility/create/redstone_contacts/RedstoneContactBlockMixin.class"),
                      {(fact.get("jar"), fact.get("entry")) for fact in facts if "sha256" in fact})


class PinnedArtifactTest(unittest.TestCase):
    """Runs only where the pinned private inputs are present; never downloads them."""
    STAGED = ROOT / "cache/research/psa-player-v18-staged"
    PACK = ROOT / "cache/research/SERVER-PACK-Society-Sunlit-Valley-4.1.5A.zip"

    @unittest.skipUnless(STAGED.is_dir() and PACK.is_file(), "pinned private inputs not present")
    def test_pinned_inputs_satisfy_every_precondition_and_match_the_record(self):
        recorded = json.loads((ROOT / "compat/coexistence-build.json").read_text())
        with zipfile.ZipFile(self.PACK) as archive:
            names = set(archive.namelist())
            outputs, receipt = compat.plan(self.STAGED / "mods/Pixelmon-1.20.1-9.2.3-universal.jar",
                                           self.STAGED / "mods/psa-aeronautics-experimental-forge-1.20.1.jar",
                                           lambda path: archive.read(path) if path in names else None)
        self.assertEqual({path: compat.sha256(data) for path, data in sorted(outputs.items())}, recorded["output_sha256"])
        self.assertEqual(receipt, recorded["receipt"])


if __name__ == "__main__":
    unittest.main()
