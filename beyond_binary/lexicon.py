"""Built-in thermal (hot/cold) lexicon + deterministic expansion rules.

Phase 2 stays on one instance. No external LLM — growth is lexicon-driven:
  synonym-under-pole → opposite-state link → related branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LexEntry:
    """One cascade step: place cause↔effect under known parents."""

    cause: str
    effect: str
    cause_parent: str
    effect_parent: str


# Ordered cascade under hot/cold (outline: hot → boiling → water → condensation).
THERMAL_CASCADE: tuple[LexEntry, ...] = (
    LexEntry("boiling", "freezing", "hot", "cold"),
    LexEntry("water", "condensation", "boiling", "cold"),
    LexEntry("steam", "frost", "hot", "cold"),
    LexEntry("warm", "cool", "hot", "cold"),
)

# Alias groups: first name is canonical; others merge into it when both exist.
THERMAL_ALIASES: tuple[tuple[str, ...], ...] = (
    ("boiling", "boil", "boiled", "scalding"),
    ("freezing", "freeze", "frozen", "chilling"),
    ("condensation", "condense", "condensing"),
    ("steam", "vapor", "vapour"),
    ("warm", "warming", "heated"),
    ("cool", "cooling", "chilly"),
    ("water", "h2o"),
    ("frost", "icing"),
)

# Direct antonym hints for orphan repair (normalized lookup built at import).
_ANTONYM_PAIRS: tuple[tuple[str, str], ...] = tuple(
    (e.cause, e.effect) for e in THERMAL_CASCADE
) + (
    ("hot", "cold"),
)


def antonym_for(name: str) -> Optional[str]:
    """Return the lexicon antonym for a name, if known."""
    key = name.strip().lower()
    for a, b in _ANTONYM_PAIRS:
        if key == a.lower():
            return b
        if key == b.lower():
            return a
    return None


def canonical_name(name: str) -> str:
    """Map an alias to its canonical lexicon name; otherwise return normalized input."""
    key = name.strip().lower()
    for group in THERMAL_ALIASES:
        canon = group[0]
        if key in {g.lower() for g in group}:
            return canon
    return key


def alias_groups() -> tuple[tuple[str, ...], ...]:
    return THERMAL_ALIASES


def pending_expansions(
    existing_names: set[str],
    *,
    parent_names: set[str],
) -> list[LexEntry]:
    """Lexicon entries whose parents exist and whose children are not yet present."""
    existing = {n.lower() for n in existing_names}
    parents = {n.lower() for n in parent_names}
    out: list[LexEntry] = []
    for entry in THERMAL_CASCADE:
        if entry.cause_parent.lower() not in parents:
            continue
        if entry.effect_parent.lower() not in parents:
            continue
        if entry.cause.lower() in existing or entry.effect.lower() in existing:
            continue
        out.append(entry)
    return out
