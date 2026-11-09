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


def build(java_home, output):
    javac = Path(java_home) / "bin/javac"
    output = Path(output)
    if output.exists() or output.is_symlink() or output.suffix != ".jar":
        raise ValueError("A fresh .jar output is required")
    if any(parent.name.casefold() == "mods" for parent in output.resolve().parents):
        raise ValueError("QA attach helper must not be built into mods/")
    version = subprocess.check_output([str(javac), "-version"], text=True, stderr=subprocess.STDOUT).strip()
    if not version.startswith("javac 17."):
        raise ValueError("Java 17 compiler required")
    manifest_source = MANIFEST.read_bytes()
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
                        "-d", str(classes), str(SOURCE)], check=True)
        with zipfile.ZipFile(temporary / "raw.jar", "x") as archive:
            archive.writestr("META-INF/MANIFEST.MF", manifest)
            for path in sorted(classes.rglob("*.class")):
                archive.write(path, path.relative_to(classes).as_posix())
        receipt = canonical_jar(temporary / "raw.jar", output)
    return dict(receipt, bytes=output.stat().st_size, source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                manifest_source_sha256=hashlib.sha256(manifest_source).hexdigest(), javac_version=version,
                agent_class="dev.psa.qacontrol.MinecraftQaControl", production_mod=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.java_home, args.output), indent=2))
