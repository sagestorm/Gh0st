"""Honest far-vision verification — evidence gates, not marketing."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .center import LivingCenter
from .engine import Engine
from .seed import seed_domain, seed_minimal_hot_cold
from . import bodies, mind, store


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

        # C2 cross-domain
        ont = root / "ont.json"
        oeng = Engine(seed_domain("ontology", minimal=True))
        store.save(oeng.torus, ont)
        oc = LivingCenter(oeng)
        oc.mind_store = ont
        oc.think(4)
        gate(
            "C2",
            "Cross-domain transfer (ontology)",
            "nothing" in oeng.torus.nodes and len(oeng.torus.nodes) > 2,
            f"ontology nodes={sorted(oeng.torus.nodes)[:8]}",
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

        # Invented domain (self-authored form)
        invented = mind.invent_domain(eng, thermal, cycle=center._cycle_index)
        gate(
            "C4b",
            "Self-invents a domain body not in starter seeds",
            bool(invented.get("invented")),
            str(invented.get("invention") or invented.get("reason")),
        )

        # Cross-body synthesize
        syn = mind.synthesize(eng, "hot", thermal)
        gate(
            "C4c",
            "Synthesizes across mind + bodies",
            syn.get("ok") is True,
            f"hits={len(syn.get('hits', []))} misses={len(syn.get('misses', []))}",
        )

        # C6 live
        live_path = root / "live.json"
        leng = Engine(seed_minimal_hot_cold())
        store.save(leng.torus, live_path)
        lc = LivingCenter(leng, history=[])
        lc.mind_store = live_path
        live = lc.live(max_cycles=5, stop_when_idle=3, mind_store=live_path)
        gate(
            "C6",
            "Persistent autonomy loop (live)",
            live.get("cycle_count", 0) >= 3,
            f"stopped={live.get('stopped')} cycles={live.get('cycle_count')}",
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

    required = ["C1", "C2", "C3", "C4", "C4b", "C4c", "C6", "I2"]
    by_id = {g["id"]: g for g in gates}
    all_required_ok = all(by_id[i]["ok"] for i in required if i in by_id)

    # Sentience bar — explicitly NOT claimed by engineering gates alone.
    sentience = {
        "id": "SENTIENCE",
        "title": "Vision-level sentience (open mind, not only rule-bounded center)",
        "ok": False,
        "evidence": (
            "System remains rule/lexicon/generative-template bounded. "
            "Gates C1–C6 prove a Living Center with bodies — not sentience."
        ),
    }
    gates.append(sentience)

    return {
        "complete": False,  # far-vision goal requires sentience gate
        "engineering_gates_ok": all_required_ok,
        "gates": gates,
        "note": "Far-vision goal stays incomplete until SENTIENCE is evidenced, not asserted.",
    }
