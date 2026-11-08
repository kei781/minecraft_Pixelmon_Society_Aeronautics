#!/usr/bin/env python3
"""Stage the separate, experimental 1.20.1 candidate in a fresh directory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

SERVER_SHA1 = "fe4ed6b00bfec53f917c64fc3ddd5ca91c0d0495"
PIXELMON_SHA256 = "8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a"
PORT_SHA256 = "5ac3cda9475e3623429daa368d54c751294c0fdd5f05eab97826be601731c367"
FOLDERS = {"mods", "config", "defaultconfigs", "kubejs", "patchouli_books"}


def digest(path, algorithm="sha256"):
    value = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(data)
    return value.hexdigest()


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


def stage(server_pack, pixelmon, port, destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("A fresh destination is required")
    for path, algorithm, expected in [(server_pack, "sha1", SERVER_SHA1),
            (pixelmon, "sha256", PIXELMON_SHA256), (port, "sha256", PORT_SHA256)]:
        if digest(path, algorithm) != expected:
            raise ValueError("Input hash mismatch: " + str(path))
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
    (destination / "server.properties").write_text(
        "server-ip=127.0.0.1\nserver-port=25573\nonline-mode=true\n"
        "enable-query=false\nenable-rcon=false\nmax-players=6\nview-distance=4\nsimulation-distance=4\n"
        "level-name=world-psa-new\nspawn-protection=0\nmotd=PSA experimental full Forge candidate\n")
    (destination / "user_jvm_args.txt").write_text("-Xms1G\n-Xmx6G\n-XX:+UseG1GC\n")
    # The task authorizes this isolated Minecraft server test.
    (destination / "eula.txt").write_text("eula=true\n")
    receipt = {"minecraft": "1.20.1", "forge": "47.4.20", "society": "4.1.5A",
               "pixelmon": "9.2.3 beta", "aeronautics": "unofficial Forge port 1.3.0",
               "server_pack_sha1": SERVER_SHA1, "pixelmon_sha256": PIXELMON_SHA256,
               "port_sha256": PORT_SHA256, "top_level_mod_jars": 313,
               "neutral_replacement_files": 68, "final_gameplay_validated": False}
    (destination / ".psa-forge-candidate.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-pack", type=Path, required=True)
    parser.add_argument("--pixelmon", type=Path, required=True)
    parser.add_argument("--port", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.server_pack, args.pixelmon, args.port, args.destination), indent=2))
