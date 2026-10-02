"""Self-invention — compose new domains from Living Center structure.

Hardcoded INVENTABLE is only a seed fallback. Primary path:
  harvest known opposite pairs → compose / promote → persist invent registry → embody.
Opposite stays opposite-state: composed poles keep dual reciprocity
(A∘C ↔ B∘D when A↔B and C↔D are known).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .engine import Engine, normalize
from .model import Hemisphere
from . import bodies
from .seed import seed_custom


# Seed catalog only — used when composition finds nothing unused.
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
    source: str = "seed"  # compose | promote | seed

    def to_dict(self) -> dict[str, str]:
        return {
            "cause": self.cause,
            "effect": self.effect,
            "instance": self.instance,
            "body_name": self.body_name,
            "source": self.source,
        }


@dataclass
class InventCandidate:
    cause: str
    effect: str
    instance: str
    source: str
    used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "effect": self.effect,
            "instance": self.instance,
            "source": self.source,
            "used": self.used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InventCandidate":
        return cls(
            cause=data["cause"],
            effect=data["effect"],
            instance=data["instance"],
            source=str(data.get("source", "seed")),
            used=bool(data.get("used", False)),
        )


@dataclass
class InventRegistry:
    candidates: list[InventCandidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"candidates": [c.to_dict() for c in self.candidates]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InventRegistry":
        return cls(
            candidates=[
                InventCandidate.from_dict(row) for row in data.get("candidates", [])
            ]
        )


def invent_registry_path(mind_store: Path | str | None = None) -> Path:
    from . import store

    target = store.store_path(mind_store)
    return target.with_name(f"{target.stem}.invent.json")


def load_invent_registry(mind_store: Path | str | None = None) -> InventRegistry:
    path = invent_registry_path(mind_store)
    if not path.exists():
        return InventRegistry()
    return InventRegistry.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_invent_registry(
    registry: InventRegistry, mind_store: Path | str | None = None
) -> Path:
    path = invent_registry_path(mind_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Dedupe by instance key; prefer unused compose/promote over seed.
    seen: dict[str, InventCandidate] = {}
    priority = {"compose": 3, "promote": 2, "seed": 1}
    for cand in registry.candidates:
        key = normalize(cand.instance)
        prev = seen.get(key)
        if prev is None:
            seen[key] = cand
            continue
        # Keep used flag if either was used; keep higher-priority source.
        used = prev.used or cand.used
        winner = (
            cand
            if priority.get(cand.source, 0) > priority.get(prev.source, 0)
            else prev
        )
        seen[key] = InventCandidate(
            cause=winner.cause,
            effect=winner.effect,
            instance=winner.instance,
            source=winner.source,
            used=used,
        )
    registry.candidates = list(seen.values())
    path.write_text(
        json.dumps(registry.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def already_used_poles(eng: Engine, registry_bodies: Iterable[dict]) -> set[str]:
    used = {normalize(n) for n in eng.torus.nodes}
    for body in registry_bodies:
        used.add(normalize(body.get("domain", "")))
        used.add(normalize(body.get("name", "")))
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


def already_used_instances(eng: Engine, registry_bodies: Iterable[dict]) -> set[str]:
    """Instances/domains/body names already claimed — not every nested node."""
    used = {normalize(eng.torus.instance)} if eng.torus.instance else set()
    for body in registry_bodies:
        if body.get("domain"):
            used.add(normalize(body["domain"]))
        if body.get("name"):
            used.add(normalize(body["name"]))
        store_path = body.get("store_path")
        if store_path:
            try:
                from . import store

                torus = store.load(store_path)
                used.add(normalize(torus.instance))
            except Exception:  # noqa: BLE001
                pass
    return used


def harvest_pairs(eng: Engine, registry_bodies: Iterable[dict]) -> list[tuple[str, str]]:
    """Collect reciprocal cause↔effect pairs from mind + bodies (structure only)."""
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _from_engine(engine: Engine) -> None:
        for node in engine.torus.nodes.values():
            if node.hemisphere is not Hemisphere.CAUSE:
                continue
            if not node.opposite:
                continue
            opp = engine.torus.nodes.get(node.opposite)
            if opp is None or opp.hemisphere is not Hemisphere.EFFECT:
                continue
            key = (normalize(node.name), normalize(opp.name))
            if key in seen:
                continue
            # Skip template generative stacking as domain poles.
            if node.name.lower().startswith("more-") or opp.name.lower().startswith(
                "more-"
            ):
                continue
            if node.name.lower().startswith("not-") or opp.name.lower().startswith(
                "not-"
            ):
                continue
            seen.add(key)
            pairs.append((node.name, opp.name))

    _from_engine(eng)
    for body in registry_bodies:
        store_path = body.get("store_path")
        if not store_path:
            continue
        try:
            from . import store

            _from_engine(Engine(store.load(store_path)))
        except Exception:  # noqa: BLE001
            continue
    return pairs


def _slug_pair(cause: str, effect: str) -> str:
    return f"{normalize(cause)}-{normalize(effect)}"


def compose_candidates(
    known_pairs: list[tuple[str, str]],
    used_poles: set[str],
    used_instances: set[str],
    *,
    limit: int = 12,
) -> list[InventCandidate]:
    """Compose new opposite-state domains from known pairs (A∘C ↔ B∘D)."""
    out: list[InventCandidate] = []
    roots = known_pairs[:8]  # prefer earlier / root-ish harvest order
    for i, (a, b) in enumerate(roots):
        for c, d in roots[i + 1 :]:
            # Product of opposites preserves opposite-state.
            cause = f"{a}-{c}"
            effect = f"{b}-{d}"
            if normalize(cause) == normalize(effect):
                continue
            if normalize(cause) in used_poles or normalize(effect) in used_poles:
                continue
            # Avoid stacking already-composed tokens too deep.
            if cause.count("-") > 2 or effect.count("-") > 2:
                continue
            instance = _slug_pair(cause, effect)
            if normalize(instance) in used_instances:
                continue
            if any(normalize(x.instance) == normalize(instance) for x in out):
                continue
            out.append(
                InventCandidate(
                    cause=cause, effect=effect, instance=instance, source="compose"
                )
            )
            if len(out) >= limit:
                return out
    return out


def promote_candidates(
    known_pairs: list[tuple[str, str]],
    eng: Engine,
    used_instances: set[str],
    *,
    limit: int = 8,
) -> list[InventCandidate]:
    """Promote non-root reciprocal pairs already in the graph into inventable domains."""
    out: list[InventCandidate] = []
    for cause, effect in known_pairs:
        if not eng.exists(cause):
            continue
        node = eng.get(cause)
        if node.parent is None:
            continue  # roots are already domains / poles
        instance = _slug_pair(cause, effect)
        if normalize(instance) in used_instances:
            continue
        if any(normalize(x.instance) == normalize(instance) for x in out):
            continue
        out.append(
            InventCandidate(
                cause=cause, effect=effect, instance=instance, source="promote"
            )
        )
        if len(out) >= limit:
            break
    return out


def seed_candidates(used_poles: set[str], used_instances: set[str]) -> list[InventCandidate]:
    out: list[InventCandidate] = []
    for cause, effect, instance in INVENTABLE:
        if normalize(cause) in used_poles or normalize(effect) in used_poles:
            continue
        if normalize(instance) in used_instances:
            continue
        out.append(
            InventCandidate(
                cause=cause, effect=effect, instance=instance, source="seed"
            )
        )
    return out


def refresh_invent_registry(eng: Engine, mind_store) -> InventRegistry:
    """Harvest structure, compose/promote, merge into dynamic invent registry."""
    body_registry = bodies.load_registry(mind_store)
    body_dicts = [b.to_dict() for b in body_registry.bodies]
    used_poles = already_used_poles(eng, body_dicts)
    used_instances = already_used_instances(eng, body_dicts)
    # Also treat already-registered invent instances as used.
    registry = load_invent_registry(mind_store)
    for cand in registry.candidates:
        if cand.used:
            used_instances.add(normalize(cand.instance))
            used_poles.add(normalize(cand.cause))
            used_poles.add(normalize(cand.effect))
    known = harvest_pairs(eng, body_dicts)

    existing_keys = {normalize(c.instance) for c in registry.candidates}

    for cand in (
        compose_candidates(known, used_poles, used_instances)
        + promote_candidates(known, eng, used_instances)
        + seed_candidates(used_poles, used_instances)
    ):
        key = normalize(cand.instance)
        if key in existing_keys:
            continue
        registry.candidates.append(cand)
        existing_keys.add(key)

    save_invent_registry(registry, mind_store)
    return registry


def next_invention(eng: Engine, mind_store) -> Optional[Invention]:
    registry = refresh_invent_registry(eng, mind_store)
    body_registry = bodies.load_registry(mind_store)
    used_names = {normalize(b.name) for b in body_registry.bodies}
    body_dicts = [b.to_dict() for b in body_registry.bodies]
    used_poles = already_used_poles(eng, body_dicts)
    used_instances = already_used_instances(eng, body_dicts)

    # Prefer compose → promote → seed among unused candidates.
    order = {"compose": 0, "promote": 1, "seed": 2}
    unused = [c for c in registry.candidates if not c.used]
    unused.sort(key=lambda c: order.get(c.source, 9))

    for cand in unused:
        if cand.source != "promote":
            if normalize(cand.cause) in used_poles or normalize(cand.effect) in used_poles:
                continue
        if normalize(cand.instance) in used_instances:
            continue
        body_name = f"inv-{cand.instance}"
        # Keep body names filesystem-safe and short-ish.
        if len(body_name) > 48:
            body_name = f"inv-{normalize(cand.cause)[:16]}-{normalize(cand.effect)[:16]}"
        if normalize(body_name) in used_names:
            continue
        return Invention(
            cause=cand.cause,
            effect=cand.effect,
            instance=cand.instance,
            body_name=body_name,
            source=cand.source,
        )
    return None


def mark_used(instance: str, mind_store) -> None:
    registry = load_invent_registry(mind_store)
    key = normalize(instance)
    for cand in registry.candidates:
        if normalize(cand.instance) == key:
            cand.used = True
    save_invent_registry(registry, mind_store)


def invent_and_embody(eng: Engine, mind_store, *, cycle: int | None = None):
    """Invent a new domain body from composed/promoted/seed structure."""
    proposal = next_invention(eng, mind_store)
    if proposal is None:
        return None

    from .engine import Engine as Eng
    from . import store
    from .center import LivingCenter

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
    mark_used(proposal.instance, mind_path)
    return {
        "invention": {
            "cause": proposal.cause,
            "effect": proposal.effect,
            "instance": proposal.instance,
            "source": proposal.source,
        },
        "body": record.to_dict(),
    }
