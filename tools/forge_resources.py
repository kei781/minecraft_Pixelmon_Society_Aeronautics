#!/usr/bin/env python3
"""Flatten Forge's per-mod data output without losing shared tag entries."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

MODS = {"aeronautics", "offroad", "simulated", "sable"}


def canonical_jar(source, destination):
    """Normalize ZIP metadata after reobfJar, preserving every file byte."""
    with zipfile.ZipFile(source) as archive:
        names = [i.filename for i in archive.infolist() if not i.is_dir()]
        if len(names) != len(set(names)) or "META-INF/MANIFEST.MF" not in names:
            raise ValueError("Expected a JAR without duplicate entries")
        files = {name: archive.read(name) for name in sorted(names)}
    with Path(destination).open("xb") as stream, zipfile.ZipFile(stream, "w") as output:
        for name, data in files.items():
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(entry, data, compresslevel=9)
    return {"files": len(files), "sha256": hashlib.sha256(Path(destination).read_bytes()).hexdigest()}


def write_files(destination, files):
    destination.mkdir(parents=True)
    receipts = []
    for name, data in sorted(files.items()):
        output = destination / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        receipts.append({"path": name, "sha256": hashlib.sha256(data).hexdigest()})
    return receipts


def combine(main, generated, destination):
    """Keep authored translations, union tags and use version-correct sounds."""
    main, generated, destination = Path(main), Path(generated), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refusing to overwrite combined resources")
    files, changed = {}, {}
    for root in [main, generated]:
        if root.is_symlink() or not root.is_dir():
            raise ValueError("A real resource directory is required")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("Resource symlinks are not allowed")
            if path.is_dir():
                continue
            relative = path.relative_to(root)
            name, data = relative.as_posix(), path.read_bytes()
            previous = files.get(name)
            if previous is not None and previous != data:
                parts = relative.parts
                if parts[0] == "data" and len(parts) > 4 and parts[2] == "tags" and path.suffix == ".json":
                    data = merge_tag(previous, data, name)
                    changed[name] = "union_tag"
                elif parts[0] == "assets" and len(parts) == 4 and parts[2] == "lang" and path.suffix == ".json":
                    authored, new = json.loads(previous), json.loads(data)
                    if not all(isinstance(d, dict) and all(isinstance(v, str) for v in d.values()) for d in [authored, new]):
                        raise ValueError("Invalid language resource: " + name)
                    data = (json.dumps(dict(new, **authored), indent=2, ensure_ascii=False) + "\n").encode()
                    changed[name] = "add_generated_translation_keys_preserve_authored_values"
                elif parts[0] == "assets" and len(parts) == 3 and parts[-1] == "sounds.json":
                    authored, new = json.loads(previous), json.loads(data)
                    if not isinstance(authored, dict) or not isinstance(new, dict):
                        raise ValueError("Invalid sound resource: " + name)
                    data = (json.dumps(dict(authored, **new), indent=2, ensure_ascii=False) + "\n").encode()
                    changed[name] = "generated_sound_definitions_take_precedence"
                else:
                    raise ValueError("Unresolved resource conflict: " + name)
            files[name] = data
    if not files:
        raise ValueError("No combined resources")
    return {"files": write_files(destination, files), "merged_resources": changed}


def merge_tag(left, right, path):
    documents = [json.loads(data) for data in [left, right]]
    fields = {"values": [], "remove": []}
    seen = {name: set() for name in fields}
    for document in documents:
        if (not isinstance(document, dict) or set(document) - {"replace", "values", "remove"}
                or document.get("replace", False) is not False or not isinstance(document.get("values"), list)
                or not isinstance(document.get("remove", []), list)):
            raise ValueError("Cannot safely merge tag: " + path)
        for name in fields:
            for value in document.get(name, []):
                if not (isinstance(value, str) or (isinstance(value, dict) and set(value) <= {"id", "required"}
                        and isinstance(value.get("id"), str) and isinstance(value.get("required", True), bool))):
                    raise ValueError("Invalid tag value: " + path)
                key = json.dumps(value, sort_keys=True)
                if key not in seen[name]:
                    fields[name].append(value)
                    seen[name].add(key)
    result = {"replace": False, "values": fields["values"]}
    if fields["remove"]:
        result["remove"] = fields["remove"]
    return (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()


def flatten(source, destination):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_dir():
        raise ValueError("A real generated-resource directory is required")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refusing to overwrite resource output")
    files, contributors, merged = {}, {}, set()
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise ValueError("Generated resources must not contain symlinks")
        if path.is_dir() or ".cache" in relative.parts:
            continue
        parts = relative.parts
        if len(parts) < 4 or parts[0] not in MODS or parts[1] not in {"assets", "data"}:
            raise ValueError("Unexpected generated output: " + relative.as_posix())
        name = Path(*parts[1:]).as_posix()
        data = path.read_bytes()
        if path.suffix == ".json":
            json.loads(data)  # Validate all JSON before creating any output.
        contributors.setdefault(name, []).append(relative.as_posix())
        if name in files and files[name] != data:
            if parts[1] == "data" and len(parts) > 5 and parts[3] == "tags" and path.suffix == ".json":
                data = merge_tag(files[name], data, name)
                merged.add(name)
            else:
                raise ValueError("Conflicting generated resource: " + name)
        files[name] = data
    if not files:
        raise ValueError("Generated output contains no resources")
    receipts = write_files(destination, files)
    for entry in receipts:
        entry["sources"] = contributors[entry["path"]]
    return {"files": receipts, "merged_tags": sorted(merged)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    flat = commands.add_parser("flatten")
    flat.add_argument("source", type=Path)
    flat.add_argument("destination", type=Path)
    combined = commands.add_parser("combine")
    combined.add_argument("main", type=Path)
    combined.add_argument("generated", type=Path)
    combined.add_argument("destination", type=Path)
    jar = commands.add_parser("canonical-jar")
    jar.add_argument("source", type=Path)
    jar.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "canonical-jar":
        print(json.dumps(canonical_jar(args.source, args.destination), indent=2))
        return
    if args.command == "flatten":
        report = flatten(args.source, args.destination)
        details = {"merged_tags": report["merged_tags"]}
    else:
        report = combine(args.main, args.generated, args.destination)
        details = {"merged_resources": report["merged_resources"]}
    print(json.dumps(dict(details, files=len(report["files"])), indent=2))


if __name__ == "__main__":
    main()
