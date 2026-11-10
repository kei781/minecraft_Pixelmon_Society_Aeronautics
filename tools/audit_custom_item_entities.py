#!/usr/bin/env python3
"""Find exact Forge custom-drop method declarations, including nested libraries.

Static metadata only: this does not prove a particular stack returns true, or
that a custom entity renders correctly. Accepts the immutable full mrpack.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile


def declarations(data):
    if data[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("Invalid class")
    count = struct.unpack_from(">H", data, 8)[0]
    pool, offset, index = [None] * count, 10, 1
    widths = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4,
              12: 4, 15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
    while index < count:
        tag = data[offset]
        offset += 1
        if tag == 1:
            length = struct.unpack_from(">H", data, offset)[0]
            offset += 2
            pool[index] = data[offset:offset + length].decode("utf-8", errors="replace")
            offset += length
        else:
            offset += widths[tag]
            if tag in (5, 6):
                index += 1
        index += 1
    offset += 6  # access, this, super
    interfaces = struct.unpack_from(">H", data, offset)[0]
    offset += 2 + 2 * interfaces
    result = []
    for section in ("fields", "methods"):
        members = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        for _ in range(members):
            access, name, descriptor, attributes = struct.unpack_from(">HHHH", data, offset)
            offset += 8
            if section == "methods" and pool[name] in ("hasCustomEntity", "createEntity"):
                result.append({"name": pool[name], "descriptor": pool[descriptor], "access": access})
            for _ in range(attributes):
                length = struct.unpack_from(">I", data, offset + 2)[0]
                offset += 6 + length
    return result


def scan(pack):
    classes, nested, candidates = 0, 0, []

    def archive(label, payload):
        nonlocal classes, nested
        with zipfile.ZipFile(io.BytesIO(payload)) as jar:
            for entry in jar.infolist():
                if entry.filename.startswith("META-INF/jarjar/") and entry.filename.endswith(".jar"):
                    nested += 1
                    archive(label + "!" + entry.filename, jar.read(entry))
                elif entry.filename.endswith(".class"):
                    classes += 1
                    data = jar.read(entry)
                    if b"hasCustomEntity" not in data and b"createEntity" not in data:
                        continue
                    found = [row for row in declarations(data) if
                             (row["name"] == "hasCustomEntity" and row["descriptor"] == "(Lnet/minecraft/world/item/ItemStack;)Z")
                             or (row["name"] == "createEntity" and row["descriptor"] == "(Lnet/minecraft/world/level/Level;Lnet/minecraft/world/entity/Entity;Lnet/minecraft/world/item/ItemStack;)Lnet/minecraft/world/entity/Entity;")]
                    if found:
                        candidates.append({"jar": label, "class": entry.filename, "declared_methods": found})
    with zipfile.ZipFile(pack) as outer:
        mods = [entry for entry in outer.infolist() if entry.filename.startswith("overrides/mods/") and entry.filename.endswith(".jar")]
        for entry in mods:
            archive(Path(entry.filename).name, outer.read(entry))
    return {"scope": "Exact declared Forge custom item-entity API metadata; conditional returns, dynamically generated code and rendering require runtime checks.",
            "pack_sha256": digest(pack), "top_level_jars": len(mods), "nested_jars": nested,
            "class_entries": classes, "candidates": candidates}


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            value.update(block)
    return value.hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    args = parser.parse_args()
    print(json.dumps(scan(args.pack), indent=2))
