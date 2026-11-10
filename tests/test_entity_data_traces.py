import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_entity_data_traces import compare, read_trace


class EntityDataTraceTests(unittest.TestCase):
    def cases_by_metadata(self):
        evidence = json.loads((Path(__file__).resolve().parents[1] / "evidence/entity-data-initialization-regression.json").read_text())
        cases = {(c["patched"], c["requested_player_order"], c["requested_cart_order"]): c
                 for c in reversed(evidence["cases"])}
        self.assertEqual(len(cases), 4)
        return cases

    @staticmethod
    def normalized(owner, fields):
        return {owner: [{"id": f["id"], "serializer_class": f["serializer"],
                         "allocator": f["owner"] + "#" + f["field"]}
                        for f in sorted(fields, key=lambda f: f["id"])]}

    def test_real_counterfactual_player_failure_and_repaired_orders(self):
        cases = self.cases_by_metadata()
        for patched in [False, True]:
            a = cases[(patched, "carryon-first", "tank-first")]
            b = cases[(patched, "pixelmon-first", "flag-first")]
            left = self.normalized("Player", a["player_schema"]["fields"])
            right = self.normalized("Player", b["player_schema"]["fields"])
            self.assertEqual(len(left["Player"]), 10)
            self.assertEqual(compare(left, right, ["Player"])["required_observed_schemas_match"], patched)

    def test_real_counterfactual_cart_failure_and_repaired_orders(self):
        cases = self.cases_by_metadata()
        for patched in [False, True]:
            sides = []
            for player_order, cart_order in [("carryon-first", "tank-first"), ("pixelmon-first", "flag-first")]:
                side = {}
                for cart in cases[(patched, player_order, cart_order)]["minecart_schemas"]:
                    side.update(self.normalized(cart["entity_type"], cart["fields"]))
                sides.append(side)
            self.assertEqual(compare(*sides, ["moreminecarts:flag_cart", "moreminecarts:tank_cart"])
                             ["required_observed_schemas_match"], patched)

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

    def test_shared_helper_does_not_hide_different_initializers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.txt"
            base = "PSA_ENTITY_DATA owner=BaseEntity id=22 serializer_class=Generic callers=DataSync#<init> <- {}#<clinit> <- Loader#load\n"
            path.write_text(base.format("Pokemon"))
            left = read_trace(path)
            path.write_text(base.format("BaseEntity"))
            right = read_trace(path)
            self.assertFalse(compare(left, right, ["BaseEntity"])["required_observed_schemas_match"])


if __name__ == "__main__":
    unittest.main()
