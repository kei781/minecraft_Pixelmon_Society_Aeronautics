#!/usr/bin/env python3
"""Run the isolated village worldgen probe against a copy of a staged profile.

The staged profile is copied to a fresh directory (copy-on-write where the
filesystem supports it), bound to loopback with a new throwaway world, and
started with tests/forge-village-probe.js. After the probe has assembled its
census, the nearest villages of each type are really generated with Chunky,
saved, and read back from the region files.

The source profile, its world and any running server are never modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

import village_world

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests/forge-village-probe.js"
ASSEMBLY_PROBE = ROOT / "tests/forge-assembly-probe.js"
PC_PROBE = ROOT / "tests/forge-pc-resync-probe.js"
CHECKS = ROOT / "tests/forge-coexistence-checks.json"
FORGE_ARGS = "libraries/net/minecraftforge/forge/1.20.1-47.4.20/unix_args.txt"
WORLD = "world-village-probe"
MARKER = ".psa-village-probe-profile"
SPAWN_SCRIPT = "kubejs/server_scripts/psa_village_spawn.js"
# Society inventory blocks whose contents must not be duplicated by physics assembly.
PHYSICS_BLOCKS = ("shippingbin:basic_shipping_bin", "society:artisan_hopper")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
SPAWN_LINE = re.compile(r"PSA_VILLAGE_SPAWN (\{.*\})\s*$")
PROBLEM = re.compile(
    r"(ERROR|WARN).*((Empty|Non-existent|nonexistent|non-existent) (template )?pool|[Tt]emplate pool|"
    r"[Jj]igsaw|[Ss]tructure (piece|start|template)|parsing blockstate|Unknown (block|structure)|"
    r"Failed to (load|place|generate) (structure|template|chunk|feature|registr)|worldgen_modifier|registry entries)")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def linked_entry(folder):
    """First symbolic link below `folder`, or None. A clone keeps links, and a link in the copy
    would send the probe scripts written into it to the place the source profile shares."""
    for base, folders, files in os.walk(folder):
        for name in sorted(folders + files):
            if os.path.islink(os.path.join(base, name)):
                return os.path.relpath(os.path.join(base, name), folder)
    return None


def prepare(source, destination, libraries, port, seed, sweep_skip=()):
    source, destination = Path(source), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("A fresh destination is required")
    if not (source / ".psa-forge-candidate.json").is_file() or not (source / ".psa-owned-smoke-test").is_file():
        raise ValueError("Source is not an owned PSA candidate profile")
    if not (Path(libraries) / "net/minecraftforge/forge/1.20.1-47.4.20/unix_args.txt").is_file():
        raise ValueError("Pinned Forge 47.4.20 libraries required")
    if not 1024 < port < 65536 or port == 25573:
        raise ValueError("Use a separate unprivileged test port")
    folders = ("mods", "config", "defaultconfigs", "kubejs", "patchouli_books")
    for name in folders:
        if (source / name).is_symlink() or not (source / name).is_dir():
            raise ValueError("Unexpected profile layout: " + name)
        linked = linked_entry(source / name)
        if linked is not None:
            raise ValueError("Profile folder holds a symbolic link: %s/%s" % (name, linked))
    destination.mkdir(parents=True)
    for name in folders:
        # APFS/Btrfs/XFS clone when available; a plain copy otherwise.
        clone = subprocess.run(["cp", "-cR", str(source / name), str(destination / name)],
                               capture_output=True) if sys.platform == "darwin" else None
        if clone is None or clone.returncode != 0:
            shutil.rmtree(destination / name, ignore_errors=True)
            shutil.copytree(source / name, destination / name, symlinks=False)
    for name in (".psa-forge-candidate.json", ".psa-mods.sha256", ".psa-owned-smoke-test", "user_jvm_args.txt"):
        shutil.copyfile(source / name, destination / name)
    (destination / "libraries").symlink_to(Path(libraries).resolve(), target_is_directory=True)
    shutil.copyfile(PROBE, destination / "kubejs/server_scripts/psa_village_probe.js")
    shutil.copyfile(ASSEMBLY_PROBE, destination / "kubejs/server_scripts/psa_assembly_probe.js")
    shutil.copyfile(PC_PROBE, destination / "kubejs/server_scripts/psa_pc_resync_probe.js")
    # JSON is a valid script literal; the probe reads the same check list in every profile.
    spec = json.loads(CHECKS.read_text())
    # A block that brings this profile's server down when placed is left out of the assembly sweep
    # so the sweep can finish; the crash itself is observed by port_repair_checks.
    spec["assembly_sweep_skip"] = {block: "named on the command line" for block in sweep_skip}
    (destination / "kubejs/server_scripts/psa_probe_spec.js").write_text(
        "global.psaProbeSpec = " + json.dumps(spec, sort_keys=True) + ";\n")
    (destination / "server.properties").write_text(
        "server-ip=127.0.0.1\nserver-port=%d\nonline-mode=true\nenable-query=false\nenable-rcon=false\n"
        "allow-flight=true\nmax-players=6\nview-distance=4\nsimulation-distance=4\nlevel-name=%s\n"
        "level-seed=%s\nmax-tick-time=-1\nspawn-protection=0\nmotd=PSA isolated village worldgen probe\n"
        % (port, WORLD, seed))
    (destination / "eula.txt").write_text("eula=false\n")
    (destination / MARKER).write_text("Disposable village worldgen probe profile; never a player server.\n")
    return destination


class Server:
    def __init__(self, profile, java):
        self.profile = Path(profile)
        self.lines = []
        self.crashed = False
        self.log = (self.profile / "console.log").open("w", buffering=1)
        self.process = subprocess.Popen(
            [str(Path(java).resolve()), "@user_jvm_args.txt", "@" + FORGE_ARGS, "nogui"], cwd=self.profile,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.process.stdout:
            self.log.write(line)
            self.lines.append(ANSI.sub("", line.rstrip("\n")))

    def send(self, command):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def wait_for(self, pattern, timeout, start=0, fail=None):
        """Return the index after the first line matching `pattern` at or after `start`."""
        deadline, position = time.time() + timeout, start
        matcher, failure = re.compile(pattern), re.compile(fail) if fail else None
        while True:
            while position < len(self.lines):
                line = self.lines[position]
                position += 1
                if failure is not None and failure.search(line):
                    raise RuntimeError("Server reported: " + line[:400])
                if "This crash report has been saved to" in line or "Failed to start the minecraft server" in line:
                    # The second is a failed mod load (the pack has a rare start-up race between Quark's
                    # and Supplementaries' event registration); the JVM stays alive after either.
                    self.crashed = True
                    raise RuntimeError("Server crashed: " + line[:400])
                if matcher.search(line):
                    return position
            if self.process.poll() is not None:
                raise RuntimeError("Server exited before: " + pattern)
            if (self.profile / "psa-stop-request").exists():
                raise RuntimeError("Stop requested by operator")
            if time.time() > deadline:
                raise TimeoutError("Timed out waiting for: " + pattern)
            time.sleep(0.5)

    def stop(self, timeout=240):
        if self.process.poll() is None and self.crashed:
            # A crashed server has saved and closed its world but its JVM can stay alive on other
            # mods' threads; it is this driver's own disposable child, so it is ended here.
            try:
                self.process.wait(60)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(60)
        elif self.process.poll() is None:
            self.send("stop")
            try:
                self.process.wait(timeout)
            except subprocess.TimeoutExpired:
                return None  # left running on purpose; the caller reports it
        return self.process.returncode


def choose(villages, per_structure):
    chosen = []
    for structure in sorted({village["structure"] for village in villages}):
        nearest = sorted((v for v in villages if v["structure"] == structure), key=lambda v: v["spawn_distance"])
        chosen.extend(nearest[:per_structure])
    return chosen


def generate(server, village, margin, timeout):
    x0, _, z0, x1, _, z1 = village["box"]
    centre_x, centre_z = (x0 + x1) // 2, (z0 + z1) // 2
    radius = max(x1 - x0, z1 - z0) // 2 + margin
    position = len(server.lines)
    for command in ("chunky world minecraft:overworld", "chunky shape square",
                    "chunky center %d %d" % (centre_x, centre_z), "chunky radius %d" % radius, "chunky start"):
        server.send(command)
        time.sleep(0.3)
    server.wait_for(r"\[Chunky\] Task finished for minecraft:overworld", timeout, position,
                    fail=r"\[Chunky\].*(already|confirm)")
    return {"centre": [centre_x, centre_z], "radius": radius}


def spawn_village(villages, decision):
    """The census village the spawn script selected, if any."""
    target = (decision or {}).get("village")
    if not target:
        return None
    for village in villages:
        if village["chunk"] == [target["chunk_x"], target["chunk_z"]] and village["structure"] == target["structure"]:
            return village
    return None


def evaluate(spec, probe):
    """Compare what the game reported with what each check expects. Checks without an expectation only record."""
    results = {"tags": [], "crafting": [], "cooking": [], "structure_sets": [], "assemblies": [], "loot": []}
    for check in spec.get("tags", []):
        values = probe["tags"].get(check["registry"] + ":" + check["tag"])
        missing = None if values is None else sorted(set(check.get("expect_contains", [])) - set(values))
        results["tags"].append({"registry": check["registry"], "tag": check["tag"], "values": values,
                                "missing": missing, "pass": values is not None and not missing})
    for check in spec.get("crafting", []):
        found = probe["crafting"].get(check["name"])
        results["crafting"].append({
            "name": check["name"], "expect": [check["expect_result"], check["expect_count"]], "found": found,
            "pass": found is not None and [found["result"], found["count"]] == [check["expect_result"], check["expect_count"]]})
    for check in spec.get("cooking", []):
        found = probe["cooking"].get(check["name"])
        results["cooking"].append({
            "name": check["name"], "expect": [check["expect_result"], check["expect_count"]], "found": found,
            "pass": found is not None and [found["result"], found["count"]] == [check["expect_result"], check["expect_count"]]})
    for name, expected in sorted(spec.get("expect_structure_set_members", {}).items()):
        members = probe["structure_sets"].get(name)
        missing = None if members is None else sorted(set(expected) - set(members))
        results["structure_sets"].append({"id": name, "members": members, "missing": missing,
                                          "pass": members is not None and not missing})
    for check in spec.get("assemble", []):
        found = probe["assemblies"].get(check["structure"])
        valid = [sample for sample in (found or {}).get("samples", []) if sample["valid"]]
        results["assemblies"].append({
            "structure": check["structure"], "found": found,
            "pass": bool(valid) and all(sample["matched"] >= check["expect_min_matched"] for sample in valid)})
    for check in spec.get("loot_tables", []):
        found = probe["loot"].get(check["table"])
        items = (found or {}).get("stacks_by_item", {})
        namespaces = sorted({name.split(":")[0] for name in items})
        missing = sorted(set(check.get("expect_items", [])) - set(items))
        missing += sorted("namespace " + name for name in set(check.get("expect_namespaces", [])) - set(namespaces))
        results["loot"].append({
            "table": check["table"], "rolls": check["rolls"], "stacks": (found or {}).get("stacks"),
            "namespaces": namespaces, "expected_item_stacks": {name: items.get(name, 0) for name in check.get("expect_items", [])},
            "missing": missing, "pass": found is not None and not missing})
    results["failed"] = sorted(kind + ":" + str(entry.get("name") or entry.get("tag") or entry.get("id")
                                                   or entry.get("structure") or entry.get("table"))
                               for kind, entries in results.items() if isinstance(entries, list)
                               for entry in entries if not entry["pass"])
    return results


def radium(lines):
    """Options Radium reports as disabled by the profile's own configuration."""
    summary = next((line.split("Radium Config/]: ", 1)[1] for line in lines if "Loaded configuration file for Radium" in line), None)
    disabled = sorted({match.group(1) for line in lines for match in [re.search(
        r"as option '([a-z_.]+)' \(added by user configuration\)", line)] if match})
    return {"loaded": summary, "disabled_by_configuration": disabled}


def kubejs_errors(profile):
    log = Path(profile) / "logs/kubejs/server.log"
    if not log.is_file():
        return None
    return [re.sub(r"^\[[0-9:]+\] ", "", line)[:300] for line in log.read_text(errors="replace").splitlines()
            if "] [ERROR] " in line or "] [ERR" in line]


def physics_assembly_check(server, block, position=(8, 200, 8), items=6):
    """Fill one Society inventory block through a hopper, assemble it with the port's own console
    command and report what the removed original block dropped. A drop means the contents now exist
    twice (the moved block entity keeps its copy). A floor that is not part of the assembled area
    keeps any dropped stack where it can be counted."""
    x, y, z = position
    steps = []

    def command(text, pause):
        start = len(server.lines)
        server.send(text)
        time.sleep(pause)
        lines = [re.sub(r"^\[[0-9:]+\] \[[^]]*\] \[[^]]*\]: ", "", line)[:400] for line in server.lines[start:]
                 if "[mixin/]" not in line]
        steps.append({"command": text, "console": lines[:6]})
        return " ".join(lines)

    def sub_level_block_entities():
        # Test-only console command from tests/forge-assembly-probe.js; None when it is not installed.
        start = len(server.lines)
        server.send("psa_probe_sublevels")
        time.sleep(2)
        return next((json.loads(line.split("PSA_PROBE_SUBLEVELS ", 1)[1]) for line in server.lines[start:]
                     if "PSA_PROBE_SUBLEVELS " in line), None)

    near = "@e[type=item,x=%d,y=%d,z=%d,distance=..8]" % (x, y, z)
    command("forceload add %d %d" % (x, z), 20)
    command("fill %d %d %d %d %d %d minecraft:stone" % (x - 3, y - 1, z - 3, x + 3, y - 1, z + 3), 1)
    placed = command("setblock %d %d %d %s" % (x, y, z, block), 1)
    command('setblock %d %d %d minecraft:hopper[facing=down]{Items:[{Slot:0b,id:"minecraft:diamond",Count:%db}]}'
            % (x, y + 1, z, items), items * 0.5 + 3)
    hopper = command("data get block %d %d %d Items" % (x, y + 1, z), 1)
    stored = command("data get block %d %d %d" % (x, y, z), 1)
    command("setblock %d %d %d minecraft:air" % (x, y + 1, z), 1)
    command("kill " + near, 1)
    before = sub_level_block_entities()
    assembled = command("sable assemble area %d %d %d %d %d %d" % (x, y, z, x, y, z), 4)
    after = sub_level_block_entities()
    moved = None
    if before is not None and after is not None:
        known = {tuple(entity["pos"]) for entity in before}
        moved = [{"pos": entity["pos"], "diamonds": sum(
                      int(re.search(r"Count:(\d+)b", stack).group(1))
                      for stack in re.findall(r'\{[^{}]*id:"minecraft:diamond"[^{}]*\}', entity["data"])
                      if re.search(r"Count:(\d+)b", stack)),
                  "data": entity["data"][:300]}
                 for entity in after if tuple(entity["pos"]) not in known]
    dropped = command("execute if entity " + near, 1)
    detail = command("data get entity %s Item" % near.replace("]", ",limit=1,sort=nearest]"), 1)
    command("kill " + near, 1)
    command("forceload remove %d %d" % (x, z), 1)
    count = re.search(r"Test passed, count: (\d+)", dropped)
    return {"block": block, "placed": "Changed the block" in placed,
            "hopper_emptied_into_block": "diamond" not in hopper and "diamond" in stored,
            "assembled": "Assembled a region" in assembled,
            "moved_block_entities": moved,
            "items_in_moved_block_entities": None if moved is None else sum(entity["diamonds"] for entity in moved),
            "item_entities_dropped_by_removed_block": int(count.group(1)) if count else 0,
            "dropped_item": detail[:300] if count else None, "steps": steps}


ASSEMBLY_CELL = (8, 200, 136)  # the cell tests/forge-assembly-probe.js uses
ASSEMBLY_LINE = re.compile(r"PSA_ASSEMBLY_PROBE (\{.*\})\s*$")


def assembly_inventory_sweep(server, timeout=900):
    """Every registered block with a block entity: put one marked item into its inventory, assemble
    the block alone and see where the marked item is afterwards (tests/forge-assembly-probe.js).
    Returns (summary, one record per block).

    Batch results are read from KubeJS's own log file, see probe_lines()."""
    x, y, z = ASSEMBLY_CELL
    for text in ("forceload add %d %d" % (x, z),
                 "fill %d %d %d %d %d %d minecraft:stone" % (x - 3, y - 1, z - 3, x + 3, y - 1, z + 3)):
        server.send(text)
    time.sleep(20)
    log = server.profile / "logs/kubejs/server.log"
    offset = log.stat().st_size if log.is_file() else 0

    def next_batch():
        nonlocal offset
        deadline, position = time.time() + timeout, len(server.lines)
        server.send("psa_probe_assembly_next")
        while True:
            with log.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
            end = data.rfind(b"\n") + 1  # only whole lines
            for line in data[:end].decode("utf-8", "replace").splitlines():
                match = ASSEMBLY_LINE.search(line)
                if match:
                    offset += end
                    return json.loads(match.group(1))
            offset += end
            crash = next((line for line in server.lines[position:] if "This crash report has been saved to" in line), None)
            if crash is not None:
                server.crashed = True
                raise RuntimeError("Server crashed: " + crash[:300])
            if server.process.poll() is not None:
                raise RuntimeError("Server exited during the assembly sweep")
            if time.time() > deadline:
                raise TimeoutError("Timed out waiting for an assembly sweep batch")
            time.sleep(0.5)

    records, failed, total = [], None, None
    while failed is None:
        position = len(server.lines)
        try:
            batch = next_batch()
        except (RuntimeError, TimeoutError) as error:
            # The block named by the last PSA_ASSEMBLY_PROBE_AT line is the one being tested.
            at = [line.split("PSA_ASSEMBLY_PROBE_AT ", 1)[1].split() for line in server.lines[position:]
                  if "PSA_ASSEMBLY_PROBE_AT " in line]
            cause = next((line for line in server.lines[position:] if "Error:" in line or "Exception:" in line), "")
            failed = str(error)[:300]
            if at and server.crashed:
                records.append({"id": at[-1][1], "outcome": "server crash", "error": cause[-400:]})
            break
        records.extend(batch.get("records", []))
        failed, total = batch.get("failed"), batch.get("total", total)
        if batch["done"]:
            break
    if server.process.poll() is None and not server.crashed:
        server.send("forceload remove %d %d" % (x, z))
    outcomes = {}
    for record in records:
        outcomes.setdefault(record["outcome"], []).append(record["id"])
    listed = ("duplicated", "lost", "dropped, not moved", "not assembled", "error", "server crash", "skipped")
    summary = {"blocks_with_block_entity": None if total is None else int(total), "tested": len(records), "failed": failed,
               "outcome_counts": {name: len(ids) for name, ids in sorted(outcomes.items())}}
    summary.update({name: sorted(outcomes.get(name, [])) for name in listed})
    return summary, records


def probe_lines(server):
    """The probe's lines as KubeJS wrote them to its own log. The pack's log filter (Log Begone)
    removes console lines that match its phrase list, and long probe lines can contain such a
    phrase: one registry part and one sweep batch were seen missing from the console only."""
    log = server.profile / "logs/kubejs/server.log"
    return log.read_text(errors="replace").splitlines() if log.is_file() else server.lines


def pc_resend_check(server, profile, pause=8):
    """Pixelmon's login handler run for a stand-in player (tests/forge-pc-resync-probe.js). The
    handler must finish, and the PC resend class must have written its debug line for that player:
    nothing else asks for the stand-in's PC, because the login event itself is not posted."""
    start = len(server.lines)
    server.send("psa_probe_pc_resend")
    time.sleep(pause)
    record = next((json.loads(line.split("PSA_PROBE_PC_RESEND ", 1)[1]) for line in server.lines[start:]
                   if "PSA_PROBE_PC_RESEND " in line), None)
    log = profile / "logs/debug.log"
    wanted = "PC sent again after login: %s" % (record or {}).get("name")
    resent = record is not None and log.is_file() and any(
        "[PSA PC resync/]" in line and wanted in line for line in log.read_text(errors="replace").splitlines())
    result = {"handler_completed": bool(record and record["handler_completed"]), "error": record and record["error"],
              "resend_logged": resent}
    result["pass"] = result["handler_completed"] and result["resend_logged"]
    return result


def port_repair_checks(server, position=(8, 200, 200)):
    """Two situations in which the unrepaired port stops the server, driven from the console:
    a placed Create Redstone Contact, and a physics structure beside a Pixelmon multi-block machine.
    Run last: on the unrepaired port the first one ends the server and the second is not reached."""
    x, y, z = position
    steps, results = [], {}

    def command(text, pause):
        if server.crashed or server.process.poll() is not None:
            return None
        start = len(server.lines)
        server.send(text)
        time.sleep(pause)
        fresh = server.lines[start:]
        lines = [re.sub(r"^\[[0-9:]+\] \[[^]]*\] \[[^]]*\]: ", "", line)[:300] for line in fresh if "[mixin/]" not in line]
        if any("This crash report has been saved to" in line or "Encountered an unexpected exception" in line for line in fresh):
            server.crashed = True
        steps.append({"command": text, "console": lines[:4], "server_crashed": server.crashed})
        return " ".join(lines)

    def alive():
        return not server.crashed and server.process.poll() is None

    command("forceload add %d %d" % (x, z), 15)
    command("fill %d %d %d %d %d %d minecraft:stone" % (x - 3, y - 1, z - 3, x + 3, y - 1, z + 3), 1)
    placed = command("setblock %d %d %d create:redstone_contact" % (x, y, z), 6)
    data = command("data get block %d %d %d" % (x, y, z), 1)
    results["redstone_contact"] = {
        "placed": placed is not None and "Changed the block" in placed,
        "block_entity": data is not None and 'id: "create:redstone_contact"' in data, "server_alive": alive()}
    command("setblock %d %d %d minecraft:air" % (x, y, z), 1)
    machine = command("setblock %d %d %d pixelmon:red_pc" % (x + 2, y, z), 2)
    neighbour = command("setblock %d %d %d minecraft:stone" % (x + 2, y, z + 1), 1)
    command("setblock %d %d %d minecraft:oak_planks" % (x + 2, y, z - 1), 1)
    assembled = command("sable assemble area %d %d %d %d %d %d" % (x + 2, y, z - 1, x + 2, y, z - 1), 10)
    results["physics_beside_pixelmon_machine"] = {
        "machine_placed": machine is not None and "Changed the block" in machine,
        "neighbour_placed": neighbour is not None and "Changed the block" in neighbour,
        "assembled": assembled is not None and "Assembled a region" in assembled, "server_alive": alive()}
    command("sable remove @e", 2)
    command("fill %d %d %d %d %d %d minecraft:air" % (x - 3, y, z - 3, x + 3, y + 1, z + 3), 1)
    command("forceload remove %d %d" % (x, z), 1)
    for result in results.values():
        result["pass"] = all(result.values())
    return {"results": results, "steps": steps}


def read_back(world, village):
    """Compare the probe's assembly with what the game saved, then count blocks/entities."""
    saved = world.structure_pieces(village["chunk"][0], village["chunk"][1], village["structure"])
    result = {"structure": village["structure"], "chunk": village["chunk"], "spawn_distance": village["spawn_distance"],
              "saved_start_found": saved is not None}
    if saved is not None:
        # A start that was saved and loaded again has its piece boxes recomputed from the templates
        # (vanilla drops the jigsaw expansion), so pieces are matched by element and horizontal centre.
        placed = lambda rows: sorted((row[0], row[1] + row[4], row[3] + row[6]) for row in rows)
        result["saved_pieces"] = len(saved)
        result["probe_pieces"] = len(village["pieces"])
        result["assembly_matches_saved_start"] = placed(saved) == placed(village["pieces"])
        result["piece_boxes_identical"] = sorted(saved) == sorted(village["pieces"])
    pieces = []
    for piece in village["pieces"]:
        family = village_world.family_of(piece[0])
        if family in ("pokecenter", "mart", "tcg_shop", "berry_farm", "battle_arena", "daycare",
                      "society_fletcher_house", "town_centre"):
            pieces.append({"piece": piece[0], "family": family, "box": piece[1:], **world.census(piece[1:])})
    result["pieces"] = pieces
    return result


def read_back_failures(entries):
    """What the saved world contradicts: a generated village whose start was not saved, was saved
    with other pieces than the probe assembled, or lies in chunks that were not fully generated.
    Piece boxes are not compared: vanilla recomputes them when a saved start is loaded."""
    if entries is None:
        return ["read back: not performed"]
    failures = []
    for entry in entries:
        label = "%s at chunk %s" % (entry["structure"], ",".join(str(part) for part in entry["chunk"]))
        if not entry["saved_start_found"]:
            failures.append("read back: saved start missing, " + label)
        elif not entry["assembly_matches_saved_start"]:
            failures.append("read back: saved pieces differ, " + label)
        if any(piece["chunks_not_full"] for piece in entry["pieces"]):
            failures.append("read back: chunks not fully generated, " + label)
    return failures


def read_back_verdict(generated, failure, entries):
    """The read-back failures of one run. A run that failed before any village was generated has
    nothing to read back and fails anyway; every other run answers for its saved world."""
    if failure is not None and not generated:
        return []
    return read_back_failures(entries)


def run(profile, java, per_structure, margin, timeout, accept_eula):
    profile = Path(profile)
    if not (profile / MARKER).is_file():
        raise ValueError("Not a prepared village probe profile")
    if (profile / WORLD).exists():
        raise ValueError("The probe needs a world that has never been created")
    if accept_eula:
        (profile / "eula.txt").write_text("eula=true\n")
    if (profile / "eula.txt").read_text().strip() != "eula=true":
        raise ValueError("Read the Minecraft EULA, then pass --accept-eula")
    server = Server(profile, java)
    candidate = json.loads((profile / ".psa-forge-candidate.json").read_text())
    outcome = {"probe_sha256": digest(PROBE), "assembly_probe_sha256": digest(ASSEMBLY_PROBE),
               "pc_probe_sha256": digest(PC_PROBE),
               "mods_list_sha256": digest(profile / ".psa-mods.sha256"),
               "candidate": {key: candidate.get(key) is not None for key in (
                   "village_compatibility", "loot_compatibility", "overlay_compatibility")}}
    generated, failure, decision, world_saved = [], None, None, False
    try:
        done = server.wait_for(r"PSA_VILLAGE_PROBE_DONE", timeout,
                               fail=r"PSA_VILLAGE_PROBE_FAILED|psa_village_(probe|spawn)\.js#\d+: Error")
        probe = village_world.parse_probe_log(probe_lines(server))
        if (profile / SPAWN_SCRIPT).is_file():
            position = server.wait_for(SPAWN_LINE.pattern, timeout, fail=r"psa_village_spawn\.js#\d+: Error")
            decision = json.loads(SPAWN_LINE.search(server.lines[position - 1]).group(1))
            # Only when the start script ran after the probe did the probe record Society's own spawn.
            outcome["start_script_ran_after_probe"] = position > done
        outcome["physics_assembly"] = [physics_assembly_check(server, block, (8 + index * 32, 200, 8))
                                       for index, block in enumerate(PHYSICS_BLOCKS)]
        chosen = choose(probe["villages"], per_structure)
        start = spawn_village(probe["villages"], decision)
        if start is not None and start not in chosen:
            chosen.append(start)
        for village in chosen:
            generated.append((village, generate(server, village, margin, timeout)))
        position = len(server.lines)
        server.send("save-all flush")
        server.wait_for(r"Saved the game", timeout, position)
        world_saved = True
        # Last, after the save: a block that brings the server down ends only this sweep.
        outcome["assembly_inventory_sweep"], assembly_records = assembly_inventory_sweep(server, timeout)
        (profile / "assembly-probe-blocks.json").write_text(json.dumps(assembly_records, indent=1) + "\n")
        outcome["pc_resend"] = pc_resend_check(server, profile)
        outcome["port_repairs"] = port_repair_checks(server)
    except (RuntimeError, TimeoutError) as error:
        failure = str(error)
    outcome["stop_exit_code"] = server.stop()
    probe = village_world.parse_probe_log(probe_lines(server))
    outcome.update({
        "failure": failure, "probe_done": probe["done"], "probe_failed": probe["failed"],
        "spawn_before_start_script": probe["spawn"], "start_script_decision": decision, "census": probe["census"],
        "summary": village_world.summarize_villages(probe["villages"]),
        "checks": evaluate(json.loads(CHECKS.read_text()), probe), "checks_sha256": digest(CHECKS),
        "radium": radium(server.lines), "kubejs_server_script_errors": kubejs_errors(profile),
        # Vanilla village pools as loaded: the Pixelmon elements in each, by weight.
        "pixelmon_elements_in_vanilla_village_pools": {
            pool: {name: int(weight) for name, weight in data["elements"].items() if name.startswith("pixelmon:")}
            for pool, data in sorted(probe["pools"].items()) if pool.startswith("minecraft:village/")
            and pool.rsplit("/", 1)[1] in ("houses", "streets", "terminators")},
        "pixelmon_hooks_in_town_centres": {
            name.split("town_centers/")[1]: {"size": data["size"], "hooks": int(sum(
                count for pool, count in data["jigsaw_pools"].items() if pool.startswith("pixelmon:")))}
            for name, data in sorted(probe["templates"].items())},
        "worldgen_log_problems": sorted({re.sub(r"^\[[0-9:]+\] ", "", line)[:300]
                                         for line in server.lines if PROBLEM.search(line) and "[mixin/]" not in line}),
    })
    sweep = outcome.get("assembly_inventory_sweep")
    if sweep is None or sweep["failed"] or sweep["duplicated"] or sweep["lost"] or sweep["server crash"]:
        outcome["checks"]["failed"].append("assembly_inventory_sweep")
    repairs = (outcome.get("port_repairs") or {}).get("results", {})
    outcome["checks"]["failed"] += ["port_repairs:" + name for name in ("redstone_contact", "physics_beside_pixelmon_machine")
                                    if not repairs.get(name, {}).get("pass")]
    if not (outcome.get("pc_resend") or {}).get("pass"):
        outcome["checks"]["failed"].append("pc_resend")
    outcome["probe_records_incomplete"] = probe["incomplete"]
    outcome["checks"]["failed"] += ["probe records: " + item for item in probe["incomplete"]]
    if world_saved and failure is None and (outcome["stop_exit_code"] == 0 or server.crashed):
        world = village_world.World(profile / WORLD)
        saved = village_world.level_spawn(profile / WORLD)
        outcome["level_dat_spawn"] = saved
        outcome["generated"] = [dict(read_back(world, village), chunky=task) for village, task in generated]
        start = spawn_village(probe["villages"], decision)
        if start is not None:
            x0, _, z0, x1, _, z1 = start["box"]
            centre = start["pieces"][0][1:]
            outcome["start_village"] = {
                "structure": start["structure"], "chunk": start["chunk"],
                "saved_spawn_inside_village_box": x0 <= saved["x"] <= x1 and z0 <= saved["z"] <= z1,
                "saved_spawn_to_town_centre": round(((saved["x"] - (centre[0] + centre[3]) / 2) ** 2
                                                     + (saved["z"] - (centre[2] + centre[5]) / 2) ** 2) ** 0.5),
                "pieces": sorted({village_world.family_of(piece[0]) for piece in start["pieces"]} - {None})}
    outcome["checks"]["failed"] += read_back_verdict(generated, failure, outcome.get("generated"))
    (profile / "village-probe-villages.json").write_text(json.dumps(probe["villages"]) + "\n")
    (profile / "village-probe-registries.json").write_text(json.dumps(probe["registries"], sort_keys=True) + "\n")
    outcome["registry_sizes"] = {name: len(ids) for name, ids in sorted(probe["registries"].items())}
    return outcome


def exit_code(outcome, allow_failed_checks=False):
    """0 only for a run that finished, stopped cleanly and failed no check. An unrepaired profile is
    expected to fail checks and to end in a crash; --allow-failed-checks records it with 0 anyway,
    but never when the run did not finish or the server could not be stopped (no exit code: it was
    left running and the saved world was not read back)."""
    if outcome["failure"] is not None or outcome["stop_exit_code"] is None:
        return 1
    if allow_failed_checks:
        return 0
    return 0 if outcome["stop_exit_code"] == 0 and not outcome["checks"]["failed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="staged profile to copy (never modified)")
    parser.add_argument("--destination", type=Path, required=True, help="fresh disposable probe profile")
    parser.add_argument("--libraries", type=Path, required=True, help="installed Forge 47.4.20 server libraries")
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=25591)
    parser.add_argument("--seed", default="20261112")
    parser.add_argument("--generate-per-structure", type=int, default=2)
    parser.add_argument("--margin", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=1500)
    parser.add_argument("--accept-eula", action="store_true")
    parser.add_argument("--allow-failed-checks", action="store_true",
                        help="exit 0 although checks failed; for recording an unrepaired profile")
    parser.add_argument("--skip-in-sweep", action="append", default=[], metavar="BLOCK",
                        help="block id the assembly sweep must not place (it stops this profile's server)")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing result")
    if not args.java.is_file():
        raise SystemExit("Java 17 executable not found")
    profile = prepare(args.source, args.destination, args.libraries, args.port, args.seed, args.skip_in_sweep)
    outcome = run(profile, args.java, args.generate_per_structure, args.margin, args.timeout, args.accept_eula)
    outcome["assembly_sweep_skip"] = sorted(args.skip_in_sweep)
    args.output.write_text(json.dumps(outcome, indent=1, sort_keys=True) + "\n")
    print(json.dumps({key: outcome.get(key) for key in (
        "failure", "probe_done", "stop_exit_code", "spawn_before_start_script", "start_script_decision",
        "level_dat_spawn", "start_village", "census", "radium", "kubejs_server_script_errors")}, indent=1))
    print("checks failed:", outcome["checks"]["failed"])
    return exit_code(outcome, args.allow_failed_checks)


if __name__ == "__main__":
    raise SystemExit(main())
