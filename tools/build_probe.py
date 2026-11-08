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
from prepare import mob_overrides, write_overrides

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["baseline", "patched", "mobs-config-only", "mobs-preserved"])
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
    mobs = args.profile.startswith("mobs-")
    if mobs:
        for project in ["kubejs", "rhino"]:
            dependency = next(file for file in lock["files"] if file["project"] == project)
            source = ROOT / "cache" / dependency["hashes"]["sha512"] / Path(dependency["path"]).name
            if not source.is_file() or hashlib.sha512(source.read_bytes()).hexdigest() != dependency["hashes"]["sha512"]:
                raise ValueError("Verified pinned probe dependency required: " + project)
            artifacts.append(source)
    if args.profile == "patched":
        patch = ROOT / "compat/creativecore/CreativeCore_NEOFORGE_v2.13.51_mc1.21.1-psa-codec1.jar"
        report = json.loads((ROOT / "evidence/creativecore-patch.json").read_text())
        if not patch.is_file() or hashlib.sha256(patch.read_bytes()).hexdigest() != report["patched_sha256"]:
            raise ValueError("Verified CreativeCore compatibility build required")
        artifacts.append(patch)
    baseline = args.profile == "baseline"
    name = "MobCoexistenceProbe" if mobs else ("PixelmonCodecBaseline" if baseline else "CodecProbe")
    metadata = "mobs-neoforge.mods.toml" if mobs else ("baseline-neoforge.mods.toml" if baseline else "probe-neoforge.mods.toml")
    classes = ROOT / "tests/generated" / (args.profile + "-classes")
    classes.mkdir(parents=True, exist_ok=True)
    mapped = libraries / "net/neoforged/neoforge/21.1.262/neoforge-21.1.262-server.jar"
    if not mapped.is_file():
        raise ValueError("Installed NeoForge's mapped server compile library is required")
    # The slim Minecraft jar still has obfuscated method names. Resolve the
    # runtime's mapped/patched classes before any duplicate Minecraft entries.
    cp = os.pathsep.join(map(str, [mapped] + artifacts + sorted(p for p in libraries.rglob("*.jar") if p != mapped)))
    subprocess.run([str(java / "javac"), "--release", "21", "-proc:none", "-cp", cp,
                    "-d", str(classes), str(ROOT / "tests" / (name + ".java"))], check=True)
    server = ROOT / "tests/generated" / (args.profile if mobs else ("pixelmon-baseline" if baseline else "codec-patched"))
    mods = server / "mods"
    mods.mkdir(parents=True, exist_ok=True)
    probe_name = "psa-mobs-probe.jar" if mobs else ("psa-baseline.jar" if baseline else "psa-codec-probe.jar")
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
    port = {"baseline": 25566, "patched": 25567, "mobs-config-only": 25568, "mobs-preserved": 25569}[args.profile]
    (server / "server.properties").write_text(
        "server-ip=127.0.0.1\nserver-port=" + str(port) + "\nmax-players=1\nview-distance=3\nsimulation-distance=3\n")
    extra = []
    if mobs:
        preserved = args.profile == "mobs-preserved"
        overrides = mob_overrides(pixelmon_jar)
        if not preserved:
            overrides = {path: data for path, data in overrides.items() if not path.startswith("kubejs/")}
        kube_data = server / "kubejs/data"
        if not preserved and kube_data.exists() and any(path.is_file() for path in kube_data.rglob("*")):
            raise ValueError("Config-only control must not have KubeJS datapack overrides")
        receipts = write_overrides(server, overrides)
        (server / ".probe-overrides.json").write_text(json.dumps(receipts, indent=2) + "\n")
        extra = ["-Dpsa.expectedMobsPreserved=" + str(preserved).lower(), "-Dpsa.probe.autoStop=true"]
    command = [str(java / "java"), "-Xms1G", "-Xmx4G", *extra,
               "@libraries/net/neoforged/neoforge/21.1.262/unix_args.txt", "nogui"]
    print("Local-only test profile:", server)
    print("Run from that directory:", shlex.join(command))


if __name__ == "__main__":
    main()
