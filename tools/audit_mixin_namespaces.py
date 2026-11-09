#!/usr/bin/env python3
"""Find ordinary top-level classes inside Mixin-reserved package prefixes.

All discovered mixin configs, including inactive ones, are candidates. Class
loading/reachability is not proven. Declared bootstrap plugins and compiler
inner classes are reported separately rather than assumed broken.
"""
import argparse
import io
import json
from pathlib import Path
import zipfile


def scan(source):
    reports, errors = [], []
    archives = 0

    def archive(label, data):
        nonlocal archives
        archives += 1
        with zipfile.ZipFile(io.BytesIO(data)) as jar:
            names = jar.namelist()
            for name in names:
                basename = name.rsplit("/", 1)[-1]
                if (name.endswith(".mixins.json") or name.endswith(".mixin.json")
                        or basename.startswith("mixins.") and basename.endswith(".json")):
                    try:
                        config = json.loads(jar.read(name))
                    except (ValueError, UnicodeDecodeError) as failure:
                        errors.append({"jar": label, "config": name, "error": type(failure).__name__})
                        continue
                    package = config.get("package")
                    if not isinstance(package, str) or not package:
                        continue
                    prefix = package.replace(".", "/") + "/"
                    plugin = config.get("plugin", "").replace(".", "/") + ".class"
                    candidates, inner = [], []
                    for entry in names:
                        if not entry.startswith(prefix) or not entry.endswith(".class") or entry == plugin:
                            continue
                        if entry.rsplit("/", 1)[-1] in {"package-info.class", "module-info.class"}:
                            continue
                        if b"Lorg/spongepowered/asm/mixin/Mixin;" in jar.read(entry):
                            continue
                        if "$" in entry:
                            inner.append(entry)
                        else:
                            candidates.append(entry)
                    reports.append({"jar": label, "config": name, "package": package,
                                    "ordinary_top_level_candidates": candidates,
                                    "unannotated_inner_classes": inner,
                                    "bootstrap_plugin_excluded": config.get("plugin")})
                elif name.startswith("META-INF/jarjar/") and name.endswith(".jar"):
                    archive(label + "!" + name, jar.read(name))

    if source.suffix == ".mrpack":
        with zipfile.ZipFile(source) as pack:
            for name in sorted(pack.namelist()):
                if name.startswith("overrides/mods/") and name.endswith(".jar"):
                    archive(name.rsplit("/", 1)[-1], pack.read(name))
    else:
        archive(source.name, source.read_bytes())
    return {"scope": __doc__.strip(), "archives": archives,
            "config_count": len(reports), "parse_errors": errors, "configs": reports}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print(json.dumps(scan(args.source), indent=2))
