"""Repair one pinned upstream item/model name mismatch using its original model."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

JAR = "mods/decorative_blocks-forge-1.20.1-4.1.3.jar"
JAR_SHA256 = "19bc47b32258dd703b808f76e7b89da1746ecddaec4ad2bd5eaa356c0d2b3d87"
MODEL = "assets/decorative_blocks/models/item/blockstate_copy_tool.json"
MODEL_SHA256 = "568a456b1b1466a3f6f25c4ad8e96d7216e334eca9479d7f5bcfc826cc63a9fc"
TEXTURE = "assets/decorative_blocks/textures/item/blockstate_copy_tool.png"
TEXTURE_SHA256 = "c254807e84c95081bc952b6190d127109548404d2eca03baf57d088eb1bbecc4"
TARGET = "assets/decorative_blocks/models/item/blockstate_copy_item.json"
PARENT = "decorative_blocks:item/blockstate_copy_tool"


def apply(overrides, files):
    """Add a client-only KubeJS asset after the original server/script inventory check."""
    source = Path(files[JAR])
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != JAR_SHA256:
        raise ValueError("Unexpected Decorative Blocks identity")
    target = "kubejs/" + TARGET
    if any(name.casefold() == target.casefold() for name in overrides):
        raise ValueError("Item model alias already supplied by KubeJS")
    expected = {MODEL: MODEL_SHA256, TEXTURE: TEXTURE_SHA256}
    with zipfile.ZipFile(source) as archive:
        for name, digest in expected.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("Original tool model/texture identity changed")
    # Another mod/pack may repair this upstream defect or replace the chosen parent.
    # Refuse to overwrite that state silently, including case collisions on Windows.
    watched = {name.casefold(): name for name in [TARGET, MODEL, TEXTURE]}
    def check_resource(name, read):
        canonical = watched.get(name.casefold())
        if canonical == TARGET:
            raise ValueError("Item model already supplied by a mod/resource pack")
        if canonical and (name != canonical or hashlib.sha256(read()).hexdigest() != expected[canonical]):
            raise ValueError("Original tool model/texture overridden by a mod/resource pack")

    def check_archive(archive, depth=0):
        for name in archive.namelist():
            check_resource(name, lambda: archive.read(name))
            if name.casefold().startswith("meta-inf/jarjar/") and name.casefold().endswith(".jar"):
                if depth >= 4:
                    raise ValueError("Nested JAR inspection depth exceeded")
                check_zip(io.BytesIO(archive.read(name)), depth + 1)

    def check_zip(source, depth=0):
        try:
            with zipfile.ZipFile(source) as archive:
                check_archive(archive, depth)
        except zipfile.BadZipFile as failure:
            raise ValueError("Invalid mod/resource pack ZIP") from failure

    for path in files.values():
        if Path(path).suffix.lower() in {".jar", ".zip"}:
            check_zip(path)
    for name, data in overrides.items():
        canonical = watched.get(name.casefold().removeprefix("kubejs/")) if name.casefold().startswith("kubejs/") else None
        if canonical and (name != "kubejs/" + canonical or canonical == TARGET
                          or hashlib.sha256(data).hexdigest() != expected[canonical]):
            raise ValueError("Original tool model/texture overridden by KubeJS")
        parts = name.split("/")
        if parts[0].casefold() == "resourcepacks":
            if len(parts) == 2 and parts[1].casefold().endswith(".zip"):
                check_zip(io.BytesIO(data))
            elif len(parts) >= 3:
                check_resource("/".join(parts[2:]), lambda: data)
    data = (json.dumps({"parent": PARENT}, indent=2) + "\n").encode()
    overrides[target] = data
    return {"item": "decorative_blocks:blockstate_copy_item", "path": target, "parent": PARENT,
            "sha256": hashlib.sha256(data).hexdigest(), "upstream_jar_sha256": JAR_SHA256,
            "original_model_sha256": MODEL_SHA256, "original_texture_sha256": TEXTURE_SHA256,
            "scope": "Original upstream tool model alias; native validation recorded separately"}
