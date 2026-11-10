#!/usr/bin/env python3
"""Overlay one verified authored HP mixin onto the accepted common JAR."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from forge_resources import canonical_jar

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "compat/pixelmon-hp-build.json"
CLASS = "dev/psa/compat/PixelmonDynamaxHitpointsMixin.class"
SOURCE = ROOT / "compat/forge-port/PixelmonDynamaxHitpointsMixin.java"
CONFIG = ROOT / "compat/forge-port/psa-forge.mixins.json"


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def build(base, tested_patch, pixelmon, destination):
    base, tested_patch, pixelmon, destination = map(Path, (base, tested_patch, pixelmon, destination))
    if (destination.exists() or destination.is_symlink() or destination.suffix.lower() != ".jar"
            or "mods" in (part.casefold() for part in destination.parts)):
        raise ValueError("Fresh non-mods output JAR required")
    manifest = json.loads(MANIFEST.read_text())
    for path, role in ((base, "base_common_sha256"), (tested_patch, "tested_patch_sha256"),
                       (pixelmon, "pixelmon_sha256"), (SOURCE, "source_sha256"),
                       (CONFIG, "config_sha256")):
        if path.is_symlink() or not path.is_file() or digest(path) != manifest[role]:
            raise ValueError("Pinned input differs: " + role)
    with zipfile.ZipFile(tested_patch) as patch:
        names = patch.namelist()
        if len(names) != len(set(names)) or names.count(CLASS) != 1:
            raise ValueError("Expected one unique tested class")
        compiled = patch.read(CLASS)
        if hashlib.sha256(compiled).hexdigest() != manifest["class_sha256"]:
            raise ValueError("Compiled mixin differs")
    with zipfile.ZipFile(base) as original:
        names = [i.filename for i in original.infolist() if not i.is_dir()]
        if len(names) != len(set(names)) or CLASS in names:
            raise ValueError("Unexpected common input inventory")
        files = {name: original.read(name) for name in names}
    old = json.loads(files["psa-forge.mixins.json"])
    if "PixelmonDynamaxHitpointsMixin" in old["mixins"]:
        raise ValueError("Mixin already registered")
    expected = dict(old, mixins=old["mixins"] + ["PixelmonDynamaxHitpointsMixin"])
    if json.loads(CONFIG.read_text()) != expected:
        raise ValueError("Only the single authored mixin registration may change")
    files[CLASS] = compiled
    files["psa-forge.mixins.json"] = CONFIG.read_bytes()
    provenance = {"change": "Shedinja native base-HP-one Dynamax maximum query",
                  "base_common_sha256": manifest["base_common_sha256"],
                  "pixelmon_sha256": manifest["pixelmon_sha256"],
                  "source_sha256": manifest["source_sha256"],
                  "class_sha256": manifest["class_sha256"]}
    files["PSA_PROVENANCE.txt"] += ("\nPSA authored HP compatibility overlay\n"
        + json.dumps(provenance, sort_keys=True) + "\n").encode()
    with tempfile.TemporaryDirectory(prefix="psa-hitpoint-overlay-") as temporary:
        raw = Path(temporary) / "raw.jar"
        with zipfile.ZipFile(raw, "w") as output:
            for name in sorted(files):
                output.writestr(name, files[name])
        receipt = canonical_jar(raw, destination)
    return dict(receipt, bytes=destination.stat().st_size,
                added=[CLASS], changed=["psa-forge.mixins.json", "PSA_PROVENANCE.txt"],
                unchanged_entries=len(files) - 3, inputs=provenance)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--tested-patch", type=Path, required=True)
    parser.add_argument("--pixelmon", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.base, args.tested_patch, args.pixelmon, args.output), indent=2))


if __name__ == "__main__":
    main()
