"""Invariant-preserving topology invent — bridge / re-parent across domains.

Searches graph edits that change attachment structure (not only labels).
Each candidate is validated on a cloned engine: dual links + no orphans.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from .engine import Engine, RuleError, normalize
from .model import Hemisphere, Torus
from . import lexicon


@dataclass(frozen=True)
class TopologyEdit:
    kind: str  # bridge | reparent
    cause: str
    effect: str
    cause_parent: str
    effect_parent: str
    domain_from: str
    domain_to: str
    why: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "cause": self.cause,
            "effect": self.effect,
            "cause_parent": self.cause_parent,
            "effect_parent": self.effect_parent,
            "domain_from": self.domain_from,
            "domain_to": self.domain_to,
            "why": self.why,
        }


def _clone_engine(eng: Engine) -> Engine:
    data = eng.torus.to_dict()
    return Engine(Torus.from_dict(copy.deepcopy(data)))


def _domain_of(name: str, domains_present: set[str]) -> str | None:
    key = normalize(name)
    for domain, (a, b) in lexicon.DOMAIN_POLES.items():
        if domain not in domains_present:
            continue
        if key in {normalize(a), normalize(b)}:
            return domain
        # Cascade members belong to their domain.
        for entry in lexicon.DOMAIN_CASCADES.get(domain, ()):
            if key in {
                normalize(entry.cause),
                normalize(entry.effect),
                normalize(entry.cause_parent),
                normalize(entry.effect_parent),
            }:
                return domain
    # Walk parents? handled by caller via root domain.
    return None


def _root_domain(eng: Engine, name: str, domains: set[str]) -> str | None:
    try:
        path = eng.path_to_root(name)
    except Exception:  # noqa: BLE001
        return _domain_of(name, domains)
    for part in path:
        d = _domain_of(part, domains)
        if d:
            return d
    return _domain_of(name, domains)


def _digest_label(prefix: str, parts: list[str]) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}{h}"


def _validate_dual(eng: Engine) -> bool:
    try:
        eng.assert_no_orphans()
    except RuleError:
        return False
    # Spot-check a few nodes for dual answers.
    checked = 0
    for node in eng.torus.nodes.values():
        if node.hemisphere is not Hemisphere.CAUSE:
            continue
        try:
            dual = eng.answer(node.name)
        except RuleError:
            return False
        if not dual.cause_paths or not dual.effect_paths:
            return False
        checked += 1
        if checked >= 4:
            break
    return checked > 0


def _apply_bridge(eng: Engine, edit: TopologyEdit) -> bool:
    try:
        eng.add_pair(
            edit.cause,
            edit.effect,
            cause_parent=edit.cause_parent,
            effect_parent=edit.effect_parent,
        )
    except RuleError:
        return False
    return _validate_dual(eng)


def _apply_reparent(eng: Engine, edit: TopologyEdit) -> bool:
    """Re-parent an existing dual pair under cross-domain parents."""
    if not eng.exists(edit.cause) or not eng.exists(edit.effect):
        return False
    try:
        eng.migrate_link(edit.cause, new_parent=edit.cause_parent)
        eng.migrate_link(edit.effect, new_parent=edit.effect_parent)
    except RuleError:
        return False
    return _validate_dual(eng)


def apply_topology_edit(eng: Engine, edit: TopologyEdit | dict[str, Any]) -> bool:
    """Apply a validated edit to a live engine. Returns success."""
    if isinstance(edit, dict):
        edit = TopologyEdit(
            kind=str(edit.get("kind", "bridge")),
            cause=str(edit["cause"]),
            effect=str(edit["effect"]),
            cause_parent=str(edit["cause_parent"]),
            effect_parent=str(edit["effect_parent"]),
            domain_from=str(edit.get("domain_from", "")),
            domain_to=str(edit.get("domain_to", "")),
            why=str(edit.get("why", "")),
        )
    if edit.kind == "bridge":
        return _apply_bridge(eng, edit)
    if edit.kind == "reparent":
        return _apply_reparent(eng, edit)
    return False


def search_topology_edits(
    eng: Engine,
    *,
    alphabet: set[str],
    used_instances: set[str],
    limit: int = 4,
) -> list[TopologyEdit]:
    """Search cross-domain bridge and re-parent edits; keep only invariant-safe ones."""
    names = set(eng.torus.nodes)
    domains = lexicon.detect_domains(names)
    if len(domains) < 2:
        return []

    # Collect cause nodes with duals, tagged by domain.
    cause_nodes: list[tuple[str, str, str]] = []  # name, opposite, domain
    for node in eng.torus.nodes.values():
        if node.hemisphere is not Hemisphere.CAUSE:
            continue
        if not node.opposite or node.opposite not in eng.torus.nodes:
            continue
        dom = _root_domain(eng, node.name, domains)
        if not dom:
            continue
        cause_nodes.append((node.name, eng.torus.nodes[node.opposite].name, dom))

    # Anchors: domain roots PLUS non-root dual pairs (open beyond pole-only search).
    anchors: dict[str, list[tuple[str, str]]] = {}
    for domain in domains:
        a, b = lexicon.DOMAIN_POLES[domain]
        if eng.exists(a) and eng.exists(b):
            anchors.setdefault(domain, []).append((a, b))
    for name, opp, dom in cause_nodes:
        if dom not in domains:
            continue
        node = eng.get(name)
        if node.parent is None:
            continue  # roots already covered
        pair = (name, opp)
        bucket = anchors.setdefault(dom, [])
        if pair not in bucket:
            bucket.append(pair)

    if len(anchors) < 2:
        return []

    out: list[TopologyEdit] = []
    domain_list = sorted(anchors.keys())

    # --- Bridge search: new dual under parents from a *different* domain ---
    for i, d_from in enumerate(domain_list):
        for d_to in domain_list[i + 1 :]:
            for cp, ep in anchors[d_to][:3]:  # try several anchors, not only poles
                label_parts = [
                    "bridge",
                    d_from,
                    d_to,
                    normalize(cp),
                    normalize(ep),
                    str(len(eng.torus.nodes)),
                ]
                sample = next((n for n, _, d in cause_nodes if d == d_from), None)
                if sample:
                    label_parts.append(normalize(sample))
                cause = _digest_label("tb", label_parts + ["c"])
                effect = _digest_label("te", label_parts + ["e"])
                if normalize(cause) in alphabet or normalize(effect) in alphabet:
                    continue
                instance = f"{normalize(cause)}-{normalize(effect)}"
                if normalize(instance) in used_instances:
                    continue
                why = (
                    f"topology:bridge:from={d_from},to={d_to},"
                    f"under={normalize(cp)}/{normalize(ep)}"
                )
                edit = TopologyEdit(
                    kind="bridge",
                    cause=cause,
                    effect=effect,
                    cause_parent=cp,
                    effect_parent=ep,
                    domain_from=d_from,
                    domain_to=d_to,
                    why=why,
                )
                trial = _clone_engine(eng)
                if _apply_bridge(trial, edit):
                    out.append(edit)
                if len(out) >= limit:
                    return out

    # --- Re-parent: move a non-root dual under another domain's anchor ---
    for name, opp, d_from in cause_nodes:
        node = eng.get(name)
        if node.parent is None:
            continue
        for d_to, pairs in anchors.items():
            if d_to == d_from:
                continue
            for cp, ep in pairs[:3]:
                if normalize(node.parent or "") == normalize(cp):
                    continue
                if normalize(name) == normalize(cp):
                    continue
                why = (
                    f"topology:reparent:node={normalize(name)},"
                    f"from={d_from},to={d_to},under={normalize(cp)}"
                )
                edit = TopologyEdit(
                    kind="reparent",
                    cause=name,
                    effect=opp,
                    cause_parent=cp,
                    effect_parent=ep,
                    domain_from=d_from,
                    domain_to=d_to,
                    why=why,
                )
                trial = _clone_engine(eng)
                if _apply_reparent(trial, edit):
                    out.append(edit)
                if len(out) >= limit:
                    return out

    return out


def edits_to_proposals(
    edits: list[TopologyEdit],
    *,
    used_instances: set[str],
) -> list[dict[str, Any]]:
    """Convert edits into invent-shaped proposals (cause/effect/instance/edit)."""
    proposals: list[dict[str, Any]] = []
    for edit in edits:
        if edit.kind == "bridge":
            instance = f"{normalize(edit.cause)}-{normalize(edit.effect)}"
            cause, effect = edit.cause, edit.effect
        else:
            # Re-parent keeps poles; invent identity is the attachment change.
            digest = _digest_label(
                "tr",
                [
                    normalize(edit.cause),
                    normalize(edit.cause_parent),
                    edit.domain_from,
                    edit.domain_to,
                ],
            )
            instance = f"reparent-{digest}"
            cause, effect = edit.cause, edit.effect
        if normalize(instance) in used_instances:
            continue
        proposals.append(
            {
                "cause": cause,
                "effect": effect,
                "instance": instance,
                "source": "topology",
                "why": edit.why,
                "edit": edit.to_dict(),
            }
        )
    return proposals
