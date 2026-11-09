#!/usr/bin/env python3
"""Offline candidate search, not a proof of dataflow or runtime correctness.

Scan constant-pool method references in classes mentioning menu data, including
nested Forge libraries. No upstream class is loaded or source reconstructed.
"""
import argparse
import io
import json
from pathlib import Path
import struct
import zipfile


def methods(data):
    if data[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("Invalid class header")
    count = struct.unpack_from(">H", data, 8)[0]
    pool, offset, index = [None] * count, 10, 1
    widths = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4,
              11: 4, 12: 4, 15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
    while index < count:
        tag = data[offset]
        offset += 1
        if tag == 1:
            length = struct.unpack_from(">H", data, offset)[0]
            offset += 2
            pool[index] = (tag, data[offset:offset + length].decode("utf-8", errors="replace"))
            offset += length
        else:
            width = widths[tag]
            pool[index] = (tag, data[offset:offset + width])
            offset += width
            if tag in {5, 6}:
                index += 1
        index += 1
    result = []
    for entry in pool:
        if entry is None or entry[0] not in {10, 11}:
            continue
        owner, signature = struct.unpack(">HH", entry[1])
        name, descriptor = struct.unpack(">HH", pool[signature][1])
        owner_name = pool[struct.unpack(">H", pool[owner][1])[0]][1]
        result.append((owner_name, pool[name][1], pool[descriptor][1]))
    return result


def scan(paths):
    references, candidates, classes = 0, [], 0

    def archive(label, stream):
        nonlocal references, classes
        with zipfile.ZipFile(stream) as jar:
            for entry in jar.infolist():
                if entry.is_dir():
                    continue
                if entry.filename.startswith("META-INF/jarjar/") and entry.filename.endswith(".jar"):
                    archive(label + "!" + entry.filename, io.BytesIO(jar.read(entry)))
                elif entry.filename.endswith(".class"):
                    classes += 1
                    data = jar.read(entry)
                    menu_data = any(token in data for token in [
                        b"net/minecraft/world/inventory/ContainerData",
                        b"net/minecraft/world/inventory/DataSlot"])
                    packet = b"net/minecraft/network/protocol/game/ClientboundContainerSetDataPacket" in data
                    if not menu_data and not packet:
                        continue
                    if menu_data:
                        references += 1
                    matches = []
                    for owner, name, descriptor in methods(data):
                        if name == "m_19879_" and descriptor == "()I":
                            matches.append(["runtime_entity_id", owner, name, descriptor])
                        elif name == "m_6815_" and descriptor == "(I)Lnet/minecraft/world/entity/Entity;":
                            matches.append(["integer_entity_lookup", owner, name, descriptor])
                        elif name == "getId":
                            matches.append(["named_id_needs_classification", owner, name, descriptor])
                    if matches or packet:
                        candidates.append({"jar": label, "class": entry.filename,
                                           "menu_data": menu_data, "packet_reference": packet,
                                           "method_references": matches})

    for path in paths:
        archive(path.name, path)
    return {"scope": "constant-pool candidate search; inspect method bodies and runtime tests before concluding",
            "top_level_jars": len(paths), "class_entries": classes,
            "menu_data_class_references": references, "candidates": candidates}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mods", type=Path)
    args = parser.parse_args()
    paths = sorted(args.mods.glob("*.jar"))
    if not paths:
        parser.error("No top-level mod JARs")
    print(json.dumps(scan(paths), indent=2) + "\n", end="")
