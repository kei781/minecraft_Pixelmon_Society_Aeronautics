#!/usr/bin/env python3
"""Prepare a hash-verified experimental integration in a fresh local directory."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "Personal-Pixelmon-Society-Aeronautics-Integration/0.1"
COMMIT = "5e7c8fa9073a86f9ac74c7cbf087551e5872016c"
PINNED = {"pixelmon": "9.4.1", "create-aeronautics": "1.3.2+mc1.21.1", "sable": "2.0.6+mc1.21.1"}
# Plentiful Ponds calls these common APIs. Its older embedded copies otherwise
# shadow the versions required by Starcatcher and Selling Bin on the server.
SERVER_REQUIRED = {"fancy-tab-sections", "libtooltips"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_upstream():
    upstream = ROOT / "upstream/society"
    revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=all"], text=True).strip()
    if revision != COMMIT or dirty:
        raise ValueError("Society checkout must be clean and match the audited commit")


def external_artifacts():
    artifacts = read_json(ROOT / "external-artifacts.json")["artifacts"]
    missing = []
    for item in artifacts:
        path = ROOT / "inputs" / item["filename"]
        if not path.is_file():
            missing.append(item["filename"])
            continue
        data = path.read_bytes()
        original = hashlib.sha1(data).hexdigest() == item["sha1"]
        build = item.get("source_build", {})
        candidate = (len(data) == build.get("size")
                     and hashlib.sha256(data).hexdigest() == build.get("sha256"))
        if not (original or candidate):
            missing.append(item["filename"])
    if missing:
        raise ValueError("Society development artifacts missing or hash mismatch: " + ", ".join(missing))
    return artifacts


def download(url, dest, hashes, expected_size=None):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise ValueError("HTTPS required: " + url)
    # Some upstream lock entries contain unescaped spaces in the URL path.
    url = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=-._~")))
    dest.parent.mkdir(parents=True, exist_ok=True)

    def valid(path):
        if not path.is_file():
            return False
        if expected_size is not None and path.stat().st_size != expected_size:
            return False
        checks = {name: hashlib.new(name) for name in hashes if name in {"sha1", "sha256", "sha512"}}
        if not checks:
            raise ValueError("No supported upstream hash: " + url)
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                for check in checks.values():
                    check.update(block)
        return all(check.hexdigest() == hashes[name].lower() for name, check in checks.items())

    if valid(dest):
        return dest
    partial = dest.with_name(dest.name + "." + str(os.getpid()) + ".partial")
    for attempt in range(3):
        if valid(dest):
            return dest
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
                if urllib.parse.urlsplit(response.geturl()).scheme != "https":
                    raise ValueError("Download redirected outside HTTPS")
                shutil.copyfileobj(response, output)
            if not valid(partial):
                raise ValueError("Upstream hash/size mismatch: " + dest.name)
            os.replace(partial, dest)
            return dest
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def make_lock():
    upstream = ROOT / "upstream/society"
    verify_upstream()
    source = read_json(upstream / "pakku-lock.json")
    config = read_json(upstream / "pakku.json")
    metadata = read_json(ROOT / "evidence/society-modrinth-projects.json")
    client_only = {p["id"] for p in metadata if p["server_side"] == "unsupported"}
    if source["mc_versions"] != ["1.21.1"] or source["loaders"] != {"Neoforge": "21.1.262"}:
        raise ValueError("Unexpected Society Minecraft/loader target")
    files = []
    for project in source["projects"]:
        slug = project["slug"].get("curseforge") or project["slug"].get("modrinth")
        candidates = sorted(project["files"], key=lambda file: file["type"] != "modrinth")
        item = candidates[0]
        filename = item["file_name"]
        if Path(filename).name != filename or "\\" in filename:
            raise ValueError("Unsafe upstream filename: " + filename)
        kind = project["type"]
        folder = {"MOD": "mods", "RESOURCE_PACK": "resourcepacks", "SHADER": "shaderpacks"}[kind]
        side = config["projects"].get(slug, {}).get("side", "BOTH").lower()
        if kind != "MOD" or project.get("id", {}).get("modrinth") in client_only:
            side = "client"
        if slug in SERVER_REQUIRED:
            side = "both"
        files.append({"project": slug, "name": next(iter(project["name"].values())), "path": folder + "/" + filename,
                      "url": item["url"], "hashes": item["hashes"], "size": item["size"], "side": side,
                      "source": "Society project-honey upstream lock"})
        if slug in SERVER_REQUIRED:
            files[-1]["side_override_reason"] = "Common API dependency of source-built Plentiful Ponds; see evidence/source-build-verification.json"
    for slug, version in PINNED.items():
        versions = read_json(ROOT / "evidence" / (slug + "-versions.json"))
        matches = [v for v in versions if v["version_number"] == version and "1.21.1" in v["game_versions"] and "neoforge" in v["loaders"]]
        if len(matches) != 1:
            raise ValueError("Pinned version not uniquely found: " + slug)
        file = next(f for f in matches[0]["files"] if f["primary"])
        files.append({"project": slug, "name": slug, "path": "mods/" + file["filename"], "url": file["url"],
                      "hashes": file["hashes"], "size": file["size"], "side": "both", "source": "Modrinth " + matches[0]["id"]})
    paths = [f["path"] for f in files]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate install paths")
    lock = {"schema": 1, "status": "experimental-unverified", "minecraft": "1.21.1", "neoforge": "21.1.262",
            "society_commit": COMMIT, "files": files}
    (ROOT / "integration-lock.json").write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Locked", len(files), "files; no launch has been validated.", flush=True)


def fetch(side):
    lock = read_json(ROOT / "integration-lock.json")
    selected = [f for f in lock["files"] if f["side"] in {"both", side}]
    failures = []

    def work(file):
        supported = {k: v for k, v in file["hashes"].items() if k in {"sha1", "sha256", "sha512"}}
        key = supported.get("sha512") or supported.get("sha256") or supported["sha1"]
        dest = ROOT / "cache" / key / Path(file["path"]).name
        download(file["url"], dest, supported, file["size"])
        return file["project"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        pending = {pool.submit(work, file): file for file in selected}
        for index, future in enumerate(as_completed(pending), 1):
            file = pending[future]
            try:
                future.result()
                if index % 20 == 0 or index == len(selected):
                    print(str(index) + "/" + str(len(selected)) + " verified", flush=True)
            except Exception as exc:
                failures.append({"project": file["project"], "error": str(exc)})
                print("FAILED", file["project"], str(exc), flush=True)
    report = {"side": side, "lock_sha256": hashlib.sha256((ROOT / "integration-lock.json").read_bytes()).hexdigest(),
              "selected": len(selected), "failures": failures}
    (ROOT / "evidence" / ("download-" + side + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    if failures:
        raise RuntimeError(str(len(failures)) + " required downloads failed; no files were silently omitted")


def stage(side):
    verify_upstream()
    artifacts = external_artifacts()
    lock = read_json(ROOT / "integration-lock.json")
    target = ROOT / ("server" if side == "server" else "client-test")
    if target.exists():
        raise ValueError("Staging requires a fresh directory: " + str(target))
    selected = [f for f in lock["files"] if f["side"] in {"both", side}]
    patch_report = read_json(ROOT / "evidence/creativecore-patch.json")
    patched_core = ROOT / "compat/creativecore/CreativeCore_NEOFORGE_v2.13.51_mc1.21.1-psa-codec1.jar"
    if not patched_core.is_file() or hashlib.sha256(patched_core.read_bytes()).hexdigest() != patch_report["patched_sha256"]:
        raise ValueError("Verified CreativeCore compatibility build required; run tools/build_compat.py first")
    # Validate every input before creating a target or copying configuration.
    sources = []
    for file in selected:
        hashes = {k: v for k, v in file["hashes"].items() if k in {"sha1", "sha256", "sha512"}}
        key = hashes.get("sha512") or hashes.get("sha256") or hashes["sha1"]
        source = ROOT / "cache" / key / Path(file["path"]).name
        download(file["url"], source, hashes, file["size"])
        rel = Path(file["path"])
        if rel.is_absolute() or ".." in rel.parts or "\\" in str(rel):
            raise ValueError("Unsafe install path")
        if file["project"] == "creativecore":
            if file["hashes"].get("sha512") != patch_report["original_sha512"]:
                raise ValueError("CreativeCore patch original hash differs from source lock")
            sources.append((patched_core, target / "mods" / patched_core.name))
        else:
            sources.append((source, target / rel))
    target.mkdir()
    for source, dest in sources:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for item in artifacts:
        shutil.copy2(ROOT / "inputs" / item["filename"], target / "mods" / item["filename"])
    upstream = ROOT / "upstream/society"
    for folder in ["config", "defaultconfigs", "kubejs"]:
        shutil.copytree(upstream / folder, target / folder)
    (target / ".integration-staging.json").write_text(json.dumps({"society_commit": COMMIT, "side": side}) + "\n")
    print("Staged", len(selected), "verified files in", target, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["lock", "fetch", "stage", "preflight"])
    parser.add_argument("--side", choices=["server", "client"], default="server")
    args = parser.parse_args()
    if args.command == "lock":
        make_lock()
    elif args.command == "fetch":
        fetch(args.side)
    elif args.command == "stage":
        stage(args.side)
    else:
        external_artifacts()
        print("Required Society development artifacts verified")


if __name__ == "__main__":
    main()
