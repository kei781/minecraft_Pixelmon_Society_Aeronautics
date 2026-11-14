import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import run_village_probe as driver
import village_world


class FakeProcess:
    def __init__(self):
        self.code = None

    def poll(self):
        return self.code


class FakeServer:
    """Stands in for a running server: answers each sweep command with the next scripted step."""

    def __init__(self, profile, steps):
        self.profile, self.steps = Path(profile), list(steps)
        self.lines, self.sent, self.crashed, self.process = [], [], False, FakeProcess()
        (self.profile / "logs/kubejs").mkdir(parents=True)
        self.log = self.profile / "logs/kubejs/server.log"
        self.log.write_text("[INFO] earlier line PSA_ASSEMBLY_PROBE {\"done\":true,\"records\":[]}\n")

    def send(self, command):
        self.sent.append(command)
        if command != "psa_probe_assembly_next":
            return
        kind, value = self.steps.pop(0)
        if kind == "batch":
            with self.log.open("a") as handle:
                handle.write("[INFO] psa_assembly_probe.js#1: PSA_ASSEMBLY_PROBE " + json.dumps(value) + "\n")
        elif kind == "crash":
            self.lines += ["[KubeJS Server/]: psa_assembly_probe.js#1: PSA_ASSEMBLY_PROBE_AT 7 " + value,
                           "java.lang.IncompatibleClassChangeError: Method must be Methodref constant",
                           "[minecraft/MinecraftServer]: This crash report has been saved to: crash.txt"]


def record(block, outcome):
    return {"id": block, "outcome": outcome}


class AssemblySweepTest(unittest.TestCase):
    def sweep(self, steps):
        with tempfile.TemporaryDirectory() as folder, patch.object(driver.time, "sleep", lambda seconds: None):
            server = FakeServer(folder, steps)
            return driver.assembly_inventory_sweep(server, timeout=5) + (server,)

    def test_batches_are_read_from_the_script_log_until_done(self):
        summary, records, server = self.sweep([
            ("batch", {"done": False, "total": 3.0, "records": [record("a:vault", "duplicated"), record("a:chest", "moved")]}),
            ("batch", {"done": True, "total": 3.0, "records": [record("a:sign", "no inventory found for the marked item")]})])
        self.assertEqual([entry["id"] for entry in records], ["a:vault", "a:chest", "a:sign"])
        self.assertEqual(summary["blocks_with_block_entity"], 3)
        self.assertEqual(summary["duplicated"], ["a:vault"])
        self.assertEqual(summary["lost"], [])
        self.assertIsNone(summary["failed"])
        self.assertEqual(summary["outcome_counts"], {"duplicated": 1, "moved": 1, "no inventory found for the marked item": 1})
        self.assertEqual(server.sent.count("psa_probe_assembly_next"), 2)  # the line written before the sweep is not a batch
        self.assertEqual(server.sent[-1], "forceload remove 8 136")

    def test_a_crash_is_charged_to_the_block_being_tested(self):
        summary, records, server = self.sweep([
            ("batch", {"done": False, "total": 9.0, "records": [record("a:chest", "moved")]}), ("crash", "create:redstone_contact")])
        self.assertTrue(server.crashed)
        self.assertEqual(summary["server crash"], ["create:redstone_contact"])
        self.assertIn("IncompatibleClassChangeError", records[-1]["error"])
        self.assertIn("Server crashed", summary["failed"])
        self.assertNotIn("forceload remove 8 136", server.sent)

    def test_a_script_failure_ends_the_sweep_and_is_reported(self):
        summary, _, _ = self.sweep([("batch", {"done": True, "failed": "TypeError: x"})])
        self.assertEqual(summary["failed"], "TypeError: x")
        self.assertEqual(summary["tested"], 0)


class PortRepairCheckTest(unittest.TestCase):
    class Console:
        """Answers console commands; `crash_on` names the command that ends the server."""

        def __init__(self, crash_on=None):
            self.lines, self.sent, self.crashed, self.process, self.crash_on = [], [], False, FakeProcess(), crash_on

        def send(self, command):
            self.sent.append(command)
            if self.crash_on and self.crash_on in command:
                self.lines.append("[minecraft/MinecraftServer]: This crash report has been saved to: crash.txt")
            elif command.startswith("setblock"):
                self.lines.append("[Server thread/INFO] [minecraft/MinecraftServer]: Changed the block at 1, 2, 3")
            elif command.startswith("data get"):
                self.lines.append('[Server thread/INFO] [minecraft/MinecraftServer]: 1, 2, 3 has the following block data: {id: "create:redstone_contact"}')
            elif command.startswith("sable assemble"):
                self.lines.append("[Server thread/INFO] [minecraft/MinecraftServer]: Assembled a region 1 blocks to a new sub-level")

    def check(self, console):
        with patch.object(driver.time, "sleep", lambda seconds: None):
            return driver.port_repair_checks(console)

    def test_both_situations_pass_on_a_server_that_survives_them(self):
        outcome = self.check(self.Console())
        self.assertEqual({name: result["pass"] for name, result in outcome["results"].items()},
                         {"redstone_contact": True, "physics_beside_pixelmon_machine": True})

    def test_a_crash_fails_the_step_that_caused_it_and_nothing_is_sent_afterwards(self):
        console = self.Console(crash_on="create:redstone_contact")
        outcome = self.check(console)
        self.assertFalse(outcome["results"]["redstone_contact"]["pass"])
        self.assertFalse(outcome["results"]["physics_beside_pixelmon_machine"]["pass"])
        self.assertTrue(console.sent[-1].startswith("setblock") and "create:redstone_contact" in console.sent[-1])
        later = self.Console(crash_on="sable assemble")
        outcome = self.check(later)
        self.assertTrue(outcome["results"]["redstone_contact"]["pass"])
        self.assertFalse(outcome["results"]["physics_beside_pixelmon_machine"]["server_alive"])


class PcResendCheckTest(unittest.TestCase):
    class Console:
        def __init__(self, record):
            self.lines, self.record = [], record

        def send(self, command):
            if self.record is not None:
                self.lines.append("[KubeJS Server/]: probe.js#24: PSA_PROBE_PC_RESEND " + json.dumps(self.record))

    def check(self, record, debug_lines):
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder)
            if debug_lines is not None:
                (profile / "logs").mkdir()
                (profile / "logs/debug.log").write_text("\n".join(debug_lines) + "\n")
            with patch.object(driver.time, "sleep", lambda seconds: None):
                return driver.pc_resend_check(self.Console(record), profile)

    def test_passes_only_when_the_handler_finished_and_the_class_logged_the_resend_for_that_player(self):
        done = {"name": "PSA_PC_Probe", "handler_completed": True, "error": None}
        line = "[Server thread/DEBUG] [PSA PC resync/]: PC sent again after login: PSA_PC_Probe"
        self.assertTrue(self.check(done, [line])["pass"])
        cases = {"no debug log": (done, None),
                 "no resend line": (done, ["[Server thread/DEBUG] [other/]: unrelated"]),
                 "resend for another player": (done, [line.replace("PSA_PC_Probe", "Someone")]),
                 "same text from another logger": (done, [line.replace("[PSA PC resync/]", "[chat/]")]),
                 "handler threw": (dict(done, handler_completed=False, error="boom"), [line]),
                 "command gave no record": (None, [line])}
        for reason, (record, lines) in cases.items():
            with self.subTest(reason):
                self.assertFalse(self.check(record, lines)["pass"])


class ExitCodeTest(unittest.TestCase):
    def test_a_failed_check_fails_the_command_unless_an_unrepaired_profile_is_being_recorded(self):
        clean = {"failure": None, "stop_exit_code": 0, "checks": {"failed": []}}
        failed = {"failure": None, "stop_exit_code": 0, "checks": {"failed": ["crafting:box"]}}
        crashed = {"failure": None, "stop_exit_code": -9, "checks": {"failed": ["port_repairs:redstone_contact"]}}
        unfinished = {"failure": "Timed out", "stop_exit_code": 0, "checks": {"failed": []}}
        still_running = {"failure": None, "stop_exit_code": None, "checks": {"failed": []}}
        outcomes = (clean, failed, crashed, unfinished, still_running)
        self.assertEqual([driver.exit_code(outcome) for outcome in outcomes], [0, 1, 1, 1, 1])
        self.assertEqual([driver.exit_code(outcome, True) for outcome in outcomes], [0, 0, 0, 1, 1])


class ReadBackVerdictTest(unittest.TestCase):
    def test_a_saved_world_that_contradicts_the_probe_fails_the_run(self):
        def village(found=True, same=True, not_full=0):
            entry = {"structure": "minecraft:village_plains", "chunk": [3, -4], "saved_start_found": found,
                     "pieces": [{"chunks_not_full": 0}, {"chunks_not_full": not_full}]}
            if found:
                entry["assembly_matches_saved_start"] = same
            return entry
        self.assertEqual(driver.read_back_failures([village(), village()]), [])
        self.assertEqual(driver.read_back_failures([]), [])
        self.assertEqual(driver.read_back_failures(None), ["read back: not performed"])
        where = ", minecraft:village_plains at chunk 3,-4"
        self.assertEqual(driver.read_back_failures([village(found=False), village(same=False), village(not_full=2)]),
                         ["read back: saved start missing" + where, "read back: saved pieces differ" + where,
                          "read back: chunks not fully generated" + where])


    def test_every_run_that_generated_villages_answers_for_its_saved_world(self):
        village = {"structure": "minecraft:village_plains", "chunk": [3, -4], "saved_start_found": True,
                   "assembly_matches_saved_start": True, "pieces": [{"chunks_not_full": 0}]}
        task = (village, {"task": "done"})
        self.assertEqual(driver.read_back_verdict([task], None, [village]), [])
        self.assertEqual(driver.read_back_verdict([], None, []), [])
        # The server could not be stopped or the world was not saved: nothing was read back.
        self.assertEqual(driver.read_back_verdict([task], None, None), ["read back: not performed"])
        self.assertEqual(driver.read_back_verdict([task], "Timed out", None), ["read back: not performed"])
        self.assertEqual(driver.read_back_verdict([], None, None), ["read back: not performed"])
        # A probe that failed before generating anything fails the run by itself.
        self.assertEqual(driver.read_back_verdict([], "PSA_VILLAGE_PROBE_FAILED", None), [])


class PrepareTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source, self.libraries = self.root / "source", self.root / "libraries"
        for name in ("mods", "config", "defaultconfigs", "kubejs/server_scripts", "patchouli_books"):
            (self.source / name).mkdir(parents=True)
        for name in (".psa-forge-candidate.json", ".psa-mods.sha256", ".psa-owned-smoke-test", "user_jvm_args.txt"):
            (self.source / name).write_text("{}")
        (self.source / "kubejs/server_scripts/society.js").write_text("// Society")
        forge = self.libraries / "net/minecraftforge/forge/1.20.1-47.4.20"
        forge.mkdir(parents=True)
        (forge / "unix_args.txt").write_text("")

    def files(self, folder):
        return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))

    def test_the_copy_gets_the_probe_scripts_and_the_source_stays_as_it_was(self):
        before = self.files(self.source)
        profile = driver.prepare(self.source, self.root / "probe", self.libraries, 25591, "1")
        self.assertEqual(self.files(self.source), before)
        scripts = sorted(path.name for path in (profile / "kubejs/server_scripts").iterdir())
        self.assertEqual(scripts, ["psa_assembly_probe.js", "psa_pc_resync_probe.js", "psa_probe_spec.js", "psa_village_probe.js", "society.js"])

    def test_a_link_inside_a_profile_folder_is_refused_before_anything_is_written(self):
        shared = self.root / "shared"
        shared.mkdir()
        (shared / "psa_village_probe.js").write_text("// somebody else's file")
        (self.source / "kubejs/server_scripts/society.js").unlink()
        (self.source / "kubejs/server_scripts").rmdir()
        (self.source / "kubejs/server_scripts").symlink_to(shared, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symbolic link: kubejs/server_scripts"):
            driver.prepare(self.source, self.root / "probe", self.libraries, 25591, "1")
        self.assertFalse((self.root / "probe").exists())
        self.assertEqual(self.files(shared), ["psa_village_probe.js"])
        self.assertEqual((shared / "psa_village_probe.js").read_text(), "// somebody else's file")
        (self.source / "kubejs/server_scripts").unlink()
        (self.source / "kubejs/server_scripts").mkdir()
        (self.source / "config/linked.toml").symlink_to(self.root / "missing.toml")  # a dangling file link
        with self.assertRaisesRegex(ValueError, "symbolic link: config/linked.toml"):
            driver.prepare(self.source, self.root / "probe", self.libraries, 25591, "1")


class ProbeRecordTest(unittest.TestCase):
    def test_a_registry_part_that_never_arrived_is_reported(self):
        line = "[INFO] psa_village_probe.js#25: PSA_VILLAGE_PROBE registry %s"
        probe = village_world.parse_probe_log([
            line % json.dumps({"name": "block", "total": 4.0, "offset": 0.0, "ids": ["a:a", "a:b"]}),
            line % json.dumps({"name": "structure", "total": 1.0, "offset": 0.0, "ids": ["a:s"]})])
        self.assertEqual(probe["incomplete"], ["registry block: 2 of 4 ids"])
        self.assertEqual(probe["registries"]["structure"], ["a:s"])


if __name__ == "__main__":
    unittest.main()
