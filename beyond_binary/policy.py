"""Experience-grown metacognition — expr kinds over empirical journal signals.

Seed enums bootstrap. Experience discovers signal keys from journal rows and
learns linear expression conditions (weighted sums vs threshold) — not only
compound/threshold over a fixed seed vocabulary. Actions can bias any channel
discovered from outcomes.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import store
from .journal import JournalEntry


# Seed vocabulary only — runtime kinds live on MetaPolicy and can grow.
SEED_CONDITIONS = (
    "flags_high",
    "growth_fruitful",
    "growth_stalled",
    "structure_hungry",
    "invent_bias",
    "nurture_bias",
)
SEED_ACTIONS = (
    "prefer_prune",
    "prefer_grow",
    "prefer_migrate",
    "prefer_invent",
    "prefer_nurture",
    "suppress_grow",
)

# Compat aliases for older imports/tests.
CONDITIONS = SEED_CONDITIONS
ACTIONS = SEED_ACTIONS

# Preference channels strategy knows how to steer.
PREFERENCE_CHANNELS = (
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
    """Weights + revisable rules + extensible condition/action kind registries."""

    policy_id: str = field(default_factory=lambda: f"pol-{uuid.uuid4().hex[:8]}")
    grow_weight: float = 1.0
    prune_weight: float = 0.5
    migrate_weight: float = 0.5
    invent_weight: float = 0.4
    nurture_weight: float = 0.4
    updates: int = 0
    rules: list[MetaRule] = field(default_factory=_seed_rules)
    rule_revisions: int = 0
    # Novel kinds: name → definition (not in SEED_* alone).
    condition_kinds: dict[str, dict[str, Any]] = field(default_factory=dict)
    action_kinds: dict[str, dict[str, Any]] = field(default_factory=dict)
    kind_revisions: int = 0
    # Empirical signal keys observed across journal history.
    observed_signals: list[str] = field(default_factory=list)

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
            "kind_revisions": self.kind_revisions,
            "rules": [r.to_dict() for r in self.rules],
            "condition_kinds": self.condition_kinds,
            "action_kinds": self.action_kinds,
            "observed_signals": list(self.observed_signals),
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
            condition_kinds=dict(data.get("condition_kinds") or {}),
            action_kinds=dict(data.get("action_kinds") or {}),
            kind_revisions=int(data.get("kind_revisions", 0) or 0),
            observed_signals=list(data.get("observed_signals") or []),
        )

    def known_conditions(self) -> set[str]:
        return set(SEED_CONDITIONS) | set(self.condition_kinds)

    def known_actions(self) -> set[str]:
        return set(SEED_ACTIONS) | set(self.action_kinds)


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


def _signal_vector(entries: list[JournalEntry]) -> dict[str, float]:
    """Numeric signals from journal — includes ANY empirical keys in entry.signals."""
    vec: dict[str, float] = {
        "flags": 0.0,
        "grow_count": 0.0,
        "node_delta": 0.0,
        "prune_count": 0.0,
        "fruitful": 0.0,
        "stalled": 0.0,
        "hungry": 0.0,
        "migrate_kept": 0.0,
    }
    for entry in entries:
        sig = entry.signals or {}
        for key, raw in sig.items():
            try:
                vec[str(key)] = float(vec.get(str(key), 0.0)) + float(raw or 0)
            except (TypeError, ValueError):
                continue
        if entry.reflection == "growth_fruitful":
            vec["fruitful"] = float(vec.get("fruitful", 0.0)) + 1.0
        if entry.reflection == "growth_stalled":
            vec["stalled"] = float(vec.get("stalled", 0.0)) + 1.0
        if entry.reflection == "structure_hungry":
            vec["hungry"] = float(vec.get("hungry", 0.0)) + 1.0
        if entry.reflection == "challenge_pressure":
            vec["flags"] = float(vec.get("flags", 0.0)) + 1.0
        if entry.strategy_hint == "invent":
            vec["hint_invent"] = float(vec.get("hint_invent", 0.0)) + 1.0
        if entry.strategy_hint == "nurture":
            vec["hint_nurture"] = float(vec.get("hint_nurture", 0.0)) + 1.0
    return vec


def _signals_from_entries(entries: list[JournalEntry]) -> dict[str, int]:
    counts = {k: 0 for k in SEED_CONDITIONS}
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


def register_condition_kind(
    policy: MetaPolicy,
    *,
    name: str,
    definition: dict[str, Any],
) -> str:
    """Register a new condition kind beyond the seed DSL."""
    if name in SEED_CONDITIONS:
        return name
    if name not in policy.condition_kinds:
        policy.condition_kinds[name] = definition
        policy.kind_revisions += 1
    else:
        prev = policy.condition_kinds[name]
        if prev != definition and definition.get("kind") in {"expr", "program"}:
            policy.condition_kinds[name] = definition
            policy.kind_revisions += 1
    return name


def register_action_kind(
    policy: MetaPolicy,
    *,
    name: str,
    definition: dict[str, Any],
) -> str:
    """Register a new action kind beyond the seed DSL."""
    if name in SEED_ACTIONS:
        return name
    if name not in policy.action_kinds:
        policy.action_kinds[name] = definition
        policy.kind_revisions += 1
    else:
        prev = policy.action_kinds[name]
        if prev != definition and definition.get("kind") == "program":
            policy.action_kinds[name] = definition
            policy.kind_revisions += 1
    return name


def _eval_expr(spec: dict[str, Any], vec: dict[str, float]) -> bool:
    weights = spec.get("weights") or {}
    threshold = float(spec.get("threshold", 0.0))
    total = 0.0
    for key, w in weights.items():
        total += float(w) * float(vec.get(str(key), 0.0))
    op = str(spec.get("op", ">="))
    if op == ">=":
        return total >= threshold
    if op == ">":
        return total > threshold
    if op == "<=":
        return total <= threshold
    if op == "<":
        return total < threshold
    if op == "==":
        return abs(total - threshold) < 1e-9
    return False


def run_meta_program(
    body: list[dict[str, Any]],
    vec: dict[str, float],
    *,
    scores: dict[str, float] | None = None,
    extras: dict[str, Any] | None = None,
    strength: float = 1.0,
) -> dict[str, Any]:
    """Interpret a CapProgram-like microprogram over a journal signal vector.

    Condition programs emit ``pred`` (truthy). Action programs may bias channels
    or set grow budget via ops — executable data, not schema tags alone.
    """
    regs: dict[str, float] = {}
    pred = False
    for step in body:
        op = str(step.get("op", ""))
        if op == "load_signal":
            sig = str(step.get("signal", ""))
            into = str(step.get("into", sig))
            regs[into] = float(vec.get(sig, 0.0))
        elif op == "const":
            into = str(step.get("into", "c"))
            regs[into] = float(step.get("value", 0.0))
        elif op == "mul":
            a = str(step.get("a", ""))
            into = str(step.get("into", a))
            if "scale" in step:
                regs[into] = float(regs.get(a, 0.0)) * float(step.get("scale", 1.0))
            else:
                b = str(step.get("b", ""))
                regs[into] = float(regs.get(a, 0.0)) * float(regs.get(b, 0.0))
        elif op == "add":
            a = str(step.get("a", ""))
            b = str(step.get("b", ""))
            into = str(step.get("into", "sum"))
            regs[into] = float(regs.get(a, 0.0)) + float(regs.get(b, 0.0))
        elif op == "cmp":
            a = str(step.get("a", ""))
            cmp_op = str(step.get("cmp", ">="))
            value = float(step.get("value", 0.0))
            into = str(step.get("into", "ok"))
            actual = float(regs.get(a, 0.0))
            ok = False
            if cmp_op == ">=":
                ok = actual >= value
            elif cmp_op == ">":
                ok = actual > value
            elif cmp_op == "<=":
                ok = actual <= value
            elif cmp_op == "<":
                ok = actual < value
            elif cmp_op == "==":
                ok = abs(actual - value) < 1e-9
            regs[into] = 1.0 if ok else 0.0
        elif op == "emit_pred":
            flag = str(step.get("flag", "ok"))
            pred = float(regs.get(flag, 0.0)) >= 0.5
        elif op == "bias_channel" and scores is not None:
            channel = str(step.get("channel", "prefer_invent"))
            amount = float(step.get("amount", 1.0)) * strength
            scores[channel] = scores.get(channel, 0.0) + amount
        elif op == "set_grow_budget" and extras is not None:
            extras["grow_budget_override"] = int(step.get("value", 1))
    return {"pred": pred, "regs": regs}


def _weights_to_program(
    weights: dict[str, float], threshold: float
) -> list[dict[str, Any]]:
    """Compile weighted features into an executable meta microprogram."""
    body: list[dict[str, Any]] = []
    acc = "score"
    body.append({"op": "const", "into": acc, "value": 0.0})
    for i, (sig, w) in enumerate(sorted(weights.items())):
        tmp = f"t{i}"
        body.append({"op": "load_signal", "signal": sig, "into": tmp})
        body.append({"op": "mul", "a": tmp, "scale": float(w), "into": tmp})
        body.append({"op": "add", "a": acc, "b": tmp, "into": acc})
    body.append(
        {"op": "cmp", "a": acc, "cmp": ">=", "value": float(threshold), "into": "ok"}
    )
    body.append({"op": "emit_pred", "flag": "ok"})
    return body


def _eval_condition(
    name: str,
    policy: MetaPolicy,
    seed_counts: dict[str, int],
    vec: dict[str, float],
) -> bool:
    if name in SEED_CONDITIONS:
        return seed_counts.get(name, 0) >= 1
    spec = policy.condition_kinds.get(name)
    if not spec:
        return False
    kind = spec.get("kind")
    if kind == "program":
        result = run_meta_program(list(spec.get("body") or []), vec)
        return bool(result.get("pred"))
    if kind == "expr":
        return _eval_expr(spec, vec)
    if kind == "all":
        return all(
            _eval_condition(c, policy, seed_counts, vec) for c in spec.get("of", [])
        )
    if kind == "any":
        return any(
            _eval_condition(c, policy, seed_counts, vec) for c in spec.get("of", [])
        )
    if kind == "threshold":
        signal = str(spec.get("signal", ""))
        op = str(spec.get("op", ">="))
        value = float(spec.get("value", 0))
        actual = float(vec.get(signal, 0.0))
        if op == ">=":
            return actual >= value
        if op == ">":
            return actual > value
        if op == "<=":
            return actual <= value
        if op == "==":
            return actual == value
    return False


def revise_kinds_from_outcomes(
    policy: MetaPolicy,
    entries: list[JournalEntry],
) -> MetaPolicy:
    """Invent program kinds (executable) from journal signals; expr is secondary."""
    if len(entries) < 2:
        return policy
    seed_counts = _signals_from_entries(entries)
    vec = _signal_vector(entries)

    for key in sorted(vec.keys()):
        if key not in policy.observed_signals:
            policy.observed_signals.append(key)

    fruitful = float(vec.get("fruitful", 0.0))
    stalled = float(vec.get("stalled", 0.0))
    flags = float(vec.get("flags", 0.0))
    node_delta = float(vec.get("node_delta", 0.0))
    grow_count = float(vec.get("grow_count", 0.0))
    feature_keys = [
        k
        for k in vec.keys()
        if k
        not in {
            "fruitful",
            "stalled",
            "hungry",
            "hint_invent",
            "hint_nurture",
        }
        and abs(float(vec.get(k, 0.0))) > 0
    ]
    if feature_keys and (fruitful >= 1 or node_delta >= 2):
        weights: dict[str, float] = {}
        if node_delta > 0:
            weights["node_delta"] = 0.5 + min(2.0, node_delta / 4.0)
        if grow_count > 0:
            weights["grow_count"] = 0.35 + min(1.5, grow_count / 6.0)
        if flags > 0:
            weights["flags"] = -0.8
        for k in feature_keys:
            if k in weights:
                continue
            mag = float(vec.get(k, 0.0))
            if mag == 0:
                continue
            tilt = (fruitful - stalled) / max(1.0, fruitful + stalled)
            weights[k] = round(0.1 * tilt * (1.0 if mag > 0 else -1.0), 4)
        if weights:
            approx = sum(
                float(w) * float(vec.get(k, 0.0)) for k, w in weights.items()
            )
            threshold = round(max(0.5, approx * 0.35), 4)
            prog_body = _weights_to_program(weights, threshold)
            cname = "cond_prog_growth"
            register_condition_kind(
                policy,
                name=cname,
                definition={
                    "kind": "program",
                    "body": prog_body,
                    "origin": "learned-program",
                    "features": sorted(weights.keys()),
                },
            )
            aname = "act_prog_invent"
            register_action_kind(
                policy,
                name=aname,
                definition={
                    "kind": "program",
                    "body": [
                        {
                            "op": "bias_channel",
                            "channel": "prefer_invent",
                            "amount": 1.4,
                        }
                    ],
                    "origin": "learned-program",
                },
            )
            existing = {(r.when, r.then) for r in policy.rules if r.enabled}
            if (cname, aname) not in existing:
                policy.rules.append(
                    MetaRule(
                        f"r-prog-{uuid.uuid4().hex[:4]}",
                        cname,
                        aname,
                        strength=1.3,
                        origin="learned",
                    )
                )
                policy.rule_revisions += 1

            # Keep expr mirror for compat / older gates reading features.
            register_condition_kind(
                policy,
                name="cond_expr_growth",
                definition={
                    "kind": "expr",
                    "weights": weights,
                    "op": ">=",
                    "threshold": threshold,
                    "origin": "learned-expr",
                    "features": sorted(weights.keys()),
                },
            )

    # Secondary: compound / threshold (compat scaffolds).
    active_seeds = sorted(k for k, v in seed_counts.items() if v >= 1)
    if len(active_seeds) >= 2:
        a, b = active_seeds[0], active_seeds[1]
        cname = f"cond_{a[:6]}_{b[:6]}"
        register_condition_kind(
            policy,
            name=cname,
            definition={"kind": "all", "of": [a, b], "origin": "learned"},
        )
        aname = f"act_boost_invent_{a[:4]}"
        register_action_kind(
            policy,
            name=aname,
            definition={
                "kind": "boost",
                "target": "invent",
                "amount": 1.25,
                "origin": "learned",
            },
        )
        existing = {(r.when, r.then) for r in policy.rules if r.enabled}
        if (cname, aname) not in existing:
            policy.rules.append(
                MetaRule(
                    f"r-kind-{uuid.uuid4().hex[:4]}",
                    cname,
                    aname,
                    strength=1.2,
                    origin="learned",
                )
            )
            policy.rule_revisions += 1

    if vec.get("node_delta", 0) >= 2:
        tname = "cond_node_delta_ge_2"
        register_condition_kind(
            policy,
            name=tname,
            definition={
                "kind": "threshold",
                "signal": "node_delta",
                "op": ">=",
                "value": 2,
                "origin": "learned",
            },
        )
        aname = "act_set_grow_budget_2"
        register_action_kind(
            policy,
            name=aname,
            definition={
                "kind": "set_grow_budget",
                "value": 2,
                "origin": "learned",
            },
        )
        existing = {(r.when, r.then) for r in policy.rules if r.enabled}
        if (tname, aname) not in existing:
            policy.rules.append(
                MetaRule(
                    f"r-thr-{uuid.uuid4().hex[:4]}",
                    tname,
                    aname,
                    strength=1.0,
                    origin="learned",
                )
            )
            policy.rule_revisions += 1

    return policy


def revise_rules_from_outcomes(
    policy: MetaPolicy,
    entries: list[JournalEntry] | list[dict[str, Any]],
) -> MetaPolicy:
    """Add/disable seed-level rules, then grow novel kinds."""
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
        if when not in policy.known_conditions() or then not in policy.known_actions():
            if when not in SEED_CONDITIONS or then not in SEED_ACTIONS:
                return
        if (when, then) in existing:
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

    if counts["growth_fruitful"] >= 2 and counts["flags_high"] == 0:
        _learn("growth_fruitful", "prefer_invent", 1.2)
    if counts["flags_high"] >= 2:
        _learn("flags_high", "prefer_prune", 1.5)
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

    policy = revise_kinds_from_outcomes(policy, normalized)
    return policy


def update_policy_from_journal(
    policy: MetaPolicy,
    entries: list[JournalEntry] | list[dict[str, Any]],
) -> MetaPolicy:
    """Adjust weights AND revise rules/kinds from journal outcomes."""
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
    before_kind = policy.kind_revisions
    policy = revise_rules_from_outcomes(policy, normalized)
    if policy.rule_revisions != before_rev or policy.kind_revisions != before_kind:
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


def _apply_action(
    then: str,
    policy: MetaPolicy,
    scores: dict[str, float],
    strength: float,
    extras: dict[str, Any],
    *,
    vec: dict[str, float] | None = None,
) -> None:
    """Apply seed or novel action kinds into scores/extras."""
    if then in SEED_ACTIONS:
        scores[then] = scores.get(then, 0.0) + strength
        return
    spec = policy.action_kinds.get(then)
    if not spec:
        return
    kind = spec.get("kind")
    if kind == "program":
        run_meta_program(
            list(spec.get("body") or []),
            vec or {},
            scores=scores,
            extras=extras,
            strength=strength,
        )
    elif kind == "bias":
        channel = str(spec.get("channel", "prefer_invent"))
        amount = float(spec.get("amount", 1.0)) * strength
        if channel not in scores:
            scores[channel] = 0.0
        scores[channel] += amount
    elif kind == "boost":
        target = str(spec.get("target", "invent"))
        amount = float(spec.get("amount", 1.0)) * strength
        key = f"prefer_{target}" if not target.startswith("prefer_") else target
        if key not in scores:
            scores[key] = 0.0
        scores[key] += amount
        if "invent" in target:
            scores["prefer_invent"] = scores.get("prefer_invent", 0.0) + amount
    elif kind == "set_grow_budget":
        extras["grow_budget_override"] = int(spec.get("value", 1))


def strategy_from_policy(
    policy: MetaPolicy,
    *,
    max_new_pairs: int = 1,
    journal_entries: list[JournalEntry] | list[dict[str, Any]] | None = None,
    invent_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive strategy from rules over seed + learned program/expr kinds."""
    normalized: list[JournalEntry] = []
    for row in journal_entries or []:
        if isinstance(row, JournalEntry):
            normalized.append(row)
        else:
            normalized.append(JournalEntry.from_dict(row))

    seed_counts = _signals_from_entries(normalized) if normalized else {}
    vec = _signal_vector(normalized) if normalized else {}
    if not normalized:
        seed_counts = {"structure_hungry": 1}

    scores = {ch: 0.0 for ch in PREFERENCE_CHANNELS}
    extras: dict[str, Any] = {}
    fired: list[str] = []
    novel_kind_fired = False
    expr_kind_fired = False
    prog_kind_fired = False

    for rule in policy.rules:
        if not rule.enabled:
            continue
        if not _eval_condition(rule.when, policy, seed_counts, vec):
            continue
        if rule.when in policy.condition_kinds or rule.then in policy.action_kinds:
            novel_kind_fired = True
            cspec = policy.condition_kinds.get(rule.when) or {}
            aspec = policy.action_kinds.get(rule.then) or {}
            if cspec.get("kind") == "program" or aspec.get("kind") == "program":
                prog_kind_fired = True
            if cspec.get("kind") == "expr" or aspec.get("origin") == "learned-expr":
                expr_kind_fired = True
        _apply_action(rule.then, policy, scores, rule.strength, extras, vec=vec)
        fired.append(rule.rule_id)

    scores["prefer_grow"] += policy.grow_weight * 0.15
    scores["prefer_prune"] += policy.prune_weight * 0.15
    scores["prefer_migrate"] += policy.migrate_weight * 0.15
    scores["prefer_invent"] += policy.invent_weight * 0.15
    scores["prefer_nurture"] += policy.nurture_weight * 0.15

    targets = invent_targets or {}
    abandoned = list(targets.get("abandoned_sources") or [])
    prefer_source = str(targets.get("prefer_source") or "")
    abandoned_count = int(targets.get("abandoned_count") or 0)
    # Outcome traces: if invent sources were abandoned, nudge away from blind invent.
    if abandoned_count >= 1 and not prefer_source:
        scores["prefer_invent"] = max(0.0, scores["prefer_invent"] - 0.5)
        scores["prefer_nurture"] += 0.3
    if prefer_source == "topology":
        scores["prefer_invent"] += 0.6

    actionable = {k: v for k, v in scores.items() if k != "suppress_grow"}
    dominant = max(actionable, key=actionable.get)
    suppress = scores["suppress_grow"] > scores["prefer_grow"]
    grow_budget = int(extras.get("grow_budget_override", max_new_pairs))

    base = {
        "from_journal": True,
        "from_policy": True,
        "policy_id": policy.policy_id,
        "active_rules": fired,
        "rule_revisions": policy.rule_revisions,
        "kind_revisions": policy.kind_revisions,
        "novel_kinds": novel_kind_fired,
        "expr_kinds": expr_kind_fired,
        "prog_kinds": prog_kind_fired,
        "condition_kind_count": len(policy.condition_kinds),
        "action_kind_count": len(policy.action_kinds),
        "observed_signals": list(policy.observed_signals),
        "invent_prefer_source": prefer_source,
        "abandoned_sources": abandoned,
        "abandoned_count": abandoned_count,
    }
    if prog_kind_fired:
        tag = "prog"
    elif expr_kind_fired:
        tag = "expr"
    elif novel_kind_fired:
        tag = "kinds"
    else:
        tag = "rules"

    if dominant == "prefer_prune" or suppress:
        return {
            **base,
            "grow_budget": 0,
            "prefer_prune": True,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:{tag}:prune",
            "want_invent": scores["prefer_invent"] > 1.0,
            "want_nurture": scores["prefer_nurture"] > 1.0,
        }
    if dominant == "prefer_migrate":
        return {
            **base,
            "grow_budget": 0,
            "prefer_prune": False,
            "prefer_migrate": True,
            "reason": f"policy:{policy.policy_id}:{tag}:migrate",
            "want_invent": scores["prefer_invent"] > 0.8,
            "want_nurture": scores["prefer_nurture"] > 0.8,
        }
    if dominant == "prefer_invent":
        return {
            **base,
            "grow_budget": 0 if suppress else max(1, grow_budget),
            "prefer_prune": False,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:{tag}:invent",
            "want_invent": True,
            "want_nurture": scores["prefer_nurture"] >= 0.5,
        }
    if dominant == "prefer_nurture":
        return {
            **base,
            "grow_budget": 0 if suppress else max(1, grow_budget),
            "prefer_prune": False,
            "prefer_migrate": False,
            "reason": f"policy:{policy.policy_id}:{tag}:nurture",
            "want_invent": scores["prefer_invent"] >= 0.5,
            "want_nurture": True,
        }
    return {
        **base,
        "grow_budget": 0 if suppress else max(1, grow_budget),
        "prefer_prune": False,
        "prefer_migrate": False,
        "reason": f"policy:{policy.policy_id}:{tag}:grow",
        "want_invent": scores["prefer_invent"] >= scores["prefer_prune"],
        "want_nurture": scores["prefer_nurture"] >= 0.7,
    }
