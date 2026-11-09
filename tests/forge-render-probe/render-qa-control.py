#!/usr/bin/env python3
"""Strict 313 production + one diagnostic controller, only in a new disposable QA profile."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
BASELINE = "935491cfd78a9ffadaaf517aeb869aebcd8f4208e1ef54b56a835cff44225812"
PROBE = "psa-render-probe-0.6.jar"
SOCKET = "psa-render-" + hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            result.update(chunk)
    return result.hexdigest()


def tmux(*args, check=True):
    return subprocess.run(["tmux", "-L", SOCKET, "-f", "/dev/null", *args],
                          cwd=ROOT, check=check, capture_output=True, text=True)


def running():
    return tmux("has-session", "-t", "server", check=False).returncode == 0


def owned():
    if tmux("show-options", "-qv", "-t", "server", "@psa-root").stdout.strip() != str(ROOT):
        raise RuntimeError("Unrecognized tmux session")


def inventory(receipt):
    manifest = ROOT / ".psa-production-mods.sha256"
    if manifest.is_symlink() or digest(manifest) != BASELINE:
        raise RuntimeError("Production313 manifest identity mismatch")
    files = {}
    for line in manifest.read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise RuntimeError("Production mod mismatch: " + name)
        files[path.name] = expected
    if len(files) != 313 or PROBE in files:
        raise RuntimeError("Invalid baseline inventory")
    expected = receipt["diagnostic_sha256"]
    if not re.fullmatch("[0-9a-f]{64}", expected):
        raise RuntimeError("Invalid diagnostic identity")
    probe = ROOT / "mods" / PROBE
    if probe.is_symlink() or digest(probe) != expected:
        raise RuntimeError("Diagnostic hash mismatch")
    actual = list((ROOT / "mods").iterdir())
    if {p.name for p in actual} != set(files) | {PROBE} or len(actual) != 314:
        raise RuntimeError("Unexpected diagnostic inventory")
    if any(p.is_symlink() or not p.is_file() for p in actual):
        raise RuntimeError("Non-regular mod entry")
    props = dict(line.split("=", 1) for line in (ROOT / "server.properties").read_text().splitlines()
                 if "=" in line and not line.startswith("#"))
    if (props.get("online-mode") != "true" or props.get("level-name") != "world-render-qa"
            or props.get("enable-rcon") != "false"):
        raise RuntimeError("Authenticated disposable world required")
    if "-Dpsa.render.enabled=true" not in (ROOT / "user_jvm_args.txt").read_text().splitlines():
        raise RuntimeError("Explicit render opt-in required")


def write_json(path, value):
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".psa-render-", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def owned_world(receipt):
    world = ROOT / "world-render-qa"
    if world.is_symlink() or world.resolve().parent != ROOT:
        raise RuntimeError("QA world path mismatch")
    marker = world / ".psa-render-world-owner.json"
    if marker.is_symlink() or not marker.is_file():
        raise RuntimeError("Existing world has no owned QA marker; refusing recovery")
    try:
        if str(uuid.UUID(receipt.get("world_generation", ""))) != receipt["world_generation"]:
            raise ValueError("Non-canonical generation")
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise RuntimeError("Invalid QA world generation") from error
    owner = json.loads(marker.read_text())
    if owner != {"owner": "psa-render-world-v1", "profile": ROOT.name, "generation": receipt.get("world_generation")}:
        raise RuntimeError("QA world generation mismatch")
    return world


def current_state():
    path = ROOT / "psa-validation/render-server-current.json"
    if not path.exists():
        return None
    if path.is_symlink():
        raise RuntimeError("Checkpoint symlink refused")
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return {"active": True, "unreadable_checkpoint": True}


def initialize_world(receipt):
    world = ROOT / "world-render-qa"
    if world.exists() or world.is_symlink():
        owned_world(receipt)
        return
    world.mkdir(mode=0o700)
    receipt["world_generation"] = str(uuid.uuid4())
    write_json(world / ".psa-render-world-owner.json", {"owner": "psa-render-world-v1", "profile": ROOT.name,
                                                        "generation": receipt["world_generation"]})
    write_json(ROOT / ".psa-render-qa.json", receipt)


def recover(receipt):
    if running():
        raise RuntimeError("Recovery requires a fully stopped owned QA process")
    inventory(receipt)
    world = owned_world(receipt)
    state = current_state()
    if state and "world_generation" in state and state["world_generation"] != receipt["world_generation"]:
        raise RuntimeError("Checkpoint belongs to another QA world")
    history = ROOT / "qa-crash-history"
    if history.is_symlink():
        raise RuntimeError("Recovery archive symlink refused")
    history.mkdir(exist_ok=True, mode=0o700)
    archive = history / (str(time.time_ns()) + "-" + receipt["world_generation"])
    archive.mkdir(mode=0o700)
    import shutil
    for name in ["console.log", ".psa-render-qa.json", "server.properties"]:
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, archive / name)
    # User explicitly permits discarding QA saves. Preserve the entire identified
    # QA world, including crashed entities/tickets, instead of editing unrelated NBT.
    world.rename(archive / world.name)
    path = ROOT / "psa-validation/render-server-current.json"
    if path.exists():
        path.rename(archive / "render-server-current.json")
    initialize_world(receipt)
    print("PSA_RENDER_QA recovery archived the exact owned disposable world; fresh generation ready")


def main():
    if not (ROOT / ".psa-disposable-qa").is_file():
        raise RuntimeError("Missing disposable marker")
    receipt = json.loads((ROOT / ".psa-render-qa.json").read_text())
    if receipt.get("owner") != "psa-render-qa-v1" or receipt.get("profile") != ROOT.name:
        raise RuntimeError("Profile ownership mismatch")
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "verify":
        inventory(receipt)
        print("PSA_RENDER_QA production313 and one pinned diagnostic verified")
    elif action == "recover":
        with (ROOT / ".psa-render-control.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            recover(receipt)
    elif action == "status":
        if running():
            owned()
            print("Running")
        else:
            print("Stopped")
    elif action == "start":
        with (ROOT / ".psa-render-control.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if running():
                owned()
                print("Already running")
                return
            inventory(receipt)
            state = current_state()
            if state and (state.get("active") or not state.get("cleanup_complete") or state.get("cleanup_failed")):
                raise RuntimeError("Unresolved prior QA run; use recover to archive the owned disposable world before restarting")
            initialize_world(receipt)
            if (ROOT / "eula.txt").read_text().strip() != "eula=true":
                raise RuntimeError("Existing explicit EULA acceptance required")
            java = ROOT / "runtime/java/bin/java"
            args = ROOT / "libraries/net/minecraftforge/forge/1.20.1-47.4.20/unix_args.txt"
            if not os.access(java, os.X_OK) or not args.is_file():
                raise RuntimeError("Pinned runtime required")
            log = ROOT / "console.log"
            if log.exists():
                (ROOT / "logs").mkdir(exist_ok=True)
                log.rename(ROOT / "logs" / ("console-render-previous-" + str(time.time_ns()) + ".log"))
            command = "exec " + shlex.join([str(java), "@user_jvm_args.txt", "@" + str(args), "nogui"])
            tmux("new-session", "-d", "-s", "server", "-c", str(ROOT), command + " >console.log 2>&1")
            tmux("set-option", "-t", "server", "@psa-root", str(ROOT))
            print("Started; verify Done before connecting")
    elif action == "stop":
        if not running():
            print("Stopped")
            return
        owned()
        tmux("send-keys", "-t", "server", "-l", "stop")
        tmux("send-keys", "-t", "server", "Enter")
        for _ in range(120):
            if not running():
                print("Stopped")
                return
            time.sleep(1)
        raise RuntimeError("Shutdown pending; no process was killed")
    elif action == "command":
        if len(sys.argv) != 3 or any(c in sys.argv[2] for c in "\r\n"):
            raise RuntimeError("One console command required")
        if not running():
            raise RuntimeError("Stopped")
        owned()
        tmux("send-keys", "-t", "server", "-l", sys.argv[2])
        tmux("send-keys", "-t", "server", "Enter")
    else:
        raise RuntimeError("Usage: render-qa-control.py verify|recover|start|stop|status|command '...'")


if __name__ == "__main__":
    main()
