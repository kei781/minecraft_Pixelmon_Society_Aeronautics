#!/usr/bin/env python3
"""Build the local QA attach helper with the pinned Java 17 compiler; never a mod."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from forge_resources import canonical_jar

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/java/MinecraftQaControl.java"
MANIFEST = ROOT / "tests/java/minecraft-qa-control-manifest.mf"


def build(java_home, output, kind="control"):
    if kind not in {"control", "connect", "ali", "ali-resync"}:
        raise ValueError("Known QA helper kind required")
    source = SOURCE if kind == "control" else ROOT / "tests/java/MinecraftQaConnect.java"
    manifest_path = MANIFEST if kind == "control" else ROOT / "tests/java/minecraft-qa-connect-manifest.mf"
    agent_class = "dev.psa.qacontrol.MinecraftQaControl" if kind == "control" else "dev.psa.qaconnect.v2.MinecraftQaConnect"
    if kind == "ali":
        source = ROOT / "tests/java/AliClientQaControl.java"
        manifest_path = ROOT / "tests/java/ali-client-qa-manifest.mf"
        agent_class = "dev.psa.aliqa.v5.AliClientQaControl"
    if kind == "ali-resync":
        source = ROOT / "tests/java/AliResyncQaControl.java"
        manifest_path = ROOT / "tests/java/ali-resync-qa-manifest.mf"
        agent_class = "dev.psa.aliresyncqa.v1.AliResyncQaControl"
    javac = Path(java_home) / "bin/javac"
    output = Path(output)
    if output.exists() or output.is_symlink() or output.suffix != ".jar":
        raise ValueError("A fresh .jar output is required")
    if any(parent.name.casefold() == "mods" for parent in output.resolve().parents):
        raise ValueError("QA attach helper must not be built into mods/")
    version = subprocess.check_output([str(javac), "-version"], text=True, stderr=subprocess.STDOUT).strip()
    if not version.startswith("javac 17."):
        raise ValueError("Java 17 compiler required")
    manifest_source = manifest_path.read_bytes()
    if not manifest_source.endswith(b"\n"):
        raise ValueError("Agent manifest source must end with a newline")
    # The JAR main section ends with a blank line; keep the text source Git-clean.
    manifest = manifest_source.rstrip(b"\n") + b"\n\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="psa-qa-control-", dir=output.parent) as temporary:
        temporary = Path(temporary)
        classes = temporary / "classes"
        classes.mkdir()
        subprocess.run([str(javac), "--release", "17", "--add-modules", "jdk.attach",
                        "-d", str(classes), str(source)], check=True)
        with zipfile.ZipFile(temporary / "raw.jar", "x") as archive:
            archive.writestr("META-INF/MANIFEST.MF", manifest)
            for path in sorted(classes.rglob("*.class")):
                archive.write(path, path.relative_to(classes).as_posix())
        receipt = canonical_jar(temporary / "raw.jar", output)
    return dict(receipt, bytes=output.stat().st_size, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                manifest_source_sha256=hashlib.sha256(manifest_source).hexdigest(), javac_version=version,
                agent_class=agent_class, production_mod=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=["control", "connect", "ali", "ali-resync"], default="control")
    args = parser.parse_args()
    print(json.dumps(build(args.java_home, args.output, args.kind), indent=2))
