"""Experience-grown concept formation — motif digests, not syllabic alphabets.

Concepts are opposite-state domains whose labels are structural digests of
discovered dual motifs (adjacency asymmetries). Naming does not use ROLE_AXES,
pressure-suffix morphs, or a fixed onset/vowel/coda mint alphabet.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .engine import Engine, is_bit_collapse_topic, normalize
from .model import Hemisphere


@dataclass(frozen=True)
class ConceptProposal:
    cause: str
    effect: str
    instance: str
    role: str  # motif tag for provenance
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


def _digest_hex(parts: list[str], *, nbytes: int = 4) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[: nbytes * 2]


def motif_label(prefix: str, motif_parts: list[str]) -> str:
    """Label from structural digest — hex of adjacency signature, not syllabic mint."""
    digest = _digest_hex(motif_parts, nbytes=4)
    # Prefix keeps cause/effect distinguishable; digest is graph-derived.
    token = f"{prefix}{digest}"
    if is_bit_collapse_topic(token):
        token = f"m{token}"
    return token


def _child_count(eng: Engine, name: str) -> int:
    return len(eng.children(name))


def _depth(eng: Engine, name: str) -> int:
    try:
        return len(eng.path_to_root(name)) - 1
    except Exception:  # noqa: BLE001
        return 0


def discover_dual_motifs(eng: Engine) -> list[dict[str, Any]]:
    """Discover dual motifs from live topology — open shape, not a fixed pair table.

    A motif is an opposite-linked pair whose child-count or depth asymmetry
    is non-zero. Motifs are ordered by asymmetry magnitude (experience order).
    """
    motifs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in eng.torus.nodes.values():
        if node.hemisphere is not Hemisphere.CAUSE:
            continue
        if not node.opposite or node.opposite not in eng.torus.nodes:
            continue
        opp = eng.torus.nodes[node.opposite]
        key = "|".join(sorted([normalize(node.name), normalize(opp.name)]))
        if key in seen:
            continue
        seen.add(key)
        c_kids = sorted(normalize(c.name) for c in eng.children(node.name))
        e_kids = sorted(normalize(c.name) for c in eng.children(opp.name))
        c_depth = _depth(eng, node.name)
        e_depth = _depth(eng, opp.name)
        deg_asym = abs(len(c_kids) - len(e_kids))
        depth_asym = abs(c_depth - e_depth)
        if deg_asym == 0 and depth_asym == 0 and not c_kids and not e_kids:
            continue
        # Motif signature: poles + child sets + depths (adjacency digest inputs).
        signature = [
            f"c:{normalize(node.name)}",
            f"e:{normalize(opp.name)}",
            f"ck:{','.join(c_kids)}",
            f"ek:{','.join(e_kids)}",
            f"cd:{c_depth}",
            f"ed:{e_depth}",
        ]
        motifs.append(
            {
                "cause_pole": node.name,
                "effect_pole": opp.name,
                "cause_children": c_kids,
                "effect_children": e_kids,
                "deg_asym": deg_asym,
                "depth_asym": depth_asym,
                "score": float(deg_asym * 2 + depth_asym),
                "signature": signature,
            }
        )
    motifs.sort(key=lambda m: (-m["score"], m["cause_pole"], m["effect_pole"]))
    return motifs


def graph_partition_metrics(eng: Engine) -> dict[str, float]:
    motifs = discover_dual_motifs(eng)
    n = max(1, len(eng.torus.nodes))
    total_asym = sum(m["score"] for m in motifs)
    return {
        "nodes": float(len(eng.torus.nodes)),
        "motif_count": float(len(motifs)),
        "motif_asymmetry": total_asym / n,
    }


def form_concepts(
    eng: Engine,
    *,
    alphabet: set[str],
    used_instances: set[str],
    limit: int = 3,
) -> list[ConceptProposal]:
    """Propose concepts by digesting discovered dual motifs (not a mint alphabet)."""
    if len(eng.torus.nodes) < 4:
        return []
    motifs = discover_dual_motifs(eng)
    if not motifs:
        return []
    metrics = graph_partition_metrics(eng)
    out: list[ConceptProposal] = []

    for motif in motifs:
        sig = list(motif["signature"])
        # Distinct prefixes so cause/effect digests diverge even on similar sets.
        cause = motif_label("c", ["L"] + sig)
        effect = motif_label("e", ["R"] + sig)
        if normalize(cause) == normalize(effect):
            effect = motif_label("e", ["R2"] + sig + [cause])
        # Collision: re-digest with salt from alphabet pressure (still structural).
        salt = 0
        while (
            normalize(cause) in alphabet
            or normalize(effect) in alphabet
            or is_bit_collapse_topic(cause)
            or is_bit_collapse_topic(effect)
        ) and salt < 8:
            salt += 1
            cause = motif_label("c", [f"L{salt}"] + sig)
            effect = motif_label("e", [f"R{salt}"] + sig)
        if normalize(cause) in alphabet or normalize(effect) in alphabet:
            continue
        if normalize(cause) == normalize(effect):
            continue
        instance = f"{normalize(cause)}-{normalize(effect)}"
        if normalize(instance) in used_instances or normalize(instance) in alphabet:
            continue
        if is_suffix_primitive_label(cause) or is_suffix_primitive_label(effect):
            continue
        if is_role_axis_label(cause) or is_role_axis_label(effect):
            continue
        if is_syllabic_mint_label(cause) or is_syllabic_mint_label(effect):
            continue
        tag = (
            f"motif:deg={motif['deg_asym']},depth={motif['depth_asym']},"
            f"pole={normalize(motif['cause_pole'])}"
        )
        why = (
            f"concept:motif:{tag}:"
            f"score={motif['score']:.1f},"
            f"motif_asymmetry={metrics['motif_asymmetry']:.2f}"
        )
        out.append(
            ConceptProposal(
                cause=cause,
                effect=effect,
                instance=instance,
                role=tag,
                why=why,
                metrics=dict(metrics),
            )
        )
        if len(out) >= limit:
            break
    return out


def is_suffix_primitive_label(label: str) -> bool:
    """Detect the old pressure-suffix mint pattern."""
    key = normalize(label)
    if re.fullmatch(r"un?[a-z0-9]{2,}ure", key):
        return True
    if key.startswith("proto") or key.startswith("ecto"):
        return True
    if re.fullmatch(r"[a-z0-9]+(iveopp|less|al)", key):
        return True
    return False


def is_role_axis_label(label: str) -> bool:
    """Detect previous ROLE_AXES table tokens (no longer used for naming)."""
    key = normalize(label).split("-")[0]
    return key in {
        "fecund",
        "sparse",
        "nexus",
        "island",
        "rooted",
        "shallow",
        "balanced",
        "skewed",
    }


def is_syllabic_mint_label(label: str) -> bool:
    """Detect slice-6 open-partition syllabic tokens (onset-vowel-coda repeats)."""
    key = normalize(label)
    # Reject pure syllabic 6-letter tokens without hex (legacy mint).
    if re.fullmatch(r"[bdfghklmnprstwyz][aeiou][knlrsxz]{1,2}"
                    r"([bdfghklmnprstwyz][aeiou][knlrsxz]{1,2})+", key):
        return True
    return False


# Backward-compatible alias used by older verify imports.
def graph_role_metrics(eng: Engine) -> dict[str, float]:
    return graph_partition_metrics(eng)
