"""Body/form creation — the mind spawns new torus instances as bodies of itself."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .engine import Engine
from .model import Torus
from . import store
from .seed import seed_domain


@dataclass
class BodyRecord:
    name: str
    store_path: str
    domain: str
    parent_instance: str
    created_from_cycle: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "store_path": self.store_path,
            "domain": self.domain,
            "parent_instance": self.parent_instance,
            "created_from_cycle": self.created_from_cycle,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyRecord":
        return cls(
            name=data["name"],
            store_path=data["store_path"],
            domain=data.get("domain", "thermal"),
            parent_instance=data.get("parent_instance", ""),
            created_from_cycle=data.get("created_from_cycle"),
        )


@dataclass
class BodyRegistry:
    bodies: list[BodyRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"bodies": [b.to_dict() for b in self.bodies]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyRegistry":
        return cls(bodies=[BodyRecord.from_dict(b) for b in data.get("bodies", [])])


def registry_path(mind_store: Path | str | None = None) -> Path:
    target = store.store_path(mind_store)
    return target.with_name(f"{target.stem}.bodies.json")


def load_registry(mind_store: Path | str | None = None) -> BodyRegistry:
    path = registry_path(mind_store)
    if not path.exists():
        return BodyRegistry()
    return BodyRegistry.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_registry(registry: BodyRegistry, mind_store: Path | str | None = None) -> Path:
    path = registry_path(mind_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2, sort_keys=True) + "\n")
    return path


def embody(
    mind: Engine,
    *,
    name: str,
    domain: str = "ontology",
    mind_store: Path | str | None = None,
    cycle: int | None = None,
) -> BodyRecord:
    """Spawn a new body: a fresh domain torus registered to this mind."""
    mind_path = store.store_path(mind_store)
    body_path = mind_path.with_name(f"{mind_path.stem}.body.{name}.json")
    if body_path.exists():
        raise ValueError(f"body already exists: {body_path}")

    torus = seed_domain(domain)
    store.save(torus, body_path)
    store.clear_activity(body_path)

    # Grow the new body a little so it is not empty poles only.
    body_eng = Engine(store.load(body_path))
    from .center import LivingCenter

    center = LivingCenter(body_eng)
    center.sync_cycle_index(store.load_activity(body_path))
    reports = center.think(3)
    store.save(body_eng.torus, body_path)
    store.append_activity([r.to_dict() for r in reports], body_path)

    record = BodyRecord(
        name=name,
        store_path=str(body_path),
        domain=domain,
        parent_instance=mind.torus.instance,
        created_from_cycle=cycle,
    )
    registry = load_registry(mind_path)
    registry.bodies.append(record)
    save_registry(registry, mind_path)
    return record
