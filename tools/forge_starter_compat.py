#!/usr/bin/env python3
"""Add the tested authored starter-recipient mixin without rewriting upstream payloads."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from forge_resources import canonical_jar

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "compat/pixelmon-starter-build.json"
CLASS = "dev/psa/startercompat/mixin/PixelmonStarterRecipientMixin.class"
SOURCE = ROOT / "compat/forge-port/PixelmonStarterRecipientMixin.java"
CONFIG = ROOT / "compat/forge-port/psa-starter-recipient.mixins.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def mixin_header(data):
    lines = data.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.startswith(b"MixinConfigs: ")]
    if len(matches) != 1:
        raise ValueError("Exactly one MixinConfigs header required")
    start = matches[0]
    end = start + 1
    while end < len(lines) and lines[end].startswith(b" "):
        end += 1
    value = lines[start][len(b"MixinConfigs: "):].rstrip(b"\r\n")
    value += b"".join(line[1:].rstrip(b"\r\n") for line in lines[start + 1:end])
    names = value.decode("ascii").split(",")
    if not all(names) or len(names) != len(set(names)):
        raise ValueError("Unique nonempty mixin configurations required")
    return lines, start, end, value, names


def append_config(data, name):
    lines, start, end, value, names = mixin_header(data)
    if name in names:
        raise ValueError("Starter configuration already registered")
    value = b"MixinConfigs: " + value + b"," + name.encode("ascii")
    folded = [value[:70] + b"\r\n"]
    value = value[70:]
    while value:
        folded.append(b" " + value[:69] + b"\r\n")
        value = value[69:]
    result = b"".join(lines[:start] + folded + lines[end:])
    if mixin_header(result)[4] != names + [name]:
        raise ValueError("Mixin manifest round trip failed")
    return result


def build(base, tested_patch, pixelmon, destination):
    base, tested_patch, pixelmon, destination = map(Path, (base, tested_patch, pixelmon, destination))
    if (destination.exists() or destination.is_symlink() or destination.suffix.lower() != ".jar"
            or "mods" in (part.casefold() for part in destination.resolve().parts)):
        raise ValueError("Fresh non-mods output JAR required")
    lock = json.loads(MANIFEST.read_text())
    for path, role in [(base, "base_common_sha256"), (tested_patch, "tested_patch_sha256"),
                       (pixelmon, "pixelmon_sha256"), (SOURCE, "source_sha256"), (CONFIG, "config_sha256")]:
        if path.is_symlink() or not path.is_file() or digest(path) != lock[role]:
            raise ValueError("Pinned input differs: " + role)
    config = json.loads(CONFIG.read_bytes())
    expected = {"required": True, "minVersion": "0.8", "package": "dev.psa.startercompat.mixin",
                "compatibilityLevel": "JAVA_17", "mixins": ["PixelmonStarterRecipientMixin"],
                "injectors": {"defaultRequire": 1}}
    if config != expected:
        raise ValueError("Only the authored starter mixin may be registered")
    with zipfile.ZipFile(tested_patch) as patch:
        names = patch.namelist()
        if len(names) != len(set(names)) or names.count(CLASS) != 1:
            raise ValueError("Unique tested compatibility class required")
        compiled = patch.read(CLASS)
        if hashlib.sha256(compiled).hexdigest() != lock["class_sha256"]:
            raise ValueError("Compiled compatibility class differs")
        if patch.read(CONFIG.name) != CONFIG.read_bytes() or mixin_header(patch.read("META-INF/MANIFEST.MF"))[4] != [CONFIG.name]:
            raise ValueError("Tested registration differs")
    with zipfile.ZipFile(base) as archive:
        names = [x.filename for x in archive.infolist() if not x.is_dir()]
        if len(names) != len(set(names)) or CLASS in names or CONFIG.name in names:
            raise ValueError("Unexpected base inventory")
        files = {name: archive.read(name) for name in names}
    files[CLASS] = compiled
    files[CONFIG.name] = CONFIG.read_bytes()
    files["META-INF/MANIFEST.MF"] = append_config(files["META-INF/MANIFEST.MF"], CONFIG.name)
    provenance = {k: lock[k] for k in ["base_common_sha256", "pixelmon_sha256", "source_sha256", "config_sha256", "class_sha256"]}
    files["PSA_PROVENANCE.txt"] += ("\nPSA authored offline starter recipient compatibility\n"
        + json.dumps(provenance, sort_keys=True) + "\n").encode()
    with tempfile.TemporaryDirectory(prefix="psa-starter-overlay-") as folder:
        raw = Path(folder) / "raw.jar"
        with zipfile.ZipFile(raw, "w") as archive:
            for name in sorted(files):
                archive.writestr(name, files[name])
        receipt = canonical_jar(raw, destination)
    return dict(receipt, bytes=destination.stat().st_size, added=[CLASS, CONFIG.name],
                changed=["META-INF/MANIFEST.MF", "PSA_PROVENANCE.txt"], unchanged_entries=len(files) - 4,
                inputs=provenance)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ["base", "tested-patch", "pixelmon", "output"]:
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.base, args.tested_patch, args.pixelmon, args.output), indent=2))
