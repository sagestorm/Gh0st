"""Domain seeds for dual-hemisphere instances."""

from __future__ import annotations

from .engine import Engine
from .model import Torus
from . import lexicon


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
    torus = torus or Torus()
    torus.instance = {
        "thermal": "hot-cold",
        "ontology": "nothing-something",
        "optical": "light-dark",
    }[domain]
    eng = Engine(torus)
    eng.add_pair(cause, effect)

    if not minimal:
        for entry in lexicon.DOMAIN_CASCADES[domain]:
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
