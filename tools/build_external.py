#!/usr/bin/env python3
"""Acquire and build the two public source candidates; not a game installer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def verify_source(source, recipe):
    if git(source, "rev-parse", "HEAD") != recipe["commit"]:
        raise ValueError("Source commit mismatch: " + str(source))
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Source checkout must be clean: " + str(source))
    license_file = source / "LICENSE"
    if hashlib.sha256(license_file.read_bytes()).hexdigest() != recipe["license_sha256"]:
        raise ValueError("Source license mismatch: " + str(source))


def acquire(recipe):
    parent = ROOT / "upstream"
    parent.mkdir(exist_ok=True)
    source = parent / recipe["checkout"]
    if not source.exists():
        # Publish only a complete checkout, so a failed fetch can be retried.
        with tempfile.TemporaryDirectory(prefix=".source-", dir=parent) as scratch:
            checkout = Path(scratch) / "repo"
            checkout.mkdir()
            git(checkout, "init", "--quiet")
            git(checkout, "remote", "add", "origin", recipe["repository"])
            git(checkout, "fetch", "--quiet", "--depth=1", "origin", recipe["commit"])
            git(checkout, "checkout", "--quiet", "--detach", recipe["commit"])
            verify_source(checkout, recipe)
            checkout.rename(source)
    verify_source(source, recipe)
    return source


def build(item, java_home):
    recipe = item["source_build"]
    source = acquire(recipe)
    env = dict(os.environ, JAVA_HOME=str(java_home), GRADLE_USER_HOME=str(ROOT / "cache/gradle"))
    subprocess.run(["bash", "./gradlew", "--no-daemon", "clean", "build"], cwd=source, env=env, check=True)
    verify_source(source, recipe)
    artifact = source / "build/libs" / item["filename"]
    data = artifact.read_bytes()
    if len(data) != recipe["size"] or hashlib.sha256(data).hexdigest() != recipe["sha256"]:
        raise ValueError("Build differs from the audited candidate; inputs were not changed: " + str(artifact))
    inputs = ROOT / "inputs"
    inputs.mkdir(exist_ok=True)
    target = inputs / item["filename"]
    if target.exists() or target.is_symlink():
        if target.is_symlink() or target.read_bytes() != data:
            raise ValueError("Refusing to replace an existing different input: " + str(target))
    else:
        with tempfile.NamedTemporaryFile(prefix=".build-", dir=inputs, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        try:
            temporary.chmod(0o644)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    print("Verified source candidate:", item["filename"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mod", choices=["all", "orchard", "plentifulponds"], nargs="?", default="all")
    parser.add_argument("--java-home", type=Path, default=Path(os.environ.get("JAVA_HOME") or ROOT / "runtime/jdk-21.0.13+9/Contents/Home"))
    args = parser.parse_args()
    java_home = args.java_home.expanduser().resolve()
    if not (java_home / "bin/javac").is_file():
        raise ValueError("A Java 21 JDK is required; set JAVA_HOME or --java-home")
    items = json.loads((ROOT / "external-artifacts.json").read_text())["artifacts"]
    for item in items:
        if "source_build" in item and args.mod in {"all", item["mod_id"]}:
            build(item, java_home)
    print("These are development candidates. Full Society startup is still gated by preflight.")


if __name__ == "__main__":
    main()
