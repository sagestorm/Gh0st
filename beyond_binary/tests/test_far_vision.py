"""Phases 3–6: cross-domain, metacognition, embody, autonomy + Sourcery fixes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from beyond_binary.center import LivingCenter
from beyond_binary.engine import Engine, RuleError
from beyond_binary.model import Hemisphere, Node
from beyond_binary.seed import seed_domain, seed_minimal_hot_cold
from beyond_binary import bodies, store
from beyond_binary.__main__ import main


class CrossDomainTests(unittest.TestCase):
    def test_ontology_grows_from_minimal(self):
        eng = Engine(seed_domain("ontology", minimal=True))
        center = LivingCenter(eng)
        center.think(5)
        names = set(eng.torus.nodes)
        self.assertIn("nothing", names)
        self.assertIn("something", names)
        self.assertTrue({"absence", "presence", "void", "form", "empty", "filled"} & names)

    def test_optical_grows_from_minimal(self):
        eng = Engine(seed_domain("optical", minimal=True))
        center = LivingCenter(eng)
        center.think(4)
        names = set(eng.torus.nodes)
        self.assertIn("light", names)
        self.assertIn("dark", names)
        self.assertTrue({"bright", "dim", "day", "night", "glow", "shadow"} & names)


class MetacognitionTests(unittest.TestCase):
    def test_strategy_differs_after_contrasting_histories(self):
        eng = Engine(seed_minimal_hot_cold())
        hungry = LivingCenter(eng).metacognize([])
        self.assertEqual(hungry.reason, "no_history")
        self.assertGreaterEqual(hungry.grow_budget, 1)

        stalled_history = [
            {
                "cycle": i,
                "nodes_before": 10,
                "nodes_after": 10,
                "acts": [
                    {"act": "grow", "detail": {"count": 1}},
                    {"act": "challenge", "detail": {"one_sided": False}},
                    {"act": "prune", "detail": {"count": 0}},
                ],
            }
            for i in range(1, 5)
        ]
        eng2 = Engine(seed_minimal_hot_cold())
        stalled = LivingCenter(eng2).metacognize(stalled_history)
        self.assertEqual(stalled.reason, "stalled_after_growth")
        self.assertTrue(stalled.prefer_migrate)
        self.assertEqual(stalled.grow_budget, 0)
        self.assertNotEqual(hungry.reason, stalled.reason)


class EmbodyTests(unittest.TestCase):
    def test_embody_creates_registered_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            mind = Engine(seed_minimal_hot_cold())
            store.save(mind.torus, mind_path)
            record = bodies.embody(
                mind, name="form-a", domain="ontology", mind_store=mind_path
            )
            self.assertTrue(Path(record.store_path).exists())
            body = store.load(record.store_path)
            self.assertIn("nothing", body.nodes)
            self.assertIn("something", body.nodes)
            registry = bodies.load_registry(mind_path)
            self.assertEqual(len(registry.bodies), 1)
            self.assertEqual(registry.bodies[0].name, "form-a")
            # Invariants on body
            body_eng = Engine(body)
            body_eng.assert_no_orphans()
            dual = body_eng.answer("nothing")
            self.assertTrue(dual.cause_paths)
            self.assertTrue(dual.effect_paths)


class SourceryFixTests(unittest.TestCase):
    def test_cycle_index_continues_from_history(self):
        eng = Engine(seed_minimal_hot_cold())
        history = [{"cycle": 7, "nodes_before": 2, "nodes_after": 2, "acts": []}]
        center = LivingCenter(eng, history=history)
        report = center.cycle()
        self.assertEqual(report.cycle, 8)

    def test_challenge_dangling_does_not_abort(self):
        eng = Engine(seed_minimal_hot_cold())
        # Plant a dangling opposite.
        eng.torus.nodes["hot"].opposite = "missing-node"
        center = LivingCenter(eng)
        report = center.cycle()  # must not raise
        challenge = next(a for a in report.acts if a.act == "challenge")
        self.assertTrue(challenge.detail["one_sided"])
        self.assertTrue(
            any(f["flag"] == "dangling_opposite" for f in challenge.detail["flags"])
        )

    def test_store_after_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json"
            rc = main(["seed-minimal", "--store", str(path), "--force"])
            self.assertEqual(rc, 0)
            self.assertTrue(path.exists())


class AutonomyTests(unittest.TestCase):
    def test_autonomy_runs_and_can_embody(self):
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_minimal_hot_cold())
            store.save(eng.torus, mind_path)
            center = LivingCenter(eng, history=[])
            center.mind_store = mind_path
            result = center.autonomy(
                2, embody_every=2, embody_domain="optical", mind_store=mind_path
            )
            self.assertEqual(len(result["cycles"]), 2)
            self.assertIsNotNone(result["embodied"])
            self.assertNotIn("error", result["embodied"])
            self.assertTrue(Path(result["embodied"]["form_path"]).exists())


class GenerativeGrowthTests(unittest.TestCase):
    def test_grows_beyond_fixed_lexicon(self):
        eng = Engine(seed_minimal_hot_cold())
        center = LivingCenter(eng)
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            store.save(eng.torus, mind_path)
            center.mind_store = mind_path
            center.max_nodes_soft_cap = 40
            reports = center.think(10)
            names = set(eng.torus.nodes)
            self.assertTrue(any(n.startswith("more-") for n in names))
            sources = [
                a.detail.get("source")
                for r in reports
                for a in r.acts
                if a.act == "grow"
            ]
            self.assertIn("generative", sources)
            # Fixed thermal cascade alone cannot explain more-* nodes.
            self.assertGreater(len(names), 10)


class LiveAutonomyTests(unittest.TestCase):
    def test_live_stops_on_idle_or_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_minimal_hot_cold())
            store.save(eng.torus, mind_path)
            center = LivingCenter(eng, history=[])
            center.mind_store = mind_path
            result = center.live(
                max_cycles=6,
                stop_when_idle=3,
                mind_store=mind_path,
            )
            self.assertGreaterEqual(result["cycle_count"], 3)
            self.assertIn(result["stopped"], {"idle", "max_cycles"})


if __name__ == "__main__":
    unittest.main()
