"""Multi-domain lexicons + deterministic expansion rules.

Domains: thermal (hot/cold), ontological (nothing/something), optical (light/dark).
Same Living Center loop grows any active domain — no external LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class LexEntry:
    """One cascade step: place cause↔effect under known parents."""

    cause: str
    effect: str
    cause_parent: str
    effect_parent: str


THERMAL_CASCADE: tuple[LexEntry, ...] = (
    LexEntry("boiling", "freezing", "hot", "cold"),
    LexEntry("water", "condensation", "boiling", "cold"),
    LexEntry("steam", "frost", "hot", "cold"),
    LexEntry("warm", "cool", "hot", "cold"),
)

ONTOLOGY_CASCADE: tuple[LexEntry, ...] = (
    LexEntry("absence", "presence", "nothing", "something"),
    LexEntry("void", "form", "nothing", "something"),
    LexEntry("empty", "filled", "nothing", "something"),
)

OPTICAL_CASCADE: tuple[LexEntry, ...] = (
    LexEntry("bright", "dim", "light", "dark"),
    LexEntry("day", "night", "light", "dark"),
    LexEntry("glow", "shadow", "light", "dark"),
)

# Backward-compatible name used by older center code paths.
DOMAIN_CASCADES: dict[str, tuple[LexEntry, ...]] = {
    "thermal": THERMAL_CASCADE,
    "ontology": ONTOLOGY_CASCADE,
    "optical": OPTICAL_CASCADE,
}

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

ONTOLOGY_ALIASES: tuple[tuple[str, ...], ...] = (
    ("absence", "absent", "missing"),
    ("presence", "present", "here"),
    ("void", "vacuum", "nil"),
    ("form", "shape", "structure"),
    ("empty", "emptiness"),
    ("filled", "full", "occupied"),
)

OPTICAL_ALIASES: tuple[tuple[str, ...], ...] = (
    ("bright", "brighter", "luminous"),
    ("dim", "dimmer", "faint"),
    ("day", "daytime"),
    ("night", "nighttime"),
    ("glow", "gleam"),
    ("shadow", "shade"),
)

ALL_ALIASES: tuple[tuple[str, ...], ...] = (
    THERMAL_ALIASES + ONTOLOGY_ALIASES + OPTICAL_ALIASES
)

_ANTONYM_PAIRS: tuple[tuple[str, str], ...] = tuple(
    (e.cause, e.effect)
    for cascade in DOMAIN_CASCADES.values()
    for e in cascade
) + (
    ("hot", "cold"),
    ("nothing", "something"),
    ("light", "dark"),
)

DOMAIN_POLES: dict[str, tuple[str, str]] = {
    "thermal": ("hot", "cold"),
    "ontology": ("nothing", "something"),
    "optical": ("light", "dark"),
}

# Readable domain-tagged invent duals that are *not* lexicon aliases.
# Wedging aliases of existing poles raises unused_path_cost (alias_dups);
# these motifs give typed-parent invent somewhere to land without undomain pollution.
DOMAIN_INVENT_MOTIFS: dict[str, tuple[tuple[str, str], ...]] = {
    "thermal": (("sear", "numb"), ("simmer", "quench"), ("humid", "arid")),
    "ontology": (("latent", "manifest"),),
    "optical": (("glare", "gloom"),),
}


def antonym_for(name: str) -> Optional[str]:
    key = name.strip().lower()
    for a, b in _ANTONYM_PAIRS:
        if key == a.lower():
            return b
        if key == b.lower():
            return a
    return None


def canonical_name(name: str) -> str:
    key = name.strip().lower()
    for group in ALL_ALIASES:
        canon = group[0]
        if key in {g.lower() for g in group}:
            return canon
    return key


def alias_groups() -> tuple[tuple[str, ...], ...]:
    return ALL_ALIASES


def all_cascades() -> tuple[LexEntry, ...]:
    out: list[LexEntry] = []
    for cascade in DOMAIN_CASCADES.values():
        out.extend(cascade)
    return tuple(out)


def detect_domains(existing_names: Iterable[str]) -> set[str]:
    names = {n.lower() for n in existing_names}
    found: set[str] = set()
    for domain, (a, b) in DOMAIN_POLES.items():
        if a in names or b in names:
            found.add(domain)
    return found


def pole_domain(name: str) -> Optional[str]:
    """Map a pole label to thermal|ontology|optical via roots, cascades, aliases.

    Returns None for undomain'd invent motifs (chaos/order, open/closed, …).
    """
    key = canonical_name(name).strip().lower()
    if not key:
        return None
    for domain, (a, b) in DOMAIN_POLES.items():
        if key in {a.lower(), b.lower()}:
            return domain
    for domain, cascade in DOMAIN_CASCADES.items():
        for entry in cascade:
            if key in {
                entry.cause.lower(),
                entry.effect.lower(),
                entry.cause_parent.lower(),
                entry.effect_parent.lower(),
            }:
                return domain
    alias_domains: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = (
        ("thermal", THERMAL_ALIASES),
        ("ontology", ONTOLOGY_ALIASES),
        ("optical", OPTICAL_ALIASES),
    )
    for domain, groups in alias_domains:
        for group in groups:
            if key in {g.lower() for g in group}:
                return domain
    for domain, pairs in DOMAIN_INVENT_MOTIFS.items():
        for cause, effect in pairs:
            if key in {cause.lower(), effect.lower()}:
                return domain
    return None


def pending_expansions(
    existing_names: set[str],
    *,
    parent_names: set[str],
    domains: set[str] | None = None,
) -> list[LexEntry]:
    """Lexicon entries whose parents exist and whose children are not yet present."""
    existing = {n.lower() for n in existing_names}
    parents = {n.lower() for n in parent_names}
    active = domains if domains is not None else detect_domains(existing_names)
    if not active:
        active = set(DOMAIN_CASCADES.keys())
    out: list[LexEntry] = []
    for domain in ("thermal", "ontology", "optical"):
        if domain not in active:
            continue
        for entry in DOMAIN_CASCADES[domain]:
            if entry.cause_parent.lower() not in parents:
                continue
            if entry.effect_parent.lower() not in parents:
                continue
            if entry.cause.lower() in existing or entry.effect.lower() in existing:
                continue
            out.append(entry)
    return out
