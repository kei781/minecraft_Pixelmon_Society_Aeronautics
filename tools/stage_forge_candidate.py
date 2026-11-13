#!/usr/bin/env python3
"""Stage the separate, experimental 1.20.1 candidate in a fresh directory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile
import forge_datapack_compat
import forge_loot_compat
import forge_overlay_compat
import forge_village_compat

SERVER_SHA1 = "fe4ed6b00bfec53f917c64fc3ddd5ca91c0d0495"
PIXELMON_SHA256 = "8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a"
PORT_SHA256 = "28e1958563c4c313bbbf42448b15594c2cc8a3ca7a7f8d1ac5b7f47426f36c1c"
FOLDERS = {"mods", "config", "defaultconfigs", "kubejs", "patchouli_books"}
LOCK = Path(__file__).resolve().parents[1] / "forge-candidate-lock.json"


def digest(path, algorithm="sha256"):
    value = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(data)
    return value.hexdigest()


def verify_published(path, role):
    item = json.loads(LOCK.read_text())["artifacts"][role]
    file = item.get("file", item)
    hashes = file.get("hashes", file.get("upstream_hashes"))
    lengths = {"sha1": 40, "sha256": 64, "sha512": 128}
    if (not isinstance(hashes, dict) or not set(hashes) & {"sha1", "sha512"}
            or any(algorithm not in lengths or not isinstance(expected, str)
                   or not re.fullmatch("[0-9a-f]{%d}" % lengths[algorithm], expected)
                   for algorithm, expected in hashes.items())):
        raise ValueError("Published hashes must include a valid SHA1 or SHA512")
    if Path(path).stat().st_size != file["size"]:
        raise ValueError("Published size/hash mismatch: " + str(path))
    for algorithm, expected in hashes.items():
        if digest(path, algorithm) != expected:
            raise ValueError("Published hash mismatch: " + str(path))
    return {"source_page": item["source_page"], "download_url": file.get("url"),
            "size": file["size"], "upstream_hashes": hashes, "verified": True}


def selected_entries(archive):
    entries, seen = [], set()
    for item in archive.infolist():
        path = PurePosixPath(item.filename)
        if (path.is_absolute() or ".." in path.parts or "\\" in item.filename
                or stat.S_ISLNK(item.external_attr >> 16)):
            raise ValueError("Unsafe server archive entry")
        if item.is_dir() or not path.parts or path.parts[0] not in FOLDERS:
            continue
        key = path.as_posix().casefold()
        if key in seen:
            raise ValueError("Duplicate server archive entry")
        seen.add(key)
        entries.append(item)
    if sum(i.filename.startswith("mods/") and i.filename.endswith(".jar") for i in entries) != 311:
        raise ValueError("Unexpected Society server mod inventory")
    return entries


def stage(server_pack, pixelmon, port, destination, mode="smoke", datapack_fix=None, coexistence=None):
    """`coexistence` is the pinned vanilla 1.20.1 data JAR; giving it applies the village, loot and overlay repairs."""
    destination = Path(destination)
    if mode not in {"smoke", "player"}:
        raise ValueError("Unknown server profile mode")
    if destination.exists() or destination.is_symlink():
        raise ValueError("A fresh destination is required")
    if datapack_fix is not None:
        forge_datapack_compat.verify_module_file(datapack_fix)
    for path, algorithm, expected in [(server_pack, "sha1", SERVER_SHA1),
            (pixelmon, "sha256", PIXELMON_SHA256), (port, "sha256", PORT_SHA256)]:
        if digest(path, algorithm) != expected:
            raise ValueError("Input hash mismatch: " + str(path))
    official_inputs = {"society_server": verify_published(server_pack, "society_server"),
                       "pixelmon": verify_published(pixelmon, "pixelmon")}
    with zipfile.ZipFile(pixelmon) as pokemon:
        replacements = sorted(n for n in pokemon.namelist()
                              if n.startswith("data/pixelmon/spawn_replacement/") and n.endswith(".json"))
        if len(replacements) != 68 or len(set(replacements)) != 68:
            raise ValueError("Unexpected Pixelmon replacement inventory")
        for name in replacements:
            if len(PurePosixPath(name).parts) != 4:
                raise ValueError("Unexpected Pixelmon replacement path")
    with zipfile.ZipFile(server_pack) as archive:
        entries = selected_entries(archive)
        try:
            forge_datapack_compat.normalize_resource(archive.read(forge_datapack_compat.RESOURCE))
        except KeyError as failure:
            raise ValueError("Pinned original global loot modifier list missing") from failure
        if coexistence is not None:
            # Validate every pinned coexistence input before anything is written.
            names = {item.filename for item in entries}
            original = lambda path: archive.read(path) if path in names else None
            forge_village_compat.plan(pixelmon, original)
            forge_loot_compat.plan(pixelmon, coexistence, original)
            forge_overlay_compat.plan(pixelmon, port, original)
        destination.mkdir(parents=True)
        (destination / ".psa-owned-smoke-test").write_text("Experimental Forge 1.20.1 candidate; not final validation.\n")
        for item in entries:
            target = destination / item.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    for source, name in [(pixelmon, "Pixelmon-1.20.1-9.2.3-universal.jar"),
                         (port, "psa-aeronautics-experimental-forge-1.20.1.jar")]:
        with Path(source).open("rb") as stream, (destination / "mods" / name).open("xb") as output:
            shutil.copyfileobj(stream, output)
    loot_list = forge_datapack_compat.apply_directory(destination)
    village = loot = overlay = None
    if coexistence is not None:
        village = forge_village_compat.apply_directory(destination, pixelmon)
        loot = forge_loot_compat.apply_directory(destination, pixelmon, coexistence)
        overlay = forge_overlay_compat.apply_directory(destination, pixelmon, port)
    datapack_module = forge_datapack_compat.install_module(destination, datapack_fix) if datapack_fix is not None else None
    neutral = {"enabled": False, "detection_logic": "simple", "replaced_mobs": [],
               "replacement_logic": "simple", "specs": []}
    for name in replacements:
        target = destination / "kubejs" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(neutral, indent=2) + "\n")
    config = destination / "config/pixelmon"
    config.mkdir(parents=True, exist_ok=True)
    if (config / "config.yml").exists():
        raise ValueError("Unexpected existing Pixelmon configuration")
    (config / "config.yml").write_text("allow-vanilla-mobs: true\n")
    bind, world = ("127.0.0.1", "world-psa-new") if mode == "smoke" else ("0.0.0.0", "world")
    (destination / "server.properties").write_text(
        "server-ip=" + bind + "\nserver-port=25573\nonline-mode=true\n"
        "enable-query=false\nenable-rcon=false\nallow-flight=true\nmax-players=6\nview-distance=4\nsimulation-distance=4\n"
        "level-name=" + world + "\nspawn-protection=0\nmotd=PSA experimental full Forge candidate\n")
    (destination / "user_jvm_args.txt").write_text("-Xms1G\n-Xmx6G\n-XX:+UseG1GC\n")
    # Acceptance is explicit at runtime via server-control.sh start --accept-eula.
    (destination / "eula.txt").write_text("eula=false\n")
    shutil.copyfile(Path(__file__).resolve().parents[1] / "server-control.sh", destination / "server-control.sh")
    (destination / "server-control.sh").chmod(0o755)
    mod_hashes = [digest(p) + "  mods/" + p.name for p in sorted((destination / "mods").glob("*.jar"))]
    (destination / ".psa-mods.sha256").write_text("\n".join(mod_hashes) + "\n")
    receipt = {"minecraft": "1.20.1", "forge": "47.4.20", "society": "4.1.5A",
               "pixelmon": "9.2.3 beta", "aeronautics": "unofficial Forge port 1.3.0",
               "server_pack_sha1": SERVER_SHA1, "pixelmon_sha256": PIXELMON_SHA256,
               "port_sha256": PORT_SHA256, "top_level_mod_jars": 313 + int(datapack_module is not None),
               "official_inputs": official_inputs, "lock_sha256": digest(LOCK),
               "neutral_replacement_files": 68, "final_gameplay_validated": False,
               "global_loot_modifier_compatibility": loot_list,
               "datapack_sync_compatibility": datapack_module,
               "village_compatibility": village, "loot_compatibility": loot,
               "overlay_compatibility": overlay}
    receipt["mode"] = mode
    (destination / ".psa-forge-candidate.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-pack", type=Path, required=True)
    parser.add_argument("--pixelmon", type=Path, required=True)
    parser.add_argument("--port", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--mode", choices=["smoke", "player"], default="smoke")
    parser.add_argument("--datapack-fix", type=Path, help="Pinned authored dedicated-server recipient compatibility JAR")
    parser.add_argument("--coexistence-fix", type=Path, metavar="VANILLA_DATA_JAR",
                        help="Apply the village, loot and overlay repairs that let the three projects coexist; "
                             "takes the pinned vanilla data JAR of the Forge install "
                             "(libraries/net/minecraft/server/1.20.1-20230612.114412/server-1.20.1-20230612.114412-extra.jar)")
    args = parser.parse_args()
    print(json.dumps(stage(args.server_pack, args.pixelmon, args.port, args.destination, args.mode,
                           args.datapack_fix, args.coexistence_fix), indent=2))
