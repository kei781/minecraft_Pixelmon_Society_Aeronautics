#!/usr/bin/env python3
"""Build a Prism-importable MRPack. Full integration never skips required mods."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.parse
import zipfile

import prepare

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = {"pixelmon", "create", "create-aeronautics", "sable", "kubejs", "rhino"}
RESOURCE_SOURCE = "resourcepacks/sunlit_overrides"


def safe_path(value):
    path = PurePosixPath(value)
    if not value or not path.parts or path.is_absolute() or path.as_posix() != value or "\\" in value or ".." in path.parts:
        raise ValueError("Unsafe client path: " + value)
    reserved = {"CON", "PRN", "AUX", "NUL"} | {prefix + str(n) for prefix in ["COM", "LPT"] for n in range(1, 10)}
    for part in path.parts:
        if any(ord(char) < 32 or char in ':<>"|?*' for char in part) or part.endswith((".", " ")) or part.split(".")[0].upper() in reserved:
            raise ValueError("Unsupported Windows path: " + value)
    return value


def data_bytes(value):
    return value if isinstance(value, bytes) else value.read_bytes()


def cache_file(file):
    safe_path(file["path"])
    hashes = {k: v for k, v in file["hashes"].items() if k in {"sha1", "sha256", "sha512"}}
    key = hashes.get("sha512") or hashes.get("sha256") or hashes["sha1"]
    source = ROOT / "cache" / key / Path(file["path"]).name
    return prepare.download(file["url"], source, hashes, file["size"])


def indexed_file(file, source):
    safe_path(file["path"])
    parts = urllib.parse.urlsplit(file["url"])
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("HTTPS download URL required")
    url = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=-._~")))
    hashes = {}
    for algorithm in ["sha1", "sha512"]:
        hashes[algorithm] = file["hashes"].get(algorithm) or hashlib.new(algorithm, source.read_bytes()).hexdigest()
    return {"path": file["path"], "hashes": hashes, "downloads": [url], "fileSize": file["size"],
            "env": {"client": "required", "server": "unsupported" if file["side"] == "client" else "required"}}


def add_zip_file(archive, name, value):
    safe_path(name)
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    with archive.open(info, "w", force_zip64=True) as destination:
        if isinstance(value, bytes):
            destination.write(value)
        else:
            with value.open("rb") as source:
                shutil.copyfileobj(source, destination)


def society_resource_pack(target):
    """Rebuild the missing zip from the pinned, tracked unpacked resource pack."""
    upstream = ROOT / "upstream/society"
    sources = prepare.tracked_files(upstream, [RESOURCE_SOURCE])
    if Path(RESOURCE_SOURCE + "/pack.mcmeta") not in {name for name, _ in sources}:
        raise ValueError("Pinned Society resource-pack sources are required")
    destination = target / "resourcepacks/sunlit_overrides.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError("Unexpected existing rebuilt resource pack")
    with zipfile.ZipFile(destination, "w") as archive:
        for name, source in sources:
            relative = name.relative_to(RESOURCE_SOURCE).as_posix()
            add_zip_file(archive, relative, source)
    return destination


def write_pack(output, profile, lock, files, overrides, bundle_sources=None):
    paths = [file["path"] for file in files] + list(overrides)
    for name in paths:
        safe_path(name)
    if any(name.casefold() == "psa-client-profile.json" for name in paths):
        raise ValueError("Reserved client profile metadata path")
    if len({name.casefold() for name in paths}) != len(paths):
        raise ValueError("Duplicate or Windows case-colliding client paths")
    source_downloads = files
    bundled = bundle_sources is not None
    if bundled:
        if set(bundle_sources) != {file["path"] for file in files}:
            raise ValueError("Bundled inputs must match every download entry")
        overrides = dict(overrides, **bundle_sources)
        files = []
    checks = {name: hashlib.sha256(data_bytes(value)).hexdigest() for name, value in sorted(overrides.items())}
    seed = json.dumps({"profile": profile, "files": files, "overrides": checks,
                       "source_downloads": source_downloads, "bundled": bundled,
                       "minecraft": lock["minecraft"], "neoforge": lock["neoforge"]}, sort_keys=True).encode()
    fingerprint = hashlib.sha256(seed).hexdigest()
    diagnostic = profile == "diagnostic"
    status = "diagnostic-without-society" if diagnostic else "experimental-unverified-integration"
    metadata = {"schema": 1, "profile": profile, "status": status, "complete_integration": False,
                "content_sha256": fingerprint, "lock_sha256": hashlib.sha256((ROOT / "integration-lock.json").read_bytes()).hexdigest(),
                "download_files": len(files), "bundled_downloads": bundled,
                "source_downloads": source_downloads, "overrides": checks}
    overrides = dict(overrides, **{"psa-client-profile.json": (json.dumps(metadata, indent=2) + "\n").encode()})
    index = {"formatVersion": 1, "game": "minecraft", "versionId": profile + "-" + fingerprint[:12],
             "name": "PSA Diagnostic - Pixelmon + Aeronautics (NO Society)" if diagnostic else "Pixelmon + Society + Aeronautics - Experimental",
             "summary": "Diagnostic only. Society is not included." if diagnostic else "Experimental integration; gameplay validation is required.",
             "dependencies": {"minecraft": lock["minecraft"], "neoforge": lock["neoforge"]}, "files": files}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".mrpack-", suffix=".partial", dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            add_zip_file(archive, "modrinth.index.json", (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode())
            for name, value in sorted(overrides.items()):
                add_zip_file(archive, "overrides/" + name, value)
        temporary.chmod(0o644)
        # Exclusive publication: a concurrent/exported file is never overwritten.
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": str(output), "profile": profile, "status": status, "version_id": index["versionId"],
            "downloads": len(files), "bundled_downloads": bundled,
            "override_files": len(overrides), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def build(profile, output, bundle_downloads=False):
    output = Path(output).expanduser().absolute()
    if output.suffix.lower() != ".mrpack":
        raise ValueError("Output must have the .mrpack extension")
    if output.exists() or output.is_symlink():
        raise ValueError("Refusing to overwrite existing export: " + str(output))
    lock = prepare.read_json(ROOT / "integration-lock.json")
    selected = [file for file in lock["files"] if file["side"] in {"both", "client"}]
    if profile == "diagnostic":
        selected = [file for file in selected if file["project"] in DIAGNOSTIC]
        if len(selected) != len(DIAGNOSTIC) or {file["project"] for file in selected} != DIAGNOSTIC:
            raise ValueError("The six pinned diagnostic projects must all be present")
        sources = {file["path"]: cache_file(file) for file in selected}
        pixelmon = next(file for file in selected if file["project"] == "pixelmon")
        overrides = prepare.mob_overrides(sources[pixelmon["path"]])
        overrides["DIAGNOSTIC-NOT-FULL-PACK.txt"] = b"Diagnostic client for Pixelmon + Create Aeronautics. Society is NOT included.\n"
        files = [indexed_file(file, sources[file["path"]]) for file in sorted(selected, key=lambda file: file["path"])]
        return write_pack(output, profile, lock, files, overrides, sources if bundle_downloads else None)
    if profile != "integration":
        raise ValueError("Unknown client profile")
    # Fail before creating staging/output directories when required content is absent.
    prepare.verify_upstream()
    prepare.external_artifacts()
    (ROOT / "cache").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="client-export-", dir=ROOT / "cache") as scratch:
        staged = prepare.stage("client", target=Path(scratch) / "client")
        society_resource_pack(staged)
        indexed = [file for file in selected if file["project"] != "creativecore"]
        files = [indexed_file(file, staged / file["path"]) for file in sorted(indexed, key=lambda file: file["path"])]
        paths = {file["path"] for file in indexed}
        overrides = {}
        for source in staged.rglob("*"):
            if source.is_symlink():
                raise ValueError("Staging must not contain symlinks")
            if source.is_file():
                relative = source.relative_to(staged).as_posix()
                if relative not in paths:
                    overrides[relative] = source
        bundles = {file["path"]: staged / file["path"] for file in indexed} if bundle_downloads else None
        return write_pack(output, profile, lock, files, overrides, bundles)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=["diagnostic", "integration"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle-downloads", action="store_true", help="Include verified downloads for a private single-file import")
    args = parser.parse_args()
    filename = "PSA-DIAGNOSTIC-NO-SOCIETY" if args.profile == "diagnostic" else "PSA-integration"
    output = args.output or ROOT / "dist" / (filename + ("-bundled" if args.bundle_downloads else "") + ".mrpack")
    print(json.dumps(build(args.profile, output, args.bundle_downloads), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
