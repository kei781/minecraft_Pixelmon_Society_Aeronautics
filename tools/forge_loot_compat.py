"""Keep Pixelmon's own chest loot next to Society's and vanilla's.

Pixelmon ships whole replacements of 40 vanilla chest loot tables.

* Three bastion tables are also replaced by Society's KubeJS data, which is
  applied last, so Pixelmon's added pools (Poke Balls, held items, gems) never
  drop there. The merged table is Society's table, unchanged, followed by the
  pools of Pixelmon's copy that contain only Pixelmon items. Vanilla pools that
  Society edited are not taken from Pixelmon's copy.
* The other 37 tables are vanilla's in the official Society pack. Pixelmon's
  older copies replace them, so vanilla 1.20.1 content (smithing templates,
  goat horns, saddles, ...) never drops. The merged table is the vanilla table,
  unchanged, followed by every pool of Pixelmon's copy that yields Pixelmon
  content. In such a pool each entry that is not Pixelmon's becomes an empty
  entry of the same weight: Pixelmon content keeps the drop chance it has in
  Pixelmon's copy and vanilla items come from the vanilla pools only.

Every input is pinned; an unexpected table on any side stops staging.
"""
import copy
import hashlib
import json
from pathlib import Path
import zipfile

FOLDER = "data/minecraft/loot_tables/"
# The only accepted vanilla 1.20.1 data JAR (server-1.20.1-20230612.114412-extra.jar of the Forge install).
VANILLA_DATA_SHA256 = "16c690f52a92ef272f3e3a5a841cbb24dadff19da5a895885b9520c5a108be38"
PIXELMON_NAMESPACES = ("pixelmon", "tcg")  # both are registered by the Pixelmon JAR
# Tables Society also replaces: table -> (Society KubeJS sha256, Pixelmon JAR entry sha256, Pixelmon-only pools).
TABLES = {
    "chests/bastion_hoglin_stable": ("4954ed7d29c2b616f3c76d2466ffb9989c90d6971435d915cbe8fcb6e84e5920",
                                     "102ca1d348b85b92f0f2d7775786b71bdf0b5bd33281de1797b2be191fdb466d", 4),
    "chests/bastion_other": ("3c99a4c44c515c271bef6a4b8d711576d1a78eefa12ec96c6827d36633a1ffe1",
                             "dcf088a234e6f083a76d4eb9074079cb9b97d3f3f3b1ed75d3d1f6353f00abde", 3),
    "chests/bastion_treasure": ("aa914e14f62ea6b48f0e26acffa471618ac43f71680e6b9f86c34b6c98507d9c",
                                "8d0ae36f83b468f340b45cca9da9bd8f416d28010fd59c9dd258ee8ddd269555", 4),
}
# Tables only Pixelmon replaces: table -> (vanilla data JAR entry sha256, Pixelmon JAR entry sha256, appended pools).
VANILLA_TABLES = {
    "chests/abandoned_mineshaft": ("ac8e330ebb6592f38fc8bd1a5cea144714b600814c50449407128a530a596d1b",
                                   "c2f418fec6eb15cfdd951a6f3c780ba905f138f72719e2f1c8d98f91942e2b2d", 7),
    "chests/bastion_bridge": ("2c49d500c90944656d66ca36309fd8f28d070962241d41fdca5a2c6c95b25ea9",
                              "fe616f4cf898cd2394717ed78f38b0e5bebe7c6b9a2d556891cb8a7d85f21f82", 3),
    "chests/buried_treasure": ("3e77c8b99c8dc1de679ee807a274624918b1b3e2764c773d1910cb792716fe7e",
                               "4ae5315cabe0fa6408c2c142706a2294c15bb2acec2c825b67fea22a494f9e35", 7),
    "chests/desert_pyramid": ("27879bd476495ffe6ce4d76443e914be3c252fc2b9c618982d3b5be2dc2d6301",
                              "3b2551e235b951ba47d1e979fffeceadc1ad0ebcc1f1a2b8f79269e5299ca01e", 4),
    "chests/end_city_treasure": ("21d494c874e1f883c3411562840ac432872748ce894643033c476bf62fa8ce9d",
                                 "d7c8d8154148d1924819e480caaab400da9cd4ab2f302f322ea3fac90624f1a4", 4),
    "chests/igloo_chest": ("6313c3136e575007511e2a573f63cd4d17a6d78fb4ab2b21512cb7f098d6a3b9",
                           "8f6af54d68c7f9b4f8946b670a8dfc2f30b020206de6af62d168e344a9ad0d79", 3),
    "chests/jungle_temple": ("16bf3ee72df14d695fe762f693f9e4d3da2ad3dfa692a0f3c8eb1ba7d5211d50",
                             "6f6b41f70df3ecd90e66f7a1f8fa5cfd409f494d22e58b6222bf69b66ceb07dd", 4),
    "chests/nether_bridge": ("56fceac267476866f2381335b4ac1b3eeab33993610d854752cd2f011c2062e6",
                             "1d6b67afcedc9946c293ad0b44d57c456abac5a542968d4f75b8eedd25f5b116", 4),
    "chests/pillager_outpost": ("dff1955174fab7f5d0a12970d02650c8cff8a2d99ff4bbf77a734b7a45f64b25",
                                "2831a1e4b0ada6f9657272146108db4c96f0f711f26e37cb678bfcd2da9d43ec", 4),
    "chests/ruined_portal": ("3e5e2a0583273236f3f632e8588199cd990602f2b7a1c6336aaa12954b18585f",
                             "b10e23d3aeb38fce51d0c712cf320b4e2912bb2439f21f90f773ebb25d2de197", 4),
    "chests/shipwreck_map": ("69546cb00de9385bd89b517152130478b0be4d16ee7a52777288d050863cd8b6",
                             "769f3db25ac5d3cbe4ac56ebd1c5d24f41e49db77c62f64c7e0ef23a5b18fb66", 3),
    "chests/shipwreck_supply": ("58a16ea508faac3e6dc77ee1b82f30bc1e4ccbd79a0db6c372fea6eadf482f25",
                                "1679f18389357bc60dc7fe2cfbd36beda958be0b8ec1f50030dbe854074c5e1c", 3),
    "chests/shipwreck_treasure": ("1861a8f752c80834afa9067a26530175e4cab0df83a89c4107fb47bb30f4a769",
                                  "f02ad8054798a80671eea7007d5a67b0d617467b69ea360db7dd48894e5f3624", 4),
    "chests/simple_dungeon": ("32f14004ab4d7dea19641411d980b98ad19e1658c8674c272eb13dfac39d7626",
                              "822fe7d1b26167fc802db4ea0ef793c4670fd56140a75f91b5c3a7db46a91998", 4),
    "chests/spawn_bonus_chest": ("4c22c342d0675e537b26499bd3fb0887e944b1be912bb3e7b882f75030c31d57",
                                 "d007d6615b3c29b03d1002f59f1d50443fd82c3cde23a19d58c0e04687a9f0b8", 1),
    "chests/stronghold_corridor": ("6937f3ca3d91052c3e8fd2a516725aecfc735d990cfdce5677d13dfad030b8a9",
                                   "1869d37049f8ed0e35433c035513c9eaec8442155c84ab4e0a3ac202a13f9f24", 4),
    "chests/stronghold_crossing": ("bce4d5e5399c1141b7c7d9f1cbfeabbfabe99b4e293a4595485af73bc08dfeaf",
                                   "1869d37049f8ed0e35433c035513c9eaec8442155c84ab4e0a3ac202a13f9f24", 4),
    "chests/stronghold_library": ("9fde26670b980b52a15969fee9cba958c8f12ea61e75974bd3cd8ee15d0d9722",
                                  "ba9def35229a22c80cf76d361d55fed2779f018d679be872be5ff93f422be477", 4),
    "chests/underwater_ruin_big": ("819d36fc83b1794f09b5d0e79913bcefb4195f3638fbb8336448889ac9108b4e",
                                   "0412d3bb464962eae749516496914b105844dd81df13e93344dd3fdbd304ac08", 2),
    "chests/underwater_ruin_small": ("40a121404f2b45897b6ca0a8f1704ca70c4ece690e6e731a6b9beaafdefcc2c9",
                                     "5c55fb3ad055483b59012602810e7eab15e66399a513a5f6cfa22366731059dc", 1),
    "chests/village/village_armorer": ("65b78046a475686f9580f465e8ab5b4fcb44aeb811bbe792aaae2938fa1518b4",
                                       "fc3b5722b0d68ad1ea5164104ceaf364432a4f371751bf1b1d46c0c9848a3090", 3),
    "chests/village/village_butcher": ("63024111b14df7597f3f53125b1c56dfea827d9875c6d0a59bd66d46f0e04b42",
                                       "39b2a65dd057fa1e25cd33246be443048e071d2b805347ed38e853f142fc1c04", 3),
    "chests/village/village_cartographer": ("5cd78c92fc4cc9b17e55802217a5d2e4ff2c3e3c6fc07c10cddcb847ae9ad17a",
                                            "c5fddb0cbeb0b7e53645c16523953ada3daaee47a8edebe41ee26366c3690be6", 4),
    "chests/village/village_desert_house": ("59c7997207fdcf506c5b0bdc93f2c1e7f179d39e11de247360199ee15da4e623",
                                            "c9dcc5ee1006aa76514abf54d0ee2c0f8ae2fbe33aa65f227e1674df705e48e3", 3),
    "chests/village/village_fisher": ("e71e42ba4cd669b4caa9da2096c6594581fb9e35e356d1fa5580caebfc49b8b2",
                                      "b0275437482f6298d320e11d897bdeb72bf5b84173cfb40b354379ad33061382", 2),
    "chests/village/village_fletcher": ("2b17391015f6d657bc5200b7e00f80a3eb387654d235d63a430184fe63c0cb6a",
                                        "8a857b5372eba66885d9520ee820f2182fe6e08d1651170359bc4ad764d4b2b5", 3),
    "chests/village/village_mason": ("0bb2b3a23b438bc1e4d9039f5e972c71f5a573bb99c4145d6664b4bbb4ed98fa",
                                     "018a2c4b71ac445246d61bd47a071f28a17d28f1570ca4e452fecc711f12d290", 4),
    "chests/village/village_plains_house": ("0c22ab83139f89720a92381f486323639f7d0545508cf3ee997e88172c97623e",
                                            "e7b524d9555e668ece61ebaa7314c9aaa79865770edc1731eb3b5f2e4420655b", 3),
    "chests/village/village_savanna_house": ("5a8927a81811311efb336ec8de74d376cc0eca3cd369eb14e2a343e600ebe5e5",
                                             "4b7299ba397399dce654d438392b600d2e9d27cda957ff72579de22ae9ec8350", 3),
    "chests/village/village_shepherd": ("4f972dbba3ad6717c129bec51da108e0428d6f014eb84940ebdfeac38d02073c",
                                        "32e552195e6e46d0cbb8066a7d77df1dccf6ebe879854a86e85397e64596f169", 4),
    "chests/village/village_snowy_house": ("7876aef54db402c56e05baa9f239b42f670ab84782d8329fbe2df2537ea764d9",
                                           "679b3fe28c32a258a6bf48fe3e426277e9214d7f2917489949e603068487464c", 3),
    "chests/village/village_taiga_house": ("49f3d7c1d463e698e72e76894b22645fc9d6046a0f54065770e59fe51e01dbd1",
                                           "53519b251f2208b0eb9a0fdf47645d697bd75228d54648904d272823c0fb305b", 3),
    "chests/village/village_tannery": ("4374067cf7ad5b290449b4408600bfc6a5fcc834614819f019f6df2590478c3e",
                                       "55cb225bff37480612c272adfa8d6013bda0a0741b7cedf3223b953e8ddc1e10", 2),
    "chests/village/village_temple": ("aa5381969739b26c3f10651af03f78696d30470749992a913196f425b43664c5",
                                      "774cfb73b89e222a8129dc9efa06d2b8a28701821190de4ed5b89039d1184d2a", 3),
    "chests/village/village_toolsmith": ("38aa8cd5309e671a069eb5a8d293121c5b76a99b3518e4e59a92bd34365ea3f1",
                                         "1bd58447b4a126b904d1426cb82a45825680d266196b6e76f3ed1c3e8c1b0aea", 4),
    "chests/village/village_weaponsmith": ("79d2965158fbd975b50926378ed3f886fbac08a15f6492a6ba5a3f2c4d0a821f",
                                           "d153a30f104c0090dd0023e6b8deda34b2eb3143ce88eb5f67b28208fa3aca3a", 3),
    "chests/woodland_mansion": ("f18f36c6de72f4a99012553720105862b6e043801b818be404f87764a0e4c03d",
                                "72003f0eadbfa34d2cce232a076114eca0674677a8a7fb4daeaed40764f78142", 5),
}
# Pixelmon files outside chests/: vanilla 1.20.1 has no table of that id, so they replace nothing and are left alone.
UNUSED = ("bastion_hoglin_stable", "bastion_other", "buried_treasure", "ruined_portal", "shipwreck_map")
COMPOSITES = ("alternatives", "group", "sequence")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _digest(path, algorithm="sha256"):
    digest = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _pinned(data, expected, label):
    if not isinstance(data, bytes) or sha256(data) != expected:
        raise ValueError("Pinned loot input required: " + label)
    return data


def _path(table):
    return "kubejs/" + FOLDER + table + ".json"


def _table_bytes(table):
    return (json.dumps(table, indent=2) + "\n").encode()


def _kind(entry):
    name = str(entry.get("type", ""))
    return name[len("minecraft:"):] if name.startswith("minecraft:") else name


def _items(entry, found):
    """Collect item ids of a loot entry tree; False when it can yield something that is not a plain item."""
    kind = _kind(entry)
    if kind == "item":
        found.append(str(entry.get("name", "")))
        return True
    if kind == "empty":
        return True
    if kind in COMPOSITES:
        return all(_items(child, found) for child in entry.get("children", []))
    return False


def pixelmon_only(pool):
    found = []
    plain = all(_items(entry, found) for entry in pool.get("entries", []))
    return plain and bool(found) and all(name.startswith("pixelmon:") for name in found)


def merge_table(table, society, pixelmon):
    society_sha, pixelmon_sha, expected = TABLES[table]
    theirs = json.loads(_pinned(society, society_sha, "Society " + table))
    ours = json.loads(_pinned(pixelmon, pixelmon_sha, "Pixelmon " + table))
    extra = [copy.deepcopy(pool) for pool in ours.get("pools", []) if pixelmon_only(pool)]
    if len(extra) != expected or any(pixelmon_only(pool) for pool in theirs.get("pools", [])):
        raise ValueError("Unexpected Pixelmon loot pools: " + table)
    merged = dict(theirs)
    merged["pools"] = list(theirs.get("pools", [])) + extra
    return _table_bytes(merged), len(theirs.get("pools", []))


def _pixelmon(entry):
    """Whether a leaf entry names an item, a tag or a loot table of Pixelmon."""
    namespace, separator, _ = str(entry.get("name", "")).partition(":")
    return _kind(entry) in ("item", "tag", "loot_table") and bool(separator) and namespace in PIXELMON_NAMESPACES


def _yields_pixelmon(entry):
    if _kind(entry) in COMPOSITES:
        return any(_yields_pixelmon(child) for child in entry.get("children", []))
    return _pixelmon(entry)


def _has_pixelmon(pool):
    return any(_yields_pixelmon(entry) for entry in pool.get("entries", []))


def _blanked(entry):
    """(entry, replaced leaves): the entry tree with every leaf that is not Pixelmon's turned into an empty entry.

    Weight, quality and conditions decide how often the other entries of a pool are picked, so the empty entry
    keeps them. Composite entries carry no weight of their own (each child counts separately) and stay in place.
    """
    kind = _kind(entry)
    if kind in COMPOSITES and isinstance(entry.get("children"), list):
        children = [_blanked(child) for child in entry["children"]]
        changed = copy.deepcopy(entry)
        changed["children"] = [child for child, _ in children]
        return changed, sum(count for _, count in children)
    if kind == "empty" or _pixelmon(entry):
        return copy.deepcopy(entry), 0
    # An expanded tag counts once per tagged item and an unknown entry type is not known to count once.
    if kind not in ("item", "tag", "loot_table", "dynamic") or (kind == "tag" and entry.get("expand")):
        raise ValueError("Unexpected loot entry type: " + str(entry.get("type")))
    blank = {"type": "minecraft:empty"}
    for key in ("weight", "quality", "conditions"):
        if key in entry:
            blank[key] = copy.deepcopy(entry[key])
    return blank, 1


def pixelmon_pool(pool):
    """(pool reduced to Pixelmon's content, replaced leaves), or None for a pool without Pixelmon content."""
    if not _has_pixelmon(pool):
        return None
    entries = [_blanked(entry) for entry in pool["entries"]]
    reduced = copy.deepcopy(pool)
    reduced["entries"] = [entry for entry, _ in entries]
    return reduced, sum(count for _, count in entries)


def extend_table(table, vanilla, pixelmon):
    """Vanilla table plus the Pixelmon content of Pixelmon's copy: (bytes, vanilla pools, replaced leaves)."""
    vanilla_sha, pixelmon_sha, expected = VANILLA_TABLES[table]
    base = json.loads(_pinned(vanilla, vanilla_sha, "vanilla " + table))
    ours = json.loads(_pinned(pixelmon, pixelmon_sha, "Pixelmon " + table))
    added = [reduced for reduced in map(pixelmon_pool, ours.get("pools", [])) if reduced is not None]
    if len(added) != expected or any(_has_pixelmon(pool) for pool in base.get("pools", [])):
        raise ValueError("Unexpected Pixelmon loot pools: " + table)
    merged = dict(base)
    merged["pools"] = list(base.get("pools", [])) + [pool for pool, _ in added]
    return _table_bytes(merged), len(base.get("pools", [])), sum(count for _, count in added)


def plan(pixelmon_jar, vanilla_jar, read_society):
    """Return ({profile path: bytes}, receipt). `read_society(path)` yields Society's original bytes or None."""
    if vanilla_jar is None or _digest(vanilla_jar) != VANILLA_DATA_SHA256:
        raise ValueError("Pinned vanilla 1.20.1 data JAR required")
    outputs, merged, restored = {}, [], []
    with zipfile.ZipFile(pixelmon_jar) as archive, zipfile.ZipFile(vanilla_jar) as vanilla:
        known = sorted(list(TABLES) + list(VANILLA_TABLES) + list(UNUSED))
        present = sorted(name[len(FOLDER):] for name in archive.namelist()
                         if name.startswith(FOLDER) and not name.endswith("/"))
        if present != sorted(table + ".json" for table in known):
            raise ValueError("Unexpected set of vanilla loot tables in Pixelmon")
        official = set(vanilla.namelist())
        if [table for table in known if FOLDER + table + ".json" not in official] != sorted(UNUSED):
            raise ValueError("Unexpected set of Pixelmon loot tables without a vanilla table")
        if [table for table in known if read_society(_path(table)) is not None] != sorted(TABLES):
            raise ValueError("Unexpected set of loot tables replaced by both projects")
        for table in sorted(TABLES):
            data, society_pools = merge_table(table, read_society(_path(table)), archive.read(FOLDER + table + ".json"))
            outputs[_path(table)] = data
            merged.append({"path": _path(table), "table": "minecraft:" + table, "original_sha256": TABLES[table][0],
                           "sha256": sha256(data), "society_pools_kept": society_pools,
                           "pixelmon_pools_added": TABLES[table][2]})
        for table in sorted(VANILLA_TABLES):
            data, vanilla_pools, blanked = extend_table(
                table, vanilla.read(FOLDER + table + ".json"), archive.read(FOLDER + table + ".json"))
            outputs[_path(table)] = data
            restored.append({"path": _path(table), "table": "minecraft:" + table,
                             "vanilla_sha256": VANILLA_TABLES[table][0], "pixelmon_sha256": VANILLA_TABLES[table][1],
                             "sha256": sha256(data), "vanilla_pools_kept": vanilla_pools,
                             "pixelmon_pools_added": VANILLA_TABLES[table][2], "entries_blanked": blanked})
    return outputs, {"loot_tables": merged, "vanilla_loot_tables": restored,
                     "unused_pixelmon_tables": ["minecraft:" + table for table in sorted(UNUSED)]}


def apply_overrides(files, pixelmon_jar, vanilla_jar):
    """Apply to a {profile path: bytes} mapping (client export). The mapping changes only on success."""
    outputs, receipt = plan(pixelmon_jar, vanilla_jar, files.get)
    files.update(outputs)
    return receipt


def _regular(root, path):
    """Location below root that is reached through real folders only: no symbolic link, no file in place of a folder."""
    target, parts = Path(root), Path(path).parts
    for index, component in enumerate(parts):
        target = target / component
        if target.is_symlink() or (index + 1 < len(parts) and target.exists() and not target.is_dir()):
            raise ValueError("Regular staged loot path required")
    return target


def apply_directory(root, pixelmon_jar, vanilla_jar):
    """Apply to an extracted profile whose KubeJS files are Society's originals."""
    def read(path):
        target = _regular(root, path)
        if target.exists() and not target.is_file():
            raise ValueError("Regular staged loot path required")
        return target.read_bytes() if target.is_file() else None
    outputs, receipt = plan(pixelmon_jar, vanilla_jar, read)
    # Every location is checked before the first write.
    targets = [(_regular(root, path), data) for path, data in outputs.items()]
    if any(target.exists() and not target.is_file() for target, _ in targets):
        raise ValueError("Regular staged loot path required")
    for target, data in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return receipt


def verify_staged(root, declaration):
    """A profile carries Society's original bastion tables and no other output, or exactly the declared tables."""
    originals = {_path(table): pins[0] for table, pins in TABLES.items()}
    known = set(originals) | {_path(table) for table in VANILLA_TABLES}
    declared = {}
    if declaration is not None:
        declared = {entry["path"]: entry["sha256"]
                    for entry in declaration["loot_tables"] + declaration.get("vanilla_loot_tables", [])}
    if not set(declared) <= known:
        raise ValueError("Declared loot table unknown to this module")
    for path in sorted(known):
        target = _regular(root, path)
        expected = declared.get(path, originals.get(path))
        if expected is None:
            if target.exists():
                raise ValueError("Undeclared loot table: " + path)
        elif path in declared and not target.is_file():
            raise ValueError("Declared loot table missing: " + path)
        elif target.is_file() and sha256(target.read_bytes()) != expected:
            raise ValueError("Staged loot table differs from its declaration: " + path)
    return declaration


def record(pixelmon_jar, vanilla_jar, server_pack):
    """Hashes of every output for the pinned inputs, as kept in compat/loot-build.json."""
    with zipfile.ZipFile(server_pack) as archive:
        names = set(archive.namelist())
        outputs, receipt = plan(pixelmon_jar, vanilla_jar, lambda path: archive.read(path) if path in names else None)
    return {"scope": "Vanilla, Society and Pixelmon chest loot merged per table; derived data only, no mod JAR changes",
            "inputs": {"pixelmon_jar_sha256": _digest(pixelmon_jar), "vanilla_data_jar_sha256": _digest(vanilla_jar),
                       "society_server_pack_sha1": _digest(server_pack, "sha1")},
            "output_sha256": {path: sha256(data) for path, data in sorted(outputs.items())},
            "receipt": receipt}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixelmon", type=Path, required=True)
    parser.add_argument("--vanilla-data", type=Path, required=True)
    parser.add_argument("--server-pack", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(record(arguments.pixelmon, arguments.vanilla_data, arguments.server_pack), indent=2))
