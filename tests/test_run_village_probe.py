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


class EvaluateTest(unittest.TestCase):
    def test_right_click_refusals_are_compared_with_the_expectation(self):
        line = "[KubeJS Server/]: psa_village_probe.js#25: PSA_VILLAGE_PROBE right_click %s"
        probe = village_world.parse_probe_log([
            line % json.dumps({"item": "create:redstone_contact", "registered": True, "canceled": False}),
            line % json.dumps({"item": "minecraft:cobblestone", "registered": True, "canceled": False})])
        spec = {"right_click": [{"item": "create:redstone_contact", "expect_refused": True},
                                {"item": "minecraft:cobblestone", "expect_refused": False},
                                {"item": "minecraft:stone", "expect_refused": False}]}
        results = driver.evaluate(spec, probe)
        self.assertEqual([entry["pass"] for entry in results["right_click"]], [False, True, False])
        self.assertEqual(results["failed"], ["right_click:create:redstone_contact", "right_click:minecraft:stone"])


if __name__ == "__main__":
    unittest.main()
