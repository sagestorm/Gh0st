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


class ReflectiveJournalTests(unittest.TestCase):
    def test_journal_content_reshapes_strategy(self):
        from beyond_binary.journal import JournalEntry

        eng = Engine(seed_minimal_hot_cold())
        grow_center = LivingCenter(eng)
        grow_center.journal_entries = [
            JournalEntry(
                cycle=i,
                reflection="structure_hungry",
                signals={"flags": 0, "grow_count": 0},
                strategy_hint="grow",
            )
            for i in range(1, 4)
        ]
        grow_strat = grow_center.metacognize([])
        self.assertTrue(grow_strat.from_journal)
        self.assertEqual(grow_strat.reason, "journal_structure_hungry")
        self.assertGreaterEqual(grow_strat.grow_budget, 1)
        self.assertFalse(grow_strat.prefer_prune)

        eng2 = Engine(seed_minimal_hot_cold())
        prune_center = LivingCenter(eng2)
        prune_center.journal_entries = [
            JournalEntry(
                cycle=i,
                reflection="challenge_pressure",
                signals={"flags": 1, "grow_count": 0},
                strategy_hint="prune",
            )
            for i in range(1, 4)
        ]
        prune_strat = prune_center.metacognize([])
        self.assertTrue(prune_strat.from_journal)
        self.assertEqual(prune_strat.reason, "journal_challenge_pressure")
        self.assertTrue(prune_strat.prefer_prune)
        self.assertEqual(prune_strat.grow_budget, 0)
        self.assertNotEqual(grow_strat.reason, prune_strat.reason)

    def test_cycle_writes_journal_and_next_strategy_reads_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_minimal_hot_cold())
            store.save(eng.torus, mind_path)
            center = LivingCenter(eng, history=[])
            center.mind_store = mind_path
            center.cycle()
            from beyond_binary import journal as journal_mod

            rows = journal_mod.load_journal(mind_path)
            self.assertGreaterEqual(len(rows), 1)
            self.assertTrue(rows[0].reflection)
            self.assertTrue(rows[0].strategy_hint)
            # Second cycle must metacognize from journal (from_journal true).
            report2 = center.cycle()
            meta = next(a for a in report2.acts if a.act == "metacognize")
            self.assertTrue(meta.detail["strategy"].get("from_journal"))
            reflect = next(a for a in report2.acts if a.act == "reflect")
            self.assertIn("strategy_hint", reflect.detail)


class InventAndSynthesizeTests(unittest.TestCase):
    def test_invent_and_synthesize(self):
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_minimal_hot_cold())
            store.save(eng.torus, mind_path)
            from beyond_binary import mind as mind_mod

            invented = mind_mod.invent_domain(eng, mind_path, cycle=1)
            self.assertTrue(invented.get("invented"))
            syn = mind_mod.synthesize(eng, "hot", mind_path)
            self.assertTrue(syn.get("ok"))
            self.assertTrue(any(h["source"] == "mind" for h in syn["hits"]))

    def test_compositional_invent_from_known_structure(self):
        """Invent must compose from Living Center structure, not only INVENTABLE seed."""
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_minimal_hot_cold())
            store.save(eng.torus, mind_path)
            # Second domain body supplies another opposite pair for composition.
            bodies.embody(
                eng, name="ont-body", domain="ontology", mind_store=mind_path
            )
            from beyond_binary import invent as invent_mod
            from beyond_binary import mind as mind_mod

            # Mark every seed catalog entry used so seed path cannot satisfy.
            registry = invent_mod.InventRegistry(
                candidates=[
                    invent_mod.InventCandidate(
                        cause=c, effect=e, instance=inst, source="seed", used=True
                    )
                    for c, e, inst in invent_mod.INVENTABLE
                ]
            )
            invent_mod.save_invent_registry(registry, mind_path)

            proposal = invent_mod.next_invention(eng, mind_path)
            self.assertIsNotNone(proposal)
            self.assertIn(proposal.source, {"compose", "promote"})
            # Composed poles are built from known structure tokens.
            if proposal.source == "compose":
                self.assertIn("-", proposal.cause)
                self.assertIn("-", proposal.effect)

            invented = mind_mod.invent_domain(eng, mind_path, cycle=2)
            self.assertTrue(invented.get("invented"))
            self.assertIn(
                invented["invention"]["source"], {"compose", "promote"}
            )
            # Dynamic invent registry persisted.
            self.assertTrue(invent_mod.invent_registry_path(mind_path).exists())


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


class VerifyFarVisionTests(unittest.TestCase):
    def test_verify_reports_incomplete_sentience(self):
        from beyond_binary import verify

        report = verify.run_verification()
        self.assertFalse(report["complete"])
        by_id = {g["id"]: g for g in report["gates"]}
        self.assertFalse(by_id["SENTIENCE"]["ok"])
        self.assertTrue(report["engineering_gates_ok"])


if __name__ == "__main__":
    unittest.main()
