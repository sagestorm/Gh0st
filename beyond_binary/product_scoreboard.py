"""Honest Null-vs-search product scoreboard.

Compares Living Center product outcomes (structure + answerability + readable
names) under identical seed/budget. Engineering SENTIENCE is unchanged — this
is the meet-or-exceed product gate that prevents greenwash.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from .center import LivingCenter, StructuralScore
from .engine import Engine, normalize
from .seed import seed_same_center
from . import invent as invent_mod
from . import search_substrate as search_mod
from . import store
from . import substrate as substrate_mod

DEFAULT_PROBES: tuple[str, ...] = invent_mod.PRODUCT_PROBES
DEFAULT_DOMAINS: tuple[str, ...] = ("thermal", "ontology", "optical")
DEFAULT_THINK_STEPS = 6


def _path_names(dual: Any) -> list[str]:
    """Flatten cause/effect paths and between-space poles for digest checks."""
    names: list[str] = []
    for p in (
        list(getattr(dual, "cause_paths", None) or [])
        + list(getattr(dual, "effect_paths", None) or [])
        + list(getattr(dual, "between", None) or [])
    ):
        if isinstance(p, (list, tuple)):
            names.extend(str(x) for x in p)
        else:
            names.append(str(p))
    return [normalize(n) for n in names]


def _snapshot(eng: Engine, probes: tuple[str, ...]) -> dict[str, Any]:
    from . import lexicon as lex

    score = LivingCenter(eng).score()
    names = [normalize(n) for n in eng.torus.nodes]
    digest_nodes = [n for n in names if search_mod.looks_like_digest_pole(n)]
    readable_ratio = (
        (len(names) - len(digest_nodes)) / float(len(names)) if names else 1.0
    )
    probe_rows: dict[str, Any] = {}
    answer_path_digests = 0
    cross_domain_path_poles = 0
    undomain_path_poles = 0
    probe_path_len_total = 0
    for topic in probes:
        if not eng.exists(topic):
            probe_rows[topic] = {
                "exists": False,
                "answerable": False,
                "path_digests": 0,
                "cross_domain_poles": 0,
                "undomain_poles": 0,
                "path_len": None,
            }
            continue
        dual = eng.answer(topic)
        flat = _path_names(dual)
        digests = sum(1 for n in flat if search_mod.looks_like_digest_pole(n))
        answer_path_digests += digests
        topic_domain = lex.pole_domain(topic) or search_mod.node_domain(eng, topic)
        cross = 0
        undomain = 0
        if topic_domain:
            for n in flat:
                d = lex.pole_domain(n)
                if d is None:
                    undomain += 1
                elif d != topic_domain:
                    cross += 1
        path_len = 0
        for p in list(dual.cause_paths or []) + list(dual.effect_paths or []):
            path_len += len(p) if isinstance(p, (list, tuple)) else 1
        cross_domain_path_poles += cross
        undomain_path_poles += undomain
        probe_path_len_total += path_len
        probe_rows[topic] = {
            "exists": True,
            "answerable": bool(dual.cause_paths and dual.effect_paths),
            "path_digests": digests,
            "cross_domain_poles": cross,
            "undomain_poles": undomain,
            "path_len": path_len,
        }
    return {
        "score": score.to_dict(),
        "node_count": len(names),
        "digest_node_count": len(digest_nodes),
        "readable_name_ratio": readable_ratio,
        "answer_path_digests": answer_path_digests,
        "cross_domain_path_poles": cross_domain_path_poles,
        "undomain_path_poles": undomain_path_poles,
        "probe_path_len_total": probe_path_len_total,
        "probes": probe_rows,
        "node_names": sorted(names),
    }


def _run_arm(
    path: Path,
    *,
    use_search: bool,
    domains: tuple[str, ...],
    think_steps: int,
    probes: tuple[str, ...],
) -> dict[str, Any]:
    eng = Engine(seed_same_center(domains, minimal=True))
    store.save(eng.torus, path)
    center = LivingCenter(eng)
    center.mind_store = path
    center.think(think_steps)
    invent_applied = False
    invent_instance = None
    invent_provenance = None
    if use_search:
        prev = os.environ.get(substrate_mod.ENV_FLAG)
        os.environ[substrate_mod.ENV_FLAG] = "search"
        try:
            substrate_mod.reset_logs_for_tests()
            result = invent_mod.invent_and_embody(eng, path, cycle=1)
            if result is not None:
                invent_applied = True
                inv = result.get("invention") if isinstance(result, dict) else None
                invent_instance = (inv or {}).get("instance") if isinstance(inv, dict) else None
                if invent_instance and (inv or {}).get("source") == "search":
                    invent_provenance = "search-substrate:invent"
                elif invent_instance:
                    invent_provenance = f"invent:{ (inv or {}).get('source') }"
        finally:
            if prev is None:
                os.environ.pop(substrate_mod.ENV_FLAG, None)
            else:
                os.environ[substrate_mod.ENV_FLAG] = prev
            substrate_mod.reset_logs_for_tests()
    snap = _snapshot(eng, probes)
    snap["invent_applied"] = invent_applied
    snap["invent_instance"] = invent_instance
    snap["invent_provenance"] = invent_provenance
    snap["substrate"] = "search" if use_search else "null"
    return snap


def _score_from_dict(d: dict[str, Any]) -> StructuralScore:
    return StructuralScore(
        dual_coverage=float(d.get("dual_coverage") or 0.0),
        link_symmetry=float(d.get("link_symmetry") or 0.0),
        unused_path_cost=float(d.get("unused_path_cost") or 0.0),
        node_count=int(float(d.get("node_count") or 0)),
    )


def evaluate_meet_or_exceed(
    null_arm: dict[str, Any],
    search_arm: dict[str, Any],
    *,
    probes: tuple[str, ...],
) -> tuple[bool, list[str]]:
    """Return (ok, regressions). Search must meet or exceed Null product metrics."""
    regressions: list[str] = []
    n_score = _score_from_dict(null_arm["score"])
    s_score = _score_from_dict(search_arm["score"])

    if s_score.dual_coverage + 1e-12 < n_score.dual_coverage:
        regressions.append(
            f"dual_coverage {s_score.dual_coverage} < null {n_score.dual_coverage}"
        )
    if s_score.link_symmetry + 1e-12 < n_score.link_symmetry:
        regressions.append(
            f"link_symmetry {s_score.link_symmetry} < null {n_score.link_symmetry}"
        )
    if s_score.unused_path_cost > n_score.unused_path_cost + 1e-9:
        regressions.append(
            f"unused_path_cost {s_score.unused_path_cost} > null {n_score.unused_path_cost}"
        )
    if float(search_arm.get("readable_name_ratio") or 0.0) + 1e-12 < float(
        null_arm.get("readable_name_ratio") or 0.0
    ):
        regressions.append(
            "readable_name_ratio "
            f"{search_arm.get('readable_name_ratio')} < null "
            f"{null_arm.get('readable_name_ratio')}"
        )
    if int(search_arm.get("answer_path_digests") or 0) > 0:
        regressions.append(
            f"answer_path_digests={search_arm.get('answer_path_digests')} (must be 0)"
        )
    if int(search_arm.get("digest_node_count") or 0) > 0:
        regressions.append(
            f"digest_node_count={search_arm.get('digest_node_count')} (must be 0)"
        )
    # #4/#5: typed cross-domain or undomain poles on probe paths are regressions.
    if int(search_arm.get("cross_domain_path_poles") or 0) > 0:
        regressions.append(
            f"cross_domain_path_poles={search_arm.get('cross_domain_path_poles')} (must be 0)"
        )
    if int(search_arm.get("undomain_path_poles") or 0) > 0:
        regressions.append(
            f"undomain_path_poles={search_arm.get('undomain_path_poles')} (must be 0)"
        )
    # #6: probe answer paths must not be longer than Null.
    if int(search_arm.get("probe_path_len_total") or 0) > int(
        null_arm.get("probe_path_len_total") or 0
    ):
        regressions.append(
            "probe_path_len_total "
            f"{search_arm.get('probe_path_len_total')} > null "
            f"{null_arm.get('probe_path_len_total')}"
        )

    n_probes = null_arm.get("probes") or {}
    s_probes = search_arm.get("probes") or {}
    for topic in probes:
        n_row = n_probes.get(topic) or {}
        s_row = s_probes.get(topic) or {}
        if n_row.get("answerable") and not s_row.get("answerable"):
            regressions.append(f"probe {topic}: search lost answerability")
        if int(s_row.get("path_digests") or 0) > 0:
            regressions.append(
                f"probe {topic}: answer path digests={s_row.get('path_digests')}"
            )
        if int(s_row.get("cross_domain_poles") or 0) > 0:
            regressions.append(
                f"probe {topic}: cross_domain_poles={s_row.get('cross_domain_poles')}"
            )
        if int(s_row.get("undomain_poles") or 0) > 0:
            regressions.append(
                f"probe {topic}: undomain_poles={s_row.get('undomain_poles')}"
            )
        n_len = n_row.get("path_len")
        s_len = s_row.get("path_len")
        if n_len is not None and s_len is not None and int(s_len) > int(n_len):
            regressions.append(
                f"probe {topic}: path_len {s_len} > null {n_len}"
            )

    return (not regressions), regressions


def run_scoreboard(
    *,
    domains: tuple[str, ...] = DEFAULT_DOMAINS,
    think_steps: int = DEFAULT_THINK_STEPS,
    probes: tuple[str, ...] = DEFAULT_PROBES,
    root: Path | None = None,
) -> dict[str, Any]:
    """Run isolated Null vs search arms; return comparative product report."""
    # Preserve ambient substrate ledger (verify may nest this harness).
    ambient_logs = substrate_mod.snapshot_logs()
    prev_flag = os.environ.get(substrate_mod.ENV_FLAG)
    cleanup = None
    if root is None:
        cleanup = tempfile.TemporaryDirectory()
        root = Path(cleanup.name)
    try:
        null_arm = _run_arm(
            root / "null.json",
            use_search=False,
            domains=domains,
            think_steps=think_steps,
            probes=probes,
        )
        search_arm = _run_arm(
            root / "search.json",
            use_search=True,
            domains=domains,
            think_steps=think_steps,
            probes=probes,
        )
        ok, regressions = evaluate_meet_or_exceed(
            null_arm, search_arm, probes=probes
        )
        # Drop bulky name lists from default report (kept for debugging via flag).
        null_public = {k: v for k, v in null_arm.items() if k != "node_names"}
        search_public = {k: v for k, v in search_arm.items() if k != "node_names"}
        return {
            "ok": ok,
            "meet_or_exceed": ok,
            "regressions": regressions,
            "probes": list(probes),
            "domains": list(domains),
            "think_steps": think_steps,
            "null": null_public,
            "search": search_public,
            "criterion": (
                "search must meet or exceed Null on dual_coverage, link_symmetry, "
                "unused_path_cost, readable_name_ratio; answer-path digests must "
                "be zero; probe answerability must not regress; typed cross-domain "
                "or undomain poles must not appear on typed probe answer paths; "
                "probe path lengths must not exceed Null"
            ),
            "note": (
                "Product honesty adjunct — does not redefine SENTIENCE; "
                "fail-closed if search regresses vs Null."
            ),
        }
    finally:
        if prev_flag is None:
            os.environ.pop(substrate_mod.ENV_FLAG, None)
        else:
            os.environ[substrate_mod.ENV_FLAG] = prev_flag
        substrate_mod.restore_logs(ambient_logs)
        if cleanup is not None:
            cleanup.cleanup()
