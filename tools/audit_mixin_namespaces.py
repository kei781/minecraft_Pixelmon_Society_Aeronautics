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


def manifest_configs(data):
    """Read main-section attributes, including JAR manifest continuation lines."""
    headers, current = {}, None
    for line in data.decode("utf-8").splitlines():
        if not line:
            break
        if line.startswith(" ") and current is not None:
            headers[current] += line[1:]
        elif ":" in line:
            key, value = line.split(":", 1)
            current = key.lower()
            headers[current] = value.lstrip(" ")
        else:
            current = None
    return {name.strip() for name in headers.get("mixinconfigs", "").split(",") if name.strip()}


def scan(source):
    reports, errors, external = [], [], []
    archives = 0

    def archive(label, data):
        nonlocal archives
        archives += 1
        with zipfile.ZipFile(io.BytesIO(data)) as jar:
            names = jar.namelist()
            registered = set()
            if "META-INF/MANIFEST.MF" in names:
                try:
                    registered = manifest_configs(jar.read("META-INF/MANIFEST.MF"))
                except UnicodeDecodeError as failure:
                    errors.append({"jar": label, "config": "META-INF/MANIFEST.MF", "error": type(failure).__name__})
            conventions = {name for name in names if name.endswith(".mixins.json") or name.endswith(".mixin.json")
                           or name.rsplit("/", 1)[-1].startswith("mixins.") and name.endswith(".json")}
            for name in sorted(registered | conventions):
                if name not in names:
                    # Forge resources can live in a dependency JAR on the classpath.
                    external.append({"registering_jar": label, "config": name})
                    continue
                if name in names:
                    try:
                        config = json.loads(jar.read(name))
                    except (ValueError, UnicodeDecodeError) as failure:
                        errors.append({"jar": label, "config": name, "error": type(failure).__name__})
                        continue
                    if not isinstance(config, dict):
                        errors.append({"jar": label, "config": name, "error": "ConfigNotObject"})
                        continue
                    package = config.get("package")
                    if not isinstance(package, str) or not package:
                        continue
                    prefix = package.replace(".", "/") + "/"
                    plugin_name = config.get("plugin") or ""
                    if not isinstance(plugin_name, str):
                        errors.append({"jar": label, "config": name, "error": "InvalidPluginType"})
                        continue
                    plugin = plugin_name.replace(".", "/") + ".class"
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
                                    "discovery": {"manifest": name in registered, "name_convention": name in conventions},
                                    "ordinary_top_level_candidates": candidates,
                                    "unannotated_inner_classes": inner,
                                    "bootstrap_plugin_excluded": config.get("plugin")})
            for name in names:
                if name.startswith("META-INF/jarjar/") and name.endswith(".jar"):
                    archive(label + "!" + name, jar.read(name))

    if source.suffix == ".mrpack":
        with zipfile.ZipFile(source) as pack:
            for name in sorted(pack.namelist()):
                if name.startswith("overrides/mods/") and name.endswith(".jar"):
                    archive(name.rsplit("/", 1)[-1], pack.read(name))
    else:
        archive(source.name, source.read_bytes())
    for reference in external:
        matches = [report for report in reports if report["config"] == reference["config"]]
        reference["matching_config_archives"] = [report["jar"] for report in matches]
        for report in matches:
            report["discovery"]["manifest"] = True
            report.setdefault("external_manifest_registrations", []).append(reference["registering_jar"])
    return {"scope": __doc__.strip(), "archives": archives,
            "scope_limits": "Class/package matching is within each config archive. External manifest registrations are matched against configs discovered in this input; unresolved external resources and strict-JSON parse failures remain unverified.",
            "config_count": len(reports), "parse_errors": errors,
            "external_manifest_references": external, "configs": reports}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print(json.dumps(scan(args.source), indent=2))
