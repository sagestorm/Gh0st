"""Generative expansion beyond the fixed lexicon.

When lexicon pending is empty, the center may still grow by:
1. Replaying learned successful pairs from prior cycles (persisted beside the store)
2. Synonym-cascade: unused alias antonyms nested under known reciprocal pairs (I5)
3. Proposing nested opposite-state children under reciprocal leaf pairs
   (more-{name} ↔ more-{opposite}) — bounded, immediately dual-linked

This is still rule-based (no external LLM). It is the bridge past static scripts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from .engine import Engine, normalize
from .lexicon import LexEntry, alias_groups, antonym_for
from . import store


@dataclass(frozen=True)
class LearnedPair:
    cause: str
    effect: str
    cause_parent: str
    effect_parent: str

    def as_entry(self) -> LexEntry:
        return LexEntry(
            self.cause, self.effect, self.cause_parent, self.effect_parent
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "cause": self.cause,
            "effect": self.effect,
            "cause_parent": self.cause_parent,
            "effect_parent": self.effect_parent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearnedPair":
        return cls(
            cause=data["cause"],
            effect=data["effect"],
            cause_parent=data["cause_parent"],
            effect_parent=data["effect_parent"],
        )


def learned_path(mind_store: Path | str | None = None) -> Path:
    target = store.store_path(mind_store)
    return target.with_name(f"{target.stem}.learned.json")


def load_learned(mind_store: Path | str | None = None) -> list[LearnedPair]:
    path = learned_path(mind_store)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [LearnedPair.from_dict(row) for row in data.get("pairs", [])]


def save_learned(
    pairs: list[LearnedPair], mind_store: Path | str | None = None
) -> Path:
    path = learned_path(mind_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Dedupe by cause/effect keys
    seen: set[tuple[str, str]] = set()
    unique: list[LearnedPair] = []
    for p in pairs:
        key = (normalize(p.cause), normalize(p.effect))
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    path.write_text(
        json.dumps({"pairs": [p.to_dict() for p in unique]}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return path


def remember_growth(
    added: Iterable[dict[str, str]],
    mind_store: Path | str | None = None,
) -> None:
    """Persist successful grow rows as learned cascade fuel."""
    existing = load_learned(mind_store)
    for row in added:
        if "error" in row:
            continue
        if not all(k in row for k in ("cause", "effect", "cause_parent", "effect_parent")):
            continue
        existing.append(
            LearnedPair(
                cause=row["cause"],
                effect=row["effect"],
                cause_parent=row["cause_parent"],
                effect_parent=row["effect_parent"],
            )
        )
    save_learned(existing, mind_store)


def pending_learned(
    eng: Engine, mind_store: Path | str | None = None
) -> list[LexEntry]:
    out: list[LexEntry] = []
    for pair in load_learned(mind_store):
        if eng.exists(pair.cause) or eng.exists(pair.effect):
            continue
        if not eng.exists(pair.cause_parent) or not eng.exists(pair.effect_parent):
            continue
        out.append(pair.as_entry())
    return out


def _alias_group_for(name: str) -> Optional[tuple[str, ...]]:
    key = normalize(name)
    for group in alias_groups():
        if key in {normalize(g) for g in group}:
            return group
    return None


def synonym_cascade_expansions(eng: Engine, *, limit: int = 4) -> list[LexEntry]:
    """Nest unused synonym/antonym aliases under known reciprocal pairs (I5).

    Opposite stays opposite-state: alias of cause pairs with alias of effect.
    These names are not in the fixed DOMAIN_CASCADE child list — growth beyond
    lexicon playback.
    """
    from .model import Hemisphere

    out: list[LexEntry] = []
    seen: set[tuple[str, str]] = set()
    for node in eng.torus.nodes.values():
        if node.hemisphere is not Hemisphere.CAUSE or not node.opposite:
            continue
        opp = eng.torus.nodes.get(node.opposite)
        if opp is None:
            continue
        cause_group = _alias_group_for(node.name)
        effect_group = _alias_group_for(opp.name)
        if not cause_group or not effect_group:
            continue
        unused_c = [
            a
            for a in cause_group
            if not eng.exists(a) and normalize(a) != normalize(node.name)
        ]
        unused_e = [
            a
            for a in effect_group
            if not eng.exists(a) and normalize(a) != normalize(opp.name)
        ]
        for cause_alias, effect_alias in zip(unused_c, unused_e):
            key = (normalize(cause_alias), normalize(effect_alias))
            if key in seen:
                continue
            seen.add(key)
            out.append(
                LexEntry(
                    cause=cause_alias,
                    effect=effect_alias,
                    cause_parent=node.name,
                    effect_parent=opp.name,
                )
            )
            if len(out) >= limit:
                return out
    return out


def generative_leaf_expansions(eng: Engine, *, limit: int = 4) -> list[LexEntry]:
    """For reciprocal leaf pairs, propose more-{cause} ↔ more-{effect} children."""
    out: list[LexEntry] = []
    seen: set[tuple[str, str]] = set()
    for node in eng.torus.nodes.values():
        if not node.opposite:
            continue
        opp = eng.torus.nodes.get(node.opposite)
        if opp is None:
            continue
        if eng.children(node.name) or eng.children(opp.name):
            continue
        # Only propose from cause side to avoid duplicates.
        from .model import Hemisphere

        if node.hemisphere is not Hemisphere.CAUSE:
            continue
        child = f"more-{node.name}"
        child_opp = f"more-{opp.name}"
        if eng.exists(child) or eng.exists(child_opp):
            continue
        # Avoid nonsense stacking
        if node.name.lower().startswith("more-"):
            continue
        key = (normalize(child), normalize(child_opp))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            LexEntry(
                cause=child,
                effect=child_opp,
                cause_parent=node.name,
                effect_parent=opp.name,
            )
        )
        if len(out) >= limit:
            break
    return out


def pending_generative(
    eng: Engine, *, mind_store: Path | str | None = None, limit: int = 4
) -> list[LexEntry]:
    """Learned first, then synonym-cascade, then more-* leaf proposals."""
    learned = pending_learned(eng, mind_store)
    if learned:
        return learned[:limit]
    syn = synonym_cascade_expansions(eng, limit=limit)
    if syn:
        return syn
    return generative_leaf_expansions(eng, limit=limit)


def fixed_cascade_child_names() -> set[str]:
    """Names that appear as cause/effect children in DOMAIN_CASCADES (not poles)."""
    from . import lexicon

    names: set[str] = set()
    for cascade in lexicon.DOMAIN_CASCADES.values():
        for entry in cascade:
            names.add(normalize(entry.cause))
            names.add(normalize(entry.effect))
    return names


def synonym_nodes_present(eng: Engine) -> list[str]:
    """Nodes present that came from alias groups but not fixed cascade children."""
    fixed = fixed_cascade_child_names()
    poles = set()
    for a, b in lexicon_domain_poles():
        poles.add(normalize(a))
        poles.add(normalize(b))
    found: list[str] = []
    for group in alias_groups():
        for alias in group:
            key = normalize(alias)
            if key in fixed or key in poles:
                continue
            if eng.exists(alias):
                found.append(alias)
    return sorted(set(found), key=str.lower)


def lexicon_domain_poles() -> list[tuple[str, str]]:
    from . import lexicon

    return list(lexicon.DOMAIN_POLES.values())
