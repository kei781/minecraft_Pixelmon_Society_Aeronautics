#!/usr/bin/env python3
"""List data files that more than one source of a staged profile provides.

A data pack file (loot table, recipe, template pool, structure template, ...)
is replaced as a whole by the last pack that contains it; only tags merge,
unless one of them sets `"replace": true`. Society's own pack was released
with its own overlaps, so the report separates overlaps that involve the two
projects this integration adds (Pixelmon and the Aeronautics port) from the
ones the official pack already had.

Static inspection only; nothing is loaded as game content.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import zipfile

ADDED = {"Pixelmon-1.20.1-9.2.3-universal.jar": "pixelmon",
         "psa-aeronautics-experimental-forge-1.20.1.jar": "aeronautics-port"}
KUBEJS = "KubeJS data"


def collect(profile):
    """{data path: [(source, sha256, replace flag)]} in mod-file name order, KubeJS last."""
    profile = Path(profile)
    owners = collections.defaultdict(list)
    for jar in sorted((profile / "mods").glob("*.jar")):
        with zipfile.ZipFile(jar) as archive:
            for name in archive.namelist():
                if name.startswith("data/") and not name.endswith("/"):
                    data = archive.read(name)
                    owners[name].append((ADDED.get(jar.name, jar.name), hashlib.sha256(data).hexdigest(), replaces(name, data)))
    root = profile / "kubejs/data"
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            name = "data/" + path.relative_to(root).as_posix()
            owners[name].append((KUBEJS, hashlib.sha256(data).hexdigest(), replaces(name, data)))
    return owners


def replaces(name, data):
    if "/tags/" not in name or not name.endswith(".json"):
        return False
    try:
        return json.loads(data).get("replace") is True
    except (ValueError, AttributeError):
        return False


def category(name):
    parts = name.split("/")
    if len(parts) > 3 and parts[2] == "worldgen":
        return "worldgen/" + parts[3]
    return parts[2] if len(parts) > 2 else "other"


def audit(profile):
    overlaps = []
    for name, sources in sorted(collect(profile).items()):
        if len(sources) < 2 or len({digest for _, digest, _ in sources}) < 2:
            continue
        is_tag = "/tags/" in name
        if is_tag and not any(flag for _, _, flag in sources):
            continue  # tags from several packs are merged
        names = [source for source, _, _ in sources]
        overlaps.append({"path": name, "category": "tags (replace)" if is_tag else category(name),
                         "sources": names, "involves_added_project": bool(set(names) & set(ADDED.values())),
                         "kubejs_wins": names[-1] == KUBEJS})
    added = [item for item in overlaps if item["involves_added_project"]]
    summary = collections.Counter(item["category"] for item in added)
    return {"overlapping_files": len(overlaps), "involving_added_projects": len(added),
            "involving_added_projects_by_category": dict(sorted(summary.items())),
            "added_project_overlaps": added,
            "original_pack_overlaps_by_category": dict(sorted(collections.Counter(
                item["category"] for item in overlaps if not item["involves_added_project"]).items()))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.profile)
    text = json.dumps(result, indent=1) + "\n"
    if args.output:
        if args.output.exists():
            raise SystemExit("Refusing to overwrite an existing result")
        args.output.write_text(text)
    print(json.dumps({key: value for key, value in result.items() if key != "added_project_overlaps"}, indent=1))
    for item in result["added_project_overlaps"]:
        print(item["category"], "|", item["path"], "<-", ", ".join(item["sources"]))
