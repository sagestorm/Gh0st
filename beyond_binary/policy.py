"""Mutable metacognition — weights plus revisable rule sets.

Open reflection requires more than weight updates on a fixed menu: the policy
can **add/disable rules** learned from journal outcomes. Strategy cites
policy_id and active rule ids.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import store
from .journal import JournalEntry


# Finite condition/action vocabulary for learned rules (still bounded — not
# sentience — but rules themselves are mutable, not only weights).
CONDITIONS = (
    "flags_high",
    "growth_fruitful",
    "growth_stalled",
    "structure_hungry",
    "invent_bias",
    "nurture_bias",
)
ACTIONS = (
    "prefer_prune",
    "prefer_grow",
    "prefer_migrate",
    "prefer_invent",
    "prefer_nurture",
    "suppress_grow",
)


@dataclass
class MetaRule:
    rule_id: str
    when: str
    then: str
    strength: float = 1.0
    origin: str = "seed"  # seed | learned
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "when": self.when,
            "then": self.then,
            "strength": self.strength,
            "origin": self.origin,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetaRule":
        return cls(
            rule_id=str(data.get("rule_id") or f"r-{uuid.uuid4().hex[:6]}"),
            when=str(data.get("when", "structure_hungry")),
            then=str(data.get("then", "prefer_grow")),
            strength=float(data.get("strength", 1.0)),
            origin=str(data.get("origin", "seed")),
            enabled=bool(data.get("enabled", True)),
        )


def _seed_rules() -> list[MetaRule]:
    return [
        MetaRule("r-seed-flags", "flags_high", "prefer_prune", 1.0, "seed"),
        MetaRule("r-seed-stall", "growth_stalled", "prefer_migrate", 1.0, "seed"),
        MetaRule("r-seed-hungry", "structure_hungry", "prefer_grow", 0.8, "seed"),
        MetaRule("r-seed-fruit", "growth_fruitful", "prefer_grow", 0.8, "seed"),
    ]


@dataclass
class MetaPolicy:
    """Learned weights + revisable rule list."""

    policy_id: str = field(default_factory=lambda: f"pol-{uuid.uuid4().hex[:8]}")
    grow_weight: float = 1.0
    prune_weight: float = 0.5
    migrate_weight: float = 0.5
    invent_weight: float = 0.4
    nurture_weight: float = 0.4
    updates: int = 0
    rules: list[MetaRule] = field(default_factory=_seed_rules)
    rule_revisions: int = 0  # increments when rules added/disabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "grow_weight": self.grow_weight,
            "prune_weight": self.prune_weight,
            "migrate_weight": self.migrate_weight,
            "invent_weight": self.invent_weight,
            "nurture_weight": self.nurture_weight,
            "updates": self.updates,
            "rule_revisions": self.rule_revisions,
            "rules": [r.to_dict() for r in self.rules],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetaPolicy":
        rules_raw = data.get("rules")
        rules = (
            [MetaRule.from_dict(r) for r in rules_raw]
            if rules_raw
            else _seed_rules()
        )
        return cls(
            policy_id=str(data.get("policy_id") or f"pol-{uuid.uuid4().hex[:8]}"),
            grow_weight=float(data.get("grow_weight", 1.0)),
            prune_weight=float(data.get("prune_weight", 0.5)),
            migrate_weight=float(data.get("migrate_weight", 0.5)),
            invent_weight=float(data.get("invent_weight", 0.4)),
            nurture_weight=float(data.get("nurture_weight", 0.4)),
            updates=int(data.get("updates", 0) or 0),
            rules=rules,
            rule_revisions=int(data.get("rule_revisions", 0) or 0),
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


def _signals_from_entries(
    entries: list[JournalEntry],
) -> dict[str, int]:
    counts = {
        "flags_high": 0,
        "growth_fruitful": 0,
        "growth_stalled": 0,
        "structure_hungry": 0,
        "invent_bias": 0,
        "nurture_bias": 0,
    }
    for entry in entries:
        if entry.reflection == "challenge_pressure" or int(
            entry.signals.get("flags", 0) or 0
        ) >= 1:
            counts["flags_high"] += 1
        if entry.reflection == "growth_fruitful":
            counts["growth_fruitful"] += 1
        if entry.reflection == "growth_stalled":
            counts["growth_stalled"] += 1
        if entry.reflection == "structure_hungry":
            counts["structure_hungry"] += 1
        if entry.strategy_hint == "invent":
            counts["invent_bias"] += 1
        if entry.strategy_hint == "nurture":
            counts["nurture_bias"] += 1
    return counts


def revise_rules_from_outcomes(
    policy: MetaPolicy,
    entries: list[JournalEntry] | list[dict[str, Any]],
) -> MetaPolicy:
    """Add/disable rules from experience — not only weight tweaks."""
    if not entries:
        return policy
    normalized: list[JournalEntry] = []
    for row in entries[-12:]:
        if isinstance(row, JournalEntry):
            normalized.append(row)
        else:
            normalized.append(JournalEntry.from_dict(row))
    counts = _signals_from_entries(normalized)
    existing = {(r.when, r.then) for r in policy.rules if r.enabled}

    def _learn(when: str, then: str, strength: float) -> None:
        nonlocal policy
        if when not in CONDITIONS or then not in ACTIONS:
            return
        if (when, then) in existing:
            # Strengthen existing learned/seed rule.
            for r in policy.rules:
                if r.when == when and r.then == then and r.enabled:
                    r.strength = min(3.0, r.strength + 0.25)
                    policy.rule_revisions += 1
                    return
            return
        rid = f"r-learn-{when[:4]}-{then[-4:]}-{uuid.uuid4().hex[:4]}"
        policy.rules.append(
            MetaRule(rid, when, then, strength=strength, origin="learned")
        )
        existing.add((when, then))
        policy.rule_revisions += 1

    # Fruitful growth while flags also present → learn invent after prune clears.
    if counts["growth_fruitful"] >= 2 and counts["flags_high"] == 0:
        _learn("growth_fruitful", "prefer_invent", 1.2)
    if counts["flags_high"] >= 2:
        _learn("flags_high", "prefer_prune", 1.5)
        # Disable grow-preferring seed rule under sustained challenge.
        for r in policy.rules:
            if (
                r.origin == "seed"
                and r.then == "prefer_grow"
                and r.enabled
                and counts["flags_high"] >= 3
            ):
                r.enabled = False
                policy.rule_revisions += 1
    if counts["growth_stalled"] >= 2:
        _learn("growth_stalled", "prefer_migrate", 1.3)
        _learn("growth_stalled", "prefer_invent", 1.0)
    if counts["structure_hungry"] >= 2:
        _learn("structure_hungry", "prefer_grow", 1.0)
        _learn("structure_hungry", "prefer_nurture", 0.9)

    return policy


def update_policy_from_journal(
    policy: MetaPolicy,
    entries: list[JournalEntry] | list[dict[str, Any]],
) -> MetaPolicy:
    """Adjust weights AND revise rules from recent journal outcomes."""
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

    before_rev = policy.rule_revisions
    policy = revise_rules_from_outcomes(policy, normalized)
    if policy.rule_revisions != before_rev:
        changed = True

    if changed:
        policy.updates += 1
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


def _match_conditions(
    entries: list[JournalEntry],
) -> set[str]:
    counts = _signals_from_entries(entries)
    active = {k for k, v in counts.items() if v >= 1}
    return active


def strategy_from_policy(
    policy: MetaPolicy,
    *,
    max_new_pairs: int = 1,
    journal_entries: list[JournalEntry] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive strategy from active rules (primary) then weights (tie-break)."""
    normalized: list[JournalEntry] = []
    for row in journal_entries or []:
        if isinstance(row, JournalEntry):
            normalized.append(row)
        else:
            normalized.append(JournalEntry.from_dict(row))

    active_conds = _match_conditions(normalized) if normalized else set()
    # If no journal yet, treat as structure_hungry so seed grow rule can fire.
    if not active_conds:
        active_conds = {"structure_hungry"}

    fired: list[MetaRule] = []
    scores = {
        "prefer_prune": 0.0,
        "prefer_grow": 0.0,
        "prefer_migrate": 0.0,
        "prefer_invent": 0.0,
        "prefer_nurture": 0.0,
        "suppress_grow": 0.0,
    }
    for rule in policy.rules:
        if not rule.enabled or rule.when not in active_conds:
            continue
        if rule.then in scores:
            scores[rule.then] += rule.strength
            fired.append(rule)

    # Blend small weight prior so empty rule-fire still works.
    scores["prefer_grow"] += policy.grow_weight * 0.15
    scores["prefer_prune"] += policy.prune_weight * 0.15
    scores["prefer_migrate"] += policy.migrate_weight * 0.15
    scores["prefer_invent"] += policy.invent_weight * 0.15
    scores["prefer_nurture"] += policy.nurture_weight * 0.15

    # Pick dominant actionable preference (ignore suppress as dominant label).
    actionable = {
        k: v
        for k, v in scores.items()
        if k != "suppress_grow"
    }
    dominant = max(actionable, key=actionable.get)
    rule_ids = [r.rule_id for r in fired]
    suppress = scores["suppress_grow"] > scores["prefer_grow"]

    base = {
        "from_journal": True,
        "from_policy": True,
        "policy_id": policy.policy_id,
        "active_rules": rule_ids,
        "rule_revisions": policy.rule_revisions,
    }
    if dominant == "prefer_prune" or suppress:
        return {
            **base,
            "grow_budget": 0,
            "prefer_prune": True,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:rules:prune",
            "want_invent": scores["prefer_invent"] > 1.0,
            "want_nurture": scores["prefer_nurture"] > 1.0,
        }
    if dominant == "prefer_migrate":
        return {
            **base,
            "grow_budget": 0,
            "prefer_prune": False,
            "prefer_migrate": True,
            "reason": f"policy:{policy.policy_id}:rules:migrate",
            "want_invent": scores["prefer_invent"] > 0.8,
            "want_nurture": scores["prefer_nurture"] > 0.8,
        }
    if dominant == "prefer_invent":
        return {
            **base,
            "grow_budget": 0 if suppress else max(1, max_new_pairs),
            "prefer_prune": False,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:rules:invent",
            "want_invent": True,
            "want_nurture": scores["prefer_nurture"] >= 0.5,
        }
    if dominant == "prefer_nurture":
        return {
            **base,
            "grow_budget": 0 if suppress else max(1, max_new_pairs),
            "prefer_prune": False,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:rules:nurture",
            "want_invent": scores["prefer_invent"] >= 0.5,
            "want_nurture": True,
        }
    return {
        **base,
        "grow_budget": 0 if suppress else max(1, max_new_pairs),
        "prefer_prune": False,
        "prefer_migrate": False,
        "reason": f"policy:{policy.policy_id}:rules:grow",
        "want_invent": scores["prefer_invent"] >= scores["prefer_prune"],
        "want_nurture": scores["prefer_nurture"] >= 0.7,
    }
