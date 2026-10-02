"""Open concept formation from graph partitions — no fixed role-axis name table.

Concepts are opposite-state domains whose labels are minted from topology
partitions (degree / depth splits) via an open syllabic generator. Names are
not looked up from ROLE_AXES and are not pressure-stem suffixes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .engine import Engine, is_bit_collapse_topic, normalize
from .model import Hemisphere


# Open syllabic atoms — generator alphabet, not concept labels.
_ONSETS = "bdfghklmnprstwyz"
_VOWELS = "aeiou"
_CODAS = "knlrsxz"


@dataclass(frozen=True)
class ConceptProposal:
    cause: str
    effect: str
    instance: str
    role: str  # partition tag for provenance (not a name-table key)
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


def _digest(parts: list[str]) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def mint_token(seed: str, *, syllables: int = 2) -> str:
    """Mint a pronounceable token from a seed digest — not a fixed label table."""
    h = _digest([seed])
    chars: list[str] = []
    # Walk hex pairs into onset-vowel-coda syllables.
    i = 0
    for _ in range(max(1, syllables)):
        o = _ONSETS[int(h[i % len(h)], 16) % len(_ONSETS)]
        v = _VOWELS[int(h[(i + 1) % len(h)], 16) % len(_VOWELS)]
        c = _CODAS[int(h[(i + 2) % len(h)], 16) % len(_CODAS)]
        chars.extend([o, v, c])
        i += 3
    token = "".join(chars)
    # Ensure token isn't accidentally a bit-collapse word.
    if is_bit_collapse_topic(token):
        token = f"x{token}"
    return token


def _child_count(eng: Engine, name: str) -> int:
    return len(eng.children(name))


def _depth(eng: Engine, name: str) -> int:
    try:
        return len(eng.path_to_root(name)) - 1
    except Exception:  # noqa: BLE001
        return 0


def partition_cause_nodes(eng: Engine) -> dict[str, list[str]]:
    """Partition cause-side nodes by structural features (no name table)."""
    causes = [
        n
        for n in eng.torus.nodes.values()
        if n.hemisphere is Hemisphere.CAUSE
    ]
    if not causes:
        return {}
    degrees = [(n.name, _child_count(eng, n.name)) for n in causes]
    depths = [(n.name, _depth(eng, n.name)) for n in causes]
    deg_vals = sorted(d for _, d in degrees)
    mid_deg = deg_vals[len(deg_vals) // 2]
    depth_vals = sorted(d for _, d in depths)
    mid_depth = depth_vals[len(depth_vals) // 2]
    high_deg = sorted(n for n, d in degrees if d >= mid_deg)
    low_deg = sorted(n for n, d in degrees if d < mid_deg)
    deep = sorted(n for n, d in depths if d >= mid_depth)
    shallow = sorted(n for n, d in depths if d < mid_depth)
    return {
        "degree_high_vs_low": high_deg,
        "degree_low": low_deg,
        "depth_deep": deep,
        "depth_shallow": shallow,
    }


def graph_partition_metrics(eng: Engine) -> dict[str, float]:
    parts = partition_cause_nodes(eng)
    n = max(1, len(eng.torus.nodes))
    return {
        "nodes": float(len(eng.torus.nodes)),
        "degree_split": float(
            abs(len(parts.get("degree_high_vs_low", [])) - len(parts.get("degree_low", [])))
        )
        / n,
        "depth_split": float(
            abs(len(parts.get("depth_deep", [])) - len(parts.get("depth_shallow", [])))
        )
        / n,
    }


def form_concepts(
    eng: Engine,
    *,
    alphabet: set[str],
    used_instances: set[str],
    limit: int = 3,
) -> list[ConceptProposal]:
    """Propose concepts by minting labels from topology partitions."""
    if len(eng.torus.nodes) < 4:
        return []
    parts = partition_cause_nodes(eng)
    metrics = graph_partition_metrics(eng)
    out: list[ConceptProposal] = []

    # Each complementary partition pair → one opposite-state concept.
    pairs = [
        ("degree_high_vs_low", "degree_low", "partition:degree"),
        ("depth_deep", "depth_shallow", "partition:depth"),
    ]
    for left_key, right_key, tag in pairs:
        left = parts.get(left_key) or []
        right = parts.get(right_key) or []
        if not left or not right:
            continue
        # Seed tokens from member sets — open mint, not ROLE_AXES lookup.
        cause = mint_token("c:" + ",".join(left), syllables=2)
        effect = mint_token("e:" + ",".join(right), syllables=2)
        if normalize(cause) == normalize(effect):
            effect = mint_token("e2:" + ",".join(right) + cause, syllables=2)
        # Collision avoidance against closed alphabet.
        salt = 0
        while (
            normalize(cause) in alphabet
            or normalize(effect) in alphabet
            or is_bit_collapse_topic(cause)
            or is_bit_collapse_topic(effect)
        ) and salt < 8:
            salt += 1
            cause = mint_token(f"c{salt}:" + ",".join(left), syllables=2 + salt % 2)
            effect = mint_token(f"e{salt}:" + ",".join(right), syllables=2 + salt % 2)
        if normalize(cause) in alphabet or normalize(effect) in alphabet:
            continue
        if normalize(cause) == normalize(effect):
            continue
        instance = f"{normalize(cause)}-{normalize(effect)}"
        if normalize(instance) in used_instances or normalize(instance) in alphabet:
            continue
        # Reject legacy suffix-primitive lookalikes.
        if is_suffix_primitive_label(cause) or is_suffix_primitive_label(effect):
            continue
        # Reject legacy role-axis table labels (fecund/sparse/…).
        if is_role_axis_label(cause) or is_role_axis_label(effect):
            continue
        why = (
            f"concept:open-partition:{tag}:"
            f"left={len(left)},right={len(right)},"
            f"degree_split={metrics['degree_split']:.2f},"
            f"depth_split={metrics['depth_split']:.2f}"
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


# Backward-compatible alias used by older verify imports.
def graph_role_metrics(eng: Engine) -> dict[str, float]:
    return graph_partition_metrics(eng)
