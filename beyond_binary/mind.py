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


def nurture(mind_store, *, steps: int = 1) -> dict[str, Any]:
    """Run think cycles inside every registered body."""
    from .center import LivingCenter

    registry = bodies.load_registry(mind_store)
    reports: list[dict[str, Any]] = []
    for body in registry.bodies:
        eng = Engine(store.load(body.store_path))
        center = LivingCenter(eng, history=store.load_activity(body.store_path))
        center.mind_store = body.store_path
        cycle_reports = center.think(steps)
        store.save(eng.torus, body.store_path)
        store.append_activity([r.to_dict() for r in cycle_reports], body.store_path)
        reports.append(
            {
                "body": body.name,
                "cycles": len(cycle_reports),
                "nodes": len(eng.torus.nodes),
            }
        )
    return {"nurtured": reports, "count": len(reports)}


def invent_domain(mind: Engine, mind_store, *, cycle: int | None = None) -> dict[str, Any]:
    result = invent.invent_and_embody(mind, mind_store, cycle=cycle)
    if result is None:
        return {"invented": False, "reason": "no unused inventable domains"}
    return {"invented": True, **result}
