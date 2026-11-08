#!/usr/bin/env python3
"""Install pinned Linux x64 Java/Forge inside an owned PSA profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import posixpath
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request


def verify(path, item):
    lengths = {"sha1": 40, "sha256": 64, "sha512": 128}
    hashes = item.get("hashes")
    if (not isinstance(hashes, dict) or not hashes
            or any(a not in lengths or not isinstance(v, str) or not re.fullmatch("[0-9a-f]{%d}" % lengths[a], v)
                   for a, v in hashes.items())):
        raise ValueError("Pinned runtime hashes are required")
    if path.stat().st_size != item["size"]:
        raise ValueError("Runtime size mismatch")
    for algorithm, expected in item["hashes"].items():
        value = hashlib.new(algorithm)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                value.update(chunk)
        if value.hexdigest() != expected:
            raise ValueError("Runtime hash mismatch")


def download(item, directory):
    target = directory / item["filename"]
    if target.is_symlink():
        raise ValueError("Runtime cache symlinks are not allowed")
    if target.exists():
        verify(target, item)
        return target
    with tempfile.NamedTemporaryFile(prefix="download-", dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            request = urllib.request.Request(item["url"], headers={"User-Agent": "Gradle/7.6.4"})
            with urllib.request.urlopen(request, timeout=120) as response:
                shutil.copyfileobj(response, stream)
            stream.flush()
            verify(temporary, item)
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def install(profile, lock_file):
    profile = Path(profile).resolve(strict=True)
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise ValueError("This installer targets Linux x64")
    if not (profile / ".psa-owned-smoke-test").is_file() or not (profile / ".psa-forge-candidate.json").is_file():
        raise ValueError("An owned staged candidate is required")
    lock = json.loads(Path(lock_file).read_text())
    runtime = profile / "runtime"
    runtime.mkdir(exist_ok=True)
    if runtime.is_symlink():
        raise ValueError("Runtime must be a real directory")
    cache = runtime / "cache"
    cache.mkdir(exist_ok=True)
    if cache.is_symlink():
        raise ValueError("Runtime cache must be a real directory")
    java_archive = download(lock["java"], cache)
    installer = download(lock["forge"], cache)
    java_dir = runtime / lock["java"]["directory"]
    java_receipt = runtime / ".psa-jdk.json"
    if java_dir.is_symlink():
        raise ValueError("Unexpected existing Java directory link")
    if not java_dir.exists():
        with tempfile.TemporaryDirectory(prefix="jdk-", dir=runtime) as scratch:
            with tarfile.open(java_archive, "r:gz") as archive:
                for member in archive.getmembers():
                    name = PurePosixPath(member.name)
                    if (name.is_absolute() or ".." in name.parts or not name.parts
                            or name.parts[0] != java_dir.name or not (member.isfile() or member.isdir() or member.issym() or member.islnk())):
                        raise ValueError("Unsafe Java archive entry")
                    if member.issym() or member.islnk():
                        base = posixpath.dirname(member.name) if member.issym() else ""
                        resolved = posixpath.normpath(posixpath.join(base, member.linkname))
                        if not (resolved == java_dir.name or resolved.startswith(java_dir.name + "/")):
                            raise ValueError("Java archive link leaves its directory")
                archive.extractall(scratch)
            (Path(scratch) / java_dir.name).rename(java_dir)
        java_receipt.write_text(json.dumps({"archive_hashes": lock["java"]["hashes"],
            "java_binary_sha256": hashlib.sha256((java_dir / "bin/java").read_bytes()).hexdigest()}, indent=2) + "\n")
    java = java_dir / "bin/java"
    trusted = json.loads(java_receipt.read_text())
    if (trusted["archive_hashes"] != lock["java"]["hashes"]
            or trusted["java_binary_sha256"] != hashlib.sha256(java.read_bytes()).hexdigest()):
        raise ValueError("Existing Java runtime identity mismatch")
    subprocess.run([str(java), "-version"], check=True)
    link = runtime / "java"
    if not link.exists() and not link.is_symlink():
        link.symlink_to(java_dir.name, target_is_directory=True)
    if link.resolve() != java_dir:
        raise ValueError("Unexpected existing Java link")
    subprocess.run([str(java), "-jar", str(installer), "--installServer"], cwd=profile, check=True)
    expected = profile / "libraries/net/minecraftforge/forge/1.20.1-47.4.20/unix_args.txt"
    if not expected.is_file():
        raise ValueError("Forge launch arguments missing after install")
    receipt = {"java_version": lock["java"]["version"], "java_archive_hashes": lock["java"]["hashes"],
               "forge_version": lock["forge"]["version"], "forge_installer_hashes": lock["forge"]["hashes"],
               "installed_in_owned_profile": True, "server_started": False}
    (profile / ".psa-runtime.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(install(args.profile, args.lock), indent=2))
