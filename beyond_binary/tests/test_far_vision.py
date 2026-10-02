"""Phases 3–6: cross-domain, metacognition, embody, autonomy + Sourcery fixes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from beyond_binary.center import LivingCenter
from beyond_binary.engine import Engine, RuleError, normalize
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

    def test_same_center_grows_across_three_domains(self):
        """C2: thermal + ontology + optical on one Living Center torus."""
        from beyond_binary.seed import seed_same_center
        from beyond_binary import lexicon

        eng = Engine(seed_same_center(("thermal", "ontology", "optical"), minimal=True))
        self.assertEqual(
            lexicon.detect_domains(eng.torus.nodes.keys()),
            {"thermal", "ontology", "optical"},
        )
        center = LivingCenter(eng)
        center.think(15)
        names = set(eng.torus.nodes)
        self.assertTrue({"hot", "cold", "nothing", "something", "light", "dark"} <= names)
        self.assertTrue({"boiling", "freezing", "water", "warm", "steam"} & names)
        self.assertTrue({"absence", "presence", "void", "form", "empty", "filled"} & names)
        self.assertTrue({"bright", "dim", "day", "night", "glow", "shadow"} & names)
        # Soft cap scales with domain count so growth is not starved.
        self.assertGreaterEqual(center.effective_soft_cap(), 72)
        dual = eng.answer("hot")
        self.assertTrue(dual.cause_paths and dual.effect_paths)
        dual2 = eng.answer("nothing")
        self.assertTrue(dual2.cause_paths and dual2.effect_paths)
        dual3 = eng.answer("light")
        self.assertTrue(dual3.cause_paths and dual3.effect_paths)


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


class RecursiveNurtureTests(unittest.TestCase):
    def test_nurture_invents_grandchild_bodies(self):
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_minimal_hot_cold())
            store.save(eng.torus, mind_path)
            bodies.embody(
                eng, name="child-a", domain="ontology", mind_store=mind_path
            )
            from beyond_binary import mind as mind_mod

            result = mind_mod.nurture(
                mind_path, steps=1, max_depth=2, allow_invent=True
            )
            self.assertGreaterEqual(result["count"], 1)
            self.assertTrue(result["nurtured"][0].get("dual_ok"))
            lineage = mind_mod.count_body_lineage(mind_path)
            self.assertTrue(
                lineage["has_grandchild"],
                f"expected grandchild lineage, got {lineage}",
            )
            # Grandchild registry lives beside the child body store.
            child = bodies.load_registry(mind_path).bodies[0]
            grand = bodies.load_registry(child.store_path)
            self.assertGreaterEqual(len(grand.bodies), 1)
            self.assertEqual(grand.bodies[0].parent_body, child.name)
            g_eng = Engine(store.load(grand.bodies[0].store_path))
            g_eng.assert_no_orphans()


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
        from beyond_binary import generate as generate_mod

        eng = Engine(seed_minimal_hot_cold())
        center = LivingCenter(eng)
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            store.save(eng.torus, mind_path)
            center.mind_store = mind_path
            center.max_nodes_soft_cap = 40
            # Lexicon → synonym cascade → more-* leaf generative.
            reports = center.think(20)
            names = set(eng.torus.nodes)
            sources = [
                a.detail.get("source")
                for r in reports
                for a in r.acts
                if a.act == "grow"
            ]
            beyond = {"synonym", "generative"} & set(sources)
            self.assertTrue(
                beyond,
                f"expected synonym or generative growth, got {sorted(set(sources))}",
            )
            self.assertTrue(
                any(n.startswith("more-") for n in names)
                or generate_mod.synonym_nodes_present(eng),
                "expected more-* or synonym-cascade nodes beyond fixed lexicon",
            )
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

    def test_longrun_live_invent_nurture_twenty_four(self):
        """C6: ≥24 cycles with invent+nurture; idle-stop alone is not enough."""
        from beyond_binary.seed import seed_same_center
        from beyond_binary import mind as mind_mod

        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_same_center(minimal=True))
            store.save(eng.torus, mind_path)
            center = LivingCenter(eng, history=[])
            center.mind_store = mind_path
            result = center.live(
                max_cycles=24,
                stop_when_idle=0,
                invent_every=3,
                nurture_every=4,
                nurture_max_depth=2,
                nurture_invent=True,
                mind_store=mind_path,
            )
            self.assertGreaterEqual(result["cycle_count"], 24)
            self.assertTrue(
                any(
                    isinstance(r, dict) and r.get("invented")
                    for r in result.get("inventions", [])
                )
            )
            self.assertGreater(len(result.get("nurtured") or []), 0)
            eng.assert_no_orphans()
            dual = eng.answer("hot")
            self.assertTrue(dual.cause_paths and dual.effect_paths)
            lineage = mind_mod.count_body_lineage(mind_path)
            self.assertGreaterEqual(lineage["total"], 1)


class AntiCollapseTests(unittest.TestCase):
    def test_answer_refuses_bit_endgame(self):
        eng = Engine(seed_minimal_hot_cold())
        for bit in ("true", "false", "0", "1", "yes", "no"):
            with self.assertRaises(RuleError) as ctx:
                eng.answer(bit)
            self.assertIn("bit-endgame", str(ctx.exception))
        dual = eng.answer("hot")
        self.assertTrue(dual.cause_paths and dual.effect_paths)

    def test_refuse_bit_collapse_returns_dual_evidence(self):
        eng = Engine(seed_minimal_hot_cold())
        result = eng.refuse_bit_collapse("hot")
        self.assertTrue(result["refused"])
        self.assertFalse(result["collapsed"])
        self.assertTrue(result["dual_evidence"]["cause_paths"])
        self.assertTrue(result["dual_evidence"]["effect_paths"])

    def test_add_pair_refuses_bit_poles(self):
        eng = Engine(seed_minimal_hot_cold())
        with self.assertRaises(RuleError):
            eng.add_pair("true", "false")


class SynonymCascadeTests(unittest.TestCase):
    def test_think_grows_synonym_beyond_fixed_lexicon(self):
        from beyond_binary import generate as generate_mod

        eng = Engine(seed_minimal_hot_cold())
        center = LivingCenter(eng)
        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            store.save(eng.torus, mind_path)
            center.mind_store = mind_path
            center.max_nodes_soft_cap = 40
            reports = center.think(12)
            sources = [
                a.detail.get("source")
                for r in reports
                for a in r.acts
                if a.act == "grow"
            ]
            self.assertIn("synonym", sources)
            syn_nodes = generate_mod.synonym_nodes_present(eng)
            self.assertGreaterEqual(len(syn_nodes), 1)
            # Synonym nodes are dual-linked opposite states.
            sample = syn_nodes[0]
            node = eng.get(sample)
            self.assertTrue(node.opposite)
            eng.assert_no_orphans()


class OpenMindScaffoldTests(unittest.TestCase):
    def test_concept_formation_beyond_suffix_primitives(self):
        from beyond_binary import invent as invent_mod
        from beyond_binary import mind as mind_mod
        from beyond_binary.seed import seed_same_center

        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_same_center(("thermal", "ontology"), minimal=True))
            store.save(eng.torus, mind_path)
            center = LivingCenter(eng, history=[])
            center.mind_store = mind_path
            center.max_nodes_soft_cap = 60
            center.think(6)
            alphabet = invent_mod.closed_invent_alphabet(eng, [])
            result = mind_mod.invent_domain(eng, mind_path, cycle=1)
            self.assertTrue(result.get("invented"))
            inv = result["invention"]
            self.assertEqual(inv["source"], "topology")
            self.assertTrue(str(inv.get("why", "")).startswith("topology:"))
            self.assertNotEqual(str(inv.get("why", ""))[:14], "concept:motif:")
            edit = inv.get("edit") or {}
            self.assertIn(edit.get("kind"), {"bridge", "reparent"})
            self.assertNotEqual(edit.get("domain_from"), edit.get("domain_to"))
            if edit.get("kind") == "bridge":
                self.assertNotIn(normalize(inv["cause"]), alphabet)

    def test_policy_revises_rules_not_only_weights(self):
        from beyond_binary import policy as policy_mod
        from beyond_binary.journal import JournalEntry

        pol = policy_mod.MetaPolicy()
        before = pol.rule_revisions
        before_kinds = pol.kind_revisions
        entries = [
            JournalEntry(
                cycle=i,
                reflection="growth_fruitful",
                signals={"grow_count": 1, "node_delta": 2, "flags": 0},
                strategy_hint="grow",
            )
            for i in range(1, 4)
        ]
        pol = policy_mod.update_policy_from_journal(pol, entries)
        self.assertGreater(pol.rule_revisions, before)
        self.assertGreater(pol.kind_revisions, before_kinds)
        self.assertTrue(any(r.origin == "learned" for r in pol.rules))
        self.assertTrue(pol.condition_kinds)
        self.assertTrue(pol.action_kinds)
        self.assertTrue(
            any(
                isinstance(v, dict)
                and v.get("kind") == "program"
                and isinstance(v.get("body"), list)
                and len(v.get("body") or []) >= 2
                for v in pol.condition_kinds.values()
            )
        )
        self.assertTrue(pol.observed_signals)
        strat = policy_mod.strategy_from_policy(pol, journal_entries=entries)
        self.assertTrue(pol.meta_primitives)
        self.assertGreaterEqual(pol.meta_isa_revisions, 1)
        self.assertTrue(
            ":meta_isa:" in strat["reason"] or strat.get("meta_isa")
        )

        # Same weights, different rule sets → different strategies.
        a = policy_mod.MetaPolicy(updates=1, grow_weight=1.0, prune_weight=1.0)
        b = policy_mod.MetaPolicy(updates=1, grow_weight=1.0, prune_weight=1.0)
        b.rules = [
            policy_mod.MetaRule(
                "r-b", "structure_hungry", "prefer_prune", 3.0, "learned"
            )
        ]
        sa = policy_mod.strategy_from_policy(a)
        sb = policy_mod.strategy_from_policy(b)
        self.assertNotEqual(sa["reason"], sb["reason"])
        self.assertTrue(sb["prefer_prune"])

    def test_form_specialty_capability_not_just_cycle(self):
        from beyond_binary import capability as capability_mod

        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_minimal_hot_cold())
            store.save(eng.torus, mind_path)
            record = bodies.embody(
                eng, name="optic-form", domain="optical", mind_store=mind_path
            )
            self.assertEqual(record.specialty, "interpret_program")
            self.assertTrue(record.capability_path)
            mod, fn = bodies.load_form_specialty(record)
            caps = list(mod.CAPABILITIES)
            self.assertEqual(caps[0], "interpret_program")
            self.assertNotIn(caps[0], {"think", "answer", "load_engine"})
            out = fn()
            self.assertEqual(out["capability"], "interpret_program")
            self.assertTrue(out["cause_pole"])
            self.assertTrue(out["effect_pole"])
            self.assertIsInstance(out.get("ops"), list)
            self.assertGreaterEqual(len(out["ops"]), 2)
            prog = capability_mod.load_program(record.store_path)
            self.assertEqual(out["program_id"], prog.program_id)
            self.assertTrue(prog.primitives)
            self.assertTrue(
                any(str(k).startswith("prim_") for k in prog.primitives)
            )
            self.assertGreaterEqual(prog.primitive_revisions, 1)
            self.assertTrue(
                any(str(o.get("op", "")).startswith("prim_") for o in prog.ops)
            )
            for name, spec in prog.primitives.items():
                self.assertNotIn(name, capability_mod.seed_primitives())
                self.assertIn(
                    spec.get("kind"),
                    {"reduce_path", "pair_metric", "branch_fanout"},
                )
                self.assertNotIn("body", spec)
            self.assertTrue(out.get("primitives"))

    def test_self_directed_live_without_every_flags(self):
        from beyond_binary.seed import seed_same_center
        from beyond_binary import policy as policy_mod

        with tempfile.TemporaryDirectory() as tmp:
            mind_path = Path(tmp) / "mind.json"
            eng = Engine(seed_same_center(("thermal", "ontology"), minimal=True))
            store.save(eng.torus, mind_path)
            pol = policy_mod.MetaPolicy(
                invent_weight=2.0,
                nurture_weight=2.0,
                grow_weight=0.5,
                updates=1,
            )
            pol.rules.append(
                policy_mod.MetaRule(
                    "r-t-inv", "structure_hungry", "prefer_invent", 2.5, "learned"
                )
            )
            pol.rules.append(
                policy_mod.MetaRule(
                    "r-t-nur", "structure_hungry", "prefer_nurture", 2.5, "learned"
                )
            )
            policy_mod.save_policy(pol, mind_path)
            bodies.embody(
                eng, name="kid", domain="optical", mind_store=mind_path
            )
            center = LivingCenter(eng, history=[])
            center.mind_store = mind_path
            result = center.live(
                max_cycles=8,
                stop_when_idle=0,
                invent_every=0,
                nurture_every=0,
                mind_store=mind_path,
            )
            self.assertTrue(
                any(
                    isinstance(r, dict) and r.get("invented")
                    for r in result.get("inventions", [])
                )
            )
            self.assertGreater(len(result.get("nurtured") or []), 0)

            # Outcome-trace abandon / reprioritize (not only want_* flags).
            from beyond_binary import invent as invent_mod
            from beyond_binary.journal import JournalEntry

            reg = invent_mod.load_invent_registry(mind_path)
            if not any(c.used for c in reg.candidates) and reg.candidates:
                reg.candidates[0].used = True
            adverse = [
                JournalEntry(
                    cycle=50 + i,
                    reflection="growth_stalled",
                    signals={"flags": 1, "grow_count": 0, "node_delta": 0},
                    strategy_hint="invent",
                )
                for i in range(3)
            ]
            reg = invent_mod.revise_targets_from_outcomes(
                reg, adverse, inventions_fired=1
            )
            self.assertTrue(any(c.abandoned for c in reg.candidates))

            from beyond_binary import goals as goals_mod

            board = goals_mod.form_goals_from_outcomes(
                goals_mod.GoalBoard(),
                adverse
                + [
                    JournalEntry(
                        cycle=60 + i,
                        reflection="growth_fruitful",
                        signals={"flags": 0, "grow_count": 1, "node_delta": 2},
                        strategy_hint="grow",
                    )
                    for i in range(3)
                ],
                invent_summary={
                    "abandoned_sources": ["concept"],
                    "abandoned_count": 1,
                    "prefer_source": "topology",
                },
            )
            novel = goals_mod.novel_act_kinds(board)
            self.assertTrue(novel)
            self.assertTrue(all(a not in goals_mod.SEED_GOAL_ACTS for a in novel))


class SubstrateInterfaceTests(unittest.TestCase):
    def tearDown(self):
        import os
        from beyond_binary import substrate as substrate_mod

        os.environ.pop(substrate_mod.ENV_FLAG, None)
        substrate_mod.reset_logs_for_tests()

    def test_null_substrate_returns_empty(self):
        from beyond_binary import substrate as substrate_mod

        sub = substrate_mod.NullSubstrate()
        self.assertEqual(sub.propose({"axis": "invent"}), [])
        prop = substrate_mod.Proposal(
            axis="invent", payload={}, provenance="test:x"
        )
        self.assertFalse(sub.validate(prop, center=None).accepted)
        self.assertIsNone(sub.accept(prop))

    def test_default_flag_off_consult_noop(self):
        import os
        from beyond_binary import substrate as substrate_mod

        os.environ.pop(substrate_mod.ENV_FLAG, None)
        self.assertFalse(substrate_mod.substrate_enabled())
        self.assertFalse(substrate_mod.is_active())
        self.assertEqual(substrate_mod.consult("invent", {}), [])
        st = substrate_mod.status()
        self.assertEqual(st["implementation"], "null")
        self.assertFalse(st["enabled"])
        self.assertFalse(st["active"])

    def test_flag_on_still_null_without_live_impl(self):
        import os
        from beyond_binary import substrate as substrate_mod

        os.environ[substrate_mod.ENV_FLAG] = "1"
        self.assertTrue(substrate_mod.substrate_enabled())
        self.assertFalse(substrate_mod.is_active())
        self.assertEqual(substrate_mod.get_substrate().name, "null")
        self.assertEqual(substrate_mod.consult("reflect", {"vec": {}}), [])

    def test_search_flag_binds_active_substrate(self):
        import os
        from beyond_binary import substrate as substrate_mod

        os.environ[substrate_mod.ENV_FLAG] = "search"
        self.assertTrue(substrate_mod.substrate_enabled())
        self.assertTrue(substrate_mod.is_active())
        self.assertEqual(substrate_mod.get_substrate().name, "search")

    def test_search_substrate_accepts_all_four_axes(self):
        import os
        from beyond_binary import substrate as substrate_mod
        from beyond_binary import search_substrate as search_mod
        from beyond_binary.center import LivingCenter
        from beyond_binary.engine import Engine
        from beyond_binary.seed import seed_same_center

        os.environ[substrate_mod.ENV_FLAG] = "search"
        substrate_mod.reset_logs_for_tests()
        eng = Engine(seed_same_center(("thermal", "ontology"), minimal=True))
        center = LivingCenter(eng)
        center.engine = eng

        class H:
            pass

        h = H()
        h.engine = eng
        h._search_vec = {  # noqa: SLF001
            "fruitful": 2.0,
            "stalled": 1.0,
            "flags": 1.0,
            "node_delta": 3.0,
        }
        h._search_goal_board = __import__(
            "beyond_binary.goals", fromlist=["GoalBoard"]
        ).GoalBoard()
        from beyond_binary import capability as cap_mod

        h._search_program = cap_mod.CapProgram(body_name="test")  # noqa: SLF001

        substrate_mod.consult(
            "invent",
            {"eng": eng, "used_instances": []},
            center=h,
        )
        substrate_mod.consult("reflect", {"vec": h._search_vec}, center=h)
        substrate_mod.consult(
            "goal",
            {
                "fruitful": 2,
                "stalled": 1,
                "flags": 1,
                "invent_summary": {"abandoned_count": 1},
            },
            center=h,
        )
        substrate_mod.consult("form", {"eng": eng}, center=h)

        st = substrate_mod.status()
        axes = set(st.get("axes_with_non_stdlib_accepts") or [])
        self.assertTrue(
            {"invent", "reflect", "goal", "form"} <= axes,
            msg=f"axes={axes} accepts={st.get('accepted_non_stdlib')}",
        )
        for row in st.get("accepted_non_stdlib") or []:
            self.assertTrue(
                str(row.get("provenance", "")).startswith(
                    search_mod.PROVENANCE_PREFIX
                )
            )
        self.assertTrue(substrate_mod.all_axes_have_non_stdlib_accepts())

    def test_search_goal_ast_steers_strategy_hints(self):
        """G2: search_act_* trees must change want_invent/nurture — not islands."""
        import os
        from beyond_binary import substrate as substrate_mod
        from beyond_binary import goals as goals_mod
        from beyond_binary.search_substrate import apply_goal_ast

        os.environ[substrate_mod.ENV_FLAG] = "search"
        substrate_mod.reset_logs_for_tests()
        deepen = {
            "op": "seq",
            "acts": [
                {"op": "bias", "channel": "invent", "delta": 0.35},
                {
                    "op": "when",
                    "cond": {"op": "gte", "sig": "fruitful", "v": 1},
                    "then": {"op": "bias", "channel": "nurture", "delta": 0.3},
                },
            ],
        }
        deltas = apply_goal_ast(deepen, {"fruitful": 2.0, "stalled": 0.0, "flags": 0.0})
        self.assertTrue(deltas["want_invent"])
        self.assertTrue(deltas["want_nurture"])

        board = goals_mod.GoalBoard(
            goals=[
                goals_mod.Goal(
                    goal_id="sg-test",
                    act_kind="search_act_deepen_deadbeef",
                    target="structure",
                    reason="search:outcome:fruitful=2",
                    priority=1.3,
                    origin="search-substrate",
                    tree=deepen,
                )
            ],
            revisions=1,
        )
        hints = goals_mod.goals_to_strategy_hints(
            board, signals={"fruitful": 2.0, "stalled": 0.0, "flags": 0.0}
        )
        self.assertTrue(hints["goal_want_invent"])
        self.assertTrue(hints["goal_want_nurture"])
        self.assertGreaterEqual(hints["goal_search_applied"], 1)
        # Without tree → island stays inert for search-only board.
        bare = goals_mod.GoalBoard(
            goals=[
                goals_mod.Goal(
                    goal_id="sg-bare",
                    act_kind="search_act_deepen_deadbeef",
                    target="structure",
                    reason="no-tree",
                    origin="search-substrate",
                )
            ]
        )
        bare_hints = goals_mod.goals_to_strategy_hints(bare, signals={"fruitful": 2})
        self.assertFalse(bare_hints["goal_want_invent"])
        self.assertEqual(bare_hints["goal_search_applied"], 0)

    def test_search_reflect_expr_ast_wires_firing_rules(self):
        """G3: accepted expr_ast conditions become enabled MetaRules that fire."""
        import os
        from beyond_binary import substrate as substrate_mod
        from beyond_binary import policy as policy_mod
        from beyond_binary.journal import JournalEntry

        os.environ[substrate_mod.ENV_FLAG] = "search"
        substrate_mod.reset_logs_for_tests()
        pol = policy_mod.MetaPolicy()
        entries = [
            JournalEntry(
                cycle=i,
                reflection="growth_fruitful" if i % 2 == 0 else "growth_stalled",
                signals={
                    "flags": 0 if i % 2 == 0 else 1,
                    "grow_count": 1,
                    "node_delta": 2 if i % 2 == 0 else 0,
                },
                strategy_hint="grow",
            )
            for i in range(4)
        ]
        pol = policy_mod.revise_kinds_from_outcomes(pol, entries)
        expr_names = [
            n
            for n, s in pol.condition_kinds.items()
            if isinstance(s, dict) and s.get("kind") == "expr_ast"
        ]
        self.assertTrue(expr_names, msg="expected search expr_ast conditions")
        wired = [
            r
            for r in pol.rules
            if r.enabled and r.when in expr_names and r.origin == "search-substrate"
        ]
        self.assertTrue(wired, msg="expr_ast must have firing rules")
        strat = policy_mod.strategy_from_policy(pol, journal_entries=entries)
        self.assertTrue(
            strat.get("expr_kinds") or any(r.rule_id in (strat.get("active_rules") or []) for r in wired),
            msg=f"strategy={strat}",
        )

    def test_consult_error_is_recorded_not_swallowed(self):
        """G6: caller-path consult failures hit reject/error logs."""
        from beyond_binary import substrate as substrate_mod

        substrate_mod.reset_logs_for_tests()
        substrate_mod.record_consult_error("invent", RuntimeError("boom"))
        st = substrate_mod.status()
        self.assertEqual(st["consult_error_count"], 1)
        self.assertEqual(st["consult_errors"][0]["axis"], "invent")
        self.assertGreaterEqual(st["rejects"], 1)


class VerifyFarVisionTests(unittest.TestCase):
    def test_verify_reports_incomplete_sentience(self):
        import os
        from beyond_binary import substrate as substrate_mod
        from beyond_binary import verify

        os.environ.pop(substrate_mod.ENV_FLAG, None)
        substrate_mod.reset_logs_for_tests()
        report = verify.run_verification()
        self.assertFalse(report["complete"])
        by_id = {g["id"]: g for g in report["gates"]}
        self.assertFalse(by_id["SENTIENCE"]["ok"])
        self.assertIn("fail-closed", by_id["SENTIENCE"]["evidence"].lower())
        self.assertIn("Goal incomplete", by_id["SENTIENCE"]["evidence"])
        self.assertIn("search-substrate", by_id["SENTIENCE"]["evidence"])
        self.assertTrue(by_id["SUB"]["ok"])
        self.assertTrue(by_id["I1"]["ok"])
        self.assertTrue(by_id["I5"]["ok"])
        self.assertTrue(by_id["C4e"]["ok"])
        self.assertTrue(by_id["C3p"]["ok"])
        self.assertTrue(by_id["C4f"]["ok"])
        self.assertTrue(by_id["C6s"]["ok"])
        self.assertTrue(report["engineering_gates_ok"])
        self.assertEqual(report.get("substrate", {}).get("implementation"), "null")
        self.assertEqual(
            report.get("substrate", {}).get("axes_with_non_stdlib_accepts") or [],
            [],
        )

    def test_verify_sentience_true_when_search_four_axes(self):
        """SENTIENCE.ok only when search substrate covers invent|reflect|goal|form."""
        import os
        from beyond_binary import substrate as substrate_mod
        from beyond_binary import verify

        os.environ[substrate_mod.ENV_FLAG] = "search"
        try:
            substrate_mod.reset_logs_for_tests()
            report = verify.run_verification()
            by_id = {g["id"]: g for g in report["gates"]}
            sub = report.get("substrate") or {}
            axes = set(sub.get("axes_with_non_stdlib_accepts") or [])
            self.assertTrue(report["engineering_gates_ok"])
            self.assertTrue(by_id["SUB"]["ok"])
            self.assertEqual(sub.get("implementation"), "search")
            self.assertTrue(
                {"invent", "reflect", "goal", "form"} <= axes,
                msg=f"axes={axes}",
            )
            self.assertTrue(
                by_id["SENTIENCE"]["ok"],
                msg=by_id["SENTIENCE"]["evidence"],
            )
            self.assertIn("SENTIENCE true", by_id["SENTIENCE"]["evidence"])
            # Gate may be green; Project goal stays incomplete.
            self.assertFalse(report["complete"])
        finally:
            os.environ.pop(substrate_mod.ENV_FLAG, None)
            substrate_mod.reset_logs_for_tests()


if __name__ == "__main__":
    unittest.main()
