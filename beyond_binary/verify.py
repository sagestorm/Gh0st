"""Honest far-vision verification — evidence gates, not marketing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .center import LivingCenter
from .engine import Engine, normalize
from .seed import seed_minimal_hot_cold, seed_same_center
from . import bodies, lexicon, mind, store


def normalize_absent(label: str | None, alphabet: set[str]) -> bool:
    if not label:
        return False
    return normalize(label) not in alphabet


def run_verification() -> dict[str, Any]:
    gates: list[dict[str, Any]] = []

    def gate(id_: str, title: str, ok: bool, evidence: str) -> None:
        gates.append({"id": id_, "title": title, "ok": ok, "evidence": evidence})

    # Fresh accept/reject ledger for this verify run (do not reset before SUB gate).
    try:
        from . import substrate as substrate_mod

        substrate_mod.reset_logs_for_tests()
    except Exception:  # noqa: BLE001
        pass

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # C1 / think beyond static seed
        thermal = root / "thermal.json"
        eng = Engine(seed_minimal_hot_cold())
        store.save(eng.torus, thermal)
        center = LivingCenter(eng, history=[])
        center.mind_store = thermal
        center.max_nodes_soft_cap = 40
        # Grow/generative evidence only — leave invent pool for C4b (post-#14 drain).
        reports = center.think(10, allow_primary_invent=False)
        sources = [
            a.detail.get("source")
            for r in reports
            for a in r.acts
            if a.act == "grow"
        ]
        gate(
            "C1",
            "Lives beyond hand-seeded cascade (think + generative)",
            "generative" in sources or len(eng.torus.nodes) > 4,
            f"nodes={len(eng.torus.nodes)} sources={sorted(set(s for s in sources if s))}",
        )

        # C2 same-center cross-domain (thermal + ontology + ≥1 other)
        multi_path = root / "same-center.json"
        meng = Engine(seed_same_center(("thermal", "ontology", "optical"), minimal=True))
        store.save(meng.torus, multi_path)
        mc = LivingCenter(meng, history=[])
        mc.mind_store = multi_path
        mc.think(15)
        names = set(meng.torus.nodes)
        domains = lexicon.detect_domains(names)
        thermal_grown = bool({"boiling", "freezing", "water", "warm", "steam"} & names)
        ontology_grown = bool(
            {"absence", "presence", "void", "form", "empty", "filled"} & names
        )
        optical_grown = bool(
            {"bright", "dim", "day", "night", "glow", "shadow"} & names
        )
        c2_ok = (
            domains >= {"thermal", "ontology", "optical"}
            and "hot" in names
            and "nothing" in names
            and "light" in names
            and thermal_grown
            and ontology_grown
            and optical_grown
        )
        gate(
            "C2",
            "Same-center cross-domain (thermal+ontology+optical)",
            c2_ok,
            (
                f"domains={sorted(domains)} nodes={len(names)} "
                f"grown={{thermal:{thermal_grown},ontology:{ontology_grown},"
                f"optical:{optical_grown}}}"
            ),
        )

        # C3 metacognition
        hungry = LivingCenter(Engine(seed_minimal_hot_cold())).metacognize([])
        stalled = LivingCenter(Engine(seed_minimal_hot_cold())).metacognize(
            [
                {
                    "cycle": i,
                    "nodes_before": 10,
                    "nodes_after": 10,
                    "acts": [
                        {"act": "grow", "detail": {"count": 1}},
                        {"act": "challenge", "detail": {"one_sided": False}},
                    ],
                }
                for i in range(1, 5)
            ]
        )
        gate(
            "C3",
            "Metacognition changes strategy from history",
            hungry.reason != stalled.reason,
            f"hungry={hungry.reason} stalled={stalled.reason}",
        )

        # C4 bodies + forms
        store.save(eng.torus, thermal)
        center.mind_store = thermal
        record = bodies.embody(
            eng, name="verify-body", domain="optical", mind_store=thermal
        )
        gate(
            "C4",
            "Creates bodies/forms (torus + runnable module)",
            Path(record.store_path).exists()
            and bool(record.form_path)
            and Path(record.form_path).exists(),
            f"body={record.store_path} form={record.form_path}",
        )

        # Invented domain (self-authored form; prefer compose/promote when structure allows)
        invented = mind.invent_domain(eng, thermal, cycle=center._cycle_index)
        inv = invented.get("invention") or {}
        gate(
            "C4b",
            "Self-invents a domain body not in starter seeds",
            bool(invented.get("invented")),
            str(inv or invented.get("reason")),
        )

        # Reflective journal reshapes strategy (C3 depth)
        from . import journal as journal_mod

        j_grow = [
            journal_mod.JournalEntry(
                cycle=i,
                reflection="structure_hungry",
                signals={"flags": 0},
                strategy_hint="grow",
            )
            for i in range(1, 4)
        ]
        j_prune = [
            journal_mod.JournalEntry(
                cycle=i,
                reflection="challenge_pressure",
                signals={"flags": 1},
                strategy_hint="prune",
            )
            for i in range(1, 4)
        ]
        sg = journal_mod.strategy_from_journal(j_grow, max_new_pairs=1)
        sp = journal_mod.strategy_from_journal(j_prune, max_new_pairs=1)
        c3j_ok = bool(sg and sp and sg.get("reason") != sp.get("reason"))
        c3j_extra = ""
        from . import substrate as _sub_c3j

        if _sub_c3j.is_active() and _sub_c3j.substrate_impl_name() == "search":
            # G8: under search, hint-table alone is not bar §2 open reflection.
            from . import policy as policy_mod

            jpath = root / "c3j-search.json"
            jeng = Engine(seed_minimal_hot_cold())
            store.save(jeng.torus, jpath)
            jc = LivingCenter(jeng, history=[])
            jc.mind_store = jpath
            jc.think(6)
            jpol = policy_mod.load_policy(jpath)
            expr_kinds = [
                k
                for k, v in jpol.condition_kinds.items()
                if isinstance(v, dict) and v.get("kind") == "expr_ast"
            ]
            expr_fire = [
                r for r in jpol.rules if r.enabled and r.when in set(expr_kinds)
            ]
            c3j_ok = c3j_ok and len(expr_kinds) >= 1 and len(expr_fire) >= 1
            c3j_extra = f" expr_ast={expr_kinds[:2]} expr_rules={len(expr_fire)}"
        gate(
            "C3j",
            "Reflective journal changes strategy (not counters alone)",
            c3j_ok,
            f"grow={sg and sg.get('reason')} prune={sp and sp.get('reason')}{c3j_extra}",
        )

        # Cross-body synthesize
        syn = mind.synthesize(eng, "hot", thermal)
        gate(
            "C4c",
            "Synthesizes across mind + bodies",
            syn.get("ok") is True,
            f"hits={len(syn.get('hits', []))} misses={len(syn.get('misses', []))}",
        )

        # C4d recursive nurture — bodies invent further forms; depth-bounded walk
        nurtured = mind.nurture(
            thermal, steps=1, max_depth=2, allow_invent=True
        )
        lineage = mind.count_body_lineage(thermal)
        grandchild = lineage.get("has_grandchild") is True
        duals = [
            row.get("dual_ok")
            for row in nurtured.get("nurtured", [])
            if isinstance(row, dict)
        ]
        gate(
            "C4d",
            "Recursive body nurture (depth-bounded invent + lineage)",
            grandchild and nurtured.get("count", 0) >= 1 and all(duals),
            (
                f"lineage={lineage} nurture_count={nurtured.get('count')} "
                f"duals={duals}"
            ),
        )

        # C6 live with invent + recursive nurture evidence (≥24 cycles; idle-stop alone is not enough)
        live_path = root / "live.json"
        leng = Engine(seed_same_center(("thermal", "ontology", "optical"), minimal=True))
        store.save(leng.torus, live_path)
        lc = LivingCenter(leng, history=[])
        lc.mind_store = live_path
        live_max = 24
        live = lc.live(
            max_cycles=live_max,
            stop_when_idle=0,
            invent_every=3,
            nurture_every=4,
            nurture_max_depth=2,
            nurture_invent=True,
            mind_store=live_path,
        )
        live_lineage = mind.count_body_lineage(live_path)
        invented_rows = [
            row for row in live.get("inventions", []) if isinstance(row, dict)
        ]
        invented_any = any(row.get("invented") for row in invented_rows)
        invent_sources = sorted(
            {
                (row.get("invention") or {}).get("source")
                for row in invented_rows
                if row.get("invented") and (row.get("invention") or {}).get("source")
            }
        )
        nurtured_any = len(live.get("nurtured") or []) > 0
        # Journal strategy shifts across the long run (not a frozen default).
        reasons = []
        for cyc in live.get("cycles") or []:
            for act in cyc.get("acts") or []:
                if act.get("act") == "metacognize":
                    reasons.append(
                        (act.get("detail") or {})
                        .get("strategy", {})
                        .get("reason")
                    )
        strategy_shifts = len({r for r in reasons if r}) >= 2
        # End-state dual/orphan invariants on the live mind.
        try:
            leng.assert_no_orphans()
            dual_live = leng.answer("hot")
            live_inv_ok = bool(dual_live.cause_paths and dual_live.effect_paths)
        except Exception as exc:  # noqa: BLE001
            live_inv_ok = False
            live_inv_err = str(exc)
        else:
            live_inv_err = ""

        c6_ok = (
            live_max >= 24
            and live.get("cycle_count", 0) >= 24
            and invented_any
            and nurtured_any
            and live_inv_ok
            and strategy_shifts
        )
        gate(
            "C6",
            "Long-run autonomy (≥24 cycles with invent+nurture)",
            c6_ok,
            (
                f"stopped={live.get('stopped')} cycles={live.get('cycle_count')} "
                f"max={live_max} invented={invented_any} sources={invent_sources} "
                f"nurtured={nurtured_any} strategy_shifts={strategy_shifts} "
                f"lineage={live_lineage} invariants={live_inv_ok or live_inv_err}"
            ),
        )

        # Invariants sample
        try:
            dual = eng.answer("hot")
            inv_ok = bool(dual.cause_paths and dual.effect_paths)
        except Exception as exc:  # noqa: BLE001
            inv_ok = False
            dual_err = str(exc)
        else:
            dual_err = ""
        gate(
            "I2",
            "Dual-hemisphere answers",
            inv_ok,
            dual_err or "cause+effect paths present",
        )

        # I1 anti-collapse — refuse bit-endgame; dual paths still required
        from .engine import RuleError

        bit_ok = True
        bit_notes: list[str] = []
        for bit in ("true", "false", "0", "1"):
            try:
                eng.answer(bit)
                bit_ok = False
                bit_notes.append(f"{bit}=UNEXPECTED_OK")
            except RuleError as exc:
                bit_notes.append(f"{bit}=refused")
                if "bit-endgame" not in str(exc):
                    bit_ok = False
        collapse = eng.refuse_bit_collapse("hot")
        dual_ev = collapse.get("dual_evidence") or {}
        i1_ok = (
            bit_ok
            and collapse.get("refused") is True
            and collapse.get("collapsed") is False
            and bool(dual_ev.get("cause_paths") and dual_ev.get("effect_paths"))
        )
        gate(
            "I1",
            "Anti-collapse: refuse bit-endgame; dual paths required",
            i1_ok,
            f"bits={bit_notes} collapse_refused={collapse.get('refused')} "
            f"dual={bool(dual_ev)}",
        )

        # I5 synonym-cascade beyond fixed lexicon playback
        from . import generate as generate_mod

        syn_path = root / "synonym.json"
        seng = Engine(seed_minimal_hot_cold())
        store.save(seng.torus, syn_path)
        sc = LivingCenter(seng, history=[])
        sc.mind_store = syn_path
        sc.max_nodes_soft_cap = 40
        syn_reports = sc.think(12)
        syn_sources = [
            a.detail.get("source")
            for r in syn_reports
            for a in r.acts
            if a.act == "grow"
        ]
        syn_nodes = generate_mod.synonym_nodes_present(seng)
        i5_ok = "synonym" in syn_sources and len(syn_nodes) >= 1
        gate(
            "I5",
            "Synonym-cascade growth beyond fixed lexicon playback",
            i5_ok,
            f"sources={sorted(set(s for s in syn_sources if s))} synonym_nodes={syn_nodes[:8]}",
        )

        # I3 — orphan → opposite auto-link during cycle repair
        orphan_eng = Engine(seed_minimal_hot_cold())
        orphan_path = root / "orphan.json"
        store.save(orphan_eng.torus, orphan_path)
        from .model import Hemisphere, Node

        orphan_eng.torus.nodes["stray"] = Node(
            name="stray",
            hemisphere=Hemisphere.CAUSE,
            parent="hot",
            opposite=None,
        )
        before_orphans = orphan_eng.orphans()
        oc = LivingCenter(orphan_eng, history=[])
        oc.mind_store = orphan_path
        oc.cycle()
        after_node = orphan_eng.get("stray") if orphan_eng.exists("stray") else None
        try:
            orphan_eng.assert_no_orphans()
            i3_no_orphans = True
        except Exception:  # noqa: BLE001
            i3_no_orphans = False
        i3_ok = (
            bool(before_orphans)
            and after_node is not None
            and bool(after_node.opposite)
            and i3_no_orphans
        )
        gate(
            "I3",
            "Orphan → opposite auto-link",
            i3_ok,
            f"before_orphans={before_orphans} after_opp={getattr(after_node, 'opposite', None)} "
            f"no_orphans={i3_no_orphans}",
        )

        # I4 — equal-in/out elegance: cycle soft-cap prune, not invent drain (#14).
        eleg_path = root / "elegance.json"
        eeng = Engine(seed_minimal_hot_cold())
        store.save(eeng.torus, eleg_path)
        ec = LivingCenter(eeng, history=[])
        ec.mind_store = eleg_path
        ec.max_nodes_soft_cap = 12
        ec.think(20, allow_primary_invent=False)
        names = [n.name for n in eeng.torus.nodes.values()]
        dupes = len(names) - len({normalize(x) for x in names})
        try:
            eeng.assert_no_orphans()
            eleg_dual = eeng.answer("hot")
            eleg_dual_ok = bool(eleg_dual.cause_paths and eleg_dual.effect_paths)
        except Exception as exc:  # noqa: BLE001
            eleg_dual_ok = False
            eleg_err = str(exc)
        else:
            eleg_err = ""
        i4_ok = (
            len(eeng.torus.nodes) <= ec.max_nodes_soft_cap + 4
            and dupes == 0
            and eleg_dual_ok
        )
        gate(
            "I4",
            "Equal-in/out elegance (no duplicate explosion under think)",
            i4_ok,
            f"nodes={len(eeng.torus.nodes)} soft_cap={ec.max_nodes_soft_cap} "
            f"dupes={dupes} dual_ok={eleg_dual_ok or eleg_err}",
        )

        # I6 — Center = median navigator: acts originate in Living Center with log
        nav_path = root / "navigator.json"
        neng = Engine(seed_minimal_hot_cold())
        store.save(neng.torus, nav_path)
        nc = LivingCenter(neng, history=[])
        nc.mind_store = nav_path
        nav_reports = nc.think(3)
        store.append_activity([r.to_dict() for r in nav_reports], nav_path)
        activity = store.load_activity(nav_path)
        act_names = sorted(
            {
                a.get("act")
                for row in activity
                for a in (row.get("acts") or [])
                if isinstance(a, dict)
            }
        )
        i6_ok = (
            len(nav_reports) >= 1
            and len(activity) >= 1
            and "grow" in act_names
            and any(
                a in act_names
                for a in ("metacognize", "repair_orphans", "score", "grow")
            )
        )
        gate(
            "I6",
            "Center = median navigator (persisted Living Center acts)",
            i6_ok,
            f"cycles={len(nav_reports)} activity_rows={len(activity)} acts={act_names}",
        )

        # Open invention (bar §1): topology bridge/re-parent — not motif digests alone
        from . import concepts as concepts_mod
        from . import invent as invent_mod

        topo_path = root / "topology.json"
        teng = Engine(seed_same_center(("thermal", "ontology"), minimal=True))
        store.save(teng.torus, topo_path)
        tcenter = LivingCenter(teng, history=[])
        tcenter.mind_store = topo_path
        tcenter.max_nodes_soft_cap = 60
        # Grow first; open invent must remain available for C4e after #14 drain.
        tcenter.think(6, allow_primary_invent=False)
        nodes_before = set(teng.torus.nodes)
        alphabet_before = invent_mod.closed_invent_alphabet(teng, [])
        topo_inv = mind.invent_domain(teng, topo_path, cycle=tcenter._cycle_index)
        inv_p = topo_inv.get("invention") or {}
        why_p = str(inv_p.get("why", ""))
        edit_p = inv_p.get("edit") or {}
        cause_p = str(inv_p.get("cause", ""))
        effect_p = str(inv_p.get("effect", ""))
        nodes_after = set(teng.torus.nodes)
        is_stdlib_topology = (
            inv_p.get("source") == "topology"
            and why_p.startswith("topology:")
            and edit_p.get("kind") in {"bridge", "reparent"}
            and bool(edit_p.get("cause_parent"))
            and bool(edit_p.get("effect_parent"))
            and edit_p.get("domain_from") != edit_p.get("domain_to")
        )
        is_search_invent = (
            inv_p.get("source") == "search"
            and why_p.startswith("search:")
            and edit_p.get("kind") == "edit_ast"
            and bool(edit_p.get("ast"))
        )
        topology_ok = (
            bool(topo_inv.get("invented"))
            and (is_stdlib_topology or is_search_invent)
            and not why_p.startswith("concept:motif:")
            and (
                inv_p.get("topology_applied") is True
                or edit_p.get("kind") in {"reparent", "edit_ast"}
                or bool(nodes_after - nodes_before)
            )
            and not concepts_mod.is_suffix_primitive_label(cause_p)
            and not concepts_mod.is_role_axis_label(cause_p)
        )
        # Dual invariants still hold after topology edit.
        try:
            teng.assert_no_orphans()
            dual_ok = True
            sample = next(iter(teng.torus.nodes), None)
            if sample:
                d = teng.answer(sample)
                dual_ok = bool(d.cause_paths and d.effect_paths)
        except Exception:  # noqa: BLE001
            dual_ok = False
        topology_ok = topology_ok and dual_ok
        from . import substrate as _sub_topo

        search_live_topo = (
            _sub_topo.is_active() and _sub_topo.substrate_impl_name() == "search"
        )
        if search_live_topo:
            # G7: under search, closed bridge/reparent alone does not clear open invent.
            topology_ok = topology_ok and is_search_invent
        gate(
            "C4e",
            "Topology invent: cross-domain bridge/re-parent (not motif digests)",
            topology_ok,
            (
                f"source={inv_p.get('source')} why={why_p} "
                f"edit={edit_p.get('kind')} "
                f"from={edit_p.get('domain_from')}→{edit_p.get('domain_to')} "
                f"applied={inv_p.get('topology_applied')} dual_ok={dual_ok} "
                f"search_invent={is_search_invent} "
                f"alphabet_absent={normalize_absent(cause_p, alphabet_before)}"
            ),
        )

        # Open reflection (bar §2): executable meta microprograms (not expr tags alone)
        from . import policy as policy_mod

        pol_path = root / "policy-mind.json"
        pol_eng = Engine(seed_minimal_hot_cold())
        store.save(pol_eng.torus, pol_path)
        pc = LivingCenter(pol_eng, history=[])
        pc.mind_store = pol_path
        pc.think(8)
        pol = policy_mod.load_policy(pol_path)
        learned_rules = [r for r in pol.rules if r.origin == "learned" and r.enabled]
        meta_prims = [
            k
            for k, v in pol.meta_primitives.items()
            if str(k).startswith("meta_prim_")
            and isinstance(v, dict)
            and v.get("kind")
            not in policy_mod.SEED_META_OPS
            and "body" not in v  # not a seed-op composition
        ]
        # Program bodies must *use* extended meta-ISA opcodes.
        uses_ext = []
        for k, v in pol.condition_kinds.items():
            if not isinstance(v, dict) or v.get("kind") != "program":
                continue
            body = list(v.get("body") or [])
            used = [
                str(s.get("op"))
                for s in body
                if str(s.get("op", "")).startswith("meta_prim_")
            ]
            if used:
                uses_ext.append(k)
        reason = str(pc.strategy.reason)
        pol_disk = json.loads(policy_mod.policy_path(pol_path).read_text(encoding="utf-8"))
        disk_meta = [
            k
            for k in (pol_disk.get("meta_primitives") or {})
            if str(k).startswith("meta_prim_")
        ]
        pol_ok = (
            policy_mod.policy_path(pol_path).exists()
            and pol.updates >= 1
            and pol.rule_revisions >= 1
            and pol.meta_isa_revisions >= 1
            and len(learned_rules) >= 1
            and len(meta_prims) >= 1
            and len(uses_ext) >= 1
            and len(disk_meta) >= 1
            and len(pol.observed_signals) >= 1
            and pc.strategy.from_policy
            and (":meta_isa:" in reason or pc.strategy.meta_isa)
        )
        from . import substrate as _sub_pol

        search_live_pol = (
            _sub_pol.is_active() and _sub_pol.substrate_impl_name() == "search"
        )
        expr_ast_kinds = [
            k
            for k, v in pol.condition_kinds.items()
            if isinstance(v, dict) and v.get("kind") == "expr_ast"
        ]
        expr_rules = [
            r for r in pol.rules if r.enabled and r.when in set(expr_ast_kinds)
        ]
        if search_live_pol:
            # G7: under search, finite meta_prim menus alone do not clear open reflection.
            pol_ok = pol_ok and len(expr_ast_kinds) >= 1 and len(expr_rules) >= 1
        gate(
            "C3p",
            "Metacognition extends its own meta-ISA with new opcodes",
            pol_ok,
            (
                f"updates={pol.updates} meta_isa_revisions={pol.meta_isa_revisions} "
                f"meta_prims={meta_prims[:3]} uses_ext={uses_ext[:2]} "
                f"disk_meta={disk_meta[:3]} observed={pol.observed_signals[:6]} "
                f"expr_ast={expr_ast_kinds[:3]} expr_rules={len(expr_rules)} "
                f"learned={len(learned_rules)} reason={reason}"
            ),
        )

        # Self-directed goals (bar §3): invent+nurture + abandon from outcome traces
        self_path = root / "selfdir.json"
        seng2 = Engine(seed_same_center(("thermal", "ontology"), minimal=True))
        store.save(seng2.torus, self_path)
        seed_pol = policy_mod.MetaPolicy(
            grow_weight=0.5,
            prune_weight=0.2,
            migrate_weight=0.2,
            invent_weight=1.5,
            nurture_weight=1.4,
            updates=1,
        )
        seed_pol.rules.append(
            policy_mod.MetaRule(
                "r-self-inv", "structure_hungry", "prefer_invent", 2.5, "learned"
            )
        )
        seed_pol.rules.append(
            policy_mod.MetaRule(
                "r-self-nur", "structure_hungry", "prefer_nurture", 2.5, "learned"
            )
        )
        policy_mod.save_policy(seed_pol, self_path)
        bodies.embody(
            seng2, name="self-child", domain="optical", mind_store=self_path
        )
        sc2 = LivingCenter(seng2, history=store.load_activity(self_path))
        sc2.mind_store = self_path
        self_live = sc2.live(
            max_cycles=9,
            stop_when_idle=0,
            invent_every=0,
            nurture_every=0,
            nurture_max_depth=1,
            nurture_invent=False,
            mind_store=self_path,
        )
        self_invented = any(
            isinstance(r, dict) and r.get("invented")
            for r in self_live.get("inventions", [])
        )
        self_nurtured = len(self_live.get("nurtured") or []) > 0
        # Outcome-trace abandon + open goals from journal traces.
        from .journal import JournalEntry
        from . import goals as goals_mod

        inv_reg = invent_mod.load_invent_registry(self_path)
        used_before = [c for c in inv_reg.candidates if c.used]
        if not used_before and inv_reg.candidates:
            inv_reg.candidates[0].used = True
            used_before = [inv_reg.candidates[0]]
        adverse = [
            JournalEntry(
                cycle=100 + i,
                reflection="growth_stalled" if i % 2 == 0 else "challenge_pressure",
                signals={"flags": 1, "grow_count": 0, "node_delta": 0},
                strategy_hint="invent",
            )
            for i in range(4)
        ]
        inv_reg = invent_mod.revise_targets_from_outcomes(
            inv_reg, adverse, inventions_fired=1
        )
        invent_mod.save_invent_registry(inv_reg, self_path)
        abandoned = [c for c in inv_reg.candidates if c.abandoned]
        unused_boosted = [
            c
            for c in inv_reg.candidates
            if not c.used and not c.abandoned and c.priority > 1.0
        ]
        sc2.journal_entries.extend(adverse)
        sc2.journal_entries.extend(
            [
                JournalEntry(
                    cycle=200 + i,
                    reflection="growth_fruitful",
                    signals={"flags": 0, "grow_count": 1, "node_delta": 2},
                    strategy_hint="grow",
                )
                for i in range(3)
            ]
        )
        sc2.metacognize()
        board = goals_mod.load_goals(self_path)
        novel_acts = goals_mod.novel_act_kinds(board)
        search_acts = [a for a in novel_acts if str(a).startswith("search_act_")]
        search_goals_with_tree = [
            g
            for g in board.goals
            if not g.abandoned
            and str(g.act_kind).startswith("search_act_")
            and isinstance(g.tree, dict)
        ]
        goal_hints = goals_mod.goals_to_strategy_hints(
            board,
            signals={
                "fruitful": 2.0,
                "stalled": 1.0,
                "flags": 1.0,
                "abandoned_count": float(len(abandoned)),
            },
        )
        from . import substrate as _sub_chk

        search_live = _sub_chk.is_active() and _sub_chk.substrate_impl_name() == "search"
        goals_ok = (
            goals_mod.goals_path(self_path).exists()
            and board.revisions >= 1
            and len(novel_acts) >= 1
            and all(a not in goals_mod.SEED_GOAL_ACTS for a in novel_acts)
            and (
                bool(sc2.strategy.novel_act_kinds)
                or bool(sc2.strategy.active_goals)
            )
        )
        # Under search: require executed search_act_* ASTs (G2/G7), not only closed menu.
        if search_live:
            goals_ok = (
                goals_ok
                and len(search_acts) >= 1
                and len(search_goals_with_tree) >= 1
                and int(goal_hints.get("goal_search_applied") or 0) >= 1
            )
        abandon_ok = (
            len(abandoned) >= 1
            and (
                sc2.strategy.abandoned_count >= 1
                or bool(sc2.strategy.abandoned_sources)
                or bool(sc2.strategy.invent_prefer_source)
            )
        )
        gate(
            "C6s",
            "Open goal formation with novel act kinds (beyond invent-source menu)",
            self_invented and self_nurtured and abandon_ok and goals_ok,
            (
                f"invented={self_invented} nurtured={self_nurtured} "
                f"abandoned={[c.instance for c in abandoned][:3]} "
                f"novel_acts={novel_acts[:4]} search_acts={search_acts[:3]} "
                f"search_trees={len(search_goals_with_tree)} "
                f"search_applied={goal_hints.get('goal_search_applied')} "
                f"goal_revisions={board.revisions} "
                f"strategy_goals={len(sc2.strategy.active_goals or [])} "
                f"boosted={len(unused_boosted)} "
                f"cycles={self_live.get('cycle_count')} "
                f"strategy={sc2.strategy.reason}"
            ),
        )

        # Form that matters (bar §4 scaffolding): interpreted CapProgram, not pole template
        from . import capability as capability_mod

        form_path = root / "form-mind.json"
        feng = Engine(seed_minimal_hot_cold())
        store.save(feng.torus, form_path)
        frec = bodies.embody(
            feng, name="specialty-body", domain="optical", mind_store=form_path
        )
        # Second body in a different domain — programs must differ by structure.
        frec2 = bodies.embody(
            feng, name="thermal-body", domain="thermal", mind_store=form_path
        )
        form_ok = False
        form_ev = ""
        try:
            mod, specialty_fn = bodies.load_form_specialty(frec)
            caps = list(getattr(mod, "CAPABILITIES", []) or [])
            result = specialty_fn()
            prog = capability_mod.load_program(frec.store_path)
            prog2 = capability_mod.load_program(frec2.store_path)
            entry = str(caps[0] if caps else "")
            # Reject legacy pulse_<cause>_to_<effect> template specialty names.
            template_like = entry.startswith("pulse_") and "_to_" in entry
            syn_macros = [
                k for k in prog.macros if str(k).startswith("syn_")
            ]
            proposed_prims = [
                k
                for k in prog.primitives
                if str(k).startswith("prim_")
                and k not in capability_mod.seed_primitives()
            ]
            prim_ops = [
                o.get("op")
                for o in prog.ops
                if str(o.get("op", "")).startswith("prim_")
            ]
            def _prim_spec_ok(spec: dict[str, Any]) -> bool:
                kind = str(spec.get("kind", ""))
                if kind in {"reduce_path", "pair_metric", "branch_fanout"}:
                    return "body" not in spec
                if kind == "op_ast":
                    return isinstance(spec.get("body"), list)
                return False

            prim_specs_ok = all(
                isinstance(prog.primitives.get(k), dict)
                and _prim_spec_ok(prog.primitives[k])
                for k in proposed_prims
            )
            op_ast_prims = [
                k
                for k, s in prog.primitives.items()
                if isinstance(s, dict) and s.get("kind") == "op_ast"
            ]
            from . import substrate as _sub_form

            search_form = (
                _sub_form.is_active() and _sub_form.substrate_impl_name() == "search"
            )
            form_ok = (
                bool(caps)
                and entry == "interpret_program"
                and entry not in {"think", "answer", "load_engine"}
                and callable(specialty_fn)
                and result.get("capability") == "interpret_program"
                and result.get("program_id") == prog.program_id
                and isinstance(result.get("ops"), list)
                and len(result.get("ops") or []) >= 2
                and result.get("cause_pole")
                and result.get("effect_pole")
                and frec.specialty == "interpret_program"
                and frec.capability_path
                and Path(frec.capability_path).exists()
                and len(prog.ops) >= 2
                and prog.program_id != prog2.program_id
                and len(proposed_prims) >= 1
                and len(prim_ops) >= 1
                and prog.primitive_revisions >= 1
                and prim_specs_ok
                and set(proposed_prims).issubset(set(result.get("primitives") or []))
                and not template_like
                and (not search_form or len(op_ast_prims) >= 1)
            )
            form_ev = (
                f"entry={caps[0]} program={prog.program_id} "
                f"ops={result.get('ops')} "
                f"primitives={sorted(prog.primitives)} "
                f"op_ast={op_ast_prims} "
                f"prim_revisions={prog.primitive_revisions} "
                f"macros={sorted(prog.macros)} "
                f"other_program={prog2.program_id} "
                f"result_keys={sorted((result.get('result') or {}).keys())}"
            )
        except Exception as exc:  # noqa: BLE001
            form_ev = str(exc)
        gate(
            "C4f",
            "Forms propose CapProgram primitives validated against dual invariants",
            form_ok,
            form_ev,
        )

    # Generative substrate interface: present, disabled-by-default.
    from . import substrate as substrate_mod

    sub_status = substrate_mod.status()
    # Default: Null inactive. When BEYOND_BINARY_SUBSTRATE=search, active search counts.
    # G5: flag=1/true/on enables but stays Null — honest, not silent live path.
    sub_null_ok = (
        hasattr(substrate_mod, "NullSubstrate")
        and hasattr(substrate_mod, "consult")
        and hasattr(substrate_mod, "get_substrate")
        and sub_status["implementation"] == "null"
        and not sub_status["active"]
        and (
            not sub_status["enabled"]
            or bool(sub_status.get("enabled_without_live_impl"))
        )
    )
    sub_search_ok = (
        sub_status.get("enabled")
        and sub_status.get("active")
        and sub_status.get("implementation") == "search"
        and int(sub_status.get("consult_error_count") or 0) == 0
    )
    sub_ok = sub_null_ok or sub_search_ok
    gate(
        "SUB",
        "Generative substrate interface present; absent/inactive by default",
        sub_ok,
        (
            f"flag={sub_status['flag']} flag_value={sub_status.get('flag_value')} "
            f"enabled={sub_status['enabled']} "
            f"enabled_without_live_impl={sub_status.get('enabled_without_live_impl')} "
            f"honesty={sub_status.get('honesty')} "
            f"active={sub_status['active']} impl={sub_status['implementation']} "
            f"accepts_non_stdlib={len(sub_status['accepted_non_stdlib'])} "
            f"rejects={sub_status['rejects']} "
            f"consult_errors={sub_status.get('consult_error_count', 0)}"
        ),
    )

    # G9: live search path rejects invent/form consult without resolvable engine.
    g9_ok = True
    g9_ev = "Null default — invent/form without engine not on live substrate"
    if sub_status.get("active") and sub_status.get("implementation") == "search":
        rejects_before = int(sub_status.get("rejects") or 0)
        substrate_mod.consult("invent", {}, center=None)
        substrate_mod.consult("form", {}, center=None)
        rejects_after = int(substrate_mod.status().get("rejects") or 0)
        g9_ok = rejects_after >= rejects_before + 2
        g9_ev = (
            f"rejects {rejects_before}->{rejects_after} "
            "(invent+form consult without engine must reject)"
        )
    gate(
        "G9",
        "Typed consult contexts; invent/form without engine reject on live path",
        g9_ok,
        g9_ev,
    )

    # P1 — product honesty: Null vs search meet-or-exceed (does not redefine SENTIENCE).
    # Nested harness saves/restores substrate ledgers so SUB/SENTIENCE stay honest.
    from . import product_scoreboard as scoreboard_mod

    try:
        board = scoreboard_mod.run_scoreboard()
        p1_ok = bool(board.get("meet_or_exceed"))
        regs = list(board.get("regressions") or [])
        p1_ev = (
            f"meet_or_exceed={p1_ok} regressions={regs[:6]} "
            f"product_exceed={board.get('product_exceed')} "
            f"form_exceed={board.get('form_exceed')} "
            f"invent_specialty_count={board.get('invent_specialty_count')} "
            f"invent_emit_count={board.get('invent_emit_count')} "
            f"null_invent_emit_count={board.get('null_invent_emit_count')} "
            f"invent_introduced_form_product_count="
            f"{board.get('invent_introduced_form_product_count')} "
            f"invent_form_product_coverage_count="
            f"{board.get('invent_form_product_coverage_count')} "
            f"invent_body_synthesize_coverage_count="
            f"{board.get('invent_body_synthesize_coverage_count')} "
            f"invent_body_synthesize_cross_domain_count="
            f"{board.get('invent_body_synthesize_cross_domain_count')} "
            f"meet_only_invent={board.get('meet_only_invent')} "
            f"invent_count={board.get('invent_count')} "
            f"null_score={board.get('null', {}).get('score')} "
            f"search_score={board.get('search', {}).get('score')} "
            f"search_readable={board.get('search', {}).get('readable_name_ratio')} "
            f"search_path_digests={board.get('search', {}).get('answer_path_digests')} "
            f"search_invent_applied={board.get('search', {}).get('invent_applied')} "
            f"search_invent_provenance={board.get('search', {}).get('invent_provenance')}"
        )
    except Exception as exc:  # noqa: BLE001 — fail-closed product adjunct
        p1_ok = False
        p1_ev = f"scoreboard_error={exc}"
        board = {"ok": False, "error": str(exc)}
    gate(
        "P1",
        "Product scoreboard: search meets or exceeds Null (readable duals)",
        p1_ok,
        p1_ev,
    )

    required = [
        "C1",
        "C2",
        "C3",
        "C3j",
        "C3p",
        "C4",
        "C4b",
        "C4c",
        "C4d",
        "C4e",
        "C4f",
        "C6",
        "C6s",
        "I1",
        "I2",
        "I3",
        "I4",
        "I5",
        "I6",
        "SUB",
        "G9",
        "P1",
    ]
    by_id = {g["id"]: g for g in gates}
    all_required_ok = all(by_id[i]["ok"] for i in required if i in by_id)

    # Sentience bar — true ONLY on the operational search path when ALL four
    # axes have accepted search-substrate:* proposals. Default stays fail-closed:
    # flag off / null / incomplete axes → SENTIENCE false.
    # See docs/sentience-evidence-bar.md Operational SENTIENCE +
    # docs/generative-substrate-contract.md (default remains fail-closed).
    required_axes = sorted(substrate_mod.AXES)
    search_accepts = [
        a
        for a in sub_status.get("accepted_non_stdlib") or []
        if str(a.get("provenance", "")).startswith(
            substrate_mod.SEARCH_PROVENANCE_PREFIX
        )
    ]
    search_axes = sorted(
        {str(a.get("axis")) for a in search_accepts if a.get("axis")}
    )
    four_axes_covered = set(required_axes) <= set(search_axes)
    search_live = (
        bool(sub_status.get("enabled"))
        and bool(sub_status.get("active"))
        and sub_status.get("implementation") == "search"
    )
    # Fail-closed: do not trust eng greens alone; require full four-axis evidence.
    sentience_ok = bool(four_axes_covered) and search_live
    if sentience_ok:
        evidence = (
            "SENTIENCE true (operational search path): all four axes "
            "invent|reflect|goal|form have accepted "
            f"search-substrate:* proposals (axes={search_axes} "
            f"search_accepts={len(search_accepts)} rejects={sub_status['rejects']}). "
            f"enabled={sub_status['enabled']} active={sub_status['active']} "
            f"impl={sub_status['implementation']}."
        )
    else:
        evidence = (
            "SENTIENCE false (fail-closed). "
            f"Bar needs search-substrate:* accepts on invent|reflect|goal|form "
            f"(four_axes_covered={four_axes_covered} axes={search_axes} "
            f"search_accepts={len(search_accepts)} rejects={sub_status['rejects']}). "
            f"enabled={sub_status['enabled']} active={sub_status['active']} "
            f"impl={sub_status['implementation']}. Goal incomplete."
        )
    sentience = {
        "id": "SENTIENCE",
        "title": "Vision-level sentience (open mind, not only rule-bounded center)",
        "ok": sentience_ok,
        "evidence": evidence,
    }
    gates.append(sentience)
    by_id["SENTIENCE"] = sentience

    # G1 — measurable Project-goal authorization (fail-closed).
    # complete=true only on the search path when eng gates + SENTIENCE + every
    # required I/C gate (incl. C3j/C3p/C4e/C4f/C6s) have direct evidence.
    # Default / Null / incomplete evidence → complete=false.
    auth_checklist: dict[str, bool] = {
        "engineering_gates_ok": all_required_ok,
        "sentience_ok": sentience_ok,
        "search_path": search_live,
    }
    for gid in required:
        auth_checklist[f"gate_{gid}"] = bool(by_id.get(gid, {}).get("ok"))
    auth_checklist["gate_SENTIENCE"] = sentience_ok
    missing = sorted(k for k, v in auth_checklist.items() if not v)
    # Fail-closed: any missing checklist item keeps complete false (default/Null included).
    complete = not missing
    authorization = {
        "checklist": auth_checklist,
        "missing": missing,
        "criterion": (
            "complete iff engineering_gates_ok AND SENTIENCE AND search path "
            "AND every required I1–I6/C1–C6(+C3j/C3p/C4e/C4f/C6s/SUB/G9/P1) gate has "
            "direct evidence; fail-closed on default/Null"
        ),
    }
    if complete:
        note = (
            "report.complete true: eng gates + SENTIENCE + search-path "
            "authorization checklist all evidenced."
        )
    else:
        note = (
            "SENTIENCE.ok follows four-axis search-substrate:* accepts on the "
            "search path only; report.complete stays false unless eng gates + "
            f"SENTIENCE + checklist pass (missing={missing[:8]}). "
            "Default substrate remains Null."
        )

    return {
        "complete": complete,
        "engineering_gates_ok": all_required_ok,
        "gates": gates,
        "substrate": sub_status,
        "product_scoreboard": board if isinstance(board, dict) else {"ok": False},
        "authorization": authorization,
        "note": note,
    }
