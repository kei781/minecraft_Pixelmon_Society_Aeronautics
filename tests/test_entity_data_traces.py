import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_entity_data_traces import compare, read_trace


class EntityDataTraceTests(unittest.TestCase):
    def test_real_counterfactual_player_failure_and_repaired_orders(self):
        evidence = json.loads((Path(__file__).resolve().parents[1] / "evidence/entity-data-initialization-regression.json").read_text())
        sides = []
        for case in evidence["cases"]:
            # The independently executed full-pack schemas are the regression oracle.
            sides.append({"Player": [{"id": f["id"], "serializer_class": f["serializer"],
                                       "allocator": f["owner"] + "#" + f["field"]}
                                      for f in sorted(case["player_schema"]["fields"], key=lambda f: f["id"])]})
        self.assertFalse(compare(sides[0], sides[1], ["Player"])["required_observed_schemas_match"])
        self.assertTrue(compare(sides[2], sides[3], ["Player"])["required_observed_schemas_match"])

    def test_missing_required_owner_cannot_pass(self):
        result = compare({"Player": []}, {"Player": []}, ["Player", "TankCart"])
        self.assertFalse(result["required_observed_schemas_match"])
        self.assertEqual(result["missing_required_owners"], ["TankCart"])

    def test_disjoint_observations_cannot_pass(self):
        self.assertFalse(compare({"A": []}, {"B": []})["required_observed_schemas_match"])

    def test_uncompared_owners_remain_explicit(self):
        result = compare({"Player": [], "UnobservedOnClient": []}, {"Player": []}, ["Player"])
        self.assertTrue(result["required_observed_schemas_match"])
        self.assertEqual(result["left_only_owners"], ["UnobservedOnClient"])
        self.assertFalse(result["all_registered_entities_or_gameplay_verified"])

    def test_merged_runs_and_empty_logs_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.txt"
            line = "PSA_ENTITY_DATA owner=Player id=22 serializer_class=Compound callers=Carry#<clinit> <- Player#init\n"
            path.write_text(line)
            self.assertEqual(read_trace(path)["Player"][0]["id"], 22)
            path.write_text(line * 2)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                read_trace(path)
            path.write_text("No observations\n")
            with self.assertRaisesRegex(ValueError, "No observed"):
                read_trace(path)


if __name__ == "__main__":
    unittest.main()
