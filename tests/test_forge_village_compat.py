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
import forge_village_compat as compat
import nbt_codec as nbt

STREET = {"name": "minecraft:street", "target": "minecraft:street", "pool": "minecraft:village/desert/streets",
          "final_state": "minecraft:structure_void", "joint": "aligned"}
HOUSE = dict(STREET, name="minecraft:building_entrance", target="minecraft:building_entrance",
             pool="minecraft:village/desert/houses")


def jigsaw(values):
    data = nbt.compound({key: nbt.string(values[key]) for key in ("joint", "name", "pool", "final_state")})
    data.value["ForgeCaps"] = nbt.compound()
    data.value["id"] = nbt.string("minecraft:jigsaw")
    data.value["target"] = nbt.string(values["target"])
    return data


def template(size, jigsaws, extra=None):
    """A flat fixture centre: air on the y=1 layer plus the given {position: (facing, values)} jigsaws."""
    palette, blocks, states = [], [], {}

    def state(name, facing=None):
        if (name, facing) not in states:
            entry = nbt.compound()
            if facing:
                entry.value["Properties"] = nbt.compound({"orientation": nbt.string(facing)})
            entry.value["Name"] = nbt.string(name)
            palette.append(entry)
            states[(name, facing)] = len(palette) - 1
        return nbt.integer(states[(name, facing)])

    for x in range(size[0]):
        for z in range(size[2]):
            position = nbt.tag_list(nbt.INT, [nbt.integer(x), nbt.integer(1), nbt.integer(z)])
            if (x, 1, z) in jigsaws:
                facing, values = jigsaws[(x, 1, z)]
                blocks.append(nbt.compound({"nbt": jigsaw(values), "pos": position, "state": state("minecraft:jigsaw", facing)}))
            else:
                blocks.append(nbt.compound({"pos": position, "state": state((extra or {}).get((x, 1, z), "minecraft:air"))}))
    return nbt.dump_gzip(nbt.compound({
        "size": nbt.tag_list(nbt.INT, [nbt.integer(value) for value in size]),
        "entities": nbt.tag_list(nbt.END, []), "blocks": nbt.tag_list(nbt.COMPOUND, blocks),
        "palette": nbt.tag_list(nbt.COMPOUND, palette), "DataVersion": nbt.integer(3465)}))


def pool(name, pixelmon=0):
    element = lambda location: {"element_type": "minecraft:legacy_single_pool_element", "location": location,
                                "processors": "minecraft:empty", "projection": "rigid"}
    elements = [{"element": element("minecraft:village/%s/a" % name), "weight": 2},
                {"element": {"element_type": "minecraft:empty_pool_element"}, "weight": 10}]
    for number in range(pixelmon):
        elements.insert(1, {"element": element("pixelmon:village/%s/extra_%d" % (name, number)), "weight": number + 1})
    return json.dumps({"fallback": "minecraft:empty", "elements": elements}).encode()


def blocks_by_position(data):
    root = nbt.load_gzip(data)
    palette = root["palette"].value
    result = {}
    for block in root["blocks"].value:
        entry = palette[block.number("state")]
        facing = entry["Properties"].text("orientation") if "Properties" in entry else None
        values = {key: item.value for key, item in block["nbt"].value.items() if item.type == nbt.STRING} if "nbt" in block else None
        result[tuple(item.value for item in block["pos"].value)] = (entry.text("Name"), facing, values)
    return result


class VillageCompatibilityTest(unittest.TestCase):
    """Small authored fixtures only; nothing here is loaded by a game."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.society = {}
        pins = {}
        self.jar = self.root / "pixelmon.jar"
        with zipfile.ZipFile(self.jar, "w") as archive:
            for name, (_, _, count) in compat.POOLS.items():
                theirs, ours = pool(name), pool(name, count)
                self.society["kubejs/" + compat.POOL_FOLDER + name + ".json"] = theirs
                archive.writestr(compat.POOL_FOLDER + name + ".json", ours)
                pins[name] = (compat.sha256(theirs), compat.sha256(ours), count)
            archive.writestr(compat.POOL_FOLDER + "desert/houses.json", pool("desert/houses", 7))  # Society has no copy
            reference = template((3, 3, 3), {(0, 1, 0): ("north_up", compat.HOOKS["pokecenter"]),
                                             (2, 1, 2): ("south_up", compat.HOOKS["mart"])})
            archive.writestr(compat.CENTRE_FOLDER + "desert_meeting_point_3.nbt", reference)
            for name in compat.CENTRES:
                archive.writestr(compat.CENTRE_FOLDER + name, template((3, 3, 3), {}))
            archive.writestr(compat.PIXELMON_DESERT_POOL, json.dumps({"elements": [
                {"element": {"location": "pixelmon:village/desert/desert_pokecenter"}, "weight": 100},
                {"element": {"location": "pixelmon:village/desert/desert_mart"}, "weight": 100}]}))
        centres = copy.deepcopy(compat.CENTRES)
        layouts = {
            "desert_meeting_point_1.nbt": {(12, 1, 0): ("north_up", STREET), (12, 1, 8): ("south_up", STREET),
                                           (16, 1, 4): ("east_up", STREET), (7, 1, 4): ("west_up", HOUSE)},
            "desert_meeting_point_2.nbt": {(6, 1, 0): ("north_up", STREET), (0, 1, 5): ("west_up", STREET),
                                           (5, 1, 11): ("south_up", STREET), (11, 1, 6): ("east_up", STREET)},
        }
        self.layouts = layouts
        for name, layout in layouts.items():
            data = template(centres[name]["size"], layout)
            self.society["kubejs/" + compat.CENTRE_FOLDER + name] = data
            centres[name]["sha256"] = compat.sha256(data)
        self.society["kubejs/server_scripts/society.js"] = b"// Society fixture"
        context = patch.multiple(compat, POOLS=pins, CENTRES=centres,
                                 PIXELMON_REFERENCE_CENTRE=("desert_meeting_point_3.nbt", compat.sha256(reference)))
        context.start()
        self.addCleanup(context.stop)

    def test_modifiers_add_only_pixelmon_elements_with_their_weights(self):
        outputs, receipt = compat.plan(self.jar, self.society.get)
        self.assertEqual(len(receipt["pool_modifiers"]), 5)
        for entry in receipt["pool_modifiers"]:
            modifier = json.loads(outputs[entry["path"]])
            self.assertEqual(modifier["type"], "lithostitched:add_template_pool_elements")
            self.assertEqual(modifier["template_pools"], entry["template_pool"])
            locations = [item["element"]["location"] for item in modifier["elements"]]
            self.assertEqual(locations, entry["added_elements"])
            self.assertTrue(all(location.startswith("pixelmon:") for location in locations))
            self.assertEqual(sorted(item["weight"] for item in modifier["elements"]), list(range(1, len(locations) + 1)))
            self.assertEqual(entry["sha256"], compat.sha256(outputs[entry["path"]]))
        self.assertNotIn(compat.MODIFIER_FOLDER + "desert_houses.json", outputs)  # Pixelmon's copy already wins there
        self.assertEqual(compat.plan(self.jar, self.society.get), (outputs, receipt))

    def test_centres_gain_hooks_and_keep_every_other_block(self):
        outputs, receipt = compat.plan(self.jar, self.society.get)
        for name, plan in compat.CENTRES.items():
            path = "kubejs/" + compat.CENTRE_FOLDER + name
            before, after = blocks_by_position(self.society[path]), blocks_by_position(outputs[path])
            edited = {position for position, _, _ in plan["hooks"]}
            for position, facing, kind in plan["hooks"]:
                found = after[position]
                self.assertEqual(found[:2], ("minecraft:jigsaw", facing))
                self.assertEqual({key: found[2][key] for key in compat.HOOKS[kind]}, compat.HOOKS[kind])
                self.assertEqual(found[2]["id"], "minecraft:jigsaw")
            for old, new in plan["moved_streets"]:
                self.assertNotIn(old, after)
                self.assertEqual(after[new], before[old])
                edited |= {old, new}
            self.assertEqual({k: v for k, v in after.items() if k not in edited},
                             {k: v for k, v in before.items() if k not in edited})
            streets = lambda blocks: sorted(p for p, value in blocks.items() if value[2] and value[2]["name"] == "minecraft:street")
            expected = len(self.layouts[name]) - len(plan["replaced_streets"]) - (1 if name.endswith("_1.nbt") else 0)
            self.assertEqual(len(streets(after)), expected)
        self.assertEqual([entry["pixelmon_hooks"] for entry in receipt["town_centres"]], [6, 6])
        self.assertEqual(receipt["spawn_script"]["sha256"], hashlib.sha256(compat.SPAWN_SOURCE.read_bytes()).hexdigest())
        self.assertEqual(outputs[compat.SPAWN_PATH], compat.SPAWN_SOURCE.read_bytes())

    def test_any_changed_input_stops_without_touching_the_mapping(self):
        changes = {
            "kubejs/" + compat.POOL_FOLDER + "plains/houses.json": pool("plains/houses") + b" ",
            "kubejs/" + compat.CENTRE_FOLDER + "desert_meeting_point_1.nbt": template((17, 6, 9), {}),
            "kubejs/" + compat.POOL_FOLDER + "desert/houses.json": pool("desert/houses"),  # a new overlap needs review
            compat.SPAWN_PATH: b"// someone else's script",
            compat.MODIFIER_FOLDER + "plains_houses.json": b"{}",
        }
        for path, data in changes.items():
            files = dict(self.society)
            files[path] = data
            before = dict(files)
            with self.subTest(path=path), self.assertRaises(ValueError):
                compat.apply_overrides(files, self.jar)
            self.assertEqual(files, before)
        files = dict(self.society)
        del files["kubejs/" + compat.POOL_FOLDER + "taiga/houses.json"]
        with self.assertRaises(ValueError):
            compat.apply_overrides(files, self.jar)

    def test_hook_positions_must_be_free_and_streets_where_expected(self):
        name = "desert_meeting_point_2.nbt"
        path = "kubejs/" + compat.CENTRE_FOLDER + name
        cases = [template((12, 6, 12), self.layouts[name], {(0, 1, 2): "minecraft:sandstone"}),   # hook position occupied
                 template((12, 6, 12), {k: v for k, v in self.layouts[name].items() if k != (11, 1, 6)}),  # no east street
                 template((12, 6, 12), self.layouts[name], {(0, 1, 10): "minecraft:sandstone"}),  # street target occupied
                 template((12, 6, 12), {**self.layouts[name], (0, 1, 5): ("west_up", HOUSE)})]  # not a street
        for data in cases:
            files = dict(self.society)
            files[path] = data
            centres = copy.deepcopy(compat.CENTRES)
            centres[name]["sha256"] = compat.sha256(data)
            with self.subTest(sha=centres[name]["sha256"][:8]), patch.object(compat, "CENTRES", centres):
                with self.assertRaises(ValueError):
                    compat.plan(self.jar, files.get)

    def test_pixelmon_hook_definition_is_checked_against_the_jar(self):
        other = self.root / "other.jar"
        with zipfile.ZipFile(self.jar) as source, zipfile.ZipFile(other, "w") as target:
            for item in source.infolist():
                data = source.read(item)
                if item.filename == compat.PIXELMON_DESERT_POOL:
                    data = json.dumps({"elements": [{"element": {"location": "pixelmon:village/desert/renamed"}, "weight": 1}]})
                target.writestr(item.filename, data)
        with self.assertRaisesRegex(ValueError, "hooks differ"):
            compat.plan(other, self.society.get)

    def test_directory_application_declares_exactly_what_it_wrote(self):
        staged = self.root / "staged"
        for path, data in self.society.items():
            target = staged / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.assertIsNone(compat.verify_staged(staged, None))
        receipt = compat.apply_directory(staged, self.jar)
        self.assertEqual(compat.verify_staged(staged, receipt), receipt)
        self.assertEqual((staged / "kubejs/server_scripts/society.js").read_bytes(), b"// Society fixture")
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            compat.verify_staged(staged, None)
        with self.assertRaises(ValueError):  # the originals are gone, so a second application is refused
            compat.apply_directory(staged, self.jar)
        (staged / compat.MODIFIER_FOLDER / "extra.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "Unexpected village pool modifier"):
            compat.verify_staged(staged, receipt)
        (staged / compat.MODIFIER_FOLDER / "extra.json").unlink()
        (staged / compat.SPAWN_PATH).write_bytes(b"// changed")
        with self.assertRaisesRegex(ValueError, "differs"):
            compat.verify_staged(staged, receipt)

    def test_symlinked_profile_folder_is_refused(self):
        outside, staged = self.root / "outside", self.root / "linked"
        for path, data in self.society.items():
            target = outside / Path(path).relative_to("kubejs")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        staged.mkdir()
        (staged / "kubejs").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Regular staged village path"):
            compat.apply_directory(staged, self.jar)
        self.assertFalse((outside / "server_scripts/psa_village_spawn.js").exists())


class PinnedArtifactTest(unittest.TestCase):
    """Runs only where the pinned private inputs are present; never downloads them."""
    JAR = ROOT / "cache/research/Pixelmon-1.20.1-9.2.3-universal.jar"
    PACK = ROOT / "cache/research/SERVER-PACK-Society-Sunlit-Valley-4.1.5A.zip"

    @unittest.skipUnless(JAR.is_file() and PACK.is_file(), "pinned private inputs not present")
    def test_pinned_inputs_produce_the_recorded_outputs(self):
        recorded = json.loads((ROOT / "compat/village-build.json").read_text())
        with zipfile.ZipFile(self.PACK) as archive:
            names = set(archive.namelist())
            outputs, receipt = compat.plan(self.JAR, lambda path: archive.read(path) if path in names else None)
        self.assertEqual({path: compat.sha256(data) for path, data in sorted(outputs.items())}, recorded["output_sha256"])
        self.assertEqual(receipt, recorded["receipt"])


if __name__ == "__main__":
    unittest.main()
