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

from .center import (
    LivingCenter,
    StructuralScore,
    MAX_DOMAIN_COMPLETE_FOLLOW_ONS,
    MAX_DOMAIN_MISS_FOLLOW_ONS,
    MAX_FOLLOW_ON_INVENTS,
    MAX_FORM_PRODUCTIVE_FOLLOW_ONS,
)
from .engine import Engine, normalize
from .seed import seed_same_center
from . import invent as invent_mod
from . import search_substrate as search_mod
from . import store
from . import substrate as substrate_mod

# None → derive live cascade probes per arm via invent.product_probes_for.
DEFAULT_PROBES: tuple[str, ...] | None = None
DEFAULT_DOMAINS: tuple[str, ...] = ("thermal", "ontology", "optical")
DEFAULT_THINK_STEPS = 6
# MAX_FOLLOW_ON_INVENTS imported from center (#13/#14 shared hard bound).


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


def _record_invent_row(
    row: dict[str, Any] | None,
    *,
    invent_instances: list[str],
    invent_specialties: list[str] | None = None,
    invent_emit_keys: list[str] | None = None,
    invent_emit_cache: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, str | None, str | None]:
    """Extract applied invent metadata from invent_domain / invent_and_embody rows."""
    if not isinstance(row, dict) or row.get("invented") is False:
        return False, None, None
    inv = row.get("invention") if isinstance(row.get("invention"), dict) else None
    if inv is None:
        return False, None, None
    instance = inv.get("instance")
    if instance:
        invent_instances.append(str(instance))
    body = row.get("body") if isinstance(row.get("body"), dict) else None
    if invent_specialties is not None:
        for name in invent_mod.invent_specialty_names_from_body(body):
            invent_specialties.append(name)
    if invent_emit_keys is not None:
        emits = invent_mod.invent_emit_fields_from_body(
            body, cache=invent_emit_cache
        )
        for ek in emits:
            invent_emit_keys.append(ek)
    if instance and inv.get("source") == "search":
        provenance = "search-substrate:invent"
    elif instance:
        provenance = f"invent:{inv.get('source')}"
    else:
        provenance = None
    return True, (str(instance) if instance else None), provenance


def _run_arm(
    path: Path,
    *,
    use_search: bool,
    domains: tuple[str, ...],
    think_steps: int,
    probes: tuple[str, ...] | None,
) -> dict[str, Any]:
    eng = Engine(seed_same_center(domains, minimal=True))
    store.save(eng.torus, path)
    center = LivingCenter(eng)
    center.mind_store = path
    invent_applied = False
    invent_instance = None
    invent_provenance = None
    invent_instances: list[str] = []
    invent_specialties: list[str] = []
    invent_emit_keys: list[str] = []
    invent_emit_cache: dict[str, dict[str, Any]] = {}
    invent_count = 0
    invent_on_think = False
    follow_on_invent = False
    if use_search:
        # #11: think under SearchSubstrate so primary invent-on-think fires.
        prev = os.environ.get(substrate_mod.ENV_FLAG)
        os.environ[substrate_mod.ENV_FLAG] = "search"
        try:
            substrate_mod.reset_logs_for_tests()
            center.think(think_steps)
            # Shared probe set from Null (or caller); else freeze post-think.
            live_probes = (
                probes if probes is not None else invent_mod.product_probes_for(eng)
            )
            # primary_inventions non-empty ⇒ invent-on-think path exercised (#2/#11).
            # #14/#18/#19: think/primary path may already drain durable + form invents.
            invent_on_think = bool(center.primary_inventions)
            for row in center.primary_inventions:
                applied, inst, prov = _record_invent_row(
                    row if isinstance(row, dict) else None,
                    invent_instances=invent_instances,
                    invent_specialties=invent_specialties,
                    invent_emit_keys=invent_emit_keys,
                    invent_emit_cache=invent_emit_cache,
                )
                if not applied:
                    continue
                invent_applied = True
                invent_count += 1
                if inst:
                    invent_instance = inst
                if prov:
                    invent_provenance = prov
            # #14: ≥2 applied primary invents ⇒ iterative invent-on-think drained exceeds.
            if invent_count >= 2:
                follow_on_invent = True
            # #13/#18/#19/#23 safety net: adjunct invent while durable, distinct
            # form, or domain-miss budget remains (usually empty after primary drain).
            from . import mind as mind_mod

            # Non-rehang invents may be form, domain-miss, or domain-complete;
            # count form conservatively as already-spent when any non-rehang landed.
            form_follow = (
                MAX_FORM_PRODUCTIVE_FOLLOW_ONS
                if invent_mod.form_productive_invent_landed(path)
                else 0
            )
            body_syn_domains = invent_mod.invent_body_synthesize_domains(
                invent_mod.invent_body_synthesize_product_poles(path, eng)
            )
            mind_domains = invent_mod.form_product_domains(
                invent_mod.answerable_form_product_poles(eng)
            )
            under = invent_mod.under_covered_body_synthesize_domains(eng, path)
            # Domain-miss spent when cross-domain earned (body ≥2); completeness
            # continues while under-covered same-center domains remain (#24).
            domain_miss_follow = (
                MAX_DOMAIN_MISS_FOLLOW_ONS
                if (
                    form_follow >= MAX_FORM_PRODUCTIVE_FOLLOW_ONS
                    and len(mind_domains) >= 2
                    and len(body_syn_domains) >= 2
                )
                else 0
            )
            domain_complete_follow = (
                MAX_DOMAIN_COMPLETE_FOLLOW_ONS
                if (
                    domain_miss_follow >= MAX_DOMAIN_MISS_FOLLOW_ONS
                    and not under
                )
                else 0
            )
            for _ in range(MAX_FOLLOW_ON_INVENTS):
                if invent_count >= MAX_FOLLOW_ON_INVENTS:
                    break
                has_durable = invent_mod.search_has_product_exceed_candidate(eng)
                invent_kind = "durable"
                if has_durable:
                    pass
                elif (
                    invent_mod.search_has_form_productive_invent_candidate(
                        eng, mind_store=path
                    )
                    and form_follow < MAX_FORM_PRODUCTIVE_FOLLOW_ONS
                ):
                    invent_kind = "form"
                elif (
                    invent_mod.search_has_domain_miss_invent_candidate(
                        eng, mind_store=path
                    )
                    and domain_miss_follow < MAX_DOMAIN_MISS_FOLLOW_ONS
                ):
                    invent_kind = "domain_miss"
                elif (
                    invent_mod.search_has_domain_miss_invent_candidate(
                        eng, mind_store=path
                    )
                    and domain_miss_follow >= MAX_DOMAIN_MISS_FOLLOW_ONS
                    and domain_complete_follow < MAX_DOMAIN_COMPLETE_FOLLOW_ONS
                ):
                    invent_kind = "domain_complete"
                else:
                    break
                follow = mind_mod.invent_domain(
                    eng, path, cycle=max(1, invent_count) + 1
                )
                applied, inst, prov = _record_invent_row(
                    follow if isinstance(follow, dict) else None,
                    invent_instances=invent_instances,
                    invent_specialties=invent_specialties,
                    invent_emit_keys=invent_emit_keys,
                    invent_emit_cache=invent_emit_cache,
                )
                if not applied:
                    break
                invent_applied = True
                follow_on_invent = True
                invent_count += 1
                if inst:
                    invent_instance = inst
                if prov:
                    invent_provenance = prov
                if invent_kind == "form":
                    form_follow += 1
                elif invent_kind == "domain_miss":
                    domain_miss_follow += 1
                elif invent_kind == "domain_complete":
                    domain_complete_follow += 1
        finally:
            if prev is None:
                os.environ.pop(substrate_mod.ENV_FLAG, None)
            else:
                os.environ[substrate_mod.ENV_FLAG] = prev
            substrate_mod.reset_logs_for_tests()
    else:
        # #17: force Null substrate for this arm even when caller ambient is search
        # (verify nests scoreboard under BEYOND_BINARY_SUBSTRATE=search).
        prev = os.environ.get(substrate_mod.ENV_FLAG)
        os.environ.pop(substrate_mod.ENV_FLAG, None)
        try:
            substrate_mod.reset_logs_for_tests()
            # Null: fail-closed think (no invent-on-think / primary invent drain).
            center.think(think_steps)
            # Honesty: Null arm must not invent even if ambient was search.
            invent_on_think = bool(center.primary_inventions)
            for row in center.primary_inventions:
                applied, inst, prov = _record_invent_row(
                    row if isinstance(row, dict) else None,
                    invent_instances=invent_instances,
                    invent_specialties=invent_specialties,
                    invent_emit_keys=invent_emit_keys,
                    invent_emit_cache=invent_emit_cache,
                )
                if not applied:
                    continue
                invent_applied = True
                invent_count += 1
                if inst:
                    invent_instance = inst
                if prov:
                    invent_provenance = prov
            # #8: freeze dynamic probes after think so Null/search share a set.
            live_probes = (
                probes if probes is not None else invent_mod.product_probes_for(eng)
            )
        finally:
            if prev is None:
                os.environ.pop(substrate_mod.ENV_FLAG, None)
            else:
                os.environ[substrate_mod.ENV_FLAG] = prev
            substrate_mod.reset_logs_for_tests()
    snap = _snapshot(eng, live_probes)
    snap["invent_applied"] = invent_applied
    snap["invent_instance"] = invent_instance
    snap["invent_provenance"] = invent_provenance
    snap["invent_count"] = invent_count
    snap["invent_instances"] = list(invent_instances)
    snap["invent_specialties"] = list(invent_specialties)
    snap["invent_specialty_count"] = len(invent_specialties)
    # #19: unique invent_* emit keys (behavioral form evidence).
    snap["invent_emit_keys"] = sorted(set(invent_emit_keys))
    snap["invent_emit_count"] = len(set(invent_emit_keys))
    # #20: mind form-product poles (readable answerable cascade/motif on this arm).
    form_poles = list(invent_mod.answerable_form_product_poles(eng))
    snap["invent_form_product_poles"] = form_poles
    snap["invent_form_product_count"] = len(form_poles)
    # #22: invent-body synthesize product poles (mind+bodies depth; not mind-only).
    body_syn_poles = list(
        invent_mod.invent_body_synthesize_product_poles(path, eng)
    )
    snap["invent_body_synthesize_poles"] = body_syn_poles
    snap["invent_body_synthesize_count"] = len(body_syn_poles)
    # #25: CapProgram dual_answer topics on invent-body product poles.
    cap_poles = list(
        invent_mod.invent_body_capprogram_product_poles(path, eng)
    )
    snap["invent_body_capprogram_product_poles"] = cap_poles
    snap["invent_body_capprogram_product_count"] = len(cap_poles)
    snap["invent_on_think"] = invent_on_think
    snap["follow_on_invent"] = follow_on_invent
    snap["substrate"] = "search" if use_search else "null"
    snap["probe_topics"] = list(live_probes)
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


def evaluate_form_exceed(
    null_arm: dict[str, Any],
    search_arm: dict[str, Any],
) -> tuple[bool, int, int]:
    """#19/#20: invent→form exceed — mind form product + invent_* emit adjuncts.

    Specialty **name** counts remain adjuncts (returned as search/null form_n).
    Form exceed requires:
      1) ≥1 invent_* emit key on search invent bodies and zero on Null, and
      2) ≥1 invent-introduced readable answerable form-product pole on search
         mind that Null lacks (cascade/motif; not digest/``ir*`` / emit-only).
    CapProgram emit presence alone is insufficient (#20 anti-orphan greenwash).
    """

    def _specialty_count(arm: dict[str, Any]) -> int:
        if "invent_specialty_count" in arm:
            return int(arm.get("invent_specialty_count") or 0)
        specs = arm.get("invent_specialties") or []
        return len(specs) if isinstance(specs, list) else 0

    def _emit_count(arm: dict[str, Any]) -> int:
        if "invent_emit_count" in arm:
            return int(arm.get("invent_emit_count") or 0)
        keys = arm.get("invent_emit_keys") or []
        return len(set(keys)) if isinstance(keys, list) else 0

    def _form_poles(arm: dict[str, Any]) -> list[str]:
        poles = arm.get("invent_form_product_poles")
        if isinstance(poles, list):
            return [str(p) for p in poles]
        return []

    s_count = _specialty_count(search_arm)
    n_count = _specialty_count(null_arm)
    s_emits = _emit_count(search_arm)
    n_emits = _emit_count(null_arm)
    introduced = invent_mod.invent_introduced_form_product_poles(
        _form_poles(search_arm), _form_poles(null_arm)
    )
    form_ok = s_emits >= 1 and n_emits == 0 and len(introduced) >= 1
    return form_ok, s_count, n_count


def evaluate_product_exceed(
    null_arm: dict[str, Any],
    search_arm: dict[str, Any],
    *,
    probes: tuple[str, ...],
) -> tuple[bool, list[str]]:
    """#9/#21/#22/#23: detect strict product exceeds of search vs Null.

    Shared ``probes`` stay Null-frozen for cascade path/coverage fairness.
    #21 adds invent-introduced readable answerable form-product poles search has
    / Null lacks as ``invent_form_product_coverage`` — distinct from form_exceed
    (emit + poles) and from cascade path-floor keys.
    #22 adds invent-body synthesize coverage on invent-touched readable product
    poles Null lacks (mind-only / CapProgram emit / digest ``ir*`` insufficient).
    #23 adds cross-domain invent-body synthesize when mind answers ≥2 seeded
    domains and invent bodies synthesize ≥2 domains Null lacks (thermal-only
    body coverage insufficient for that class).
    #24 adds complete same-center invent-body domain synthesize vs Null.
    #25 adds CapProgram dual_answer topics on invent-touched / body-synthesize
    readable product poles Null lacks (torus synthesize / invent_* emit /
    root-only ``dual_answer`` insufficient for that class).
    """
    exceeds: list[str] = []
    n_score = _score_from_dict(null_arm["score"])
    s_score = _score_from_dict(search_arm["score"])
    if s_score.better_than(n_score):
        exceeds.append("structural_score")
    if int(search_arm.get("probe_path_len_total") or 0) < int(
        null_arm.get("probe_path_len_total") or 0
    ):
        exceeds.append("probe_path_len_total")
    n_probes = null_arm.get("probes") or {}
    s_probes = search_arm.get("probes") or {}
    for topic in probes:
        n_len = (n_probes.get(topic) or {}).get("path_len")
        s_len = (s_probes.get(topic) or {}).get("path_len")
        if n_len is not None and s_len is not None and int(s_len) < int(n_len):
            exceeds.append(f"probe_path_shorter:{topic}")
        n_ans = bool((n_probes.get(topic) or {}).get("answerable"))
        s_ans = bool((s_probes.get(topic) or {}).get("answerable"))
        if s_ans and not n_ans:
            exceeds.append(f"usable_probe_coverage:{topic}")
    # Broader usable coverage: search answers more of the shared probe set.
    n_ans_count = sum(
        1 for t in probes if (n_probes.get(t) or {}).get("answerable")
    )
    s_ans_count = sum(
        1 for t in probes if (s_probes.get(t) or {}).get("answerable")
    )
    if s_ans_count > n_ans_count:
        exceeds.append("usable_probe_coverage")
    # #21: form-derived product class — invent-introduced mind poles Null lacks.
    # CapProgram emit / form_exceed alone is insufficient (poles required).
    introduced = invent_mod.invent_introduced_form_product_poles(
        search_arm.get("invent_form_product_poles") or [],
        null_arm.get("invent_form_product_poles") or [],
    )
    if introduced:
        exceeds.append("invent_form_product_coverage")
        for pole in introduced:
            exceeds.append(f"invent_form_product_coverage:{pole}")
    # #22: mind+bodies synthesize product — invent-body hits Null lacks.
    # Mind-only / emit-only / digest-ir body answers do not earn this class.
    body_syn = invent_mod.invent_introduced_form_product_poles(
        search_arm.get("invent_body_synthesize_poles") or [],
        null_arm.get("invent_body_synthesize_poles") or [],
    )
    if body_syn:
        exceeds.append("invent_body_synthesize_coverage")
        for pole in body_syn:
            exceeds.append(f"invent_body_synthesize_coverage:{pole}")
    # #23: cross-domain invent-body synthesize — thermal-only insufficient when
    # mind answers multi-domain form-product poles. Mind-only / digest insufficient.
    mind_domains = invent_mod.form_product_domains(
        search_arm.get("invent_form_product_poles") or []
    )
    body_domains = invent_mod.invent_body_synthesize_domains(body_syn)
    null_body_domains = invent_mod.invent_body_synthesize_domains(
        null_arm.get("invent_body_synthesize_poles") or []
    )
    cross_domains = frozenset(d for d in body_domains if d not in null_body_domains)
    if len(mind_domains) >= 2 and len(cross_domains) >= 2:
        exceeds.append("invent_body_synthesize_cross_domain")
        for domain in sorted(cross_domains):
            exceeds.append(f"invent_body_synthesize_cross_domain:{domain}")
    # #24: complete same-center invent-body domain coverage vs Null — every
    # mind-answered seeded domain must be invent-body synthesized. Fail closed
    # while any remains body-empty; mind-only / cross-domain-2-of-3 insufficient.
    search_complete = invent_mod.same_center_body_synthesize_complete(
        mind_domains, body_domains
    )
    null_complete = invent_mod.same_center_body_synthesize_complete(
        mind_domains, null_body_domains
    )
    if search_complete and not null_complete:
        exceeds.append("invent_body_synthesize_domain_complete")
        for domain in sorted(mind_domains):
            exceeds.append(f"invent_body_synthesize_domain_complete:{domain}")
    # #25: CapProgram product specialty — dual_answer on invent-body product poles.
    # Torus synthesize / invent_* emit / root-only dual_answer insufficient.
    cap_poles = invent_mod.invent_introduced_form_product_poles(
        search_arm.get("invent_body_capprogram_product_poles") or [],
        null_arm.get("invent_body_capprogram_product_poles") or [],
    )
    if cap_poles:
        exceeds.append("invent_body_capprogram_product_coverage")
        for pole in cap_poles:
            exceeds.append(f"invent_body_capprogram_product_coverage:{pole}")
    return bool(exceeds), exceeds


def run_scoreboard(
    *,
    domains: tuple[str, ...] = DEFAULT_DOMAINS,
    think_steps: int = DEFAULT_THINK_STEPS,
    probes: tuple[str, ...] | None = DEFAULT_PROBES,
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
        # Share Null's live cascade probe set with search for fair path-economy.
        shared_probes = tuple(null_arm.get("probe_topics") or ())
        if probes is not None:
            shared_probes = probes
        search_arm = _run_arm(
            root / "search.json",
            use_search=True,
            domains=domains,
            think_steps=think_steps,
            probes=shared_probes,
        )
        ok, regressions = evaluate_meet_or_exceed(
            null_arm, search_arm, probes=shared_probes
        )
        product_exceed, exceeds = evaluate_product_exceed(
            null_arm, search_arm, probes=shared_probes
        )
        form_exceed, search_form_n, null_form_n = evaluate_form_exceed(
            null_arm, search_arm
        )
        # #9/#11: meet-only vs product exceed on cumulative post-invent snapshot.
        meet_only_invent = bool(search_arm.get("invent_applied")) and not product_exceed
        # Drop bulky name lists from default report (kept for debugging via flag).
        null_public = {k: v for k, v in null_arm.items() if k != "node_names"}
        search_public = {k: v for k, v in search_arm.items() if k != "node_names"}
        search_emit_n = int(search_arm.get("invent_emit_count") or 0)
        null_emit_n = int(null_arm.get("invent_emit_count") or 0)
        introduced_poles = invent_mod.invent_introduced_form_product_poles(
            search_arm.get("invent_form_product_poles") or [],
            null_arm.get("invent_form_product_poles") or [],
        )
        form_product_coverage = sum(
            1
            for e in exceeds
            if e == "invent_form_product_coverage"
            or str(e).startswith("invent_form_product_coverage:")
        )
        # Class key + per-pole keys; count poles (exclude the bare class token).
        form_product_coverage_count = max(0, form_product_coverage - (
            1 if "invent_form_product_coverage" in exceeds else 0
        ))
        body_syn_poles = invent_mod.invent_introduced_form_product_poles(
            search_arm.get("invent_body_synthesize_poles") or [],
            null_arm.get("invent_body_synthesize_poles") or [],
        )
        body_syn_coverage = sum(
            1
            for e in exceeds
            if e == "invent_body_synthesize_coverage"
            or str(e).startswith("invent_body_synthesize_coverage:")
        )
        body_syn_coverage_count = max(0, body_syn_coverage - (
            1 if "invent_body_synthesize_coverage" in exceeds else 0
        ))
        body_syn_domains = sorted(
            invent_mod.invent_body_synthesize_domains(body_syn_poles)
        )
        cross_domain_n = sum(
            1
            for e in exceeds
            if e == "invent_body_synthesize_cross_domain"
            or str(e).startswith("invent_body_synthesize_cross_domain:")
        )
        cross_domain_count = max(
            0,
            cross_domain_n
            - (1 if "invent_body_synthesize_cross_domain" in exceeds else 0),
        )
        domain_complete_n = sum(
            1
            for e in exceeds
            if e == "invent_body_synthesize_domain_complete"
            or str(e).startswith("invent_body_synthesize_domain_complete:")
        )
        domain_complete_count = max(
            0,
            domain_complete_n
            - (1 if "invent_body_synthesize_domain_complete" in exceeds else 0),
        )
        cap_product_poles = invent_mod.invent_introduced_form_product_poles(
            search_arm.get("invent_body_capprogram_product_poles") or [],
            null_arm.get("invent_body_capprogram_product_poles") or [],
        )
        cap_product_n = sum(
            1
            for e in exceeds
            if e == "invent_body_capprogram_product_coverage"
            or str(e).startswith("invent_body_capprogram_product_coverage:")
        )
        cap_product_coverage_count = max(
            0,
            cap_product_n
            - (1 if "invent_body_capprogram_product_coverage" in exceeds else 0),
        )
        return {
            "ok": ok,
            "meet_or_exceed": ok,
            "product_exceed": product_exceed,
            "form_exceed": form_exceed,
            "invent_specialty_count": search_form_n,
            "null_invent_specialty_count": null_form_n,
            "invent_emit_count": search_emit_n,
            "null_invent_emit_count": null_emit_n,
            "invent_form_product_count": len(
                search_arm.get("invent_form_product_poles") or []
            ),
            "null_invent_form_product_count": len(
                null_arm.get("invent_form_product_poles") or []
            ),
            "invent_introduced_form_product_count": len(introduced_poles),
            "invent_introduced_form_product_poles": list(introduced_poles),
            "invent_form_product_coverage_count": form_product_coverage_count,
            "invent_body_synthesize_count": len(
                search_arm.get("invent_body_synthesize_poles") or []
            ),
            "null_invent_body_synthesize_count": len(
                null_arm.get("invent_body_synthesize_poles") or []
            ),
            "invent_body_synthesize_coverage_count": body_syn_coverage_count,
            "invent_body_synthesize_poles": list(body_syn_poles),
            "invent_body_synthesize_domains": body_syn_domains,
            "invent_body_synthesize_cross_domain_count": cross_domain_count,
            "invent_body_synthesize_domain_complete_count": domain_complete_count,
            "invent_body_capprogram_product_poles": list(cap_product_poles),
            "invent_body_capprogram_product_coverage_count": cap_product_coverage_count,
            "null_invent_body_capprogram_product_count": len(
                null_arm.get("invent_body_capprogram_product_poles") or []
            ),
            "exceeds": exceeds,
            "meet_only_invent": meet_only_invent,
            "invent_on_think": bool(search_arm.get("invent_on_think")),
            "follow_on_invent": bool(search_arm.get("follow_on_invent")),
            "invent_count": int(search_arm.get("invent_count") or 0),
            "regressions": regressions,
            "probes": list(shared_probes),
            "domains": list(domains),
            "think_steps": think_steps,
            "null": null_public,
            "search": search_public,
            "criterion": (
                "search must meet or exceed Null on dual_coverage, link_symmetry, "
                "unused_path_cost, readable_name_ratio; answer-path digests must "
                "be zero; probe answerability must not regress; typed cross-domain "
                "or undomain poles must not appear on typed probe answer paths; "
                "probe path lengths must not exceed Null; search arm exercises "
                "invent-on-think (primary-path iterative invent while durable "
                "product-exceed or distinct form-productive invent candidates remain, "
                "bounded; cascade path-shorten / structural preferred over "
                "path-neutral motif coverage and invent-motif path-shortens; "
                "post-floor invent earns mind form product "
                "(invent-introduced answerable poles Null lacks) plus invent_* "
                "emit adjuncts — not dual_attach clone floods or orphan CapProgram "
                "emit greenwash; Living Center product_exceed credits invent-form "
                "product coverage vs Null alongside cascade path floor; scoreboard "
                "adjunct safety-net) and reports cumulative product_exceed / mind "
                "form_exceed vs meet_only_invent"
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
