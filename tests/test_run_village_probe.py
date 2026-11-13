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


class ExitCodeTest(unittest.TestCase):
    def test_a_failed_check_fails_the_command_unless_an_unrepaired_profile_is_being_recorded(self):
        clean = {"failure": None, "stop_exit_code": 0, "checks": {"failed": []}}
        failed = {"failure": None, "stop_exit_code": 0, "checks": {"failed": ["crafting:box"]}}
        crashed = {"failure": None, "stop_exit_code": -9, "checks": {"failed": ["port_repairs:redstone_contact"]}}
        unfinished = {"failure": "Timed out", "stop_exit_code": 0, "checks": {"failed": []}}
        self.assertEqual([driver.exit_code(outcome) for outcome in (clean, failed, crashed, unfinished)], [0, 1, 1, 1])
        self.assertEqual([driver.exit_code(outcome, True) for outcome in (clean, failed, crashed, unfinished)], [0, 0, 0, 1])


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
