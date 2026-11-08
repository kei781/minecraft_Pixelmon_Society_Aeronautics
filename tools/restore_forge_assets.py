#!/usr/bin/env python3
"""Restore official Aeronautics assets locally; preserve port translations."""
import argparse
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

from stage_forge_candidate import verify_published

NAMESPACES = {"aeronautics", "simulated", "offroad"}


def restore(official_jar, resources):
    verified = verify_published(official_jar, "aeronautics_resources")
    resources = Path(resources)
    if resources.is_symlink() or not resources.is_dir():
        raise ValueError("Existing source resource directory required")
    files, preserved = {}, []
    with zipfile.ZipFile(official_jar) as bundle:
        for name in bundle.namelist():
            if not name.startswith("META-INF/jarjar/") or not name.endswith(".jar"):
                continue
            with zipfile.ZipFile(io.BytesIO(bundle.read(name))) as module:
                for entry in module.infolist():
                    path = PurePosixPath(entry.filename)
                    if entry.is_dir() or len(path.parts) < 3 or path.parts[0] != "assets" or path.parts[1] not in NAMESPACES:
                        continue
                    if path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
                        raise ValueError("Unsafe asset path")
                    key, data = path.as_posix(), module.read(entry)
                    if key in files and files[key] != data:
                        raise ValueError("Conflicting official asset: " + key)
                    files[key] = data
    if not files:
        raise ValueError("No official assets found")
    for name, data in files.items():
        target = resources / name
        if any(p.is_symlink() for p in [target, *target.parents] if p == resources or resources in p.parents):
            raise ValueError("Source resource symlink: " + name)
        if target.exists() and target.read_bytes() != data:
            if len(PurePosixPath(name).parts) == 4 and "/lang/" in name and name.endswith(".json"):
                preserved.append(name)
            else:
                raise ValueError("Conflicting authored resource: " + name)
    written = 0
    for name, data in sorted(files.items()):
        target = resources / name
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(data)
        written += 1
    return {"verified_official_input": verified, "restored_files": written,
            "preserved_authored_translations": len(preserved)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-jar", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(restore(args.official_jar, args.resources), indent=2))
