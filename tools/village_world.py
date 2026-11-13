#!/usr/bin/env python3
"""Read village facts back from probe output and from a saved world.

Two independent sources are compared:

* `PSA_VILLAGE_PROBE` lines written by tests/forge-village-probe.js, which
  assemble villages through the running game's Structure.generate path.
* Saved Anvil region files, where the game recorded the structure starts,
  blocks and entities it really generated.

Nothing here writes to a world.
"""
import collections
import json
from pathlib import Path
import re

import nbt_codec

PROBE = re.compile(r"PSA_VILLAGE_PROBE (\w+) (\{.*\})\s*$")
ELEMENT = re.compile(r"(?:Left|Right)\[([a-z0-9_.-]+:[a-z0-9_./-]+)\]")
FEATURE = re.compile(r"placed_feature / ([a-z0-9_.-]+:[a-z0-9_./-]+)\]")
# Piece families that only exist because of one of the two projects.
FAMILIES = [
    ("pokecenter", re.compile(r"^pixelmon:village/\w+/\w*pokecenter$")),
    ("mart", re.compile(r"^pixelmon:village/\w+/\w*mart$")),
    ("tcg_shop", re.compile(r"^pixelmon:village/\w+/\w*tcg_shop_\w+$")),
    ("berry_farm", re.compile(r"^pixelmon:village/\w+/berry_farm_\d+$")),
    ("battle_arena", re.compile(r"^pixelmon:village/\w+/\w*battle_arena_\w+$")),
    ("daycare", re.compile(r"^pixelmon:village/\w+/\w*daycare$")),
    ("nurse_npc", re.compile(r"^pixelmon:npc/(nurse|doctor)$")),
    ("shopkeeper_npc", re.compile(r"^pixelmon:npc/shopkeeper/\w+$")),
    ("society_fletcher_house", re.compile(r"^minecraft:village/\w+/houses/\w+_fletcher_house_1$")),
    ("vanilla_farm", re.compile(r"^minecraft:village/\w+/houses/\w*farm\w*$")),
    ("town_centre", re.compile(r"^minecraft:village/\w+/(zombie/)?town_centers/\w+$")),
]


def element_name(text):
    """Canonical name for a StructurePoolElement.toString() value."""
    names = ELEMENT.findall(text)
    if text.startswith("List["):
        return "list[" + ",".join(names) + "]"
    if names:
        return names[0]
    feature = FEATURE.search(text)
    if feature:
        return "feature:" + feature.group(1)
    if text.startswith("Empty"):
        return "empty"
    return text


def parse_probe_log(lines):
    """Return {'spawn': {...}, 'pools': {...}, 'templates': {...}, 'villages': [...], 'census': {...}}."""
    result = {"spawn": None, "pools": {}, "templates": {}, "villages": [], "census": None,
              "registries": {}, "loot": {}, "tags": {}, "crafting": {}, "cooking": {}, "structure_sets": {},
              "assemblies": {}, "incomplete": [],
              "done": False, "failed": None}
    parts = {}
    for line in lines:
        if "PSA_VILLAGE_PROBE_DONE" in line:
            result["done"] = True
            continue
        if "PSA_VILLAGE_PROBE_FAILED" in line:
            result["failed"] = line.split("PSA_VILLAGE_PROBE_FAILED", 1)[1].strip()[:500]
            continue
        match = PROBE.search(line)
        if not match:
            continue
        kind, data = match.group(1), json.loads(match.group(2))
        if kind == "spawn":
            result["spawn"] = data
        elif kind == "pool":
            for field in ("elements", "lithostitched_entries"):
                if data.get(field) is not None:
                    merged = collections.Counter()
                    for name, count in data[field].items():
                        merged[element_name(name)] += count
                    data[field] = dict(sorted(merged.items()))
            result["pools"][data["id"]] = data
        elif kind == "template":
            result["templates"][data["id"]] = data
        elif kind == "village":
            data["pieces"] = [[element_name(piece[0])] + piece[1:] for piece in data["pieces"]]
            result["villages"].append(data)
        elif kind == "census":
            result["census"] = data
        elif kind == "loot":
            result["loot"][data["table"]] = {"rolls": int(data["rolls"]), "stacks": int(data["stacks"]),
                                             "stacks_by_item": {name: int(count) for name, count in sorted(
                                                 data["stacks_by_item"].items())}}
        elif kind == "tag":
            result["tags"][data["registry"] + ":" + data["tag"]] = data["values"]
        elif kind == "crafting":
            result["crafting"][data["name"]] = {"recipe": data["recipe"], "result": data["result"],
                                                "count": int(data["count"]), "missing_items": data["missing_items"]}
        elif kind == "cooking":
            result["cooking"][data["name"]] = {"recipe": data["recipe"], "result": data["result"], "count": int(data["count"])}
        elif kind == "structure_set":
            result["structure_sets"][data["id"]] = data["structures"]
        elif kind == "assembly":
            result["assemblies"][data["structure"]] = {
                "registered": data["registered"], "count_pieces_containing": data["count_pieces_containing"],
                "samples": [{"chunk": [int(v) for v in sample["chunk"]], "valid": sample["valid"],
                             "pieces": int(sample["pieces"]), "matched": int(sample["matched"])} for sample in data["samples"]]}
        elif kind == "registry":
            parts.setdefault(data["name"], {"total": int(data["total"]), "by_offset": {}})["by_offset"][int(data["offset"])] = data["ids"]
    for name, registry in sorted(parts.items()):
        ids = [value for offset in sorted(registry["by_offset"]) for value in registry["by_offset"][offset]]
        result["registries"][name] = ids
        if len(ids) != registry["total"]:
            # A part that never arrived: the id list must not pass for the whole registry.
            result["incomplete"].append("registry %s: %d of %d ids" % (name, len(ids), registry["total"]))
    return result


def family_of(name):
    for family, pattern in FAMILIES:
        if pattern.match(name):
            return family
    return None


def summarize_villages(villages):
    """Per structure: how many assembled villages contain each project-specific piece family."""
    summary = {}
    for village in villages:
        entry = summary.setdefault(village["structure"], {
            "villages": 0, "pieces": 0, "with": collections.Counter(), "piece_total": collections.Counter(),
            "namespaces": collections.Counter(), "town_centres": {}})
        entry["villages"] += 1
        entry["pieces"] += len(village["pieces"])
        present = collections.Counter()
        centre = None
        for piece in village["pieces"]:
            name = piece[0]
            family = family_of(name)
            if family == "town_centre" and centre is None:
                centre = name.rsplit("/", 1)[1]
            if family:
                present[family] += 1
            if ":" in name and not name.startswith(("feature:", "list[")):
                entry["namespaces"][name.split(":", 1)[0]] += 1
        for family, count in present.items():
            entry["with"][family] += 1
            entry["piece_total"][family] += count
        if present["pokecenter"] and present["mart"]:
            entry["with"]["pokecenter_and_mart"] += 1
        if present["pokecenter"] > 1 or present["mart"] > 1:
            entry["with"]["duplicate_pokecenter_or_mart"] += 1
        by_centre = entry["town_centres"].setdefault(centre or "unknown", collections.Counter())
        by_centre["villages"] += 1
        for family in ("pokecenter", "mart"):
            if present[family]:
                by_centre[family] += 1
    for entry in summary.values():
        entry["with"] = dict(sorted(entry["with"].items()))
        entry["piece_total"] = dict(sorted(entry["piece_total"].items()))
        entry["namespaces"] = dict(sorted(entry["namespaces"].items()))
        entry["town_centres"] = {name: dict(sorted(counts.items())) for name, counts in sorted(entry["town_centres"].items())}
    return dict(sorted(summary.items()))


# ---- saved world ---------------------------------------------------------

def _saved_element_name(element):
    kind = element.text("element_type")
    if kind.endswith("list_pool_element"):
        return "list[" + ",".join(_saved_element_name(item) for item in element["elements"].value) + "]"
    if kind.endswith("feature_pool_element"):
        return "feature:" + element.text("feature")
    if kind.endswith("empty_pool_element"):
        return "empty"
    if "delegate" in element:
        return _saved_element_name(element["delegate"])
    location = element.text("location")
    return location if location else kind


def region_path(world, folder, chunk_x, chunk_z):
    return Path(world) / folder / ("r.%d.%d.mca" % (chunk_x >> 5, chunk_z >> 5))


class World:
    """Lazy, read-only access to the overworld chunks of a saved world."""

    def __init__(self, world):
        self.world = Path(world)
        self._regions = {}

    def _region(self, folder, chunk_x, chunk_z):
        key = (folder, chunk_x >> 5, chunk_z >> 5)
        if key not in self._regions:
            path = region_path(self.world, folder, chunk_x, chunk_z)
            chunks = {}
            if path.is_file():
                for local_x, local_z, root in nbt_codec.read_region_chunks(path.read_bytes()):
                    chunks[(local_x, local_z)] = root
            self._regions[key] = chunks
        return self._regions[key]

    def chunk(self, chunk_x, chunk_z):
        return self._region("region", chunk_x, chunk_z).get((chunk_x & 31, chunk_z & 31))

    def entity_chunk(self, chunk_x, chunk_z):
        return self._region("entities", chunk_x, chunk_z).get((chunk_x & 31, chunk_z & 31))

    def structure_pieces(self, chunk_x, chunk_z, structure):
        """Pieces of `structure` whose start was saved in this chunk, as [name, box...] rows."""
        root = self.chunk(chunk_x, chunk_z)
        if root is None:
            return None
        starts = root.get("structures")
        start = starts.get("starts").get(structure) if starts is not None and starts.get("starts") is not None else None
        if start is None or start.get("Children") is None:
            return None
        rows = []
        for child in start["Children"].value:
            element = child.get("pool_element")
            name = _saved_element_name(element) if element is not None else child.text("id")
            rows.append([name] + [int(value) for value in child["BB"].value])
        return rows

    def census(self, box):
        """Count non-vanilla blocks and all entities inside an inclusive [x0,y0,z0,x1,y1,z1] box."""
        x0, y0, z0, x1, y1, z1 = box
        blocks, entities, missing = collections.Counter(), collections.Counter(), 0
        for chunk_x in range(x0 >> 4, (x1 >> 4) + 1):
            for chunk_z in range(z0 >> 4, (z1 >> 4) + 1):
                root = self.chunk(chunk_x, chunk_z)
                if root is None or root.text("Status") not in ("minecraft:full", "full"):
                    missing += 1
                    continue
                for section in root["sections"].value:
                    states = section.get("block_states")
                    base_y = section.number("Y") * 16
                    if states is None or base_y > y1 or base_y + 15 < y0:
                        continue
                    palette = [entry.text("Name") for entry in states["palette"].value]
                    wanted = [index for index, name in enumerate(palette) if not name.startswith("minecraft:")]
                    if not wanted:
                        continue
                    if len(palette) == 1:
                        continue  # a uniform modded section is not a village building
                    data = states["data"].value
                    bits = max(4, (len(palette) - 1).bit_length())
                    per_long, mask = 64 // bits, (1 << bits) - 1
                    wanted_set = set(wanted)
                    for local_y in range(max(y0, base_y) - base_y, min(y1, base_y + 15) - base_y + 1):
                        for local_z in range(max(z0, chunk_z * 16) - chunk_z * 16, min(z1, chunk_z * 16 + 15) - chunk_z * 16 + 1):
                            for local_x in range(max(x0, chunk_x * 16) - chunk_x * 16, min(x1, chunk_x * 16 + 15) - chunk_x * 16 + 1):
                                index = (local_y * 16 + local_z) * 16 + local_x
                                value = (data[index // per_long] >> ((index % per_long) * bits)) & mask
                                if value in wanted_set:
                                    blocks[palette[value]] += 1
                saved = self.entity_chunk(chunk_x, chunk_z)
                if saved is not None and saved.get("Entities") is not None:
                    for entity in saved["Entities"].value:
                        position = [item.value for item in entity["Pos"].value]
                        if x0 <= position[0] < x1 + 1 and y0 <= position[1] < y1 + 1 and z0 <= position[2] < z1 + 1:
                            entities[entity.text("id")] += 1
        return {"blocks": dict(sorted(blocks.items())), "entities": dict(sorted(entities.items())),
                "chunks_not_full": missing}


def level_spawn(world):
    data = nbt_codec.load_gzip((Path(world) / "level.dat").read_bytes())["Data"]
    return {"x": data.number("SpawnX"), "y": data.number("SpawnY"), "z": data.number("SpawnZ")}
