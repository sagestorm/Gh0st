"""Mutable metacognition policy — open reflection beyond fixed hint tables.

Policy weights update from journal outcomes and are persisted beside the mind
store. Strategy selection can cite a learned policy_id.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import store
from .journal import JournalEntry


@dataclass
class MetaPolicy:
    """Learned grow/prune/migrate/invent/nurture weights."""

    policy_id: str = field(default_factory=lambda: f"pol-{uuid.uuid4().hex[:8]}")
    grow_weight: float = 1.0
    prune_weight: float = 0.5
    migrate_weight: float = 0.5
    invent_weight: float = 0.4
    nurture_weight: float = 0.4
    updates: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "grow_weight": self.grow_weight,
            "prune_weight": self.prune_weight,
            "migrate_weight": self.migrate_weight,
            "invent_weight": self.invent_weight,
            "nurture_weight": self.nurture_weight,
            "updates": self.updates,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetaPolicy":
        return cls(
            policy_id=str(data.get("policy_id") or f"pol-{uuid.uuid4().hex[:8]}"),
            grow_weight=float(data.get("grow_weight", 1.0)),
            prune_weight=float(data.get("prune_weight", 0.5)),
            migrate_weight=float(data.get("migrate_weight", 0.5)),
            invent_weight=float(data.get("invent_weight", 0.4)),
            nurture_weight=float(data.get("nurture_weight", 0.4)),
            updates=int(data.get("updates", 0) or 0),
        )


def policy_path(mind_store: Path | str | None = None) -> Path:
    target = store.store_path(mind_store)
    return target.with_name(f"{target.stem}.policy.json")


def load_policy(mind_store: Path | str | None = None) -> MetaPolicy:
    path = policy_path(mind_store)
    if not path.exists():
        return MetaPolicy()
    return MetaPolicy.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_policy(policy: MetaPolicy, mind_store: Path | str | None = None) -> Path:
    path = policy_path(mind_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(policy.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def update_policy_from_journal(
    policy: MetaPolicy,
    entries: list[JournalEntry] | list[dict[str, Any]],
) -> MetaPolicy:
    """Adjust weights from recent journal outcomes (open reflection)."""
    if not entries:
        return policy
    normalized: list[JournalEntry] = []
    for row in entries[-8:]:
        if isinstance(row, JournalEntry):
            normalized.append(row)
        else:
            normalized.append(JournalEntry.from_dict(row))

    changed = False
    for entry in normalized:
        sig = entry.signals or {}
        if entry.reflection == "growth_fruitful" or (
            int(sig.get("grow_count", 0) or 0) > 0
            and int(sig.get("node_delta", 0) or 0) > 0
        ):
            policy.grow_weight += 0.15
            policy.invent_weight += 0.05
            changed = True
        elif entry.reflection == "challenge_pressure" or int(
            sig.get("flags", 0) or 0
        ) > 0:
            policy.prune_weight += 0.2
            policy.grow_weight = max(0.1, policy.grow_weight - 0.1)
            changed = True
        elif entry.reflection == "growth_stalled":
            policy.migrate_weight += 0.2
            policy.grow_weight = max(0.1, policy.grow_weight - 0.05)
            changed = True
        elif entry.reflection == "structure_hungry":
            policy.grow_weight += 0.1
            policy.invent_weight += 0.1
            changed = True
        elif entry.strategy_hint == "invent":
            policy.invent_weight += 0.15
            changed = True

    if changed:
        policy.updates += 1
        # Soft normalize so one weight cannot dominate forever.
        total = (
            policy.grow_weight
            + policy.prune_weight
            + policy.migrate_weight
            + policy.invent_weight
            + policy.nurture_weight
        )
        if total > 8.0:
            scale = 5.0 / total
            policy.grow_weight *= scale
            policy.prune_weight *= scale
            policy.migrate_weight *= scale
            policy.invent_weight *= scale
            policy.nurture_weight *= scale
    return policy


def strategy_from_policy(
    policy: MetaPolicy,
    *,
    max_new_pairs: int = 1,
) -> dict[str, Any]:
    """Derive Strategy-shaped dict from learned weights (not fixed hint names)."""
    weights = {
        "grow": policy.grow_weight,
        "prune": policy.prune_weight,
        "migrate": policy.migrate_weight,
        "invent": policy.invent_weight,
        "nurture": policy.nurture_weight,
    }
    dominant = max(weights, key=weights.get)
    if dominant == "prune":
        return {
            "grow_budget": 0,
            "prefer_prune": True,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:prune",
            "from_journal": True,
            "from_policy": True,
            "policy_id": policy.policy_id,
            "want_invent": False,
            "want_nurture": weights["nurture"] >= weights["grow"],
        }
    if dominant == "migrate":
        return {
            "grow_budget": 0,
            "prefer_prune": False,
            "prefer_migrate": True,
            "reason": f"policy:{policy.policy_id}:migrate",
            "from_journal": True,
            "from_policy": True,
            "policy_id": policy.policy_id,
            "want_invent": weights["invent"] > 0.8,
            "want_nurture": weights["nurture"] > 0.8,
        }
    if dominant == "invent":
        return {
            "grow_budget": max(1, max_new_pairs),
            "prefer_prune": False,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:invent",
            "from_journal": True,
            "from_policy": True,
            "policy_id": policy.policy_id,
            "want_invent": True,
            "want_nurture": weights["nurture"] >= 0.5,
        }
    if dominant == "nurture":
        return {
            "grow_budget": max(1, max_new_pairs),
            "prefer_prune": False,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:nurture",
            "from_journal": True,
            "from_policy": True,
            "policy_id": policy.policy_id,
            "want_invent": weights["invent"] >= 0.5,
            "want_nurture": True,
        }
    return {
        "grow_budget": max(1, max_new_pairs),
        "prefer_prune": False,
        "prefer_migrate": False,
        "reason": f"policy:{policy.policy_id}:grow",
        "from_journal": True,
        "from_policy": True,
        "policy_id": policy.policy_id,
        "want_invent": weights["invent"] >= weights["prune"],
        "want_nurture": weights["nurture"] >= 0.7,
    }
