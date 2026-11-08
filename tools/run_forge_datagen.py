#!/usr/bin/env python3
"""Run Forge 1.20.1 datagen in its own JVM; propagate real failures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

EXPORT_SCRIPT = Path(__file__).with_name("forge-datagen-export.gradle")


def generate(project, gradle, java_home, gradle_home):
    project = Path(project).resolve(strict=True)
    gradle = Path(gradle).resolve(strict=True)
    java_home = Path(java_home).resolve(strict=True)
    java = (java_home / "bin/java").resolve(strict=True)
    gradle_home = Path(gradle_home).absolute()
    logs = project / "build/psa-datagen"
    logs.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, JAVA_HOME=str(java_home), GRADLE_USER_HOME=str(gradle_home))
    with tempfile.TemporaryDirectory(prefix="run-", dir=logs) as scratch:
        recipe = Path(scratch) / "launcher.json"
        prep_log = Path(scratch) / "prepare.log"
        data_log = Path(scratch) / "generator.log"
        with prep_log.open("w") as stream:
            prepared = subprocess.run([str(gradle), "--no-daemon", "--console", "plain", "--max-workers", "2",
                "-I", str(EXPORT_SCRIPT), "-p", str(project), "-PpsaDataRecipe=" + str(recipe), "runData"],
                env=env, stdout=stream, stderr=subprocess.STDOUT)
        # Copy logs even on failure; never reuse a launcher from an earlier run.
        saved_prepare = logs / (Path(scratch).name + "-prepare.log")
        saved_prepare.write_bytes(prep_log.read_bytes())
        if prepared.returncode:
            raise RuntimeError("Datagen preparation failed; see " + str(saved_prepare))
        raw = recipe.read_bytes()
        launch = json.loads(raw)
        command = launch["command"]
        workdir = Path(launch["cwd"]).resolve(strict=True)
        if (not isinstance(command, list) or not all(isinstance(arg, str) for arg in command)
                or not command or Path(command[0]).resolve() != java
                or "cpw.mods.bootstraplauncher.BootstrapLauncher" not in command
                or "forgedatauserdev" not in command or project not in workdir.parents):
            raise ValueError("Unexpected datagen launcher")
        variables = launch["environment"]
        if set(variables) != {"MOD_CLASSES"} or not isinstance(variables["MOD_CLASSES"], str) or not variables["MOD_CLASSES"]:
            raise ValueError("Only Forge's explicit mod-root environment is accepted")
        env.update(variables)
        with data_log.open("w") as stream:
            generated = subprocess.run(command, cwd=workdir, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stream, stderr=subprocess.STDOUT)
        saved_data = logs / (Path(scratch).name + "-generator.log")
        saved_data.write_bytes(data_log.read_bytes())
        if generated.returncode:
            raise RuntimeError("Datagen JVM failed with code " + str(generated.returncode) + "; see " + str(saved_data))
        return {"prepare_exit_code": prepared.returncode, "generator_exit_code": generated.returncode,
                "launcher_sha256": hashlib.sha256(raw).hexdigest(),
                "generator_log_sha256": hashlib.sha256(saved_data.read_bytes()).hexdigest(),
                "generator_log": str(saved_data)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--gradle", type=Path, required=True)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--gradle-home", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.project, args.gradle, args.java_home, args.gradle_home), indent=2))


if __name__ == "__main__":
    main()
