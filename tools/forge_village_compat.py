"""Let Pixelmon's and Society's village content generate in the same villages.

Both projects replace whole vanilla village resources. Society's KubeJS data is
applied last, so five of Pixelmon's edited template pools and two of its desert
town centres never reach the game. Nothing of Society's is removed here:

* the Pixelmon-only pool elements are added back with Lithostitched
  `add_template_pool_elements` modifiers (Lithostitched ships with Society),
* Society's two desert town centres receive Pixelmon's Pokemon Center and
  PokeMart jigsaw hooks, and
* a server script keeps Society's start biome but starts new worlds at the
  nearest plains village that really contains a Pokemon Center.

Every input is pinned; an unexpected Society or Pixelmon file stops staging.
"""
import copy
import hashlib
import json
from pathlib import Path
import zipfile

import nbt_codec

ROOT = Path(__file__).resolve().parents[1]
SPAWN_SOURCE = ROOT / "compat/village/psa_village_spawn.js"
SPAWN_PATH = "kubejs/server_scripts/psa_village_spawn.js"
MODIFIER_FOLDER = "kubejs/data/psa_village/lithostitched/worldgen_modifier/"
POOL_FOLDER = "data/minecraft/worldgen/template_pool/village/"
CENTRE_FOLDER = "data/minecraft/structures/village/desert/town_centers/"

# Pools that both projects replace: pool -> (Society KubeJS sha256, Pixelmon JAR entry sha256, Pixelmon elements).
POOLS = {
    "plains/houses": ("616b1ff732e31198c49aa5ed0b8f067b9e4db0a986606364bb60700b5db26cc5",
                      "486fdbe83e515ab20dcb0ecbf9486892591928995ac3a892a4863d3443d1d4e8", 7),
    "savanna/houses": ("76bbcd94142dc15f59f9bc0374f2e826eca390578bb496cda8816ea1250538c0",
                       "a40c677aba50ef178397bd9f4384746b5d3c743a6757b8cf629cc7feba371844", 7),
    "savanna/streets": ("f92c578a03e481476bd3cda74cee23b1f383e683beb72da4f026444db4695d28",
                        "ffbb7cdc28d7195324492c3ffefcde9f455c5c0dde6095973689b23bdc5fff79", 2),
    "snowy/houses": ("fc194a5923047b239df1bd89d35c49ec522a603955ac5e48c8a8e6e3502b78dd",
                     "8a1b100af5da8efc25a390517eaa7f44fadab6031f286eb59457aeb18265a1a4", 7),
    "taiga/houses": ("adc7288a24b27c2a9d5eeda56bde86f9e494fc451092b81c99d5a05afbb20a62",
                     "5bf6f633cc748eeaf4c1e88bc8c3ecab54353fe5b84292472c8d72c804705e39", 7),
}
# Pixelmon's own remaining desert centre proves the hook values below are the ones it ships.
PIXELMON_REFERENCE_CENTRE = ("desert_meeting_point_3.nbt",
                             "8dc450faa3e01316ae7b7f93ef35e7501a507ee1e50a3f36bae818985e0dbb5e")
PIXELMON_DESERT_POOL = "data/pixelmon/worldgen/template_pool/village/desert.json"
HOOKS = {
    "pokecenter": {"name": "pixelmon:pokecenter", "target": "pixelmon:pokecenter",
                   "pool": "pixelmon:village/desert", "final_state": "minecraft:air", "joint": "rollable"},
    "mart": {"name": "pixelmon:mart", "target": "pixelmon:mart",
             "pool": "pixelmon:village/desert", "final_state": "minecraft:air", "joint": "rollable"},
}
STREET = {"name": "minecraft:street", "target": "minecraft:street", "pool": "minecraft:village/desert/streets"}
# Society centre -> pinned sha256, size, hooks (position, facing, kind), streets moved (from, to).
# Centre 1 keeps all three streets and the house lot; the hooks flank the lot's free western end.
# Centre 2 uses Pixelmon's own arrangement: the east street becomes the Pokemon Center side and the
# west street moves south to leave room for the PokeMart.
CENTRES = {
    "desert_meeting_point_1.nbt": {
        "sha256": "fbdf5e3e0f0483b08551173a1ac7935c8ed817eb6835de6b19a3a51ec95fded9",
        "size": (17, 6, 9),
        "hooks": [((0, 1, 0), "north_up", "pokecenter"), ((1, 1, 0), "north_up", "pokecenter"),
                  ((2, 1, 0), "north_up", "pokecenter"), ((0, 1, 8), "south_up", "mart"),
                  ((1, 1, 8), "south_up", "mart"), ((2, 1, 8), "south_up", "mart")],
        "replaced_streets": [], "moved_streets": [],
    },
    "desert_meeting_point_2.nbt": {
        "sha256": "ec02c7fe9fca12aca2a42d1870679be9ed177582312ac4227ff1d8510689f26f",
        "size": (12, 6, 12),
        "hooks": [((11, 1, 5), "east_up", "pokecenter"), ((11, 1, 6), "east_up", "pokecenter"),
                  ((11, 1, 7), "east_up", "pokecenter"), ((0, 1, 1), "west_up", "mart"),
                  ((0, 1, 2), "west_up", "mart"), ((0, 1, 3), "west_up", "mart")],
        "replaced_streets": [(11, 1, 6)], "moved_streets": [((0, 1, 5), (0, 1, 10))],
    },
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _pinned(data, expected, label):
    if not isinstance(data, bytes) or sha256(data) != expected:
        raise ValueError("Pinned village input required: " + label)
    return data


def _entry(archive, name):
    try:
        return archive.read(name)
    except KeyError as failure:
        raise ValueError("Pinned village input required: Pixelmon " + name) from failure


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def pool_modifier(pool, society, pixelmon):
    """Lithostitched modifier adding the elements only Pixelmon's version of `pool` has."""
    society_sha, pixelmon_sha, expected = POOLS[pool]
    theirs = json.loads(_pinned(society, society_sha, "Society " + pool))
    ours = json.loads(_pinned(pixelmon, pixelmon_sha, "Pixelmon " + pool))
    present = {entry["element"].get("location") for entry in theirs["elements"]}
    added = [{"element": entry["element"], "weight": entry["weight"]} for entry in ours["elements"]
             if str(entry["element"].get("location", "")).startswith("pixelmon:")]
    locations = [entry["element"]["location"] for entry in added]
    if (len(added) != expected or len(set(locations)) != expected or present & set(locations)
            or any(not isinstance(entry["weight"], int) or not 1 <= entry["weight"] <= 150 for entry in added)):
        raise ValueError("Unexpected Pixelmon village pool content: " + pool)
    modifier = {"type": "lithostitched:add_template_pool_elements",
                "template_pools": "minecraft:village/" + pool, "elements": added}
    return _json_bytes(modifier), locations


def _position(block):
    return tuple(item.value for item in block["pos"].value)


def _jigsaw_state(root, facing):
    """Index of the jigsaw palette entry with this orientation, appended when Society's file lacks it."""
    palette = root["palette"].value
    prototype = None
    for index, entry in enumerate(palette):
        if entry.text("Name") == "minecraft:jigsaw":
            prototype = entry
            if entry["Properties"].text("orientation") == facing:
                return index
    if prototype is None:
        raise ValueError("Town centre without jigsaw blocks")
    entry = copy.deepcopy(prototype)
    entry["Properties"].value["orientation"] = nbt_codec.string(facing)
    palette.append(entry)
    return len(palette) - 1


def _is(root, block, name):
    return root["palette"].value[block.number("state")].text("Name") == name


def _street(root, block, facing):
    entry = root["palette"].value[block.number("state")]
    data = block.get("nbt")
    return (entry.text("Name") == "minecraft:jigsaw" and entry["Properties"].text("orientation") == facing
            and data is not None and all(data.text(key) == value for key, value in STREET.items()))


def merge_centre(name, society):
    """Society's desert town centre with Pixelmon's Pokemon Center and PokeMart hooks added."""
    plan = CENTRES[name]
    root = nbt_codec.load_gzip(_pinned(society, plan["sha256"], "Society " + name))
    if tuple(item.value for item in root["size"].value) != plan["size"]:
        raise ValueError("Unexpected town centre size: " + name)
    blocks = root["blocks"].value
    by_position = {}
    for block in blocks:
        if _position(block) in by_position:
            raise ValueError("Duplicate town centre block position")
        by_position[_position(block)] = block
    facings = {position: facing for position, facing, _ in plan["hooks"]}
    template = None  # any existing jigsaw supplies the block-entity layout Society saved
    for block in blocks:
        if _is(root, block, "minecraft:jigsaw"):
            template = block["nbt"]
            break
    for old, new in plan["moved_streets"]:
        source, target = by_position.get(old), by_position.get(new)
        if source is None or target is None or not _is(root, target, "minecraft:air"):
            raise ValueError("Unexpected street layout: " + name)
        facing = root["palette"].value[source.number("state")]["Properties"].text("orientation")
        if not _street(root, source, facing):
            raise ValueError("Unexpected street layout: " + name)
        target.value = {"nbt": source["nbt"], "pos": target["pos"], "state": source["state"]}
        # An unset position is what the old street's structure_void final state left behind.
        del blocks[next(index for index, block in enumerate(blocks) if block is source)]
        del by_position[old]
    for position, facing, kind in plan["hooks"]:
        block = by_position.get(position)
        replaced = position in plan["replaced_streets"]
        if block is None or not (_street(root, block, facing) if replaced else _is(root, block, "minecraft:air")):
            raise ValueError("Unexpected block at Pixelmon hook position: " + name)
        data = copy.deepcopy(template)
        for key, value in HOOKS[kind].items():
            data.value[key] = nbt_codec.string(value)
        block.value = {"nbt": data, "pos": block["pos"], "state": nbt_codec.integer(_jigsaw_state(root, facing))}
    if any(position not in facings for position in plan["replaced_streets"]):
        raise ValueError("Replaced street without a hook")
    return nbt_codec.dump_gzip(root)


def _verify_pixelmon_hooks(archive):
    """The shipped Pixelmon centre and pool must define exactly the hooks this module adds."""
    name, expected = PIXELMON_REFERENCE_CENTRE
    root = nbt_codec.load_gzip(_pinned(_entry(archive, CENTRE_FOLDER + name), expected, "Pixelmon " + name))
    seen = set()
    for block in root["blocks"].value:
        data = block.get("nbt")
        if data is not None and _is(root, block, "minecraft:jigsaw"):
            for kind, values in HOOKS.items():
                if all(data.text(key) == value for key, value in values.items()):
                    seen.add(kind)
    pool = json.loads(_entry(archive, PIXELMON_DESERT_POOL))
    locations = sorted(entry["element"].get("location") for entry in pool["elements"])
    if seen != set(HOOKS) or locations != ["pixelmon:village/desert/desert_mart", "pixelmon:village/desert/desert_pokecenter"]:
        raise ValueError("Pixelmon desert village hooks differ from the pinned definition")


def plan(pixelmon_jar, read_society):
    """Return ({profile path: bytes}, receipt). `read_society(path)` yields Society's original bytes or None."""
    outputs, modifiers, centres = {}, [], []
    with zipfile.ZipFile(pixelmon_jar) as archive:
        _verify_pixelmon_hooks(archive)
        overridden = sorted(
            name[len(POOL_FOLDER):-len(".json")] for name in archive.namelist()
            if name.startswith(POOL_FOLDER) and name.endswith(".json") and read_society("kubejs/" + name) is not None)
        if overridden != sorted(POOLS):
            raise ValueError("Unexpected set of village pools replaced by both projects")
        for pool in sorted(POOLS):
            society = read_society("kubejs/" + POOL_FOLDER + pool + ".json")
            data, locations = pool_modifier(pool, society, _entry(archive, POOL_FOLDER + pool + ".json"))
            path = MODIFIER_FOLDER + pool.replace("/", "_") + ".json"
            outputs[path] = data
            modifiers.append({"path": path, "sha256": sha256(data), "template_pool": "minecraft:village/" + pool,
                              "added_elements": locations})
        shared = sorted(name[len(CENTRE_FOLDER):] for name in archive.namelist()
                        if name.startswith(CENTRE_FOLDER) and name.endswith(".nbt")
                        and read_society("kubejs/" + name) is not None)
        if shared != sorted(CENTRES):
            raise ValueError("Unexpected set of desert town centres replaced by both projects")
    for name in sorted(CENTRES):
        path = "kubejs/" + CENTRE_FOLDER + name
        data = merge_centre(name, read_society(path))
        outputs[path] = data
        centres.append({"path": path, "original_sha256": CENTRES[name]["sha256"], "sha256": sha256(data),
                        "pixelmon_hooks": len(CENTRES[name]["hooks"]),
                        "replaced_streets": len(CENTRES[name]["replaced_streets"]),
                        "moved_streets": len(CENTRES[name]["moved_streets"])})
    script = SPAWN_SOURCE.read_bytes()
    outputs[SPAWN_PATH] = script
    replaced = {entry["path"] for entry in centres}
    for path in outputs:
        if path not in replaced and read_society(path) is not None:
            raise ValueError("Village compatibility path already used: " + path)
    receipt = {"pool_modifiers": modifiers, "town_centres": centres,
               "spawn_script": {"path": SPAWN_PATH, "sha256": sha256(script),
                                "source": "compat/village/psa_village_spawn.js"}}
    return outputs, receipt


def apply_overrides(files, pixelmon_jar):
    """Apply to a {profile path: bytes} mapping (client export). The mapping changes only on success."""
    outputs, receipt = plan(pixelmon_jar, files.get)
    files.update(outputs)
    return receipt


def _regular(root, path):
    """Location below root that is reached through real folders only: no symbolic link, no file in place of a folder."""
    target, parts = Path(root), Path(path).parts
    for index, component in enumerate(parts):
        target = target / component
        if target.is_symlink() or (index + 1 < len(parts) and target.exists() and not target.is_dir()):
            raise ValueError("Regular staged village path required")
    return target


def apply_directory(root, pixelmon_jar):
    """Apply to an extracted profile whose KubeJS files are Society's originals."""
    def read(path):
        target = _regular(root, path)
        if target.exists() and not target.is_file():
            raise ValueError("Regular staged village path required")
        return target.read_bytes() if target.is_file() else None
    outputs, receipt = plan(pixelmon_jar, read)
    # Every location is checked before the first write.
    targets = [(_regular(root, path), data) for path, data in outputs.items()]
    if any(target.exists() and not target.is_file() for target, _ in targets):
        raise ValueError("Regular staged village path required")
    for target, data in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return receipt


def verify_staged(root, declaration):
    """A profile either carries exactly the declared outputs or none of them."""
    present = [path for path in (SPAWN_PATH, MODIFIER_FOLDER.rstrip("/")) if _regular(root, path).exists()]
    if declaration is None:
        if present:
            raise ValueError("Undeclared village compatibility content")
        return None
    entries = declaration["pool_modifiers"] + declaration["town_centres"] + [declaration["spawn_script"]]
    for entry in entries:
        target = _regular(root, entry["path"])
        if not target.is_file() or sha256(target.read_bytes()) != entry["sha256"]:
            raise ValueError("Declared village compatibility content differs: " + entry["path"])
    folder = _regular(root, MODIFIER_FOLDER.rstrip("/"))
    if sorted(item.name for item in folder.iterdir()) != sorted(Path(e["path"]).name for e in declaration["pool_modifiers"]):
        raise ValueError("Unexpected village pool modifier files")
    return declaration


def record(pixelmon_jar, server_pack):
    """Hashes of every output for the pinned inputs, as kept in compat/village-build.json."""
    with zipfile.ZipFile(server_pack) as archive:
        names = set(archive.namelist())
        outputs, receipt = plan(pixelmon_jar, lambda path: archive.read(path) if path in names else None)
    return {"scope": "Pixelmon village content added beside Society's village overrides; derived data only, no mod JAR changes",
            "inputs": {"pixelmon_jar_sha256": sha256(Path(pixelmon_jar).read_bytes()),
                       "society_server_pack_sha1": hashlib.sha1(Path(server_pack).read_bytes()).hexdigest()},
            "output_sha256": {path: sha256(data) for path, data in sorted(outputs.items())},
            "receipt": receipt}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixelmon", type=Path, required=True)
    parser.add_argument("--server-pack", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(record(arguments.pixelmon, arguments.server_pack), indent=2))
