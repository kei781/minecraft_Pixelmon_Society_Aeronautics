"""Repair one pinned upstream item/model name mismatch using its original model."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from export_client import safe_path

JAR = "mods/decorative_blocks-forge-1.20.1-4.1.3.jar"
JAR_SHA256 = "19bc47b32258dd703b808f76e7b89da1746ecddaec4ad2bd5eaa356c0d2b3d87"
MODEL = "assets/decorative_blocks/models/item/blockstate_copy_tool.json"
MODEL_SHA256 = "568a456b1b1466a3f6f25c4ad8e96d7216e334eca9479d7f5bcfc826cc63a9fc"
TEXTURE = "assets/decorative_blocks/textures/item/blockstate_copy_tool.png"
TEXTURE_SHA256 = "c254807e84c95081bc952b6190d127109548404d2eca03baf57d088eb1bbecc4"
TARGET = "assets/decorative_blocks/models/item/blockstate_copy_item.json"
PARENT = "decorative_blocks:item/blockstate_copy_tool"
ADDITIONAL_ITEMS = {"displaydelight:beetroot_soup", "displaydelight:mushroom_stew",
                    "displaydelight:rabbit_stew", "verdantvibes:potted_burnweed", "vintagedelight:vinegar_jar"}


def apply_verified(overrides, files, *, jar, jar_sha256, target_path, parent, resources, item):
    """Reference a pinned original model after the original server/script inventory check."""
    source = Path(files[jar])
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != jar_sha256:
        raise ValueError("Unexpected original model archive identity")
    target = "kubejs/" + target_path
    if any(name.casefold() == target.casefold() for name in overrides):
        raise ValueError("Item model alias already supplied by KubeJS")
    expected = dict(resources)
    with zipfile.ZipFile(source) as archive:
        for name, digest in expected.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("Original tool model/texture identity changed")
    # Another mod/pack may repair this upstream defect or replace the chosen parent.
    # Refuse to overwrite that state silently, including case collisions on Windows.
    watched = {name.casefold(): name for name in [target_path, *expected]}
    def check_resource(name, read):
        canonical = watched.get(name.casefold())
        if canonical == target_path:
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
        if canonical and (name != "kubejs/" + canonical or canonical == target_path
                          or hashlib.sha256(data).hexdigest() != expected[canonical]):
            raise ValueError("Original tool model/texture overridden by KubeJS")
        parts = name.split("/")
        if parts[0].casefold() == "resourcepacks":
            if len(parts) == 2 and parts[1].casefold().endswith(".zip"):
                check_zip(io.BytesIO(data))
            elif len(parts) >= 3:
                check_resource("/".join(parts[2:]), lambda: data)
    data = (json.dumps({"parent": parent}, indent=2) + "\n").encode()
    overrides[target] = data
    return {"item": item, "path": target, "parent": parent,
            "sha256": hashlib.sha256(data).hexdigest(), "upstream_jar_sha256": jar_sha256,
            "original_resources": expected,
            "scope": "Original matching model alias; native validation recorded separately"}


def apply(overrides, files):
    """Preserve the accepted Decorative Blocks alias and its exact receipt format."""
    receipt = apply_verified(overrides, files, jar=JAR, jar_sha256=JAR_SHA256,
                             target_path=TARGET, parent=PARENT,
                             resources={MODEL: MODEL_SHA256, TEXTURE: TEXTURE_SHA256},
                             item="decorative_blocks:blockstate_copy_item")
    return {"item": receipt["item"], "path": receipt["path"], "parent": receipt["parent"],
            "sha256": receipt["sha256"], "upstream_jar_sha256": JAR_SHA256,
            "original_model_sha256": MODEL_SHA256, "original_texture_sha256": TEXTURE_SHA256,
            "scope": "Original upstream tool model alias; native validation recorded separately"}


def apply_additional(overrides, files, spec_path):
    """Validate the complete pinned batch before committing any additional client asset."""
    specs = json.loads(Path(spec_path).read_text())
    if not isinstance(specs, list) or len(specs) != len(ADDITIONAL_ITEMS) or {s["item"] for s in specs} != ADDITIONAL_ITEMS:
        raise ValueError("Unexpected additional item model inventory")
    staged = dict(overrides)
    receipts = []
    for spec in specs:
        namespace, name = spec["item"].split(":")
        if (spec["target_path"] != "assets/" + namespace + "/models/item/" + name + ".json"
                or not spec["parent"].startswith(namespace + ":block/")):
            raise ValueError("An original matching block model is required")
        parent_path = "assets/" + spec["parent"].replace(":", "/models/") + ".json"
        if parent_path not in spec["resources"]:
            raise ValueError("Pinned original parent provenance required")
        validate_dependencies(spec, files)
        receipt = apply_verified(staged, files, **{k:v for k,v in spec.items() if k != "vanilla_dependencies"})
        receipt["vanilla_dependencies"] = list(spec["vanilla_dependencies"])
        receipts.append(receipt)
    overrides.update(staged)
    return receipts


def validate_dependencies(spec, files):
    """Require complete original model/texture references, separating vanilla resources."""
    vanilla = spec.get("vanilla_dependencies")
    if (not isinstance(vanilla, list) or not all(isinstance(path, str) and path.startswith("assets/minecraft/")
            and path.endswith((".json", ".png")) for path in vanilla) or len(vanilla) != len(set(vanilla))):
        raise ValueError("Explicit unique vanilla dependency paths required")
    for path in vanilla:
        safe_path(path)
    source = Path(files[spec["jar"]])
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != spec["jar_sha256"]:
        raise ValueError("Unexpected original model archive identity")
    observed_vanilla = set()
    resources = spec["resources"]
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        for path in resources:
            safe_path(path)
            if not path.startswith("assets/") or not path.endswith((".json", ".png")):
                raise ValueError("Only original model/texture resources may be pinned")
            if not path.endswith(".json"):
                continue
            model = json.loads(archive.read(path))
            references = []
            if model.get("parent"):
                references.append((model["parent"], "models/", ".json"))
            for value in model.get("textures", {}).values():
                if not isinstance(value, str):
                    raise ValueError("Invalid original texture reference")
                if not value.startswith("#"):
                    references.append((value, "textures/", ".png"))
            for value, folder, suffix in references:
                namespace, name = value.split(":") if ":" in value else ("minecraft", value)
                if namespace == "minecraft" and name in {"builtin/generated", "builtin/entity"} and folder == "models/":
                    continue
                reference = safe_path("assets/" + namespace + "/" + folder + name + suffix)
                if reference in resources:
                    continue
                if reference not in names and namespace == "minecraft" and reference in vanilla:
                    observed_vanilla.add(reference)
                    continue
                raise ValueError("Unpinned original model/texture dependency: " + reference)
    if observed_vanilla != set(vanilla):
        raise ValueError("Unused or missing vanilla dependency provenance")
