#!/usr/bin/env python3
"""Export the full, private experimental Forge client; never skip content."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from export_client import safe_path, add_zip_file, data_bytes
from stage_forge_candidate import PORT_SHA256, PIXELMON_SHA256, digest
import forge_model_pack
import forge_item_model_alias

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FILES = 367
EXPECTED_SHARED = 311
EXPECTED_REPLACEMENTS = 68
EXPECTED_MODEL_OVERRIDES = 17
MENU_PATCH_NAME = "PSA-Client-Menu-Compat-1.1.jar"
MENU_PATCH_SHA256 = "44cacaa5794d6ff581f8b8d4e877942187d28843c30d4d05395f91b6bbd1d9f9"
ALI_PATCH_NAME = "PSA-ALI-Client-Compat-0.1.jar"
ALI_PATCH_SHA256 = "0b05990106c46a19aa1c84a91553e14d7e387bc7de2924c9e4b5d02df45c5055"
ALI_TARGET_PATH = "mods/AdvancedLootInfo-forge-1.20.1-1.12.0.jar"
ALI_TARGET_SHA256 = "6a0b368a0c19476ce1c6e73ecd923855e5ef45834077dea1ae0ca94820ce8eb8"
OVERRIDE_FOLDERS = {"config", "configureddefaults", "defaultconfigs", "kubejs", "patchouli_books", "resourcepacks", "shaderpacks"}


def target_path(kind, filename):
    folders = {"mod": "mods", "resourcepack": "resourcepacks", "shaderpack": "shaderpacks"}
    if kind not in folders or Path(filename).name != filename:
        raise ValueError("Unknown client file kind")
    suffix = ".jar" if kind == "mod" else ".zip"
    if not filename.endswith(suffix):
        raise ValueError("Unexpected client file extension")
    return safe_path(folders[kind] + "/" + filename)


def overrides_from(archive):
    result, folded = {}, set()
    for item in archive.infolist():
        if item.is_dir() or not item.filename.startswith("overrides/"):
            continue
        name = item.filename[len("overrides/"):]
        safe_path(name)
        if stat.S_ISLNK(item.external_attr >> 16):
            raise ValueError("Client archive symlinks are not allowed")
        if name.split("/")[0] not in OVERRIDE_FOLDERS and name not in {"options.txt", "optionsof.txt"}:
            raise ValueError("Unrecognized client override: " + name)
        if name.casefold() in folded:
            raise ValueError("Duplicate client override")
        folded.add(name.casefold())
        result[name] = archive.read(item)
    return result


def verify_mod(path, entry):
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ValueError("A regular verified mod file is required: " + entry["path"])
    if path.stat().st_size != entry["size"] or set(entry["hashes"]) != {"sha1", "sha512"}:
        raise ValueError("Invalid mod size/hash metadata")
    for algorithm, expected in entry["hashes"].items():
        if digest(path, algorithm) != expected:
            raise ValueError("Client mod hash mismatch: " + entry["path"])


def apply_client_overrides(files, lock, extras):
    originals = {f["path"]: f for f in lock["files"]}
    for entry in lock.get("client_overrides", []):
        old = entry["replaces_path"]
        original = originals.get(old, {})
        if original.get("side") != "client" or original.get("kind") != "mod" or old not in files:
            raise ValueError("Compatibility overrides may replace only client-only mod JARs")
        name = target_path(entry["kind"], Path(entry["path"]).name)
        if entry.get("side") != "client" or entry.get("kind") != "mod" or name != entry["path"] or name in files:
            raise ValueError("Invalid client compatibility override")
        source = extras / Path(name).name
        verify_mod(source, entry)
        classes = entry.get("required_classes")
        if not isinstance(classes, list) or not classes or not all(isinstance(n, str) and n.endswith('.class') for n in classes):
            raise ValueError("Explicit compatibility target classes are required")
        with zipfile.ZipFile(source) as archive:
            for required in classes:
                safe_path(required)
                if required not in archive.namelist():
                    raise ValueError("Missing client compatibility class: " + required)
                data = archive.read(required)
                if len(data) < 8 or data[:4] != b'\xca\xfe\xba\xbe' or not 45 <= int.from_bytes(data[6:8], 'big') <= 61:
                    raise ValueError("Client compatibility class requires a different Java version")
        del files[old]
        files[name] = source


def build(server, extras, society_zip, output, menu_fix=None, ali_fix=None):
    server, extras, society_zip, output = map(Path, [server, extras, society_zip, output])
    if output.exists() or output.is_symlink() or output.suffix.lower() != ".mrpack":
        raise ValueError("A fresh .mrpack output is required")
    if menu_fix is not None:
        menu_fix = Path(menu_fix)
        if (menu_fix.is_symlink() or menu_fix.parent.is_symlink() or not menu_fix.is_file()
                or digest(menu_fix) != MENU_PATCH_SHA256):
            raise ValueError("Client menu compatibility hash mismatch")
    if ali_fix is not None:
        ali_fix = Path(ali_fix)
        if (ali_fix.is_symlink() or ali_fix.parent.is_symlink() or not ali_fix.is_file()
                or digest(ali_fix) != ALI_PATCH_SHA256):
            raise ValueError("Client ALI compatibility hash mismatch")
    if not (server / ".psa-forge-candidate.json").is_file():
        raise ValueError("An owned full candidate is required")
    lock_path = ROOT / "forge-client-lock.json"
    lock = json.loads(lock_path.read_text())
    base = lock["base_pack"]
    if society_zip.stat().st_size != base["size"] or digest(society_zip, "sha1") != base["sha1"]:
        raise ValueError("Official Society client archive hash mismatch")
    if len(lock["files"]) != EXPECTED_FILES or sum(f["side"] == "both" for f in lock["files"]) != EXPECTED_SHARED:
        raise ValueError("Incomplete frozen Society client inventory")
    files = {}
    for entry in lock["files"]:
        name = safe_path(entry["path"])
        if name != target_path(entry["kind"], Path(name).name) or len(Path(name).parts) != 2:
            raise ValueError("Unexpected mod path")
        if entry["side"] == "both" and entry["kind"] != "mod":
            raise ValueError("Only mod JARs may be shared with this server")
        source = server / name if entry["side"] == "both" else extras / Path(name).name
        verify_mod(source, entry)
        if name in files:
            raise ValueError("Duplicate client mod")
        files[name] = source
    additions = {"mods/Pixelmon-1.20.1-9.2.3-universal.jar": PIXELMON_SHA256,
                 "mods/psa-aeronautics-experimental-forge-1.20.1.jar": PORT_SHA256}
    for name, expected in additions.items():
        source = server / name
        if source.is_symlink() or source.parent.is_symlink() or digest(source) != expected:
            raise ValueError("Integration mod identity mismatch")
        files[name] = source
    expected_server = {f["path"] for f in lock["files"] if f["side"] == "both"} | set(additions)
    actual_server = {p.relative_to(server).as_posix() for p in (server / "mods").rglob("*") if p.is_file()}
    if actual_server != expected_server:
        raise ValueError("Unexpected or missing server mod files")
    apply_client_overrides(files, lock, extras)
    if menu_fix is not None:
        name = "mods/" + MENU_PATCH_NAME
        if name in files:
            raise ValueError("Duplicate client menu compatibility mod")
        files[name] = menu_fix
    if ali_fix is not None:
        target = files.get(ALI_TARGET_PATH)
        if target is None or digest(target) != ALI_TARGET_SHA256:
            raise ValueError("Pinned ALI target missing or incompatible")
        name = "mods/" + ALI_PATCH_NAME
        if name in files:
            raise ValueError("Duplicate client ALI compatibility mod")
        files[name] = ali_fix
    with zipfile.ZipFile(society_zip) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if {(f["projectID"], f["fileID"]) for f in manifest["files"]} != {(f["project_id"], f["file_id"]) for f in lock["files"]}:
            raise ValueError("Client lock does not match the official manifest")
        overrides = overrides_from(archive)
    for name, data in overrides.items():
        if name.startswith("kubejs/"):
            source = server / name
            if source.is_symlink() or source.read_bytes() != data:
                raise ValueError("Society KubeJS client/server mismatch: " + name)
    neutral = (json.dumps({"enabled": False, "detection_logic": "simple", "replaced_mobs": [],
                          "replacement_logic": "simple", "specs": []}, indent=2) + "\n").encode()
    with zipfile.ZipFile(server / "mods/Pixelmon-1.20.1-9.2.3-universal.jar") as pokemon:
        replacements = [n for n in pokemon.namelist() if n.startswith("data/pixelmon/spawn_replacement/") and n.endswith(".json")]
    if len(replacements) != EXPECTED_REPLACEMENTS:
        raise ValueError("Unexpected legacy Pixelmon replacement inventory")
    for name in replacements:
        target = "kubejs/" + safe_path(name)
        if (server / target).read_bytes() != neutral:
            raise ValueError("Server mob compatibility data mismatch")
        overrides[target] = neutral
    expected_scripts = {name for name in overrides if name.startswith("kubejs/")}
    actual_scripts = {p.relative_to(server).as_posix() for p in (server / "kubejs").rglob("*") if p.is_file()}
    if actual_scripts != expected_scripts:
        raise ValueError("Unrecognized or missing server KubeJS content")
    item_model_alias = forge_item_model_alias.apply(overrides, files)
    additional_item_models = forge_item_model_alias.apply_additional(
        overrides, files, ROOT / "compat/item-model-aliases.json")
    overrides["config/pixelmon/config.yml"] = b"allow-vanilla-mobs: true\n"
    model_data, model_receipt = forge_model_pack.build(
        server / "mods/psa-aeronautics-experimental-forge-1.20.1.jar", PORT_SHA256, EXPECTED_MODEL_OVERRIDES)
    forge_model_pack.enable(overrides, model_data)
    payload = dict(overrides)
    for name in set(payload) & set(files):
        if data_bytes(payload[name]) != data_bytes(files[name]):
            raise ValueError("Indexed client file differs from a bundled override: " + name)
    payload.update(files)
    payload["psa-forge-client-lock.json"] = lock_path.read_bytes()
    payload["psa-forge-integration-lock.json"] = (ROOT / "forge-candidate-lock.json").read_bytes()
    names = list(payload)
    for name in names:
        safe_path(name)
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Windows case-colliding client files")
    checks = {name: hashlib.sha256(data_bytes(value)).hexdigest() for name, value in sorted(payload.items())}
    metadata = {"status": "experimental-full-content-gameplay-unverified", "complete_integration": False,
                "minecraft": lock["minecraft"], "forge": lock["forge"], "society": lock["society"],
                "mod_jars": sum(name.startswith("mods/") and name.endswith(".jar") for name in files),
                "indexed_resourcepacks": sum(f["kind"] == "resourcepack" for f in lock["files"]),
                "indexed_shaderpacks": sum(f["kind"] == "shaderpack" for f in lock["files"]),
                "all_three_projects_included": True,
                "shared_society_mods": EXPECTED_SHARED, "lock_sha256": digest(lock_path),
                "client_compatibility_overrides": [{k: item[k] for k in ["replaces_path", "path", "reason"]}
                                                   for item in lock.get("client_overrides", [])],
                "port_sha256": PORT_SHA256, "overrides": checks}
    metadata["forge_model_compatibility"] = model_receipt
    metadata["item_model_aliases"] = [item_model_alias] + additional_item_models
    if menu_fix is not None:
        metadata["client_menu_compatibility"] = {
            "path": "mods/" + MENU_PATCH_NAME, "sha256": MENU_PATCH_SHA256,
            "client_only": True, "source": "compat/client-menu"}
    if ali_fix is not None:
        metadata["client_ali_compatibility"] = {
            "path": "mods/" + ALI_PATCH_NAME, "sha256": ALI_PATCH_SHA256,
            "client_only": True, "source": "compat/ali-client",
            "target_ali_sha256": ALI_TARGET_SHA256}
    fingerprint = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
    payload["psa-forge-client-profile.json"] = (json.dumps(metadata, indent=2) + "\n").encode()
    index = {"formatVersion": 1, "game": "minecraft", "versionId": "psa-forge-" + fingerprint[:12],
             "name": "PSA - Society + Pixelmon + Aeronautics (Experimental)",
             "summary": "All three projects included; gameplay validation is ongoing.",
             "dependencies": {"minecraft": lock["minecraft"], "forge": lock["forge"]}, "files": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".forge-pack-", dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            add_zip_file(archive, "modrinth.index.json", (json.dumps(index, indent=2) + "\n").encode())
            for name, value in sorted(payload.items()):
                add_zip_file(archive, "overrides/" + name, value)
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"filename": output.name, "sha256": digest(output), "size": output.stat().st_size,
            "version_id": index["versionId"], "mod_jars": metadata["mod_jars"],
            "indexed_resourcepacks": metadata["indexed_resourcepacks"], "indexed_shaderpacks": metadata["indexed_shaderpacks"],
            "override_files": len(payload),
            "longest_relative_path": max(map(len, payload)), "full_gameplay_validated": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--extras", type=Path, required=True)
    parser.add_argument("--society-client", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--menu-fix", type=Path, help="Pinned client-only menu and discount display compatibility JAR")
    parser.add_argument("--ali-fix", type=Path, help="Pinned client-only ALI empty-tooltip compatibility JAR")
    args = parser.parse_args()
    print(json.dumps(build(args.server, args.extras, args.society_client, args.output, args.menu_fix, args.ali_fix), indent=2))
