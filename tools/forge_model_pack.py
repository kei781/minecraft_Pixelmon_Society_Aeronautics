"""Build private Forge OBJ overrides from the exact verified port JAR."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

from export_client import add_zip_file, safe_path

PACK_NAME = "PSA-Forge-Model-Compat.zip"
PACK_ID = "file/" + PACK_NAME
MODS = {"aeronautics", "offroad", "simulated", "sable"}


def build(port, expected_sha256, expected_models=17):
    port = Path(port)
    if port.is_symlink() or hashlib.sha256(port.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Unexpected port identity for model compatibility pack")
    files, changed = {}, []
    with zipfile.ZipFile(port) as archive:
        names = set(archive.namelist())
        for name in sorted(names):
            parts = name.split("/")
            if len(parts) < 5 or parts[0] != "assets" or parts[1] not in MODS or parts[2] != "models" or not name.endswith(".json"):
                continue
            document = json.loads(archive.read(name))
            loader = document.get("loader", "") if isinstance(document, dict) else ""
            if not isinstance(loader, str) or not loader.startswith("neoforge:"):
                continue
            if loader != "neoforge:obj":
                raise ValueError("Unsupported NeoForge model loader: " + name)
            model = document.get("model")
            if not isinstance(model, str) or model.count(":") != 1:
                raise ValueError("An explicit OBJ resource is required: " + name)
            namespace, path = model.split(":")
            obj = safe_path("assets/" + namespace + "/" + path)
            if namespace not in MODS or not path.startswith("models/") or not path.endswith(".obj") or obj not in names:
                raise ValueError("Missing or unexpected OBJ resource: " + name)
            document["loader"] = "forge:obj"
            files[safe_path(name)] = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode()
            changed.append({"path": name, "model": model,
                            "original_sha256": hashlib.sha256(archive.read(name)).hexdigest(),
                            "override_sha256": hashlib.sha256(files[name]).hexdigest()})
    if len(changed) != expected_models:
        raise ValueError("Unexpected NeoForge OBJ model inventory")
    files["pack.mcmeta"] = (json.dumps({"pack": {"pack_format": 15,
        "description": "PSA Forge 1.20.1 model loader compatibility"}}, indent=2) + "\n").encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in sorted(files.items()):
            add_zip_file(archive, name, data)
    data = output.getvalue()
    return data, {"filename": PACK_NAME, "pack_id": PACK_ID, "port_sha256": expected_sha256,
                  "sha256": hashlib.sha256(data).hexdigest(), "models": changed}


def enable(overrides, data):
    """Enable on first import and retain the pack's existing default selections."""
    target = "resourcepacks/" + PACK_NAME
    if target in overrides:
        raise ValueError("Model compatibility resource pack already exists")
    config = "config/resourcepackoverrides.json"
    document = json.loads(overrides[config])
    packs, settings = document.get("default_packs"), document.get("pack_overrides")
    if document.get("schema_version") != 2 or not isinstance(packs, list) or not all(isinstance(p, str) for p in packs) or not isinstance(settings, dict):
        raise ValueError("Unsupported Resource Pack Overrides configuration")
    if PACK_ID in packs or PACK_ID in settings:
        raise ValueError("Unexpected existing model pack configuration")
    packs.append(PACK_ID)
    settings[PACK_ID] = {"hidden": False, "required": True}
    options = "configureddefaults/options.txt"
    lines = overrides[options].decode().splitlines()
    indices = [i for i, line in enumerate(lines) if line.startswith("resourcePacks:")]
    if len(indices) != 1:
        raise ValueError("Exactly one default resource pack selection is required")
    index = indices[0]
    selected = json.loads(lines[index].split(":", 1)[1])
    if not isinstance(selected, list) or not all(isinstance(p, str) for p in selected) or PACK_ID in selected:
        raise ValueError("Invalid existing resource pack selection")
    selected.append(PACK_ID)
    lines[index] = "resourcePacks:" + json.dumps(selected, separators=(",", ":"))
    overrides[config] = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode()
    overrides[options] = ("\n".join(lines) + "\n").encode()
    overrides[target] = data
