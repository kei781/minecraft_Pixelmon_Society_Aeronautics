import copy
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
import forge_loot_compat as compat


def item(name, weight=1):
    return {"type": "minecraft:item", "name": name, "weight": weight}


def pool(*entries, **keys):
    return dict({"rolls": 1, "entries": list(entries)}, **keys)


def empty(weight, **keys):
    return dict({"type": "minecraft:empty", "weight": weight}, **keys)


def path(table):
    return "kubejs/" + compat.FOLDER + table + ".json"


def slots(entry):
    """Weight, quality and conditions of every leaf below a pool or entry, in the order the game expands them."""
    children = entry.get("entries", entry.get("children"))
    if children is not None:
        return [slot for child in children for slot in slots(child)]
    return [(entry.get("weight", 1), entry.get("quality", 0), entry.get("conditions"))]


def content(entry):
    """Every leaf below a pool or entry that can yield something."""
    children = entry.get("entries", entry.get("children"))
    if children is not None:
        return [leaf for child in children for leaf in content(child)]
    return [] if entry["type"] in ("empty", "minecraft:empty") else [entry]


# Bastion tables: Society and Pixelmon both replace them.
SOCIETY_POOL = pool(item("minecraft:diamond"), item("numismatics:crown"))
VANILLA_POOL = pool(item("minecraft:diamond"), item("minecraft:netherite_scrap"))
PIXELMON_POOLS = [pool(item("pixelmon:poke_ball"), {"type": "minecraft:empty", "weight": 3}),
                  pool({"type": "minecraft:alternatives", "children": [item("pixelmon:fire_gem"), item("pixelmon:nugget")]})]

# Tables only Pixelmon replaces: a vanilla 1.20.1 table and Pixelmon's older copy of it.
RESTORED = ("chests/desert_pyramid", "chests/village/village_armorer")
COUNT = [{"function": "minecraft:set_count", "count": {"min": 1, "max": 3}}]
CHANCE = [{"condition": "minecraft:random_chance", "chance": 0.5}]
VANILLA_TABLE = {
    "type": "minecraft:chest",
    "pools": [{"bonus_rolls": 0.0, "entries": [dict(item("minecraft:saddle", 20), functions=COUNT), empty(6)],
               "rolls": {"type": "minecraft:uniform", "max": 4.0, "min": 2.0}},
              {"bonus_rolls": 0.0, "entries": [item("minecraft:dune_armor_trim_smithing_template")], "rolls": 1.0}],
    "functions": [{"function": "minecraft:explosion_decay"}],
    "random_sequence": "minecraft:chests/fixture",
}
VANILLA_ONLY = pool(item("minecraft:iron_ingot", 5), {"type": "minecraft:loot_table", "name": "minecraft:chests/igloo_chest"},
                    name="vanilla")
PURE = pool(item("pixelmon:poke_ball", 2), dict(item("tcg:pack"), functions=COUNT), {"type": "empty", "weight": 5}, name="balls")
REFERENCE = pool({"type": "minecraft:loot_table", "name": "pixelmon:special/random_berry", "functions": COUNT},
                 {"type": "empty", "weight": 7})
MIXED = pool(dict(item("minecraft:diamond_helmet", 3), functions=COUNT, conditions=CHANCE, quality=2),
             item("pixelmon:platinum_helmet"),
             {"type": "minecraft:tag", "name": "minecraft:planks", "weight": 4, "expand": False},
             {"type": "minecraft:loot_table", "name": "minecraft:chests/simple_dungeon", "functions": COUNT},
             empty(2), name="armors", rolls={"min": 1, "max": 3})
MIXED_REDUCED = pool(empty(3, conditions=CHANCE, quality=2), item("pixelmon:platinum_helmet"), empty(4),
                     {"type": "minecraft:empty"}, empty(2), name="armors", rolls={"min": 1, "max": 3})
COMPOSITE = pool(
    {"type": "minecraft:alternatives", "children": [
        dict(item("minecraft:golden_apple", 2), conditions=CHANCE),
        {"type": "minecraft:group", "children": [item("pixelmon:fire_gem", 3), dict(item("minecraft:rail", 6), functions=COUNT)]}]},
    {"type": "minecraft:sequence", "conditions": CHANCE, "children": [item("minecraft:stick", 4), item("minecraft:bone")]})
COMPOSITE_REDUCED = pool(
    {"type": "minecraft:alternatives", "children": [
        empty(2, conditions=CHANCE),
        {"type": "minecraft:group", "children": [item("pixelmon:fire_gem", 3), empty(6)]}]},
    {"type": "minecraft:sequence", "conditions": CHANCE, "children": [empty(4), empty(1)]})
PIXELMON_COPY = {"type": "minecraft:chest", "pools": [VANILLA_ONLY, PURE, MIXED, COMPOSITE, REFERENCE]}
APPENDED = [PURE, MIXED_REDUCED, COMPOSITE_REDUCED, REFERENCE]


class LootCompatibilityTest(unittest.TestCase):
    """Small authored JSON fixtures only; nothing here is loaded by a game."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.society, self.pixelmon, self.vanilla = {}, {}, {}
        bastion, restored = {}, {}
        for table in compat.TABLES:
            theirs = json.dumps({"type": "minecraft:chest", "pools": [SOCIETY_POOL]}).encode()
            self.society[path(table)] = theirs
            self.pixelmon[table] = json.dumps({"type": "minecraft:chest", "pools": PIXELMON_POOLS + [VANILLA_POOL]}).encode()
            self.vanilla[table] = json.dumps({"type": "minecraft:chest", "pools": [VANILLA_POOL]}).encode()
            bastion[table] = (compat.sha256(theirs), compat.sha256(self.pixelmon[table]), 2)
        for table in RESTORED:
            self.vanilla[table] = json.dumps(VANILLA_TABLE, indent=2).encode()
            self.pixelmon[table] = json.dumps(PIXELMON_COPY).encode()
            restored[table] = (compat.sha256(self.vanilla[table]), compat.sha256(self.pixelmon[table]), 4)
        for table in compat.UNUSED:
            self.pixelmon[table] = b"{}"  # vanilla has no table of that id
        self.jar = self.archive("pixelmon.jar", self.pixelmon)
        self.data = self.archive("vanilla.jar", self.vanilla)
        context = patch.multiple(compat, TABLES=bastion, VANILLA_TABLES=restored,
                                 VANILLA_DATA_SHA256=compat.sha256(self.data.read_bytes()))
        context.start()
        self.addCleanup(context.stop)

    def archive(self, name, tables, other=()):
        target = self.root / name
        with zipfile.ZipFile(target, "w") as archive:
            for table, data in tables.items():
                archive.writestr(compat.FOLDER + table + ".json", data)
            for entry in other:
                archive.writestr(entry, b"")
        return target

    def files(self, staged):
        return {target.relative_to(staged).as_posix(): target.read_bytes() for target in staged.rglob("*") if target.is_file()}

    def stage(self, folder):
        staged = self.root / folder
        for name, data in self.society.items():
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return staged

    def test_society_pools_stay_first_and_only_pixelmon_pools_are_added(self):
        outputs, receipt = compat.plan(self.jar, self.data, self.society.get)
        self.assertEqual(sorted(outputs), sorted(list(self.society) + [path(table) for table in RESTORED]))
        self.assertEqual([entry["path"] for entry in receipt["loot_tables"]], sorted(self.society))
        for entry in receipt["loot_tables"]:
            merged = json.loads(outputs[entry["path"]])
            self.assertEqual(merged["type"], "minecraft:chest")
            self.assertEqual(merged["pools"], [SOCIETY_POOL] + PIXELMON_POOLS)
            self.assertEqual(outputs[entry["path"]], (json.dumps(merged, indent=2) + "\n").encode())
            self.assertNotIn(VANILLA_POOL, merged["pools"])  # Society removed that vanilla content on purpose
            self.assertEqual((entry["society_pools_kept"], entry["pixelmon_pools_added"]), (1, 2))
            self.assertEqual(entry["sha256"], compat.sha256(outputs[entry["path"]]))
        self.assertEqual(compat.plan(self.jar, self.data, self.society.get), (outputs, receipt))

    def test_pool_classification(self):
        self.assertTrue(compat.pixelmon_only(PIXELMON_POOLS[0]))
        self.assertTrue(compat.pixelmon_only(PIXELMON_POOLS[1]))
        for other in [VANILLA_POOL, pool({"type": "minecraft:empty"}), pool(),
                      pool(item("pixelmon:poke_ball"), item("minecraft:stick")),
                      pool(item("pixelmon:poke_ball"), {"type": "minecraft:loot_table", "name": "pixelmon:x"}),
                      pool(item("pixelmon:poke_ball"), {"type": "minecraft:tag", "name": "pixelmon:x"})]:
            self.assertFalse(compat.pixelmon_only(other))

    def test_vanilla_pools_stay_first_and_verbatim_before_pixelmon_content(self):
        outputs, receipt = compat.plan(self.jar, self.data, self.society.get)
        self.assertEqual([entry["table"] for entry in receipt["vanilla_loot_tables"]], ["minecraft:" + table for table in RESTORED])
        for table, entry in zip(RESTORED, receipt["vanilla_loot_tables"]):
            self.assertNotIn(path(table), self.society)
            merged = json.loads(outputs[path(table)])
            self.assertEqual(outputs[path(table)], (json.dumps(merged, indent=2) + "\n").encode())
            self.assertEqual(list(merged), list(VANILLA_TABLE))
            self.assertEqual({key: merged[key] for key in ("type", "functions", "random_sequence")},
                             {key: VANILLA_TABLE[key] for key in ("type", "functions", "random_sequence")})
            self.assertEqual(merged["pools"][:2], VANILLA_TABLE["pools"])
            self.assertEqual(merged["pools"][2:], APPENDED)
            self.assertNotIn(VANILLA_ONLY, merged["pools"])
            self.assertEqual([leaf["name"] for added in merged["pools"][2:] for leaf in content(added)],
                             ["pixelmon:poke_ball", "tcg:pack", "pixelmon:platinum_helmet", "pixelmon:fire_gem",
                              "pixelmon:special/random_berry"])
            self.assertEqual(entry, {
                "path": path(table), "table": "minecraft:" + table, "sha256": compat.sha256(outputs[path(table)]),
                "vanilla_sha256": compat.sha256(self.vanilla[table]), "pixelmon_sha256": compat.sha256(self.pixelmon[table]),
                "vanilla_pools_kept": 2, "pixelmon_pools_added": 4, "entries_blanked": 7})
        self.assertEqual(receipt["unused_pixelmon_tables"], ["minecraft:" + table for table in sorted(compat.UNUSED)])
        self.assertEqual(json.loads(json.dumps(receipt)), receipt)  # a staged profile keeps the receipt as JSON

    def test_pixelmon_content_keeps_its_drop_chance(self):
        for original, expected, blanked in [(PURE, PURE, 0), (REFERENCE, REFERENCE, 0), (MIXED, MIXED_REDUCED, 3),
                                            (COMPOSITE, COMPOSITE_REDUCED, 4)]:
            before = copy.deepcopy(original)
            with self.subTest(pool=original.get("name"), blanked=blanked):
                reduced, count = compat.pixelmon_pool(original)
                self.assertEqual((reduced, count), (expected, blanked))
                self.assertEqual(original, before)
                self.assertEqual(slots(reduced), slots(original))
                self.assertEqual(sum(slot[0] for slot in slots(reduced)), sum(slot[0] for slot in slots(original)))
                self.assertEqual(content(reduced), [leaf for leaf in content(original)
                                                    if leaf["name"].split(":")[0] in ("pixelmon", "tcg")])
                self.assertEqual({key: reduced[key] for key in reduced if key != "entries"},
                                 {key: original[key] for key in original if key != "entries"})
        for other in [VANILLA_ONLY, VANILLA_POOL, pool(empty(1)), pool(), pool(item("pixelmon")), pool(item("minecraft:pixelmon")),
                      pool({"type": "minecraft:group", "children": [item("minecraft:stick")]})]:
            self.assertIsNone(compat.pixelmon_pool(other))

    def test_entries_without_a_fixed_weight_are_refused(self):
        for entry in [{"type": "minecraft:tag", "name": "minecraft:planks", "expand": True},
                      {"type": "othermod:item", "name": "minecraft:stick"}, {"name": "minecraft:stick"},
                      {"type": "minecraft:group"}]:
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, "Unexpected loot entry type"):
                compat.pixelmon_pool(pool(item("pixelmon:poke_ball"), entry))
        berries = pool({"type": "minecraft:tag", "name": "pixelmon:berries", "expand": True})  # Pixelmon's own: kept as it is
        self.assertEqual(compat.pixelmon_pool(berries), (berries, 0))

    def test_changed_or_unexpected_inputs_stop_without_touching_the_mapping(self):
        bastion = path("chests/bastion_other")
        cases = {bastion: self.society[bastion] + b" ",
                 path(RESTORED[0]): self.vanilla[RESTORED[0]],  # a new overlap needs review
                 path(compat.UNUSED[0]): b"{}"}
        for name, data in cases.items():
            files = dict(self.society)
            files[name] = data
            before = dict(files)
            with self.subTest(name=name), self.assertRaises(ValueError):
                compat.apply_overrides(files, self.jar, self.data)
            self.assertEqual(files, before)
        files = dict(self.society)
        del files[bastion]
        with self.assertRaises(ValueError):
            compat.apply_overrides(files, self.jar, self.data)
        for pins in ("TABLES", "VANILLA_TABLES"):
            more = {table: values[:2] + (values[2] + 1,) for table, values in getattr(compat, pins).items()}
            with patch.object(compat, pins, more), self.assertRaisesRegex(ValueError, "Unexpected Pixelmon loot pools"):
                compat.plan(self.jar, self.data, self.society.get)

    def test_changed_vanilla_or_pixelmon_archives_stop_without_touching_the_mapping(self):
        table, files = RESTORED[0], dict(self.society)

        def refused(message, pixelmon=None, vanilla=None, accept=False):
            jar = self.jar if pixelmon is None else self.archive("changed-pixelmon.jar", pixelmon)
            data = self.data if vanilla is None else self.archive("changed-vanilla.jar", vanilla)
            accepted = compat.sha256(data.read_bytes()) if accept else compat.VANILLA_DATA_SHA256
            with self.subTest(message=message), patch.object(compat, "VANILLA_DATA_SHA256", accepted):
                with self.assertRaisesRegex(ValueError, message):
                    compat.apply_overrides(files, jar, data)
            self.assertEqual(files, self.society)

        changed = dict(self.vanilla, **{table: self.vanilla[table] + b" "})
        refused("vanilla 1.20.1 data JAR", vanilla=changed)  # not the pinned file
        with self.assertRaisesRegex(ValueError, "vanilla 1.20.1 data JAR"):
            compat.apply_overrides(files, self.jar, None)
        refused("Pinned loot input required: vanilla " + table, vanilla=changed, accept=True)
        refused("without a vanilla table", vanilla={name: data for name, data in self.vanilla.items() if name != table}, accept=True)
        refused("without a vanilla table", vanilla=dict(self.vanilla, **{compat.UNUSED[0]: b"{}"}), accept=True)
        refused("Pinned loot input required: Pixelmon " + table, pixelmon=dict(self.pixelmon, **{table: self.pixelmon[table] + b" "}))
        refused("Unexpected set of vanilla loot tables in Pixelmon", pixelmon=dict(self.pixelmon, **{"chests/ancient_city": b"{}"}))
        refused("Unexpected set of vanilla loot tables in Pixelmon",
                pixelmon={name: data for name, data in self.pixelmon.items() if name != compat.UNUSED[0]})
        with self.assertRaisesRegex(ValueError, "Unexpected set of vanilla loot tables in Pixelmon"):  # not a table at all
            compat.apply_overrides(files, self.archive("other-file.jar", self.pixelmon, [compat.FOLDER + "chests/notes.txt"]), self.data)
        self.assertEqual(files, self.society)
        self.assertEqual(compat.apply_overrides(files, self.jar, self.data), compat.plan(self.jar, self.data, self.society.get)[1])
        self.assertEqual(sorted(files), sorted(list(self.society) + [path(name) for name in RESTORED]))

    def test_pixelmon_content_already_in_a_kept_table_is_refused(self):
        table, bastion = RESTORED[0], "chests/bastion_other"
        changed = json.dumps(dict(VANILLA_TABLE, pools=VANILLA_TABLE["pools"] + [REFERENCE])).encode()
        data = self.archive("pixelmon-in-vanilla.jar", dict(self.vanilla, **{table: changed}))
        pins = dict(compat.VANILLA_TABLES, **{table: (compat.sha256(changed),) + compat.VANILLA_TABLES[table][1:]})
        with patch.multiple(compat, VANILLA_TABLES=pins, VANILLA_DATA_SHA256=compat.sha256(data.read_bytes())):
            with self.assertRaisesRegex(ValueError, "Unexpected Pixelmon loot pools: " + table):
                compat.plan(self.jar, data, self.society.get)
        theirs = json.dumps({"type": "minecraft:chest", "pools": [SOCIETY_POOL, PIXELMON_POOLS[0]]}).encode()
        pins = dict(compat.TABLES, **{bastion: (compat.sha256(theirs),) + compat.TABLES[bastion][1:]})
        with patch.object(compat, "TABLES", pins), self.assertRaisesRegex(ValueError, "Unexpected Pixelmon loot pools: " + bastion):
            compat.plan(self.jar, self.data, dict(self.society, **{path(bastion): theirs}).get)
        self.assertEqual(len(compat.plan(self.jar, self.data, self.society.get)[0]), len(compat.TABLES) + len(RESTORED))

    def test_directory_application_and_declaration(self):
        staged = self.stage("staged")
        self.assertIsNone(compat.verify_staged(staged, None))
        receipt = compat.apply_directory(staged, self.jar, self.data)
        self.assertEqual(compat.verify_staged(staged, receipt), receipt)
        outputs = compat.plan(self.jar, self.data, self.society.get)[0]
        self.assertEqual({name: (staged / name).read_bytes() for name in outputs}, outputs)
        with self.assertRaisesRegex(ValueError, "differs"):  # merged tables without a declaration
            compat.verify_staged(staged, None)
        bastion_only = {"loot_tables": receipt["loot_tables"]}  # what a profile staged before the vanilla tables declares
        with self.assertRaisesRegex(ValueError, "Undeclared loot table"):
            compat.verify_staged(staged, bastion_only)
        with self.assertRaises(ValueError):  # originals are gone; a second application is refused
            compat.apply_directory(staged, self.jar, self.data)
        restored = [staged / entry["path"] for entry in receipt["vanilla_loot_tables"]]
        restored[0].write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "differs"):
            compat.verify_staged(staged, receipt)
        for target in restored:
            target.unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            compat.verify_staged(staged, receipt)
        self.assertEqual(compat.verify_staged(staged, bastion_only), bastion_only)
        (staged / receipt["loot_tables"][0]["path"]).unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            compat.verify_staged(staged, bastion_only)
        with self.assertRaisesRegex(ValueError, "unknown"):
            compat.verify_staged(staged, {"loot_tables": [{"path": path("chests/ancient_city"), "sha256": compat.sha256(b"{}")}]})

    def test_restored_vanilla_table_without_a_declaration_is_refused(self):
        staged = self.stage("staged")
        outputs = compat.plan(self.jar, self.data, self.society.get)[0]
        target = staged / path(RESTORED[1])
        target.parent.mkdir(parents=True)
        target.write_bytes(outputs[path(RESTORED[1])])
        with self.assertRaisesRegex(ValueError, "Undeclared loot table: " + path(RESTORED[1])):
            compat.verify_staged(staged, None)
        target.unlink()
        self.assertIsNone(compat.verify_staged(staged, None))

    def test_refused_directory_application_writes_nothing(self):
        staged = self.stage("staged")
        changed = staged / path("chests/bastion_other")
        changed.write_bytes(changed.read_bytes() + b" ")
        before = self.files(staged)
        with self.assertRaisesRegex(ValueError, "Pinned loot input required: Society"):
            compat.apply_directory(staged, self.jar, self.data)
        self.assertEqual(self.files(staged), before)
        self.assertFalse((staged / path(RESTORED[1])).parent.exists())

    def test_profile_with_a_folder_or_file_in_the_wrong_place_is_refused_before_writing(self):
        folder = self.stage("folder")  # a folder where a table belongs
        (folder / path(RESTORED[0])).mkdir()
        blocked = self.stage("blocked")  # a file where the folder of the last output belongs
        (blocked / path(RESTORED[1])).parent.write_bytes(b"")
        for staged in (folder, blocked):
            before = self.files(staged)
            with self.subTest(staged=staged.name):
                with self.assertRaisesRegex(ValueError, "Regular staged loot path"):
                    compat.apply_directory(staged, self.jar, self.data)
                self.assertEqual(self.files(staged), before)
                with self.assertRaisesRegex(ValueError, "Undeclared loot table|Regular staged loot path"):
                    compat.verify_staged(staged, None)

    def test_symlinked_profile_folder_is_refused(self):
        outside, staged = self.root / "outside", self.root / "linked"
        for name, data in self.society.items():
            target = outside / Path(name).relative_to("kubejs")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        staged.mkdir()
        (staged / "kubejs").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Regular staged loot path"):
            compat.apply_directory(staged, self.jar, self.data)
        with self.assertRaisesRegex(ValueError, "Regular staged loot path"):
            compat.verify_staged(staged, None)
        self.assertEqual(self.files(outside), {Path(name).relative_to("kubejs").as_posix(): data for name, data in self.society.items()})

    def test_symlinked_table_is_refused(self):
        staged, elsewhere = self.stage("staged"), self.root / "elsewhere.json"
        (staged / path(RESTORED[0])).symlink_to(elsewhere)  # dangling: writing through it would create the file
        before = self.files(staged)
        with self.assertRaisesRegex(ValueError, "Regular staged loot path"):
            compat.apply_directory(staged, self.jar, self.data)
        with self.assertRaisesRegex(ValueError, "Regular staged loot path"):
            compat.verify_staged(staged, None)
        self.assertEqual(self.files(staged), before)
        self.assertFalse(elsewhere.exists())

    def test_record_lists_the_inputs_and_every_output(self):
        pack = self.root / "server-pack.zip"
        with zipfile.ZipFile(pack, "w") as archive:
            for name, data in self.society.items():
                archive.writestr(name, data)
        outputs, receipt = compat.plan(self.jar, self.data, self.society.get)
        recorded = compat.record(self.jar, self.data, pack)
        self.assertEqual(recorded["receipt"], receipt)
        self.assertEqual(recorded["output_sha256"], {name: compat.sha256(data) for name, data in sorted(outputs.items())})
        self.assertEqual(recorded["inputs"], {"pixelmon_jar_sha256": compat.sha256(self.jar.read_bytes()),
                                              "vanilla_data_jar_sha256": compat.VANILLA_DATA_SHA256,
                                              "society_server_pack_sha1": hashlib.sha1(pack.read_bytes()).hexdigest()})


class PinnedArtifactTest(unittest.TestCase):
    """The recorded build against the module's pins; the outputs themselves only where the private inputs are present."""
    JAR = ROOT / "cache/research/Pixelmon-1.20.1-9.2.3-universal.jar"
    PACK = ROOT / "cache/research/SERVER-PACK-Society-Sunlit-Valley-4.1.5A.zip"
    LIBRARY = "libraries/net/minecraft/server/1.20.1-20230612.114412/server-1.20.1-20230612.114412-extra.jar"
    DATA = next((found for pattern in ("server/" + LIBRARY, "server/*/" + LIBRARY, "tests/generated/*/" + LIBRARY)
                 for found in sorted(ROOT.glob(pattern)) if compat.sha256(found.read_bytes()) == compat.VANILLA_DATA_SHA256), None)

    def test_recorded_build_names_every_pinned_table(self):
        recorded = json.loads((ROOT / "compat/loot-build.json").read_text())
        self.assertEqual(recorded["inputs"]["vanilla_data_jar_sha256"], compat.VANILLA_DATA_SHA256)
        receipt = recorded["receipt"]
        self.assertEqual({entry["path"]: (entry["original_sha256"], entry["pixelmon_pools_added"]) for entry in receipt["loot_tables"]},
                         {path(table): (pins[0], pins[2]) for table, pins in compat.TABLES.items()})
        self.assertEqual({entry["path"]: (entry["vanilla_sha256"], entry["pixelmon_sha256"], entry["pixelmon_pools_added"])
                          for entry in receipt["vanilla_loot_tables"]},
                         {path(table): pins for table, pins in compat.VANILLA_TABLES.items()})
        self.assertEqual((len(compat.TABLES), len(compat.VANILLA_TABLES), len(compat.UNUSED)), (3, 37, 5))
        self.assertEqual({entry["path"]: entry["sha256"] for entry in receipt["loot_tables"] + receipt["vanilla_loot_tables"]},
                         recorded["output_sha256"])

    @unittest.skipUnless(JAR.is_file() and PACK.is_file() and DATA is not None, "pinned private inputs not present")
    def test_pinned_inputs_produce_the_recorded_outputs(self):
        recorded = json.loads((ROOT / "compat/loot-build.json").read_text())
        with zipfile.ZipFile(self.PACK) as archive, zipfile.ZipFile(self.DATA) as vanilla:
            names = set(archive.namelist())
            outputs, receipt = compat.plan(self.JAR, self.DATA, lambda name: archive.read(name) if name in names else None)
            self.assertEqual({name: compat.sha256(data) for name, data in sorted(outputs.items())}, recorded["output_sha256"])
            self.assertEqual(receipt, recorded["receipt"])
            for entry in receipt["vanilla_loot_tables"]:
                self.assertNotIn(entry["path"], names)
                merged = json.loads(outputs[entry["path"]])
                original = json.loads(vanilla.read(entry["path"][len("kubejs/"):]))
                self.assertEqual(merged["pools"][:entry["vanilla_pools_kept"]], original["pools"])
                self.assertEqual(len(merged["pools"]), entry["vanilla_pools_kept"] + entry["pixelmon_pools_added"])
                self.assertEqual({key: value for key, value in merged.items() if key != "pools"},
                                 {key: value for key, value in original.items() if key != "pools"})


if __name__ == "__main__":
    unittest.main()
