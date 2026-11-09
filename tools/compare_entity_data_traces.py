#!/usr/bin/env python3
"""Compare observed allocations, rejecting incomplete required coverage or merged runs."""
import argparse
import json
from pathlib import Path
import re

LINE = re.compile(r"PSA_ENTITY_DATA owner=(\S+) id=([0-9]+) serializer_class=(\S+) callers=(.+)")


def read_trace(path):
    owners = {}
    for number, raw in enumerate(Path(path).read_text().splitlines(), 1):
        if not raw.startswith("PSA_ENTITY_DATA "):
            continue
        match = LINE.fullmatch(raw)
        if not match:
            raise ValueError(f"Malformed trace at line {number}")
        owner, index, serializer, callers = match.groups()
        index = int(index)
        if not 0 <= index <= 254:
            raise ValueError("Invalid entity data index")
        fields = owners.setdefault(owner, {})
        if index in fields:
            raise ValueError("Duplicate owner/index; use a trace from one fresh JVM run")
        frames = callers.split(" <- ")
        # Helpers such as DataSync allocate for several independent static initializers.
        # Keeping only DataSync#<init> would erase the allocator that determines order.
        allocator = next((frame for frame in frames if frame.endswith("#<clinit>")), frames[0])
        fields[index] = {"id": index, "serializer_class": serializer, "allocator": allocator}
    if not owners:
        raise ValueError("No observed allocations")
    return {key: [fields[i] for i in sorted(fields)] for key, fields in sorted(owners.items())}


def compare(left, right, required=()):
    missing = sorted(set(required) - (left.keys() & right.keys()))
    shared = sorted(left.keys() & right.keys())
    differences = [{"owner": owner, "left": left[owner], "right": right[owner]}
                   for owner in shared if left[owner] != right[owner]]
    return {"scope": "observed allocation IDs, serializer classes and allocator order only; no field values",
            "shared_owners": len(shared), "different_owners": len(differences),
            "differences": differences, "missing_required_owners": missing,
            "left_only_owners": sorted(left.keys() - right.keys()),
            "right_only_owners": sorted(right.keys() - left.keys()),
            "required_observed_schemas_match": bool(shared) and not missing and not differences,
            "all_registered_entities_or_gameplay_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--require-owner", action="append", default=[])
    args = parser.parse_args()
    result = compare(read_trace(args.left), read_trace(args.right), args.require_owner)
    print(json.dumps(result, indent=2))
    return 0 if result["required_observed_schemas_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
