"""Open goal formation from outcome traces — beyond invent-source menus.

Goals are persisted beside the mind. Act kinds may be novel (not only
prefer_invent / prefer_nurture / seed actions). Formation uses journal + invent
outcomes; abandon demotes goals rather than only invent sources.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import store
from .journal import JournalEntry


# Seed act menu — novel goals must use act_kinds outside this set.
SEED_GOAL_ACTS = frozenset(
    {
        "prefer_prune",
        "prefer_grow",
        "prefer_migrate",
        "prefer_invent",
        "prefer_nurture",
        "suppress_grow",
        "invent",
        "nurture",
        "grow",
        "prune",
        "migrate",
    }
)


@dataclass
class Goal:
    goal_id: str
    act_kind: str
    target: str
    reason: str
    priority: float = 1.0
    abandoned: bool = False
    origin: str = "outcome"
    # SearchSubstrate act_ast body — required for search_act_* to steer strategy.
    tree: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        row = {
            "goal_id": self.goal_id,
            "act_kind": self.act_kind,
            "target": self.target,
            "reason": self.reason,
            "priority": self.priority,
            "abandoned": self.abandoned,
            "origin": self.origin,
        }
        if self.tree is not None:
            row["tree"] = dict(self.tree)
        return row

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        tree = data.get("tree")
        return cls(
            goal_id=str(data.get("goal_id") or f"g-{uuid.uuid4().hex[:8]}"),
            act_kind=str(data.get("act_kind", "prefer_invent")),
            target=str(data.get("target", "")),
            reason=str(data.get("reason", "")),
            priority=float(data.get("priority", 1.0) or 1.0),
            abandoned=bool(data.get("abandoned", False)),
            origin=str(data.get("origin", "outcome")),
            tree=dict(tree) if isinstance(tree, dict) else None,
        )


@dataclass
class GoalBoard:
    goals: list[Goal] = field(default_factory=list)
    revisions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "goals": [g.to_dict() for g in self.goals],
            "revisions": self.revisions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoalBoard":
        return cls(
            goals=[Goal.from_dict(g) for g in data.get("goals", [])],
            revisions=int(data.get("revisions", 0) or 0),
        )


def goals_path(mind_store: Path | str | None = None) -> Path:
    target = store.store_path(mind_store)
    return target.with_name(f"{target.stem}.goals.json")


def load_goals(mind_store: Path | str | None = None) -> GoalBoard:
    path = goals_path(mind_store)
    if not path.exists():
        return GoalBoard()
    return GoalBoard.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_goals(board: GoalBoard, mind_store: Path | str | None = None) -> Path:
    path = goals_path(mind_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(board.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _normalize_entries(rows: list[Any]) -> list[JournalEntry]:
    out: list[JournalEntry] = []
    for row in rows[-16:]:
        if isinstance(row, JournalEntry):
            out.append(row)
        else:
            try:
                out.append(JournalEntry.from_dict(row))
            except Exception:  # noqa: BLE001
                continue
    return out


def form_goals_from_outcomes(
    board: GoalBoard,
    journal_rows: list[Any],
    *,
    invent_summary: dict[str, Any] | None = None,
) -> GoalBoard:
    """Form / abandon goals from outcomes — novel act kinds allowed."""
    entries = _normalize_entries(journal_rows)
    if len(entries) < 2 and not invent_summary:
        return board

    fruitful = sum(1 for e in entries if e.reflection == "growth_fruitful")
    stalled = sum(1 for e in entries if e.reflection == "growth_stalled")
    flags = sum(
        1
        for e in entries
        if e.reflection == "challenge_pressure"
        or int((e.signals or {}).get("flags", 0) or 0) > 0
    )
    invent_hints = sum(1 for e in entries if e.strategy_hint == "invent")
    summary = invent_summary or {}
    abandoned_sources = list(summary.get("abandoned_sources") or [])
    prefer_source = str(summary.get("prefer_source") or "")
    abandoned_count = int(summary.get("abandoned_count") or 0)

    existing = {(g.act_kind, g.target) for g in board.goals if not g.abandoned}

    from . import substrate as substrate_mod

    search_live = substrate_mod.is_active() and substrate_mod.substrate_impl_name() == "search"

    # G13: when search substrate is live, mint goals via consult before closed menus.
    if search_live:
        try:
            from . import search_substrate as search_mod

            handle = substrate_mod.GoalConsultContext(goal_board=board)
            substrate_mod.consult(
                "goal",
                {
                    "fruitful": fruitful,
                    "stalled": stalled,
                    "flags": flags,
                    "invent_summary": dict(summary),
                    "active_goal_count": len(active_goals(board)),
                },
                center=handle,
            )
            for row in search_mod.drain_pending_goals():
                act = str(row.get("act_kind", ""))
                if not act or act in SEED_GOAL_ACTS:
                    continue
                hit = next(
                    (g for g in board.goals if g.act_kind == act and not g.abandoned),
                    None,
                )
                if hit is not None:
                    tree = row.get("tree")
                    if hit.tree is None and isinstance(tree, dict):
                        hit.tree = dict(tree)
                        board.revisions += 1
                    continue
                board.goals.append(Goal.from_dict(row))
                board.revisions += 1
        except Exception as exc:  # noqa: BLE001
            substrate_mod.record_consult_error("goal", exc)

    def _upsert(act_kind: str, target: str, reason: str, priority: float) -> None:
        nonlocal board
        key = (act_kind, target)
        for g in board.goals:
            if (g.act_kind, g.target) == key and not g.abandoned:
                g.priority = max(g.priority, priority)
                g.reason = reason
                board.revisions += 1
                return
        if key in existing:
            return
        board.goals.append(
            Goal(
                goal_id=f"g-{uuid.uuid4().hex[:6]}",
                act_kind=act_kind,
                target=target,
                reason=reason,
                priority=priority,
                origin="outcome",
            )
        )
        existing.add(key)
        board.revisions += 1

    # Closed outcome menu — skip when search substrate supplies search_act_* (G13).
    if search_live:
        if flags >= 2 and invent_hints >= 1:
            for g in board.goals:
                if g.act_kind in SEED_GOAL_ACTS and not g.abandoned:
                    g.abandoned = True
                    g.priority = 0.1
                    board.revisions += 1
        return board

    # Novel act: seek topology when multi-domain invent is preferred / abandoned concept.
    if prefer_source == "topology" or "concept" in abandoned_sources:
        _upsert(
            "seek_topology_bridge",
            "cross-domain",
            "outcome:prefer_topology_after_source_pressure",
            1.5,
        )

    # Novel act: retire invent pressure when flags/stalled after invent.
    if invent_hints >= 1 and (flags >= 1 or stalled >= 1):
        _upsert(
            "retire_invent_pressure",
            "invent-menu",
            f"outcome:flags={flags},stalled={stalled}",
            1.2,
        )

    # Novel act: propose body primitives when growth is fruitful.
    if fruitful >= 2 and flags == 0:
        _upsert(
            "propose_body_primitive",
            "capability",
            f"outcome:fruitful={fruitful}",
            1.1,
        )

    # Novel act: nurture lineage when invent abandoned.
    if abandoned_count >= 1:
        _upsert(
            "deepen_nurture_lineage",
            "bodies",
            f"outcome:abandoned_count={abandoned_count}",
            1.3,
        )

    # Abandon goals that conflict with adverse invent-after-flags.
    if flags >= 2 and invent_hints >= 1:
        for g in board.goals:
            if g.act_kind == "seek_topology_bridge" and not g.abandoned:
                # Keep topology seek; abandon pure invent-menu goals if any slipped in.
                pass
            if g.act_kind in SEED_GOAL_ACTS and not g.abandoned:
                g.abandoned = True
                g.priority = 0.1
                board.revisions += 1

    return board


def active_goals(board: GoalBoard) -> list[Goal]:
    return sorted(
        [g for g in board.goals if not g.abandoned],
        key=lambda g: (-g.priority, g.goal_id),
    )


def novel_act_kinds(board: GoalBoard) -> list[str]:
    return sorted(
        {
            g.act_kind
            for g in board.goals
            if not g.abandoned and g.act_kind not in SEED_GOAL_ACTS
        }
    )


def goals_to_strategy_hints(
    board: GoalBoard,
    *,
    signals: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Translate active goals into strategy extras (beyond want_invent/nurture).

    Closed outcome acts keep their fixed mappings. Search-minted ``search_act_*``
    goals apply persisted act_ast trees (otherwise they are islands — accepted
    but inert).
    """
    active = active_goals(board)
    novel = novel_act_kinds(board)
    want_invent = False
    want_nurture = False
    invent_prefer_source = ""
    suppress_invent = False
    search_applied = 0
    channel_bias: dict[str, float] = {}
    sig = dict(signals or {})

    for g in active:
        if g.act_kind.startswith("search_act_") and g.tree:
            from . import search_substrate as search_mod

            deltas = search_mod.apply_goal_ast(g.tree, sig)
            search_applied += 1
            if deltas.get("want_invent"):
                want_invent = True
            if deltas.get("want_nurture"):
                want_nurture = True
            if deltas.get("suppress_invent"):
                suppress_invent = True
            prefer = str(deltas.get("invent_prefer_source") or "")
            if prefer:
                invent_prefer_source = prefer
            for ch, amount in (deltas.get("channel_bias") or {}).items():
                channel_bias[ch] = channel_bias.get(ch, 0.0) + float(amount)
            continue
        if g.act_kind == "seek_topology_bridge":
            want_invent = True
            invent_prefer_source = invent_prefer_source or "topology"
        elif g.act_kind == "retire_invent_pressure":
            suppress_invent = True
        elif g.act_kind == "deepen_nurture_lineage":
            want_nurture = True
        elif g.act_kind == "propose_body_primitive":
            want_invent = True  # invent path still grows bodies/forms
    if suppress_invent:
        want_invent = False
    # Channel bias from search ASTs can also flip want flags.
    if channel_bias.get("invent", 0) > 0 or channel_bias.get("prefer_invent", 0) > 0:
        if not suppress_invent:
            want_invent = True
    if channel_bias.get("nurture", 0) > 0 or channel_bias.get("prefer_nurture", 0) > 0:
        want_nurture = True
    if channel_bias.get("migrate", 0) > 0 and not invent_prefer_source:
        invent_prefer_source = invent_prefer_source or "search"
    return {
        "active_goals": [g.to_dict() for g in active[:8]],
        "novel_act_kinds": novel,
        "goal_want_invent": want_invent,
        "goal_want_nurture": want_nurture,
        "goal_invent_prefer_source": invent_prefer_source,
        "goal_suppress_invent": suppress_invent,
        "goal_revisions": board.revisions,
        "goal_search_applied": search_applied,
        "goal_channel_bias": channel_bias,
    }
