#!/usr/bin/env python3
"""Candidate search for hit-location ray math, not a dataflow/correctness proof.

Reads pinned production mod JARs and their Forge nested JARs without loading
upstream classes. Input is a mods directory or an exported bundled mrpack.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from audit_menu_id_references import methods


def scan(source):
    candidates = []
    counts = {"top_level_jars": 0, "nested_jars": 0, "class_entries": 0,
              "hit_location_classes": 0}

    def archive(label, data, nested=False):
        counts["nested_jars" if nested else "top_level_jars"] += 1
        with zipfile.ZipFile(io.BytesIO(data)) as jar:
            for entry in jar.infolist():
                if entry.is_dir():
                    continue
                if entry.filename.startswith("META-INF/jarjar/") and entry.filename.endswith(".jar"):
                    archive(label + "!" + entry.filename, jar.read(entry), True)
                elif entry.filename.endswith(".class"):
                    counts["class_entries"] += 1
                    bytecode = jar.read(entry)
                    if b"net/minecraft/world/phys/" not in bytecode:
                        continue
                    refs = methods(bytecode)
                    hits = [ref for ref in refs if ref[0] in {
                        "net/minecraft/world/phys/HitResult", "net/minecraft/world/phys/BlockHitResult",
                        "net/minecraft/world/phys/EntityHitResult"}
                        and ref[1] in {"m_82450_", "getLocation"}]
                    if not hits:
                        continue
                    counts["hit_location_classes"] += 1
                    math = [ref for ref in refs if
                            (ref[0] == "net/minecraft/world/phys/AABB" and ref[1] == "<init>"
                             and "Lnet/minecraft/world/phys/Vec3;" in ref[2])
                            or (ref[0] in {"net/minecraft/world/phys/Vec3", "net/minecraft/core/BlockPos"}
                                and ref[1] in {"m_82557_", "distanceToSqr", "m_123331_", "distSqr"})]
                    if math:
                        candidates.append({"jar": label, "class": entry.filename,
                                           "class_sha256": hashlib.sha256(bytecode).hexdigest(),
                                           "hit_location_references": hits, "math_references": math})

    if source.is_dir():
        for path in sorted(source.glob("*.jar")):
            archive(path.name, path.read_bytes())
    else:
        with zipfile.ZipFile(source) as pack:
            for name in sorted(pack.namelist()):
                if name.startswith("overrides/mods/") and name.endswith(".jar"):
                    archive(name.rsplit("/", 1)[-1], pack.read(name))
    if not counts["top_level_jars"]:
        raise ValueError("No production JARs found")
    return {"scope": "Constant-pool candidates only; method bodies and runtime controls required.",
            **counts, "candidates": candidates}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print(json.dumps(scan(args.source), indent=2))
