#!/usr/bin/env python3
"""Build separate, local-only codec test profiles. Does not start Minecraft."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["baseline", "patched"])
    parser.add_argument("--java-home", type=Path, default=Path(os.environ.get("JAVA_HOME") or ROOT / "runtime/jdk-21.0.13+9/Contents/Home"))
    args = parser.parse_args()
    java = args.java_home.expanduser().resolve() / "bin"
    lock = json.loads((ROOT / "integration-lock.json").read_text())
    pixelmon = next(f for f in lock["files"] if f["project"] == "pixelmon")
    key = pixelmon["hashes"]["sha512"]
    pixelmon_jar = ROOT / "cache" / key / Path(pixelmon["path"]).name
    if not pixelmon_jar.is_file() or hashlib.sha512(pixelmon_jar.read_bytes()).hexdigest() != key:
        raise ValueError("Verified pinned Pixelmon download required")
    libraries = ROOT / "runtime/loader/libraries"
    artifacts = [pixelmon_jar]
    if args.profile == "patched":
        patch = ROOT / "compat/creativecore/CreativeCore_NEOFORGE_v2.13.51_mc1.21.1-psa-codec1.jar"
        report = json.loads((ROOT / "evidence/creativecore-patch.json").read_text())
        if not patch.is_file() or hashlib.sha256(patch.read_bytes()).hexdigest() != report["patched_sha256"]:
            raise ValueError("Verified CreativeCore compatibility build required")
        artifacts.append(patch)
    baseline = args.profile == "baseline"
    name = "PixelmonCodecBaseline" if baseline else "CodecProbe"
    metadata = "baseline-neoforge.mods.toml" if baseline else "probe-neoforge.mods.toml"
    classes = ROOT / "tests/generated" / (args.profile + "-classes")
    classes.mkdir(parents=True, exist_ok=True)
    cp = os.pathsep.join(map(str, artifacts + list(libraries.rglob("*.jar"))))
    subprocess.run([str(java / "javac"), "--release", "21", "-proc:none", "-cp", cp,
                    "-d", str(classes), str(ROOT / "tests" / (name + ".java"))], check=True)
    server = ROOT / "tests/generated" / ("pixelmon-baseline" if baseline else "codec-patched")
    mods = server / "mods"
    mods.mkdir(parents=True, exist_ok=True)
    probe_name = "psa-baseline.jar" if baseline else "psa-codec-probe.jar"
    allowed = {p.name for p in artifacts} | {probe_name}
    if any(p.name not in allowed for p in mods.iterdir()):
        raise ValueError("Unexpected file in owned test profile mods directory")
    for source in artifacts:
        target = mods / source.name
        if target.is_symlink():
            if target.resolve() != source.resolve():
                raise ValueError("Unexpected test artifact symlink")
        else:
            shutil.copy2(source, target)
    linked_libraries = server / "libraries"
    if linked_libraries.exists() or linked_libraries.is_symlink():
        if linked_libraries.resolve() != libraries.resolve():
            raise ValueError("Unexpected test library location")
    else:
        linked_libraries.symlink_to(libraries, target_is_directory=True)
    with zipfile.ZipFile(mods / probe_name, "w") as output:
        entry = "dev/psa/codecprobe/" + name + ".class"
        output.write(classes / entry, entry)
        output.write(ROOT / "tests" / metadata, "META-INF/neoforge.mods.toml")
    (server / "eula.txt").write_text("eula=true\n")
    port = 25566 if baseline else 25567
    (server / "server.properties").write_text(
        "server-ip=127.0.0.1\nserver-port=" + str(port) + "\nmax-players=1\nview-distance=3\nsimulation-distance=3\n")
    command = [str(java / "java"), "-Xms1G", "-Xmx4G",
               "@libraries/net/neoforged/neoforge/21.1.262/unix_args.txt", "nogui"]
    print("Local-only test profile:", server)
    print("Run from that directory:", shlex.join(command))


if __name__ == "__main__":
    main()
