#!/usr/bin/env python3
"""Build the narrowly scoped, source-included CreativeCore compatibility patch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ENTRY = "team/creative/creativecore/mixin/ComponentSerializationMixin.class"


def apply_patch(original, replacement, target):
    target = Path(target)
    with zipfile.ZipFile(original) as source:
        if source.namelist().count(ENTRY) != 1:
            raise ValueError("Expected exactly one CreativeCore codec mixin")
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=target.parent, suffix=".partial")
        os.close(handle)
        temporary = Path(temporary)
        try:
            with zipfile.ZipFile(temporary, "w") as output:
                for info in source.infolist():
                    output.writestr(info, replacement if info.filename == ENTRY else source.read(info.filename))
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--java-home", type=Path, default=Path(os.environ.get("JAVA_HOME") or ROOT / "runtime/jdk-21.0.13+9/Contents/Home"))
    args = parser.parse_args()
    lock = json.loads((ROOT / "integration-lock.json").read_text())
    file = next(f for f in lock["files"] if f["project"] == "creativecore")
    if Path(file["path"]).name != "CreativeCore_NEOFORGE_v2.13.51_mc1.21.1.jar":
        raise ValueError("Patch is audited only for CreativeCore 2.13.51")
    hashes = file["hashes"]
    key = hashes.get("sha512") or hashes.get("sha256") or hashes["sha1"]
    original = ROOT / "cache" / key / Path(file["path"]).name
    if hashlib.sha512(original.read_bytes()).hexdigest() != file["hashes"]["sha512"]:
        raise ValueError("Original CreativeCore hash mismatch")
    classes = ROOT / "compat/creativecore/classes"
    classes.mkdir(exist_ok=True)
    libraries = list((ROOT / "runtime/loader/libraries").rglob("*.jar"))
    classpath = os.pathsep.join(map(str, [original] + libraries))
    subprocess.run([str(args.java_home.expanduser().resolve() / "bin/javac"),
                    "--release", "21", "-proc:none", "-classpath", classpath, "-d", str(classes),
                    str(ROOT / "compat/creativecore/ComponentSerializationMixin.java")], check=True)
    replacement = (classes / ENTRY).read_bytes()
    target = ROOT / "compat/creativecore/CreativeCore_NEOFORGE_v2.13.51_mc1.21.1-psa-codec1.jar"
    apply_patch(original, replacement, target)
    report = {"original_sha512": file["hashes"]["sha512"], "entry": ENTRY,
              "replacement_sha256": hashlib.sha256(replacement).hexdigest(),
              "patched_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
              "reason": "Preserve both Pixelmon and CreativeCore component types without injecting into Pixelmon's overwritten codec method"}
    (ROOT / "evidence/creativecore-patch.json").write_text(json.dumps(report, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
