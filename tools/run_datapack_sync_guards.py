#!/usr/bin/env python3
"""Recompile and run closed metadata guards, never Minecraft or a transformed upstream class."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

import forge_datapack_compat as compat


def run(java_home, module, target, dependencies, output):
    module, target, output = Path(module), Path(target), Path(output)
    compat.verify_module_file(module)
    if target.is_symlink() or not target.is_file() or compat.digest(target) != compat.TARGET_SHA256:
        raise ValueError("Pinned original SerializerDebug guard input required")
    dependencies = [Path(p) for p in dependencies]
    if not dependencies or any(p.is_symlink() or not p.is_file() for p in dependencies):
        raise ValueError("Regular local ASM, ASM-tree and Mixin dependency JARs required")
    if output.exists() or output.is_symlink():
        raise ValueError("Fresh guard output directory required")
    suffix = ".exe" if os.name == "nt" else ""
    java, javac = [Path(java_home)/"bin"/(name+suffix) for name in ["java", "javac"]]
    if not java.is_file() or not javac.is_file():
        raise ValueError("Local Java 17 JDK required")
    output.mkdir(parents=True, mode=0o700)
    output = output.resolve()
    source = Path(__file__).resolve().parents[1]/"tests/java/DatapackSyncGateProbe.java"
    classes = output/"classes"; classes.mkdir()
    classpath = os.pathsep.join(str(p.resolve()) for p in [module]+dependencies)
    compile_result = subprocess.run([str(javac.resolve()), "--release", "17", "-proc:none",
        "-cp", classpath, "-d", str(classes), str(source)], capture_output=True, text=True)
    (output/"compile-private.log").write_text(compile_result.stdout+compile_result.stderr)
    compile_result.check_returncode()
    shared = output/"owned-original/mods"; shared.mkdir(parents=True)
    shutil.copyfile(target, shared/"serializer_debug-1.0.1.jar")
    cases = {"valid":("valid","PINNED_INPUT_ACCEPTED"),
        **{name:("refuse","INVALID_PINNED_INPUT_REFUSED")
           for name in ["missing","changed","symlink","symlink-mods"]},
        "unapplied":("unapplied","UNAPPLIED_REDIRECT_REFUSED"),
        **{name:(name,"INVALID_REDIRECT_METADATA_REFUSED") for name in ["wrong-target","original",
            "merged-only","missing-handler","extra-send","wrong-descriptor","static-native"]},
        "completed-metadata":("completed-metadata","COMPLETED_REDIRECT_METADATA_ACCEPTED_NOT_GAME_EXECUTION")}
    results = {}
    for name,(mode,expected) in cases.items():
        root=output/name; root.mkdir(); mods=root/"mods"
        if name == "symlink-mods": mods.symlink_to(shared, target_is_directory=True)
        else:
            mods.mkdir(); file=mods/"serializer_debug-1.0.1.jar"
            if name == "symlink": file.symlink_to(shared/"serializer_debug-1.0.1.jar")
            elif name == "changed": file.write_bytes(b"owned invalid file fixture, never executed")
            elif name != "missing": shutil.copyfile(target,file)
        result=subprocess.run([str(java.resolve()),"-cp",str(classes)+os.pathsep+classpath,
            "dev.psa.datapacksync.DatapackSyncGateProbe",mode],cwd=root,capture_output=True,text=True)
        (root/"private.log").write_text(result.stdout+result.stderr)
        if result.returncode or result.stdout.strip()!=expected:
            raise RuntimeError("Guard case failed; inspect private output: "+name)
        results[name]=expected
    receipt={"scope":"Compiled guard/ASM metadata fixtures only; never native game execution",
        "artifact_sha256":compat.digest(module),"target_sha256":compat.digest(target),
        "probe_source_sha256":compat.digest(source),
        "dependency_sha256":{p.name:compat.digest(p) for p in dependencies},"results":results}
    (output/"result.json").write_text(json.dumps(receipt,indent=2)+"\n")
    return receipt


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home",type=Path,required=True)
    parser.add_argument("--module",type=Path,required=True)
    parser.add_argument("--target",type=Path,required=True)
    parser.add_argument("--dependency",type=Path,action="append",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=run(args.java_home,args.module,args.target,args.dependency,args.output)
    print(json.dumps({"passed":len(result["results"]),"scope":result["scope"]}))
