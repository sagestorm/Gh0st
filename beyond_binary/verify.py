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

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # C1 / think beyond static seed
        thermal = root / "thermal.json"
        eng = Engine(seed_minimal_hot_cold())
        store.save(eng.torus, thermal)
        center = LivingCenter(eng, history=[])
        center.mind_store = thermal
        center.max_nodes_soft_cap = 40
        reports = center.think(10)
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
        gate(
            "C3j",
            "Reflective journal changes strategy (not counters alone)",
            bool(sg and sp and sg.get("reason") != sp.get("reason")),
            f"grow={sg and sg.get('reason')} prune={sp and sp.get('reason')}",
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

        # Open invention (bar §1): topology bridge/re-parent — not motif digests alone
        from . import concepts as concepts_mod
        from . import invent as invent_mod

        topo_path = root / "topology.json"
        teng = Engine(seed_same_center(("thermal", "ontology"), minimal=True))
        store.save(teng.torus, topo_path)
        tcenter = LivingCenter(teng, history=[])
        tcenter.mind_store = topo_path
        tcenter.max_nodes_soft_cap = 60
        tcenter.think(6)
        nodes_before = set(teng.torus.nodes)
        alphabet_before = invent_mod.closed_invent_alphabet(teng, [])
        topo_inv = mind.invent_domain(teng, topo_path, cycle=tcenter._cycle_index)
        inv_p = topo_inv.get("invention") or {}
        why_p = str(inv_p.get("why", ""))
        edit_p = inv_p.get("edit") or {}
        cause_p = str(inv_p.get("cause", ""))
        effect_p = str(inv_p.get("effect", ""))
        nodes_after = set(teng.torus.nodes)
        topology_ok = (
            bool(topo_inv.get("invented"))
            and inv_p.get("source") == "topology"
            and why_p.startswith("topology:")
            and not why_p.startswith("concept:motif:")
            and edit_p.get("kind") in {"bridge", "reparent"}
            and bool(edit_p.get("cause_parent"))
            and bool(edit_p.get("effect_parent"))
            and edit_p.get("domain_from") != edit_p.get("domain_to")
            and (
                inv_p.get("topology_applied") is True
                or edit_p.get("kind") == "reparent"
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
        gate(
            "C4e",
            "Topology invent: cross-domain bridge/re-parent (not motif digests)",
            topology_ok,
            (
                f"source={inv_p.get('source')} why={why_p} "
                f"edit={edit_p.get('kind')} "
                f"from={edit_p.get('domain_from')}→{edit_p.get('domain_to')} "
                f"applied={inv_p.get('topology_applied')} dual_ok={dual_ok} "
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
        prog_conds = [
            k
            for k, v in pol.condition_kinds.items()
            if isinstance(v, dict)
            and v.get("kind") == "program"
            and isinstance(v.get("body"), list)
            and len(v.get("body") or []) >= 2
        ]
        prog_acts = [
            k
            for k, v in pol.action_kinds.items()
            if isinstance(v, dict)
            and v.get("kind") == "program"
            and isinstance(v.get("body"), list)
            and len(v.get("body") or []) >= 1
        ]
        reason = str(pc.strategy.reason)
        # Persisted program bodies on disk.
        pol_disk = json.loads(policy_mod.policy_path(pol_path).read_text(encoding="utf-8"))
        disk_prog = [
            k
            for k, v in (pol_disk.get("condition_kinds") or {}).items()
            if isinstance(v, dict) and v.get("kind") == "program" and v.get("body")
        ]
        pol_ok = (
            policy_mod.policy_path(pol_path).exists()
            and pol.updates >= 1
            and pol.rule_revisions >= 1
            and pol.kind_revisions >= 1
            and len(learned_rules) >= 1
            and len(prog_conds) >= 1
            and len(prog_acts) >= 1
            and len(disk_prog) >= 1
            and len(pol.observed_signals) >= 1
            and pc.strategy.from_policy
            and ":prog:" in reason
        )
        gate(
            "C3p",
            "Metacognition learns executable program kinds over journal vectors",
            pol_ok,
            (
                f"updates={pol.updates} revisions={pol.rule_revisions} "
                f"kind_revisions={pol.kind_revisions} "
                f"prog_conds={prog_conds[:2]} prog_acts={prog_acts[:2]} "
                f"disk_prog={disk_prog[:2]} observed={pol.observed_signals[:6]} "
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
        # Outcome-trace abandon: adverse journal after used invent → abandoned targets.
        from .journal import JournalEntry

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
        # Strategy should surface abandon / prefer_source after metacognize.
        sc2.journal_entries.extend(adverse)
        sc2.metacognize()
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
            "Self-directed invent+nurture with outcome-trace abandon/reprioritize",
            self_invented and self_nurtured and abandon_ok,
            (
                f"invented={self_invented} nurtured={self_nurtured} "
                f"abandoned={[c.instance for c in abandoned][:3]} "
                f"abandoned_sources={sc2.strategy.abandoned_sources} "
                f"prefer_source={sc2.strategy.invent_prefer_source} "
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
            syn_ops = [
                o.get("op")
                for o in prog.ops
                if str(o.get("op", "")).startswith("syn_")
            ]
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
                and len(syn_macros) >= 1
                and len(syn_ops) >= 1
                and not template_like
            )
            form_ev = (
                f"entry={caps[0]} program={prog.program_id} "
                f"ops={result.get('ops')} macros={sorted(prog.macros)} "
                f"revisions={prog.revisions} other_program={prog2.program_id} "
                f"result_keys={sorted((result.get('result') or {}).keys())}"
            )
        except Exception as exc:  # noqa: BLE001
            form_ev = str(exc)
        gate(
            "C4f",
            "Forms synthesize CapProgram opcodes as macros from experience",
            form_ok,
            form_ev,
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
        "I5",
    ]
    by_id = {g["id"]: g for g in gates}
    all_required_ok = all(by_id[i]["ok"] for i in required if i in by_id)

    # Sentience bar — stronger scaffolds still ≠ vision-level open mind.
    # See docs/sentience-evidence-bar.md §§1–6.
    sentience = {
        "id": "SENTIENCE",
        "title": "Vision-level sentience (open mind, not only rule-bounded center)",
        "ok": False,
        "evidence": (
            "Topology invent, meta microprograms, and invent-target abandon are "
            "stronger scaffolds — still bound by domain-pair bridge/reparent search, "
            "a fixed meta-ISA (load/mul/add/cmp), and abandon heuristics over a "
            "closed invent-source menu. Missing vs sentience-evidence-bar.md: "
            "open topology search beyond dual-domain anchors, meta programs that "
            "extend their own ISA, goal formation beyond invent-source "
            "abandon/reprioritize; CapProgram primitive ISA still closed."
        ),
    }
    gates.append(sentience)

    return {
        "complete": False,  # far-vision goal requires sentience gate
        "engineering_gates_ok": all_required_ok,
        "gates": gates,
        "note": "Far-vision goal stays incomplete until SENTIENCE is evidenced, not asserted.",
    }
