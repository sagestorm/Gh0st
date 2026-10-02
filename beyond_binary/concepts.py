"""Structural concept formation — new opposite-state domains from graph roles.

Not pressure-stem suffixes (`{stem}ure`). Concepts are derived from measurable
roles on the living torus (branching, bridging, depth), then named with
role-tokens + a graph fingerprint so labels fall outside the closed invent
alphabet.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from .engine import Engine, is_bit_collapse_topic, normalize
from .model import Hemisphere


# Role → opposite-state concept axes (structural, not stem morphs).
ROLE_AXES: tuple[tuple[str, str, str], ...] = (
    ("branching", "fecund", "sparse"),
    ("bridging", "nexus", "island"),
    ("depth", "rooted", "shallow"),
    ("symmetry", "balanced", "skewed"),
)


@dataclass(frozen=True)
class ConceptProposal:
    cause: str
    effect: str
    instance: str
    role: str
    why: str
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "effect": self.effect,
            "instance": self.instance,
            "role": self.role,
            "why": self.why,
            "metrics": self.metrics,
            "source": "concept",
        }


def _fingerprint(eng: Engine) -> str:
    keys = ",".join(sorted(eng.torus.nodes.keys()))
    return hashlib.sha1(keys.encode("utf-8")).hexdigest()[:6]


def _child_count(eng: Engine, name: str) -> int:
    return len(eng.children(name))


def _depth(eng: Engine, name: str) -> int:
    try:
        return len(eng.path_to_root(name)) - 1
    except Exception:  # noqa: BLE001
        return 0


def graph_role_metrics(eng: Engine) -> dict[str, float]:
    """Aggregate structural metrics used to pick a concept axis."""
    nodes = list(eng.torus.nodes.values())
    if not nodes:
        return {
            "branching": 0.0,
            "bridging": 0.0,
            "depth": 0.0,
            "symmetry": 0.0,
        }
    branching = sum(_child_count(eng, n.name) for n in nodes) / len(nodes)
    # Bridging: nodes whose opposite lives under a different root instance chain.
    bridges = 0
    for n in nodes:
        if n.hemisphere is not Hemisphere.CAUSE or not n.opposite:
            continue
        if n.parent is None:
            continue
        opp = eng.torus.nodes.get(n.opposite)
        if opp and opp.parent and normalize(n.parent) != normalize(opp.parent or ""):
            # Cross-parent reciprocal ≈ structural bridge.
            bridges += 1
    bridging = bridges / max(1, len(nodes) // 2)
    depth = sum(_depth(eng, n.name) for n in nodes) / len(nodes)
    # Symmetry: fraction of reciprocal opposite links.
    sym = 0
    for n in nodes:
        if not n.opposite:
            continue
        opp = eng.torus.nodes.get(n.opposite)
        if opp and opp.opposite == normalize(n.name):
            sym += 1
    symmetry = sym / len(nodes)
    return {
        "branching": float(branching),
        "bridging": float(bridging),
        "depth": float(depth),
        "symmetry": float(symmetry),
    }


def _pick_axis(metrics: dict[str, float]) -> tuple[str, str, str]:
    """Choose the role axis with the strongest structural signal."""
    # Prefer axes that are "activated" (non-trivial structure).
    scored: list[tuple[float, tuple[str, str, str]]] = []
    for role, cause, effect in ROLE_AXES:
        score = metrics.get(role, 0.0)
        if role == "symmetry":
            # Low symmetry is the interesting pressure.
            score = 1.0 - score
        scored.append((score, (role, cause, effect)))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def form_concepts(
    eng: Engine,
    *,
    alphabet: set[str],
    used_instances: set[str],
    limit: int = 3,
) -> list[ConceptProposal]:
    """Propose concept domains from graph roles; labels must leave the alphabet."""
    if len(eng.torus.nodes) < 4:
        return []
    metrics = graph_role_metrics(eng)
    fp = _fingerprint(eng)
    out: list[ConceptProposal] = []
    # Rank all axes; emit novel labels per axis until limit.
    ranked = sorted(
        ROLE_AXES,
        key=lambda ax: (
            (1.0 - metrics["symmetry"])
            if ax[0] == "symmetry"
            else metrics.get(ax[0], 0.0)
        ),
        reverse=True,
    )
    for role, base_c, base_e in ranked:
        # Role token + fingerprint ⇒ not a closed stem-suffix of a pressure node.
        cause = f"{base_c}-{fp}"
        effect = f"{base_e}-{fp}"
        if is_bit_collapse_topic(cause) or is_bit_collapse_topic(effect):
            continue
        if normalize(cause) in alphabet or normalize(effect) in alphabet:
            # Slightly mutate fingerprint slice if collision.
            cause = f"{base_c}x{fp[:4]}"
            effect = f"{base_e}x{fp[:4]}"
            if normalize(cause) in alphabet or normalize(effect) in alphabet:
                continue
        instance = f"{normalize(cause)}-{normalize(effect)}"
        if normalize(instance) in used_instances or normalize(instance) in alphabet:
            continue
        # Reject if it looks like the old pressure-suffix primitive pattern.
        if re.search(r"(ure|iveopp)$", normalize(cause)) or normalize(
            effect
        ).startswith("un") and normalize(effect).endswith("ure"):
            continue
        why = (
            f"concept:{role}:"
            f"branching={metrics['branching']:.2f},"
            f"bridging={metrics['bridging']:.2f},"
            f"depth={metrics['depth']:.2f},"
            f"symmetry={metrics['symmetry']:.2f}"
        )
        out.append(
            ConceptProposal(
                cause=cause,
                effect=effect,
                instance=instance,
                role=role,
                why=why,
                metrics=dict(metrics),
            )
        )
        if len(out) >= limit:
            break
    return out


def is_suffix_primitive_label(label: str) -> bool:
    """Detect the old pressure-suffix mint pattern (not concept formation)."""
    key = normalize(label)
    if key.endswith("ure") and (key.startswith("un") or not key.startswith("un")):
        if key.endswith("ure") and len(key) > 4:
            # hoture / unhoture style
            if re.fullmatch(r"un?[a-z0-9]{2,}ure", key):
                return True
    if key.startswith("proto") or key.startswith("ecto"):
        return True
    if key.endswith("iveopp") or key.endswith("less") and len(key) > 5:
        if re.fullmatch(r"[a-z0-9]+(iveopp|less|al)", key):
            return True
    return False
