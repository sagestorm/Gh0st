"""Self-invention — the mind proposes domains it was not handed as fixed seeds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .engine import Engine, normalize
from . import bodies
from .seed import seed_custom


# Domains the mind may invent when ready (not the starter three).
INVENTABLE: tuple[tuple[str, str, str], ...] = (
    ("open", "closed", "open-closed"),
    ("begin", "end", "begin-end"),
    ("inner", "outer", "inner-outer"),
    ("chaos", "order", "chaos-order"),
    ("self", "other", "self-other"),
    ("signal", "noise", "signal-noise"),
    ("question", "answer", "question-answer"),
)


@dataclass(frozen=True)
class Invention:
    cause: str
    effect: str
    instance: str
    body_name: str


def already_used_poles(eng: Engine, registry_bodies: Iterable[dict]) -> set[str]:
    used = {normalize(n) for n in eng.torus.nodes}
    for body in registry_bodies:
        used.add(normalize(body.get("domain", "")))
        used.add(normalize(body.get("name", "")))
        # poles encoded in instance like open-closed
        inst = body.get("parent_instance") or ""
        for part in inst.replace("_", "-").split("-"):
            if part:
                used.add(normalize(part))
        store_path = body.get("store_path")
        if store_path:
            try:
                from . import store

                torus = store.load(store_path)
                used.update(normalize(k) for k in torus.nodes)
                used.add(normalize(torus.instance))
            except Exception:  # noqa: BLE001
                pass
    return used


def next_invention(eng: Engine, mind_store) -> Optional[Invention]:
    from . import bodies as bodies_mod

    registry = bodies_mod.load_registry(mind_store)
    body_dicts = [b.to_dict() for b in registry.bodies]
    used = already_used_poles(eng, body_dicts)
    used_names = {normalize(b.name) for b in registry.bodies}

    for cause, effect, instance in INVENTABLE:
        if normalize(cause) in used or normalize(effect) in used:
            continue
        body_name = f"inv-{instance}"
        if normalize(body_name) in used_names:
            continue
        return Invention(
            cause=cause, effect=effect, instance=instance, body_name=body_name
        )
    return None


def invent_and_embody(eng: Engine, mind_store, *, cycle: int | None = None):
    """Invent a new domain body the starter seeds did not provide."""
    proposal = next_invention(eng, mind_store)
    if proposal is None:
        return None

    from .engine import Engine as Eng
    from . import store
    from .center import LivingCenter
    from pathlib import Path

    mind_path = store.store_path(mind_store)
    body_path = mind_path.with_name(f"{mind_path.stem}.body.{proposal.body_name}.json")
    if body_path.exists():
        return None

    torus = seed_custom(proposal.cause, proposal.effect, instance=proposal.instance)
    store.save(torus, body_path)
    store.clear_activity(body_path)

    body_eng = Eng(store.load(body_path))
    center = LivingCenter(body_eng)
    center.mind_store = body_path
    reports = center.think(3)
    store.save(body_eng.torus, body_path)
    store.append_activity([r.to_dict() for r in reports], body_path)

    record = bodies.BodyRecord(
        name=proposal.body_name,
        store_path=str(body_path),
        domain=proposal.instance,
        parent_instance=eng.torus.instance,
        created_from_cycle=cycle,
    )
    form_path = bodies.write_form_module(record, mind_path)
    record.form_path = str(form_path)
    registry = bodies.load_registry(mind_path)
    registry.bodies.append(record)
    bodies.save_registry(registry, mind_path)
    return {
        "invention": {
            "cause": proposal.cause,
            "effect": proposal.effect,
            "instance": proposal.instance,
        },
        "body": record.to_dict(),
    }
