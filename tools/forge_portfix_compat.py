#!/usr/bin/env python3
"""Add the two tested authored port repairs to the common JAR without rewriting upstream payloads.

The Aeronautics port stops the server in two situations that need code, not data:
a placed Create Redstone Contact, and a physics structure near a block whose collision
shape reads the level (Pixelmon's multi-block machines). Each repair is one mixin class
on the port's own code. This tool adds the two compiled classes and their mixin
configuration to the accepted common JAR and registers the configuration; every other
entry is carried over byte for byte.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from forge_resources import canonical_jar
from forge_starter_compat import append_config, digest, mixin_header

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "compat/port-fix-build.json"
CONFIG = ROOT / "compat/forge-port/psa-port-fix.mixins.json"
NAMES = ("PortColliderShapeMixin", "PortRedstoneContactTickerMixin")
SOURCES = {name: ROOT / ("compat/forge-port/%s.java" % name) for name in NAMES}
CLASSES = {name: "dev/psa/portfix/mixin/%s.class" % name for name in NAMES}
EXPECTED_CONFIG = {"required": True, "minVersion": "0.8", "package": "dev.psa.portfix.mixin",
                   "compatibilityLevel": "JAVA_17", "mixins": list(NAMES), "injectors": {"defaultRequire": 1}}


def overlay(base, tested_patch, destination, manifest, config, sources, classes, expected_config, pinned_classes, title):
    """Add compiled authored mixin classes and their configuration to a pinned common JAR."""
    base, tested_patch, destination = map(Path, (base, tested_patch, destination))
    names = tuple(classes)
    if (destination.exists() or destination.is_symlink() or destination.suffix.lower() != ".jar"
            or "mods" in (part.casefold() for part in destination.resolve().parts)):
        raise ValueError("Fresh non-mods output JAR required")
    lock = json.loads(manifest.read_text())
    pinned = [(base, lock["base_common_sha256"], "base_common_sha256"),
              (tested_patch, lock["tested_patch_sha256"], "tested_patch_sha256"),
              (config, lock["config_sha256"], "config_sha256")]
    pinned += [(sources[name], lock["source_sha256"][name], "source_sha256 " + name) for name in names]
    for path, wanted, role in pinned:
        if path.is_symlink() or not path.is_file() or digest(path) != wanted:
            raise ValueError("Pinned input differs: " + role)
    if json.loads(config.read_bytes()) != expected_config:
        raise ValueError("Only the authored classes of this step may be registered")
    with zipfile.ZipFile(tested_patch) as patch:
        entries = patch.namelist()
        compiled = {}
        for name in names:
            if len(entries) != len(set(entries)) or entries.count(classes[name]) != 1:
                raise ValueError("Unique tested repair class required")
            compiled[name] = patch.read(classes[name])
            if hashlib.sha256(compiled[name]).hexdigest() != lock["class_sha256"][name]:
                raise ValueError("Compiled repair class differs: " + name)
        if (patch.read(config.name) != config.read_bytes()
                or mixin_header(patch.read("META-INF/MANIFEST.MF"))[4] != [config.name]):
            raise ValueError("Tested registration differs")
    with zipfile.ZipFile(base) as archive:
        entries = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
        if len(entries) != len(set(entries)) or config.name in entries or any(path in entries for path in classes.values()):
            raise ValueError("Unexpected base inventory")
        files = {name: archive.read(name) for name in entries}
    # The repairs are written against these exact classes; different ones need a new look.
    for entry, wanted in sorted(lock[pinned_classes].items() if pinned_classes else []):
        if hashlib.sha256(files.get(entry, b"")).hexdigest() != wanted:
            raise ValueError("Repaired port class differs: " + entry)
    for name in names:
        files[classes[name]] = compiled[name]
    files[config.name] = config.read_bytes()
    files["META-INF/MANIFEST.MF"] = append_config(files["META-INF/MANIFEST.MF"], config.name)
    provenance = {key: lock[key] for key in ("base_common_sha256", "source_sha256", "config_sha256", "class_sha256")}
    files["PSA_PROVENANCE.txt"] += ("\n" + title + "\n" + json.dumps(provenance, sort_keys=True) + "\n").encode()
    with tempfile.TemporaryDirectory(prefix="psa-authored-") as folder:
        raw = Path(folder) / "raw.jar"
        with zipfile.ZipFile(raw, "w") as archive:
            for name in sorted(files):
                archive.writestr(name, files[name])
        receipt = canonical_jar(raw, destination)
    added = sorted(classes.values()) + [config.name]
    return dict(receipt, bytes=destination.stat().st_size, added=added,
                changed=["META-INF/MANIFEST.MF", "PSA_PROVENANCE.txt"], unchanged_entries=len(files) - len(added) - 2,
                inputs=provenance)


def build(base, tested_patch, destination):
    return overlay(base, tested_patch, destination, MANIFEST, CONFIG, SOURCES, CLASSES, EXPECTED_CONFIG,
                   "port_class_sha256",
                   "PSA authored port repairs (collision shape of foreign blocks, redstone contact ticker)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("base", "tested-patch", "output"):
        parser.add_argument("--" + argument, type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.base, arguments.tested_patch, arguments.output), indent=2))
