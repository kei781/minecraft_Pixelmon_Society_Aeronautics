"""Pinned no-op loot-list normalization and optional authored server-only recipient module."""
import hashlib
import json
from pathlib import Path
import shutil

RESOURCE = "kubejs/data/forge/loot_modifiers/global_loot_modifiers.json"
RESOURCE_SHA256 = "46c89c99252c03e37a923ac4a0f78b92cb59622a4cf8fc762eb11babde0a3f76"
MODULE_PATH = "mods/PSA-Datapack-Sync-Compat-0.1.jar"
MODULE_SHA256 = "02ef84d99f5cbd086624403160a6e0ba4cd2c87516874692f1e1cdcc4f5d948d"
TARGET_PATH = "mods/serializer_debug-1.0.1.jar"
TARGET_SHA256 = "fe77df10d803e08c95b9d47608444982629d2a426d1f74ac41ec569eb8fe96a8"


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            result.update(block)
    return result.hexdigest()


def normalize_resource(data):
    if not isinstance(data, bytes) or hashlib.sha256(data).hexdigest() != RESOURCE_SHA256:
        raise ValueError("Pinned original global loot modifier list required")
    original = json.loads(data)
    if original != {"forge:conditions": [{"type": "forge:false"}]}:
        raise ValueError("Only the original condition-only no-op list may be normalized")
    original.update({"replace": False, "entries": []})
    corrected = (json.dumps(original, indent=2) + "\n").encode()
    return corrected, {"path": RESOURCE, "original_sha256": RESOURCE_SHA256,
        "sha256": hashlib.sha256(corrected).hexdigest(), "replace": False, "entries": 0,
        "original_conditions_preserved": True}


def apply_overrides(files):
    corrected, receipt = normalize_resource(files.get(RESOURCE))
    files[RESOURCE] = corrected
    return receipt


def apply_directory(root):
    root = Path(root)
    target = root
    for component in Path(RESOURCE).parts:
        target = target / component
        if target.is_symlink():
            raise ValueError("Regular staged loot modifier path required")
    if not target.is_file():
        raise ValueError("Pinned original global loot modifier list missing")
    corrected, receipt = normalize_resource(target.read_bytes())
    target.write_bytes(corrected)
    return receipt


def verify_module_file(source):
    source = Path(source)
    if source.is_symlink() or source.parent.is_symlink() or not source.is_file() or digest(source) != MODULE_SHA256:
        raise ValueError("Pinned authored server datapack module required")


def module_receipt():
    return {"path": MODULE_PATH, "sha256": MODULE_SHA256, "server_only": True,
        "source": "compat/datapack-sync", "target_sha256": TARGET_SHA256}


def verify_target(root):
    target = Path(root) / TARGET_PATH
    if target.is_symlink() or target.parent.is_symlink() or not target.is_file() or digest(target) != TARGET_SHA256:
        raise ValueError("Pinned original SerializerDebug target required")


def install_module(root, source):
    verify_module_file(source)
    verify_target(root)
    target = Path(root) / MODULE_PATH
    if target.exists() or target.is_symlink():
        raise ValueError("Fresh server-only compatibility path required")
    with Path(source).open("rb") as input_stream, target.open("xb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream)
    return module_receipt()


def verify_staged_module(root, declaration):
    target = Path(root) / MODULE_PATH
    if not target.exists() and not target.is_symlink():
        if declaration is not None:
            raise ValueError("Declared server datapack module missing")
        return None
    if declaration != module_receipt():
        raise ValueError("Exact staged server datapack declaration required")
    verify_module_file(target)
    verify_target(root)
    return module_receipt()
