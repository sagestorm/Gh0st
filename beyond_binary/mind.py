"""Mind-level operations across the Living Center and its bodies."""

from __future__ import annotations

from typing import Any

from .engine import Engine, RuleError
from . import bodies, invent, store


def synthesize(mind: Engine, topic: str, mind_store) -> dict[str, Any]:
    """Answer a topic across the mind and every registered body (dual paths each)."""
    results: list[dict[str, Any]] = []

    def _one(label: str, eng: Engine) -> None:
        try:
            dual = eng.answer(topic)
            results.append(
                {
                    "source": label,
                    "ok": True,
                    "cause_paths": dual.cause_paths,
                    "effect_paths": dual.effect_paths,
                    "between": dual.between,
                }
            )
        except RuleError as exc:
            results.append({"source": label, "ok": False, "error": str(exc)})

    _one("mind", mind)
    registry = bodies.load_registry(mind_store)
    for body in registry.bodies:
        try:
            eng = Engine(store.load(body.store_path))
        except Exception as exc:  # noqa: BLE001
            results.append({"source": body.name, "ok": False, "error": str(exc)})
            continue
        _one(body.name, eng)

    ok = [r for r in results if r.get("ok")]
    return {
        "topic": topic,
        "hits": ok,
        "misses": [r for r in results if not r.get("ok")],
        "note": "Synthesis spans mind + bodies; no single-hemisphere collapse.",
        "ok": len(ok) > 0,
    }


def nurture(
    mind_store,
    *,
    steps: int = 1,
    max_depth: int = 2,
    allow_invent: bool = False,
    _depth: int = 0,
    _seen: set[str] | None = None,
) -> dict[str, Any]:
    """Run think (and optional invent) inside bodies; recurse into child registries.

    Depth is bounded. Each body may invent further forms registered beside its
    own store; nurture then walks those grandchildren up to max_depth.
    """
    from .center import LivingCenter

    if _depth > max_depth:
        return {
            "nurtured": [],
            "count": 0,
            "depth": _depth,
            "stopped": "max_depth",
        }

    seen = _seen if _seen is not None else set()
    registry = bodies.load_registry(mind_store)
    reports: list[dict[str, Any]] = []

    for body in list(registry.bodies):
        key = str(body.store_path)
        if key in seen:
            continue
        seen.add(key)

        try:
            eng = Engine(store.load(body.store_path))
        except Exception as exc:  # noqa: BLE001
            reports.append({"body": body.name, "error": str(exc), "depth": _depth})
            continue

        center = LivingCenter(eng, history=store.load_activity(body.store_path))
        center.mind_store = body.store_path
        cycle_reports = center.think(steps)
        store.save(eng.torus, body.store_path)
        store.append_activity([r.to_dict() for r in cycle_reports], body.store_path)

        invented: dict[str, Any] | None = None
        if allow_invent and _depth < max_depth:
            invented = invent.invent_and_embody(
                eng,
                body.store_path,
                cycle=center._cycle_index,
                parent_body=body.name,
            )
            if invented is None:
                invented = {
                    "invented": False,
                    "reason": "no unused composed/promoted/seed domains",
                }
            else:
                invented = {"invented": True, **invented}

        child_nurture = nurture(
            body.store_path,
            steps=steps,
            max_depth=max_depth,
            allow_invent=allow_invent,
            _depth=_depth + 1,
            _seen=seen,
        )

        # Dual-hemisphere sanity on the nurtured body.
        dual_ok = False
        try:
            roots = [n for n in eng.torus.nodes.values() if n.parent is None]
            topic = roots[0].name if roots else next(iter(eng.torus.nodes))
            dual = eng.answer(topic)
            dual_ok = bool(dual.cause_paths and dual.effect_paths)
            eng.assert_no_orphans()
        except Exception:  # noqa: BLE001
            dual_ok = False

        reports.append(
            {
                "body": body.name,
                "depth": _depth,
                "cycles": len(cycle_reports),
                "nodes": len(eng.torus.nodes),
                "invented": invented,
                "children": child_nurture,
                "dual_ok": dual_ok,
                "parent_body": body.parent_body,
            }
        )

    return {
        "nurtured": reports,
        "count": len(reports),
        "depth": _depth,
        "max_depth": max_depth,
        "allow_invent": allow_invent,
    }


def invent_domain(
    mind: Engine,
    mind_store,
    *,
    cycle: int | None = None,
    parent_body: str | None = None,
    activity: list[dict[str, Any]] | None = None,
    journal_rows: list[Any] | None = None,
) -> dict[str, Any]:
    result = invent.invent_and_embody(
        mind,
        mind_store,
        cycle=cycle,
        parent_body=parent_body,
        activity=activity,
        journal_rows=journal_rows,
    )
    if result is None:
        return {
            "invented": False,
            "reason": "no unused primitive/composed/promoted/seed domains",
        }
    return {"invented": True, **result}


def count_body_lineage(mind_store, *, max_scan_depth: int = 4) -> dict[str, Any]:
    """Count bodies across nested registries (mind → children → grandchildren)."""
    seen: set[str] = set()
    depths: dict[int, int] = {}

    def _walk(path, depth: int) -> None:
        if depth > max_scan_depth:
            return
        registry = bodies.load_registry(path)
        for body in registry.bodies:
            key = str(body.store_path)
            if key in seen:
                continue
            seen.add(key)
            depths[depth] = depths.get(depth, 0) + 1
            _walk(body.store_path, depth + 1)

    _walk(mind_store, 0)
    max_d = max(depths.keys(), default=-1)
    return {
        "total": len(seen),
        "by_depth": {str(k): v for k, v in sorted(depths.items())},
        "has_grandchild": max_d >= 1,
    }
