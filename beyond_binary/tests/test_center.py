"""Unit tests for Living Center Phase 2 acceptance criteria."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from beyond_binary.center import LivingCenter
from beyond_binary.engine import Engine, RuleError
from beyond_binary.model import Hemisphere, Node, Torus
from beyond_binary.seed import seed_hot_cold, seed_minimal_hot_cold
from beyond_binary import store
from beyond_binary.__main__ import main


class GrowFromMinimalSeedTests(unittest.TestCase):
    def test_think_grows_cascade_from_minimal(self):
        eng = Engine(seed_minimal_hot_cold())
        self.assertEqual(set(eng.torus.nodes), {"hot", "cold"})
        center = LivingCenter(eng)
        reports = center.think(5)
        self.assertEqual(len(reports), 5)
        names = set(eng.torus.nodes)
        # At least boiling/freezing/water/condensation (or equivalents).
        self.assertIn("boiling", names)
        self.assertIn("freezing", names)
        self.assertIn("water", names)
        self.assertIn("condensation", names)
        self.assertEqual(eng.get("boiling").opposite, "freezing")
        self.assertEqual(eng.get("water").opposite, "condensation")
        eng.assert_no_orphans()
        # No duplicate normalized keys (dict invariant + alias merge).
        lowered = [n.lower() for n in names]
        self.assertEqual(len(lowered), len(set(lowered)))

    def test_dual_answer_after_grow(self):
        eng = Engine(seed_minimal_hot_cold())
        LivingCenter(eng).think(5)
        dual = eng.answer("water")
        self.assertTrue(dual.cause_paths)
        self.assertTrue(dual.effect_paths)
        self.assertIn("water", dual.cause_paths[0] or dual.effect_paths[0])
        # Opposite side of water is condensation.
        flat_between = dual.between
        self.assertTrue(
            any(pair == ("water", "condensation") or pair == ("condensation", "water")
                for pair in flat_between)
            or eng.get("water").opposite == "condensation"
        )


class OrphanRepairInCycleTests(unittest.TestCase):
    def test_orphan_repaired_during_cycle(self):
        eng = Engine(seed_minimal_hot_cold())
        # Inject an orphan under hot (no opposite).
        eng.torus.nodes["stray"] = Node(
            name="stray",
            hemisphere=Hemisphere.CAUSE,
            parent="hot",
            opposite=None,
        )
        self.assertTrue(eng.orphans())
        LivingCenter(eng).cycle()
        self.assertFalse(eng.orphans())
        stray = eng.get("stray")
        self.assertIsNotNone(stray.opposite)
        opp = eng.get(stray.opposite)
        self.assertIs(opp.hemisphere, Hemisphere.EFFECT)
        self.assertEqual(opp.opposite, "stray")


class DedupeTests(unittest.TestCase):
    def test_dedupe_merges_aliases_in_cycle(self):
        eng = Engine(seed_minimal_hot_cold())
        eng.add_under("hot", "boiling", opposite_name="freezing", opposite_parent="cold")
        # Alias duplicate under hot (scalding → boiling per lexicon aliases).
        eng.add_under("hot", "scalding", opposite_name="chilling", opposite_parent="cold")
        self.assertTrue(eng.exists("scalding"))
        LivingCenter(eng).cycle()
        self.assertFalse(eng.exists("scalding"))
        self.assertTrue(eng.exists("boiling"))
        eng.assert_no_orphans()


class NoUnboundedExplosionTests(unittest.TestCase):
    def test_repeated_think_does_not_explode_duplicates(self):
        eng = Engine(seed_minimal_hot_cold())
        center = LivingCenter(eng)
        center.think(5)
        n_after_5 = len(eng.torus.nodes)
        center.think(20)
        n_after_25 = len(eng.torus.nodes)
        # Soft cap + lexicon finish ⇒ bounded; no duplicate explosion.
        self.assertLessEqual(n_after_25, LivingCenter(eng).max_nodes_soft_cap)
        self.assertLessEqual(n_after_25, n_after_5 + 8)  # remaining lexicon pairs only
        # Unique normalized keys
        self.assertEqual(len(eng.torus.nodes), len(set(eng.torus.nodes)))
        eng.assert_no_orphans()


class ActivityLogTests(unittest.TestCase):
    def test_activity_persisted_beside_torus(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "torus.json"
            store.save(seed_minimal_hot_cold(), path)
            rc = main(["--store", str(path), "think", "--steps", "2"])
            self.assertEqual(rc, 0)
            log_path = store.activity_log_path(path)
            self.assertTrue(log_path.exists())
            rows = store.load_activity(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["cycle"], 1)
            acts = [a["act"] for a in rows[0]["acts"]]
            self.assertIn("grow", acts)
            self.assertIn("repair_orphans", acts)
            self.assertIn("dedupe", acts)
            self.assertIn("log", acts)

    def test_cycle_index_continues_across_cli_invokes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "torus.json"
            store.save(seed_minimal_hot_cold(), path)
            self.assertEqual(main(["think", "--steps", "2", "--store", str(path)]), 0)
            rows = store.load_activity(path)
            self.assertEqual([r["cycle"] for r in rows], [1, 2])
            self.assertEqual(main(["cycle", "--store", str(path)]), 0)
            rows = store.load_activity(path)
            self.assertEqual([r["cycle"] for r in rows], [1, 2, 3])
            # Fresh LivingCenter from prior activity alone also continues.
            eng = Engine(store.load(path))
            center = LivingCenter(eng, prior_activity=rows)
            report = center.cycle()
            self.assertEqual(report.cycle, 4)


class ChallengeSafetyTests(unittest.TestCase):
    def test_dangling_opposite_challenge_does_not_abort_cycle(self):
        eng = Engine(seed_minimal_hot_cold())
        # Broken link: opposite points at a missing node.
        eng.get("hot").opposite = "missing-cold"
        center = LivingCenter(eng)
        report = center.cycle()
        acts = [a.act for a in report.acts]
        self.assertIn("challenge", acts)
        self.assertIn("prune", acts)
        self.assertIn("log", acts)
        # Cycle completed end-to-end (prune/log after challenge).
        self.assertEqual(acts[-1], "log")
        self.assertGreater(acts.index("log"), acts.index("challenge"))
        self.assertGreater(acts.index("prune"), acts.index("challenge"))
        challenge = next(a for a in report.acts if a.act == "challenge")
        flags = challenge.detail["flags"]
        self.assertTrue(
            any(f["flag"] == "dangling_opposite" for f in flags)
            or any(f["flag"] == "orphan" for f in flags)
        )
        # center() stamp must not have raised; last CHALLENGE entry may refuse.
        challenge_logs = [
            e for e in eng.torus.center_log if e.get("action") == "challenge"
        ]
        self.assertTrue(challenge_logs)


class StoreFlagPlacementTests(unittest.TestCase):
    def test_store_after_subcommand(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "torus.json"
            self.assertEqual(
                main(["seed-minimal", "--force", "--store", str(path)]),
                0,
            )
            self.assertTrue(path.exists())
            self.assertEqual(main(["show", "--store", str(path)]), 0)

    def test_store_before_subcommand_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "torus.json"
            self.assertEqual(
                main(["--store", str(path), "seed-minimal", "--force"]),
                0,
            )
            self.assertTrue(path.exists())


class CliThinkSmoke(unittest.TestCase):
    def test_think_show_answer_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "torus.json"
            self.assertEqual(main(["--store", str(path), "seed-minimal", "--force"]), 0)
            self.assertEqual(main(["--store", str(path), "think", "--steps", "5"]), 0)
            # show + answer via engine load
            eng = Engine(store.load(path))
            self.assertIn("water", eng.torus.nodes)
            dual = eng.answer("water")
            self.assertTrue(dual.cause_paths and dual.effect_paths)
            self.assertEqual(main(["--store", str(path), "log", "--limit", "1"]), 0)


class MinimalSeedUnit(unittest.TestCase):
    def test_minimal_is_poles_only(self):
        eng = Engine(seed_minimal_hot_cold())
        self.assertEqual(sorted(eng.torus.nodes), ["cold", "hot"])
        self.assertEqual(eng.get("hot").opposite, "cold")


if __name__ == "__main__":
    unittest.main()
