"""Logic of the Miltank milk script against stand-ins; needs Node.js, loads no game class."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "compat/coexistence/overlay/kubejs/server_scripts/psa_miltank_milk.js"
HARNESS = ROOT / "tests/overlay-milk-harness.cjs"


@unittest.skipUnless(shutil.which("node"), "Node.js not installed")
class MiltankMilkScriptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        done = subprocess.run(["node", str(HARNESS), str(SCRIPT)], capture_output=True, text=True, check=True)
        cls.results = json.loads(done.stdout)

    def test_milk_reaches_the_player_whether_it_lands_in_the_inventory_or_on_the_ground(self):
        wanted = {"inventory": {"minecraft:bucket": 1, "society:milk": 1}, "ground": [], "society_refusals": 0}
        self.assertEqual(self.results["single_bucket"], wanted)
        self.assertEqual(self.results["stack_with_room"],
                         {"inventory": {"minecraft:bucket": 3, "society:milk": 1}, "ground": [], "society_refusals": 0})
        # No free slot: what Pixelmon drops is already society:milk and the bucket is back in its stack.
        self.assertEqual(self.results["stack_with_full_inventory"],
                         {"inventory": {"minecraft:bucket": 3, "minecraft:cobblestone": 192},
                          "ground": ["society:milk x1"], "society_refusals": 0})

    def test_milk_that_no_milking_produced_stays_under_societys_rule(self):
        self.assertEqual(self.results["foreign_milk_bucket"],
                         {"inventory": {"minecraft:bucket": 1}, "ground": [], "society_refusals": 1})
        self.assertEqual(self.results["unrelated_drop"], {"dropped": "minecraft:milk_bucket", "inventory": {}})
        later = self.results["dropped_then_foreign_bucket"]
        self.assertEqual(later["ground"], ["society:milk x1"])
        self.assertEqual(later["society_refusals"], 1)
        self.assertNotIn("society:milk", later["inventory"])
        self.assertEqual(self.results["warnings"], [])


if __name__ == "__main__":
    unittest.main()
