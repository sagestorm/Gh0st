"""Reflective journal — metacognition that reshapes strategy, not a dead event log.

After each cycle the center writes a reflection (signals + hint). Strategy is
derived from those reflections so contrasting journals produce different bias.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import store


@dataclass
class JournalEntry:
    cycle: int
    reflection: str
    signals: dict[str, Any] = field(default_factory=dict)
    strategy_hint: str = "balanced"  # grow | prune | migrate | invent | balanced

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "reflection": self.reflection,
            "signals": self.signals,
            "strategy_hint": self.strategy_hint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry":
        return cls(
            cycle=int(data.get("cycle", 0) or 0),
            reflection=str(data.get("reflection", "")),
            signals=dict(data.get("signals") or {}),
            strategy_hint=str(data.get("strategy_hint", "balanced")),
        )


def journal_path(mind_store: Path | str | None = None) -> Path:
    target = store.store_path(mind_store)
    return target.with_name(f"{target.stem}.journal.jsonl")


def load_journal(mind_store: Path | str | None = None) -> list[JournalEntry]:
    path = journal_path(mind_store)
    if not path.exists():
        return []
    rows: list[JournalEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(JournalEntry.from_dict(json.loads(line)))
    return rows


def append_journal(
    entries: list[JournalEntry],
    mind_store: Path | str | None = None,
) -> Path:
    path = journal_path(mind_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
    return path


def clear_journal(mind_store: Path | str | None = None) -> None:
    path = journal_path(mind_store)
    if path.exists():
        path.unlink()


def reflect_on_report(report: dict[str, Any]) -> JournalEntry:
    """Turn one cycle report into a reflection that can reshape strategy."""
    cycle = int(report.get("cycle", 0) or 0)
    acts = report.get("acts") or []
    grow_count = 0
    prune_count = 0
    flags = 0
    migrate_kept = 0
    grow_source = "none"
    for act in acts:
        if not isinstance(act, dict):
            continue
        name = act.get("act")
        detail = act.get("detail") or {}
        if name == "grow":
            grow_count = int(detail.get("count", 0) or 0)
            grow_source = str(detail.get("source") or "none")
        elif name == "prune":
            prune_count = int(detail.get("count", 0) or 0)
        elif name == "challenge" and detail.get("one_sided"):
            flags += 1
        elif name == "experiment_migrate":
            for exp in detail.get("experiments") or []:
                if isinstance(exp, dict) and exp.get("kept"):
                    migrate_kept += 1

    before = int(report.get("nodes_before", 0) or 0)
    after = int(report.get("nodes_after", 0) or 0)
    delta = after - before
    signals = {
        "grow_count": grow_count,
        "prune_count": prune_count,
        "flags": flags,
        "migrate_kept": migrate_kept,
        "node_delta": delta,
        "grow_source": grow_source,
    }

    if flags >= 1:
        return JournalEntry(
            cycle=cycle,
            reflection="challenge_pressure",
            signals=signals,
            strategy_hint="prune",
        )
    if grow_count > 0 and delta <= 0:
        return JournalEntry(
            cycle=cycle,
            reflection="growth_stalled",
            signals=signals,
            strategy_hint="migrate",
        )
    if grow_count == 0 and flags == 0 and prune_count == 0:
        return JournalEntry(
            cycle=cycle,
            reflection="structure_hungry",
            signals=signals,
            strategy_hint="grow",
        )
    if migrate_kept:
        return JournalEntry(
            cycle=cycle,
            reflection="migration_paid_off",
            signals=signals,
            strategy_hint="migrate",
        )
    if grow_count > 0 and delta > 0:
        return JournalEntry(
            cycle=cycle,
            reflection="growth_fruitful",
            signals=signals,
            strategy_hint="grow",
        )
    return JournalEntry(
        cycle=cycle,
        reflection="balanced_cycle",
        signals=signals,
        strategy_hint="balanced",
    )


def strategy_from_journal(
    entries: list[JournalEntry] | list[dict[str, Any]],
    *,
    max_new_pairs: int = 1,
    soft_cap: int = 24,
    node_count: int = 0,
) -> Optional[dict[str, Any]]:
    """Derive strategy bias from journal reflections.

    Returns a Strategy-shaped dict, or None if the journal is empty
    (caller falls back to raw activity metacognition).
    """
    if not entries:
        return None

    normalized: list[JournalEntry] = []
    for row in entries:
        if isinstance(row, JournalEntry):
            normalized.append(row)
        else:
            normalized.append(JournalEntry.from_dict(row))

    recent = normalized[-12:]
    hints = [e.strategy_hint for e in recent]
    prune_n = hints.count("prune")
    migrate_n = hints.count("migrate")
    grow_n = hints.count("grow")
    invent_n = hints.count("invent")
    flag_sum = sum(int(e.signals.get("flags", 0) or 0) for e in recent)
    stalled = sum(1 for e in recent if e.reflection == "growth_stalled")

    # Journal content drives bias — contrasting journals must diverge.
    if prune_n >= 2 or flag_sum >= 2 or (
        node_count > soft_cap and prune_n >= 1
    ):
        return {
            "grow_budget": 0,
            "prefer_prune": True,
            "prefer_migrate": False,
            "reason": "journal_challenge_pressure",
            "from_journal": True,
        }
    if migrate_n >= 2 or stalled >= 2:
        return {
            "grow_budget": 0,
            "prefer_prune": False,
            "prefer_migrate": True,
            "reason": "journal_growth_stalled",
            "from_journal": True,
        }
    if invent_n >= 2 and grow_n == 0:
        return {
            "grow_budget": max(1, max_new_pairs),
            "prefer_prune": False,
            "prefer_migrate": False,
            "reason": "journal_invent_bias",
            "from_journal": True,
        }
    if grow_n >= 2 and prune_n == 0 and migrate_n == 0:
        return {
            "grow_budget": max(1, max_new_pairs),
            "prefer_prune": False,
            "prefer_migrate": False,
            "reason": "journal_structure_hungry",
            "from_journal": True,
        }
    return {
        "grow_budget": max_new_pairs,
        "prefer_prune": False,
        "prefer_migrate": migrate_n > grow_n,
        "reason": "journal_balanced",
        "from_journal": True,
    }
