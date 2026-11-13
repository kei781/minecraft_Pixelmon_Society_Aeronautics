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


def build(base, tested_patch, destination):
    base, tested_patch, destination = map(Path, (base, tested_patch, destination))
    if (destination.exists() or destination.is_symlink() or destination.suffix.lower() != ".jar"
            or "mods" in (part.casefold() for part in destination.resolve().parts)):
        raise ValueError("Fresh non-mods output JAR required")
    lock = json.loads(MANIFEST.read_text())
    pinned = [(base, lock["base_common_sha256"], "base_common_sha256"),
              (tested_patch, lock["tested_patch_sha256"], "tested_patch_sha256"),
              (CONFIG, lock["config_sha256"], "config_sha256")]
    pinned += [(SOURCES[name], lock["source_sha256"][name], "source_sha256 " + name) for name in NAMES]
    for path, wanted, role in pinned:
        if path.is_symlink() or not path.is_file() or digest(path) != wanted:
            raise ValueError("Pinned input differs: " + role)
    if json.loads(CONFIG.read_bytes()) != EXPECTED_CONFIG:
        raise ValueError("Only the two authored port repairs may be registered")
    with zipfile.ZipFile(tested_patch) as patch:
        names = patch.namelist()
        compiled = {}
        for name in NAMES:
            if len(names) != len(set(names)) or names.count(CLASSES[name]) != 1:
                raise ValueError("Unique tested repair class required")
            compiled[name] = patch.read(CLASSES[name])
            if hashlib.sha256(compiled[name]).hexdigest() != lock["class_sha256"][name]:
                raise ValueError("Compiled repair class differs: " + name)
        if (patch.read(CONFIG.name) != CONFIG.read_bytes()
                or mixin_header(patch.read("META-INF/MANIFEST.MF"))[4] != [CONFIG.name]):
            raise ValueError("Tested registration differs")
    with zipfile.ZipFile(base) as archive:
        names = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
        if len(names) != len(set(names)) or CONFIG.name in names or any(path in names for path in CLASSES.values()):
            raise ValueError("Unexpected base inventory")
        files = {name: archive.read(name) for name in names}
    # The repairs are written against these exact port classes; a different port needs a new look.
    for entry, wanted in sorted(lock["port_class_sha256"].items()):
        if hashlib.sha256(files.get(entry, b"")).hexdigest() != wanted:
            raise ValueError("Repaired port class differs: " + entry)
    for name in NAMES:
        files[CLASSES[name]] = compiled[name]
    files[CONFIG.name] = CONFIG.read_bytes()
    files["META-INF/MANIFEST.MF"] = append_config(files["META-INF/MANIFEST.MF"], CONFIG.name)
    provenance = {key: lock[key] for key in ("base_common_sha256", "source_sha256", "config_sha256", "class_sha256")}
    files["PSA_PROVENANCE.txt"] += ("\nPSA authored port repairs (collision shape of foreign blocks, redstone contact ticker)\n"
                                    + json.dumps(provenance, sort_keys=True) + "\n").encode()
    with tempfile.TemporaryDirectory(prefix="psa-port-fix-") as folder:
        raw = Path(folder) / "raw.jar"
        with zipfile.ZipFile(raw, "w") as archive:
            for name in sorted(files):
                archive.writestr(name, files[name])
        receipt = canonical_jar(raw, destination)
    added = sorted(CLASSES.values()) + [CONFIG.name]
    return dict(receipt, bytes=destination.stat().st_size, added=added,
                changed=["META-INF/MANIFEST.MF", "PSA_PROVENANCE.txt"], unchanged_entries=len(files) - len(added) - 2,
                inputs=provenance)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("base", "tested-patch", "output"):
        parser.add_argument("--" + argument, type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.base, arguments.tested_patch, arguments.output), indent=2))
