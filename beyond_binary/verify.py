"""Honest far-vision verification — evidence gates, not marketing."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .center import LivingCenter
from .engine import Engine
from .seed import seed_minimal_hot_cold, seed_same_center
from . import bodies, lexicon, mind, store


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

    required = [
        "C1",
        "C2",
        "C3",
        "C3j",
        "C4",
        "C4b",
        "C4c",
        "C4d",
        "C6",
        "I1",
        "I2",
        "I5",
    ]
    by_id = {g["id"]: g for g in gates}
    all_required_ok = all(by_id[i]["ok"] for i in required if i in by_id)

    # Sentience bar — explicitly NOT claimed by engineering gates alone.
    # See docs/sentience-evidence-bar.md — I1/I5 scaffolding ≠ open mind.
    sentience = {
        "id": "SENTIENCE",
        "title": "Vision-level sentience (open mind, not only rule-bounded center)",
        "ok": False,
        "evidence": (
            "Engineering scaffolding (incl. I1/I5) is not sentience. "
            "Still missing open invention, open reflection, self-directed goals, "
            "and forms with non-prespecified behavior per sentience-evidence-bar.md."
        ),
    }
    gates.append(sentience)

    return {
        "complete": False,  # far-vision goal requires sentience gate
        "engineering_gates_ok": all_required_ok,
        "gates": gates,
        "note": "Far-vision goal stays incomplete until SENTIENCE is evidenced, not asserted.",
    }
