import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import nbt_codec as nbt
import village_world as world

LINE = "[19:00:00] [Server thread/INFO] [KubeJS Server/]: psa_village_probe.js#25: PSA_VILLAGE_PROBE %s %s"


def region(chunks):
    """Anvil file bytes for {(local_x, local_z): root compound}."""
    header, body, sector = bytearray(8192), b"", 2
    for (local_x, local_z), root in chunks.items():
        data = zlib.compress(nbt.serialize(root))
        record = struct.pack(">IB", len(data) + 1, 2) + data
        record += b"\x00" * (-len(record) % 4096)
        index = (local_z * 32 + local_x) * 4
        header[index:index + 4] = struct.pack(">I", (sector << 8) | (len(record) // 4096))
        body += record
        sector += len(record) // 4096
    return bytes(header) + body


def section(y, names, placed):
    """One chunk section whose palette is `names`; `placed` maps (x, y, z) to a palette index."""
    bits = max(4, (len(names) - 1).bit_length())
    per_long = 64 // bits
    values = [0] * 4096
    for (x, local_y, z), index in placed.items():
        values[(local_y * 16 + z) * 16 + x] = index
    longs = []
    for start in range(0, 4096, per_long):
        packed = 0
        for offset, value in enumerate(values[start:start + per_long]):
            packed |= value << (offset * bits)
        longs.append(packed - (1 << 64) if packed >= 1 << 63 else packed)
    return nbt.compound({"Y": nbt.byte(y), "block_states": nbt.compound({
        "palette": nbt.tag_list(nbt.COMPOUND, [nbt.compound({"Name": nbt.string(name)}) for name in names]),
        "data": nbt.Tag(nbt.LONG_ARRAY, tuple(longs))})})


class VillageWorldTest(unittest.TestCase):
    def test_probe_lines_become_normalised_records(self):
        village = {"structure": "minecraft:village_plains", "chunk": [1, 2], "box": [0, 60, 0, 40, 80, 40],
                   "biome": "minecraft:plains", "spawn_distance": 12.0,
                   "pieces": [["LegacySingle[Left[minecraft:village/plains/town_centers/plains_meeting_point_1]]", 0, 60, 0, 9, 66, 10],
                              ["Single[Left[pixelmon:village/plains/plains_pokecenter]]", 10, 60, 0, 20, 70, 13],
                              ["Single[Left[pixelmon:npc/nurse]]", 15, 62, 9, 15, 64, 9],
                              ["Feature[Reference{ResourceKey[minecraft:worldgen/placed_feature / minecraft:oak]=x}]", 1, 60, 1, 1, 60, 1],
                              ["List[[Single[Left[minecraft:village/plains/plains_lamp_1]]]]", 2, 60, 2, 2, 63, 2],
                              ["Empty", 3, 60, 3, 3, 60, 3]]}
        lines = ["noise", LINE % ("spawn", json.dumps({"x": 1, "y": 64, "z": 2})),
                 LINE % ("pool", json.dumps({"id": "minecraft:village/plains/houses", "total_weight": 3,
                                             "elements": {"Single[Left[pixelmon:village/plains/berry_farm_1]]": 2, "Empty": 1},
                                             "lithostitched_entries": None})),
                 LINE % ("template", json.dumps({"id": "minecraft:x", "size": [1, 2, 3], "jigsaw_pools": {}})),
                 LINE % ("registry", json.dumps({"name": "block", "total": 3, "offset": 0, "ids": ["a:b", "a:c"]})),
                 LINE % ("registry", json.dumps({"name": "block", "total": 3, "offset": 2, "ids": ["a:d"]})),
                 LINE % ("village", json.dumps(village)), LINE % ("census", json.dumps({"found": {}})),
                 "x: PSA_VILLAGE_PROBE_DONE"]
        parsed = world.parse_probe_log(lines)
        self.assertTrue(parsed["done"])
        self.assertIsNone(parsed["failed"])
        self.assertEqual(parsed["spawn"]["y"], 64)
        self.assertEqual(parsed["registries"], {"block": ["a:b", "a:c", "a:d"]})
        self.assertEqual(parsed["pools"]["minecraft:village/plains/houses"]["elements"],
                         {"empty": 1, "pixelmon:village/plains/berry_farm_1": 2})
        self.assertEqual([piece[0] for piece in parsed["villages"][0]["pieces"]], [
            "minecraft:village/plains/town_centers/plains_meeting_point_1", "pixelmon:village/plains/plains_pokecenter",
            "pixelmon:npc/nurse", "feature:minecraft:oak", "list[minecraft:village/plains/plains_lamp_1]", "empty"])
        failed = world.parse_probe_log(["x: PSA_VILLAGE_PROBE_FAILED TypeError: boom"])
        self.assertEqual(failed["failed"], "TypeError: boom")
        self.assertFalse(failed["done"])

    def test_summary_counts_villages_not_pieces(self):
        centre = ["minecraft:village/desert/town_centers/desert_meeting_point_1", 0, 0, 0, 1, 1, 1]
        villages = [
            {"structure": "minecraft:village_desert", "pieces": [centre, ["pixelmon:village/desert/desert_pokecenter", 0, 0, 0, 1, 1, 1],
                                                                  ["pixelmon:village/desert/desert_mart", 0, 0, 0, 1, 1, 1],
                                                                  ["pixelmon:village/desert/berry_farm_2", 0, 0, 0, 1, 1, 1],
                                                                  ["pixelmon:village/desert/berry_farm_3", 0, 0, 0, 1, 1, 1]]},
            {"structure": "minecraft:village_desert", "pieces": [centre, ["minecraft:village/desert/houses/desert_fletcher_house_1", 0, 0, 0, 1, 1, 1],
                                                                  ["pixelmon:village/desert/desert_pokecenter", 0, 0, 0, 1, 1, 1],
                                                                  ["pixelmon:village/desert/desert_pokecenter", 0, 0, 0, 1, 1, 1]]},
        ]
        summary = world.summarize_villages(villages)["minecraft:village_desert"]
        self.assertEqual(summary["villages"], 2)
        self.assertEqual(summary["with"]["pokecenter"], 2)
        self.assertEqual(summary["with"]["berry_farm"], 1)
        self.assertEqual(summary["piece_total"]["berry_farm"], 2)
        self.assertEqual(summary["with"]["pokecenter_and_mart"], 1)
        self.assertEqual(summary["with"]["duplicate_pokecenter_or_mart"], 1)
        self.assertEqual(summary["with"]["society_fletcher_house"], 1)
        self.assertEqual(summary["town_centres"], {"desert_meeting_point_1": {"mart": 1, "pokecenter": 2, "villages": 2}})
        self.assertEqual(world.family_of("pixelmon:village/snowy/snowy_battle_arena_a"), "battle_arena")
        self.assertIsNone(world.family_of("minecraft:village/plains/houses/plains_small_house_1"))

    def test_saved_world_is_read_back_inside_the_requested_box_only(self):
        start = nbt.compound({"id": nbt.string("minecraft:village_plains"), "Children": nbt.tag_list(nbt.COMPOUND, [
            nbt.compound({"id": nbt.string("minecraft:jigsaw"), "BB": nbt.Tag(nbt.INT_ARRAY, (0, 64, 0, 9, 70, 10)),
                          "pool_element": nbt.compound({"element_type": nbt.string("minecraft:single_pool_element"),
                                                        "location": nbt.string("pixelmon:village/plains/plains_pokecenter")})}),
            nbt.compound({"id": nbt.string("minecraft:jigsaw"), "BB": nbt.Tag(nbt.INT_ARRAY, (1, 64, 1, 1, 64, 1)),
                          "pool_element": nbt.compound({"element_type": nbt.string("minecraft:feature_pool_element"),
                                                        "feature": nbt.string("minecraft:oak")})}),
            nbt.compound({"id": nbt.string("minecraft:jigsaw"), "BB": nbt.Tag(nbt.INT_ARRAY, (2, 64, 2, 2, 64, 2)),
                          "pool_element": nbt.compound({"element_type": nbt.string("lithostitched:delegating"),
                                                        "delegate": nbt.compound({
                                                            "element_type": nbt.string("minecraft:legacy_single_pool_element"),
                                                            "location": nbt.string("minecraft:village/common/animals/cat")})})})])})
        names = ["minecraft:air", "pixelmon:red_healer", "minecraft:stone"]
        chunk = nbt.compound({
            "Status": nbt.string("minecraft:full"),
            "sections": nbt.tag_list(nbt.COMPOUND, [
                section(4, names, {(1, 0, 1): 1, (2, 0, 2): 2, (15, 0, 15): 1}),
                section(5, ["pixelmon:red_healer"], {})]),  # a uniform section is ignored
            "structures": nbt.compound({"starts": nbt.compound({"minecraft:village_plains": start})})})
        proto = nbt.compound({"Status": nbt.string("minecraft:structure_starts"), "sections": nbt.tag_list(nbt.COMPOUND, [])})
        entities = nbt.compound({"Entities": nbt.tag_list(nbt.COMPOUND, [
            nbt.compound({"id": nbt.string("pixelmon:npc_nursejoy"), "Pos": nbt.tag_list(nbt.DOUBLE, [
                nbt.Tag(nbt.DOUBLE, 5.5), nbt.Tag(nbt.DOUBLE, 65.0), nbt.Tag(nbt.DOUBLE, 5.5)])}),
            nbt.compound({"id": nbt.string("minecraft:villager"), "Pos": nbt.tag_list(nbt.DOUBLE, [
                nbt.Tag(nbt.DOUBLE, 14.5), nbt.Tag(nbt.DOUBLE, 65.0), nbt.Tag(nbt.DOUBLE, 14.5)])})])})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "region").mkdir()
            (root / "entities").mkdir()
            (root / "region/r.0.0.mca").write_bytes(region({(0, 0): chunk, (1, 0): proto}))
            (root / "entities/r.0.0.mca").write_bytes(region({(0, 0): entities}))
            (root / "level.dat").write_bytes(nbt.dump_gzip(nbt.compound({"Data": nbt.compound({
                "SpawnX": nbt.integer(384), "SpawnY": nbt.integer(68), "SpawnZ": nbt.integer(-528)})})))
            saved = world.World(root)
            self.assertEqual(saved.structure_pieces(0, 0, "minecraft:village_plains"), [
                ["pixelmon:village/plains/plains_pokecenter", 0, 64, 0, 9, 70, 10], ["feature:minecraft:oak", 1, 64, 1, 1, 64, 1],
                ["minecraft:village/common/animals/cat", 2, 64, 2, 2, 64, 2]])
            self.assertIsNone(saved.structure_pieces(0, 0, "minecraft:village_desert"))
            self.assertIsNone(saved.structure_pieces(5, 5, "minecraft:village_plains"))
            self.assertEqual(saved.census([0, 64, 0, 9, 70, 10]), {
                "blocks": {"pixelmon:red_healer": 1}, "entities": {"pixelmon:npc_nursejoy": 1}, "chunks_not_full": 0})
            self.assertEqual(saved.census([0, 64, 0, 31, 70, 15])["chunks_not_full"], 1)
            self.assertEqual(saved.census([0, 64, 0, 15, 64, 15])["blocks"], {"pixelmon:red_healer": 2})
            self.assertEqual(world.level_spawn(root), {"x": 384, "y": 68, "z": -528})


if __name__ == "__main__":
    unittest.main()
