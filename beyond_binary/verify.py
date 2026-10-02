"""Honest far-vision verification — evidence gates, not marketing."""

from __future__ import annotations

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

        # Open invention (bar §1): structural concept formation beyond suffix primitives
        from . import concepts as concepts_mod
        from . import invent as invent_mod

        prim_path = root / "concept.json"
        peng = Engine(seed_minimal_hot_cold())
        store.save(peng.torus, prim_path)
        pcenter = LivingCenter(peng, history=[])
        pcenter.mind_store = prim_path
        pcenter.max_nodes_soft_cap = 40
        pcenter.think(8)
        alphabet_before = invent_mod.closed_invent_alphabet(peng, [])
        concept_inv = mind.invent_domain(peng, prim_path, cycle=pcenter._cycle_index)
        inv_p = concept_inv.get("invention") or {}
        concept_ok = (
            bool(concept_inv.get("invented"))
            and inv_p.get("source") == "concept"
            and normalize_absent(inv_p.get("cause"), alphabet_before)
            and normalize_absent(inv_p.get("effect"), alphabet_before)
            and str(inv_p.get("why", "")).startswith("concept:")
            and not concepts_mod.is_suffix_primitive_label(str(inv_p.get("cause", "")))
            and not concepts_mod.is_suffix_primitive_label(str(inv_p.get("effect", "")))
        )
        gate(
            "C4e",
            "Concept formation beyond pressure-suffix primitives",
            concept_ok,
            str(inv_p or concept_inv.get("reason")),
        )

        # Open reflection (bar §2): policy revises its own rules (not only weights)
        from . import policy as policy_mod

        pol_path = root / "policy-mind.json"
        pol_eng = Engine(seed_minimal_hot_cold())
        store.save(pol_eng.torus, pol_path)
        pc = LivingCenter(pol_eng, history=[])
        pc.mind_store = pol_path
        pc.think(8)
        pol = policy_mod.load_policy(pol_path)
        learned_rules = [r for r in pol.rules if r.origin == "learned" and r.enabled]
        pol_ok = (
            policy_mod.policy_path(pol_path).exists()
            and pol.updates >= 1
            and pol.rule_revisions >= 1
            and len(learned_rules) >= 1
            and pc.strategy.from_policy
            and ":rules:" in str(pc.strategy.reason)
        )
        gate(
            "C3p",
            "Metacognition revises its own rules from experience",
            pol_ok,
            (
                f"updates={pol.updates} revisions={pol.rule_revisions} "
                f"learned={len(learned_rules)} reason={pc.strategy.reason}"
            ),
        )

        # Self-directed goals (bar §3 scaffolding): invent+nurture with every=0
        self_path = root / "selfdir.json"
        seng2 = Engine(seed_same_center(("thermal", "ontology"), minimal=True))
        store.save(seng2.torus, self_path)
        # Seed a policy with rules that prefer invent+nurture without human intervals.
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
        # Need a body present for nurture to matter.
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
        gate(
            "C6s",
            "Self-directed invent+nurture without human every-N flags",
            self_invented and self_nurtured,
            (
                f"invented={self_invented} nurtured={self_nurtured} "
                f"cycles={self_live.get('cycle_count')} "
                f"strategy={sc2.strategy.reason}"
            ),
        )

        # Form that matters (bar §4 scaffolding): body-specific specialty capability
        form_path = root / "form-mind.json"
        feng = Engine(seed_minimal_hot_cold())
        store.save(feng.torus, form_path)
        frec = bodies.embody(
            feng, name="specialty-body", domain="optical", mind_store=form_path
        )
        form_ok = False
        form_ev = ""
        try:
            mod, specialty_fn = bodies.load_form_specialty(frec)
            caps = list(getattr(mod, "CAPABILITIES", []) or [])
            result = specialty_fn()
            form_ok = (
                bool(caps)
                and caps[0] not in {"think", "answer", "load_engine"}
                and callable(specialty_fn)
                and result.get("capability") == caps[0]
                and result.get("cause_pole")
                and result.get("effect_pole")
                and frec.specialty == caps[0]
            )
            form_ev = (
                f"specialty={caps[0]} cause={result.get('cause_pole')} "
                f"effect={result.get('effect_pole')} gradient={result.get('gradient')}"
            )
        except Exception as exc:  # noqa: BLE001
            form_ev = str(exc)
        gate(
            "C4f",
            "Forms expose non-prespecified specialty capability",
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
            "Concept/role invent, rule-revising policy, and specialty forms are "
            "stronger scaffolds — still bounded vocabularies/templates. Missing: "
            "unconstrained concept formation, metacognition that invents new "
            "condition/action kinds, forms whose behavior is not generated from "
            "pole-templates (sentience-evidence-bar.md)."
        ),
    }
    gates.append(sentience)

    return {
        "complete": False,  # far-vision goal requires sentience gate
        "engineering_gates_ok": all_required_ok,
        "gates": gates,
        "note": "Far-vision goal stays incomplete until SENTIENCE is evidenced, not asserted.",
    }
