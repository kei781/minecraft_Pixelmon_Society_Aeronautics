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
import subprocess
import tempfile
import zipfile

from audit_menu_id_references import methods


def family_references(refs):
    """Independent of hit-location reads: range/accessor code often has none."""
    result = []
    for owner, name, descriptor in refs:
        category = None
        if owner == "net/minecraft/world/phys/AABB":
            if name == "<init>":
                category = "aabb_constructor"
            elif name in {"m_82371_", "clip"}:
                category = "aabb_clip"
            elif name in {"m_82390_", "m_82376_", "contains"}:
                category = "aabb_contains"
            elif name in {"m_272282_", "distanceToSqr"}:
                category = "aabb_distance"
        elif owner in {"net/minecraft/world/phys/Vec3", "net/minecraft/core/BlockPos",
                       "net/minecraft/core/Vec3i"} and name in {
                           "m_82557_", "m_82554_", "m_82531_", "m_123331_",
                           "distanceTo", "distanceToSqr", "distSqr"}:
            category = "point_distance"
        elif owner.startswith("net/minecraft/world/entity/") or owner == "net/minecraft/server/level/ServerPlayer":
            if name in {"m_20280_", "m_20238_", "m_20275_", "m_20270_", "distanceTo", "distanceToSqr"}:
                category = "entity_distance"
        if category is None and owner.startswith("net/minecraft/"):
            # Include inherited LevelAccessor/EntityGetter interface owners too.
            if "Lnet/minecraft/world/phys/AABB;" in descriptor and descriptor.endswith("Ljava/util/List;"):
                category = "entity_query"
        if category:
            result.append([category, owner, name, descriptor])
    return result


def method_summary(bytecode, javap):
    """Keep API/method metadata only; no upstream instruction text is published."""
    with tempfile.TemporaryDirectory(prefix="psa-spatial-methods-") as temporary:
        target = Path(temporary) / "Candidate.class"
        target.write_bytes(bytecode)
        output = subprocess.run([str(javap), "-c", "-p", str(target)],
                                capture_output=True, text=True, check=True, timeout=30).stdout
    methods_found, current = [], None
    for line in output.splitlines():
        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(";"):
            current = {"method": line.strip(), "hit_reads": 0, "math_calls": 0, "query_calls": 0}
            methods_found.append(current)
        elif current is not None and "// Method" in line:
            if ".m_82450_:" in line or ".getLocation:" in line:
                current["hit_reads"] += 1
            if any(token in line for token in ['AABB."<init>"', 'Vec3.m_82557_', 'BlockPos.m_123331_']):
                current["math_calls"] += 1
            if any(token in line for token in ['Level.m_6249_', 'Level.m_45976_', 'Level.m_45547_', 'BlockGetter.m_45547_']):
                current["query_calls"] += 1
    return [method for method in methods_found if method["hit_reads"]
            and (method["math_calls"] or method["query_calls"])]


def scan(source, expanded=False, summary=False, focus_jar=None, javap=None):
    candidates = []
    counts = {"top_level_jars": 0, "nested_jars": 0, "class_entries": 0,
              "hit_location_classes": 0}
    category_counts, jar_counts = {}, {}

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
                    if not expanded and b"net/minecraft/world/phys/" not in bytecode:
                        continue
                    refs = methods(bytecode)
                    hits = [ref for ref in refs if ref[0] in {
                        "net/minecraft/world/phys/HitResult", "net/minecraft/world/phys/BlockHitResult",
                        "net/minecraft/world/phys/EntityHitResult"}
                        and ref[1] in {"m_82450_", "getLocation"}]
                    if not hits and not expanded:
                        continue
                    if hits:
                        counts["hit_location_classes"] += 1
                    math = [ref for ref in refs if
                            (ref[0] == "net/minecraft/world/phys/AABB" and ref[1] == "<init>"
                             and "Lnet/minecraft/world/phys/Vec3;" in ref[2])
                            or (ref[0] in {"net/minecraft/world/phys/Vec3", "net/minecraft/core/BlockPos"}
                                and ref[1] in {"m_82557_", "distanceToSqr", "m_123331_", "distSqr"})]
                    family = family_references(refs) if expanded else []
                    if (family if expanded else math):
                        item = {"jar": label, "class": entry.filename,
                                           "class_sha256": hashlib.sha256(bytecode).hexdigest(),
                                           "hit_location_references": hits, "math_references": math}
                        if expanded:
                            item["family_references"] = family
                            for category in set(ref[0] for ref in family):
                                category_counts[category] = category_counts.get(category, 0) + 1
                            jar_counts[label] = jar_counts.get(label, 0) + 1
                        if javap is not None and (not summary or label == focus_jar):
                            item["same_method_candidates"] = method_summary(bytecode, javap)
                        candidates.append(item)

    if source.is_dir():
        for path in sorted(source.glob("*.jar")):
            archive(path.name, path.read_bytes())
    elif source.suffix == ".jar":
        archive(source.name, source.read_bytes())
    else:
        with zipfile.ZipFile(source) as pack:
            for name in sorted(pack.namelist()):
                if name.startswith("overrides/mods/") and name.endswith(".jar"):
                    archive(name.rsplit("/", 1)[-1], pack.read(name))
    if not counts["top_level_jars"]:
        raise ValueError("No production JARs found")
    result = {"scope": "Constant-pool candidates only; method bodies and runtime controls required.",
              "expanded_family": expanded, **counts, "candidate_classes": len(candidates)}
    if expanded:
        result.update({"category_class_counts": category_counts, "jar_candidate_counts": jar_counts})
    if summary:
        result["candidate_details_scope"] = "Only the exact focus JAR; aggregate counts cover the full input."
        candidates = [item for item in candidates if item["jar"] == focus_jar]
    result["candidates"] = candidates
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--expanded", action="store_true", help="Search distance/contains/clip/query calls without requiring a hit read")
    parser.add_argument("--summary", action="store_true", help="Keep whole-input aggregates and focus-JAR detail only")
    parser.add_argument("--focus-jar", help="Exact JAR label whose details appear with --summary")
    parser.add_argument("--javap", type=Path, help="Optional JDK javap for a reproducible method metadata summary; raw instructions are not retained")
    args = parser.parse_args()
    if args.summary and not args.focus_jar:
        parser.error("--summary requires --focus-jar")
    print(json.dumps(scan(args.source, args.expanded, args.summary, args.focus_jar, args.javap), indent=2))
