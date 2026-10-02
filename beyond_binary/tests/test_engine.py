"""Unit tests for core rules and hot/cold seed."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from beyond_binary.engine import Engine, RuleError
from beyond_binary.model import CenterAction, Hemisphere, Torus
from beyond_binary.seed import seed_hot_cold
from beyond_binary import store


class SeedTests(unittest.TestCase):
    def test_hot_cold_cascade_structure(self):
        eng = Engine(seed_hot_cold())
        self.assertEqual(eng.torus.instance, "hot-cold")
        self.assertEqual(eng.get("hot").hemisphere, Hemisphere.CAUSE)
        self.assertEqual(eng.get("cold").hemisphere, Hemisphere.EFFECT)
        self.assertEqual(eng.get("hot").opposite, "cold")
        self.assertEqual(eng.get("boiling").parent, "hot")
        self.assertEqual(eng.get("boiling").opposite, "freezing")
        self.assertEqual(eng.get("water").parent, "boiling")
        self.assertEqual(eng.get("water").opposite, "condensation")
        self.assertEqual(eng.get("condensation").parent, "cold")
        self.assertEqual(eng.get("freezing").parent, "cold")
        eng.assert_no_orphans()

    def test_answer_spans_both_hemispheres(self):
        eng = Engine(seed_hot_cold())
        dual = eng.answer("water")
        self.assertTrue(dual.cause_paths)
        self.assertTrue(dual.effect_paths)
        self.assertEqual(dual.cause_paths[0], ["hot", "boiling", "water"])
        self.assertEqual(dual.effect_paths[0], ["cold", "condensation"])
        self.assertIn(("water", "condensation"), dual.between)


class RuleTests(unittest.TestCase):
    def test_refuse_duplicate(self):
        eng = Engine(seed_hot_cold())
        with self.assertRaises(RuleError):
            eng.add_pair("hot", "chilly")

    def test_add_under_creates_opposite_immediately(self):
        eng = Engine(Torus())
        eng.add_pair("hot", "cold")
        child, opp = eng.add_under("hot", "warm", opposite_name="cool")
        self.assertEqual(child.opposite, "cool")
        self.assertEqual(opp.opposite, "warm")
        eng.assert_no_orphans()

    def test_merge_dedupes_with_opposite_pair(self):
        eng = Engine(Torus())
        eng.add_pair("hot", "cold")
        eng.add_under("hot", "boiling", opposite_name="freezing")
        eng.add_under("hot", "scalding", opposite_name="chilling")
        eng.merge("scalding", "boiling")
        self.assertFalse(eng.exists("scalding"))
        self.assertFalse(eng.exists("chilling"))
        self.assertEqual(eng.get("boiling").opposite, "freezing")
        self.assertEqual(eng.get("freezing").opposite, "boiling")
        eng.assert_no_orphans()

    def test_migrate_opposite(self):
        eng = Engine(seed_hot_cold())
        # After merge-style setup: migrate water's opposite from condensation to freezing
        # would orphan condensation — refuse.
        with self.assertRaises(RuleError):
            eng.migrate_link("water", new_opposite="freezing")

    def test_center_with_topic_is_dual(self):
        eng = Engine(seed_hot_cold())
        payload = eng.center(CenterAction.REVIEW, "hot")
        self.assertIn("dual", payload)
        self.assertTrue(payload["dual"]["cause_paths"])
        self.assertTrue(payload["dual"]["effect_paths"])

    def test_one_hemisphere_answer_refused_for_orphan(self):
        eng = Engine(Torus())
        eng.torus.nodes["alone"] = __import__(
            "beyond_binary.model", fromlist=["Node"]
        ).Node(name="alone", hemisphere=Hemisphere.CAUSE)
        with self.assertRaises(RuleError):
            eng.answer("alone")


class StoreCliSmoke(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "torus.json"
            torus = seed_hot_cold()
            store.save(torus, path)
            loaded = store.load(path)
            self.assertEqual(loaded.instance, "hot-cold")
            self.assertIn("water", loaded.nodes)
            # JSON is stable enough to re-parse
            data = json.loads(path.read_text())
            self.assertEqual(data["nodes"]["water"]["opposite"], "condensation")


if __name__ == "__main__":
    unittest.main()
