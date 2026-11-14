"""Add the coexistence overlay to a staged profile.

The overlay is a small tree of tracked files (tags, one template pool, worldgen
modifiers, KubeJS server scripts) that none of the three projects ships and that
repair proven gaps between them, plus the four Radium (Lithium) options the
Aeronautics port declares in a part of its mods.toml that Radium never reads.

Nothing of Society's is replaced except config/lithium.properties, which only
gains lines. Each overlay file exists because of a specific fact in the pinned
inputs; those facts are listed in compat/coexistence/preconditions.json and are
re-checked on every run, so a changed upstream file stops staging instead of
leaving a stale repair in place.
"""
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "compat/coexistence/overlay"
PRECONDITIONS = ROOT / "compat/coexistence/preconditions.json"
LITHIUM_PATH = "config/lithium.properties"
LITHIUM_SHA256 = "09759af4787e05f7d6f2eac3bd19fe5c79f4676444f568820814a93ca7e6b265"
# Declared by the port under a top-level ["lithium:options"] table; Radium only reads per-mod tables.
LITHIUM_OPTIONS = ("mixin.entity.collisions.unpushable_cramming", "mixin.world.chunk_access",
                   "mixin.world.chunk_ticking", "mixin.world.tick_scheduler")
PORT_MODS_TOML = "META-INF/mods.toml"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def overlay_files():
    """{profile path: bytes} of the tracked overlay tree."""
    if OVERLAY.is_symlink() or not OVERLAY.is_dir():
        raise ValueError("Tracked coexistence overlay required")
    files = {}
    for path in sorted(OVERLAY.rglob("*")):
        if path.is_symlink():
            raise ValueError("Regular overlay files required")
        if path.is_file() and path.name != ".DS_Store":
            name = path.relative_to(OVERLAY).as_posix()
            if not name.startswith("kubejs/"):
                raise ValueError("Overlay files belong under kubejs/: " + name)
            if name.endswith(".json"):
                json.loads(path.read_text())  # a broken JSON file must never reach a profile
            files[name] = path.read_bytes()
    if not files:
        raise ValueError("Empty coexistence overlay")
    return files


def _archive(source, pixelmon_jar, port_jar, read_society):
    if source == "pixelmon":
        return zipfile.ZipFile(pixelmon_jar)
    if source == "port":
        return zipfile.ZipFile(port_jar)
    if not source.startswith("mods/") or not source.endswith(".jar"):
        raise ValueError("Unknown precondition source: " + source)
    data = read_society(source)
    if data is None:
        raise ValueError("Coexistence precondition failed: missing " + source)
    return zipfile.ZipFile(io.BytesIO(data))


def check_preconditions(pixelmon_jar, port_jar, read_society):
    """Every recorded upstream fact must still hold. Returns the number of facts checked."""
    facts = json.loads(PRECONDITIONS.read_text())
    if not isinstance(facts, list) or not facts:
        raise ValueError("Coexistence preconditions required")
    for fact in facts:
        label = "%s %s" % (fact.get("jar", "society"), fact.get("entry", fact.get("file")))
        if "file" in fact:
            data = read_society(fact["file"])
        else:
            with _archive(fact["jar"], pixelmon_jar, port_jar, read_society) as archive:
                data = archive.read(fact["entry"]) if fact["entry"] in archive.namelist() else None
        if fact.get("absent"):
            holds = data is None
        elif "sha256" in fact:
            holds = data is not None and sha256(data) == fact["sha256"]
        elif "contains" in fact:
            holds = data is not None and all(text.encode() in data for text in fact["contains"])
        else:
            raise ValueError("Precondition without a test: " + label)
        if not holds:
            raise ValueError("Coexistence precondition failed: " + label)
    return len(facts)


def lithium_config(original, port_jar):
    """Society's Radium config plus the options the port declares but Radium never sees."""
    if not isinstance(original, bytes) or sha256(original) != LITHIUM_SHA256:
        raise ValueError("Pinned original Radium configuration required")
    with zipfile.ZipFile(port_jar) as archive:
        declared = archive.read(PORT_MODS_TOML).decode()
    table = declared.split('["lithium:options"]', 1)
    lines = table[1].split("[[", 1)[0].split("[", 1)[0].splitlines() if len(table) == 2 else []
    options = tuple(line.split("=")[0].strip().strip('"') for line in lines
                    if line.strip() and line.split("=")[-1].strip() == "false")
    if options != LITHIUM_OPTIONS:
        raise ValueError("Port no longer declares the pinned Lithium options")
    return original + "".join("\r\n%s=false" % option for option in LITHIUM_OPTIONS).encode()


def plan(pixelmon_jar, port_jar, read_society):
    """Return ({profile path: bytes}, receipt). `read_society(path)` yields original profile bytes or None."""
    checked = check_preconditions(pixelmon_jar, port_jar, read_society)
    outputs = overlay_files()
    for path in outputs:
        if read_society(path) is not None:
            raise ValueError("Coexistence overlay path already used: " + path)
    files = [{"path": path, "sha256": sha256(data)} for path, data in sorted(outputs.items())]
    config = lithium_config(read_society(LITHIUM_PATH), port_jar)
    outputs[LITHIUM_PATH] = config
    receipt = {"files": files, "preconditions_checked": checked,
               "radium_config": {"path": LITHIUM_PATH, "original_sha256": LITHIUM_SHA256, "sha256": sha256(config),
                                 "disabled_options": list(LITHIUM_OPTIONS)}}
    return outputs, receipt


def apply_overrides(files, pixelmon_jar, port_jar, read_mod=None):
    """Apply to a {profile path: bytes} mapping (client export). The mapping changes only on success."""
    def read(path):
        if path.startswith("mods/") and read_mod is not None:
            return read_mod(path)
        return files.get(path)
    outputs, receipt = plan(pixelmon_jar, port_jar, read)
    files.update(outputs)
    return receipt


def _regular(root, path):
    """Location below root that is reached through real folders only: no symbolic link, no file in place of a folder."""
    target, parts = Path(root), Path(path).parts
    for index, component in enumerate(parts):
        target = target / component
        if target.is_symlink() or (index + 1 < len(parts) and target.exists() and not target.is_dir()):
            raise ValueError("Regular staged overlay path required")
    return target


def apply_directory(root, pixelmon_jar, port_jar):
    """Apply to an extracted profile whose files are Society's originals."""
    def read(path):
        target = _regular(root, path)
        if target.exists() and not target.is_file():
            raise ValueError("Regular staged overlay path required")
        return target.read_bytes() if target.is_file() else None
    outputs, receipt = plan(pixelmon_jar, port_jar, read)
    # Every location is checked before the first write.
    targets = [(_regular(root, path), data) for path, data in outputs.items()]
    if any(target.exists() and not target.is_file() for target, _ in targets):
        raise ValueError("Regular staged overlay path required")
    for target, data in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return receipt


def verify_staged(root, declaration):
    """A profile carries either none of the overlay (and the original Radium config) or exactly what it declares."""
    config = _regular(root, LITHIUM_PATH)
    if declaration is None:
        for path in overlay_files():
            if _regular(root, path).exists():
                raise ValueError("Undeclared coexistence overlay content: " + path)
        if config.is_file() and sha256(config.read_bytes()) != LITHIUM_SHA256:
            raise ValueError("Undeclared Radium configuration change")
        return None
    for entry in declaration["files"] + [declaration["radium_config"]]:
        target = _regular(root, entry["path"])
        if not target.is_file() or sha256(target.read_bytes()) != entry["sha256"]:
            raise ValueError("Declared coexistence content differs: " + entry["path"])
    return declaration


def record(pixelmon_jar, port_jar, server_pack):
    """Hashes of every output for the pinned inputs, as kept in compat/coexistence-build.json."""
    with zipfile.ZipFile(server_pack) as archive:
        names = set(archive.namelist())
        outputs, receipt = plan(pixelmon_jar, port_jar, lambda path: archive.read(path) if path in names else None)
    return {"scope": "Coexistence overlay (tags, one template pool, worldgen modifier, KubeJS server scripts) and the "
                     "Radium options the Aeronautics port declares; derived data only, no mod JAR changes",
            "inputs": {"pixelmon_jar_sha256": sha256(Path(pixelmon_jar).read_bytes()),
                       "port_jar_sha256": sha256(Path(port_jar).read_bytes()),
                       "society_server_pack_sha1": hashlib.sha1(Path(server_pack).read_bytes()).hexdigest()},
            "output_sha256": {path: sha256(data) for path, data in sorted(outputs.items())},
            "receipt": receipt}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixelmon", type=Path, required=True)
    parser.add_argument("--port", type=Path, required=True)
    parser.add_argument("--server-pack", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(record(arguments.pixelmon, arguments.port, arguments.server_pack), indent=2))
