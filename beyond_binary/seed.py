"""Domain seeds for dual-hemisphere instances."""

from __future__ import annotations

from typing import Iterable

from .engine import Engine
from .model import Torus
from . import lexicon

DOMAIN_INSTANCE_NAMES: dict[str, str] = {
    "thermal": "hot-cold",
    "ontology": "nothing-something",
    "optical": "light-dark",
}

# Acceptance C2: thermal + ontology + ≥1 other on the same center.
DEFAULT_SAME_CENTER_DOMAINS: tuple[str, ...] = ("thermal", "ontology", "optical")


def seed_minimal_hot_cold(torus: Torus | None = None) -> Torus:
    """Poles only — Living Center grow fills the cascade."""
    return seed_domain("thermal", torus=torus, minimal=True)


def seed_hot_cold(torus: Torus | None = None) -> Torus:
    return seed_domain("thermal", torus=torus, minimal=False)


def seed_domain(
    domain: str,
    *,
    torus: Torus | None = None,
    minimal: bool = True,
) -> Torus:
    """Seed a named domain. minimal=True → poles only for think growth."""
    if domain not in lexicon.DOMAIN_POLES:
        raise ValueError(
            f"unknown domain {domain!r}; choose: {', '.join(lexicon.DOMAIN_POLES)}"
        )
    cause, effect = lexicon.DOMAIN_POLES[domain]
    return seed_custom(
        cause,
        effect,
        instance=DOMAIN_INSTANCE_NAMES[domain],
        torus=torus,
        cascade=None if minimal else lexicon.DOMAIN_CASCADES[domain],
    )


def seed_same_center(
    domains: Iterable[str] | None = None,
    *,
    torus: Torus | None = None,
    minimal: bool = True,
) -> Torus:
    """Seed multiple domain pole pairs on **one** torus for the same Living Center.

    Required shape for far-vision C2: thermal + ontology + ≥1 other (optical).
    """
    chosen = tuple(domains) if domains is not None else DEFAULT_SAME_CENTER_DOMAINS
    if len(chosen) < 2:
        raise ValueError("same-center seed needs at least two domains")
    unknown = [d for d in chosen if d not in lexicon.DOMAIN_POLES]
    if unknown:
        raise ValueError(
            f"unknown domain(s) {unknown!r}; choose: {', '.join(lexicon.DOMAIN_POLES)}"
        )

    torus = torus or Torus()
    eng = Engine(torus)
    for domain in chosen:
        cause, effect = lexicon.DOMAIN_POLES[domain]
        if eng.exists(cause) or eng.exists(effect):
            continue
        eng.add_pair(cause, effect)
        if not minimal:
            for entry in lexicon.DOMAIN_CASCADES[domain]:
                if eng.exists(entry.cause) or eng.exists(entry.effect):
                    continue
                if not eng.exists(entry.cause_parent) or not eng.exists(
                    entry.effect_parent
                ):
                    continue
                eng.add_under(
                    entry.cause_parent,
                    entry.cause,
                    opposite_name=entry.effect,
                    opposite_parent=entry.effect_parent,
                )
    torus.instance = "same-center-" + "-".join(chosen)
    eng.assert_no_orphans()
    return torus


def seed_custom(
    cause: str,
    effect: str,
    *,
    instance: str | None = None,
    torus: Torus | None = None,
    cascade=None,
) -> Torus:
    """Seed an arbitrary opposite-state pole pair (used by self-invention)."""
    torus = torus or Torus()
    torus.instance = instance or f"{cause}-{effect}"
    eng = Engine(torus)
    eng.add_pair(cause, effect)
    if cascade:
        for entry in cascade:
            if eng.exists(entry.cause) or eng.exists(entry.effect):
                continue
            if not eng.exists(entry.cause_parent) or not eng.exists(entry.effect_parent):
                continue
            eng.add_under(
                entry.cause_parent,
                entry.cause,
                opposite_name=entry.effect,
                opposite_parent=entry.effect_parent,
            )
    eng.assert_no_orphans()
    return torus
