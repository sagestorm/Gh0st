"""Core rules and graph operations for Beyond Binary AI.

Enforced:
  - no duplicates (normalized name)
  - orphan without opposite state must link opposite immediately
  - answers / center traces never from one hemisphere alone
  - merge + migrate for elegant mutable organization
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .model import CenterAction, Hemisphere, Node, Torus


class RuleError(ValueError):
    """Raised when a core principle would be violated."""


def normalize(name: str) -> str:
    key = re.sub(r"\s+", " ", name.strip().lower())
    if not key:
        raise RuleError("name must not be empty")
    return key


def display_name(name: str) -> str:
    return name.strip()


@dataclass
class DualAnswer:
    """An answer that always spans both hemispheres."""

    topic: str
    cause_paths: list[list[str]]
    effect_paths: list[list[str]]
    between: list[tuple[str, str]]  # opposite-state edges involved
    note: str


class Engine:
    def __init__(self, torus: Torus):
        self.torus = torus

    # --- queries ---------------------------------------------------------

    def get(self, name: str) -> Node:
        key = normalize(name)
        if key not in self.torus.nodes:
            raise RuleError(f"unknown node: {name!r}")
        return self.torus.nodes[key]

    def exists(self, name: str) -> bool:
        return normalize(name) in self.torus.nodes

    def children(self, name: str) -> list[Node]:
        key = normalize(name)
        return [n for n in self.torus.nodes.values() if n.parent == key]

    def path_to_root(self, name: str) -> list[str]:
        node = self.get(name)
        chain = [node.name]
        seen = {normalize(node.name)}
        while node.parent:
            if node.parent in seen:
                raise RuleError(f"cycle detected at {node.parent}")
            seen.add(node.parent)
            node = self.get(node.parent)
            chain.append(node.name)
        return list(reversed(chain))

    def orphans(self) -> list[Node]:
        return [n for n in self.torus.nodes.values() if not n.opposite]

    def assert_no_orphans(self) -> None:
        orphans = self.orphans()
        if orphans:
            names = ", ".join(n.name for n in orphans)
            raise RuleError(
                f"orphan without opposite state (link opposite immediately): {names}"
            )

    # --- mutations -------------------------------------------------------

    def add_pair(
        self,
        cause_name: str,
        effect_name: str,
        *,
        cause_parent: Optional[str] = None,
        effect_parent: Optional[str] = None,
    ) -> tuple[Node, Node]:
        """Add an antonym pair across hemispheres and link opposite states."""
        c_key = normalize(cause_name)
        e_key = normalize(effect_name)
        if c_key == e_key:
            raise RuleError("pair members must be distinct")
        if self.exists(c_key) or self.exists(e_key):
            raise RuleError(
                f"duplicate refused: {cause_name!r} or {effect_name!r} already exists; "
                "merge or migrate instead"
            )
        if cause_parent:
            parent = self.get(cause_parent)
            if parent.hemisphere is not Hemisphere.CAUSE:
                raise RuleError("cause-side parent must live in cause hemisphere")
        if effect_parent:
            parent = self.get(effect_parent)
            if parent.hemisphere is not Hemisphere.EFFECT:
                raise RuleError("effect-side parent must live in effect hemisphere")

        cause = Node(
            name=display_name(cause_name),
            hemisphere=Hemisphere.CAUSE,
            parent=normalize(cause_parent) if cause_parent else None,
            opposite=e_key,
        )
        effect = Node(
            name=display_name(effect_name),
            hemisphere=Hemisphere.EFFECT,
            parent=normalize(effect_parent) if effect_parent else None,
            opposite=c_key,
        )
        self.torus.nodes[c_key] = cause
        self.torus.nodes[e_key] = effect
        return cause, effect

    def add_under(
        self,
        parent: str,
        child: str,
        *,
        opposite: Optional[str] = None,
        opposite_parent: Optional[str] = None,
        opposite_name: Optional[str] = None,
    ) -> tuple[Node, Node]:
        """Add a node under a pole; must create/link opposite state immediately.

        If opposite already exists, link to it. Otherwise create opposite_name
        (default: 'not-<child>') on the other hemisphere under opposite_parent
        (default: parent's opposite).
        """
        parent_node = self.get(parent)
        child_key = normalize(child)
        if self.exists(child_key):
            raise RuleError(
                f"duplicate refused: {child!r} already exists; merge or migrate instead"
            )

        if opposite:
            opp = self.get(opposite)
            if opp.hemisphere is parent_node.hemisphere:
                raise RuleError("opposite must live in the other hemisphere")
            child_node = Node(
                name=display_name(child),
                hemisphere=parent_node.hemisphere,
                parent=normalize(parent),
                opposite=normalize(opposite),
            )
            self.torus.nodes[child_key] = child_node
            # ensure reciprocal link (may re-point; caller can migrate later)
            if opp.opposite and opp.opposite != child_key:
                raise RuleError(
                    f"{opposite!r} already has opposite {opp.opposite!r}; "
                    "migrate that link first"
                )
            opp.opposite = child_key
            return child_node, opp

        # Create opposite immediately (no orphan islands).
        if not parent_node.opposite:
            raise RuleError(
                f"parent {parent!r} has no opposite; cannot place child opposite"
            )
        opp_parent_key = (
            normalize(opposite_parent)
            if opposite_parent
            else parent_node.opposite
        )
        opp_parent = self.get(opp_parent_key)
        if opp_parent.hemisphere is parent_node.hemisphere:
            raise RuleError("opposite parent must be in the other hemisphere")

        auto_name = opposite_name or f"not-{display_name(child)}"
        opp_key = normalize(auto_name)
        if self.exists(opp_key):
            raise RuleError(
                f"duplicate refused for auto-opposite {auto_name!r}; "
                "pass --opposite to an existing node or choose another name"
            )

        child_node = Node(
            name=display_name(child),
            hemisphere=parent_node.hemisphere,
            parent=normalize(parent),
            opposite=opp_key,
        )
        opp_node = Node(
            name=display_name(auto_name),
            hemisphere=Hemisphere.other(parent_node.hemisphere),
            parent=opp_parent_key,
            opposite=child_key,
        )
        self.torus.nodes[child_key] = child_node
        self.torus.nodes[opp_key] = opp_node
        return child_node, opp_node

    def link_opposite(self, a: str, b: str) -> tuple[Node, Node]:
        """Link (or re-link after clearing) opposite states across hemispheres."""
        na, nb = self.get(a), self.get(b)
        if na.hemisphere is nb.hemisphere:
            raise RuleError("opposite-state link must cross hemispheres")
        # If either already linked to something else, refuse — use migrate.
        a_key, b_key = normalize(a), normalize(b)
        if na.opposite and na.opposite != b_key:
            raise RuleError(
                f"{a!r} already opposite {na.opposite!r}; use migrate-link"
            )
        if nb.opposite and nb.opposite != a_key:
            raise RuleError(
                f"{b!r} already opposite {nb.opposite!r}; use migrate-link"
            )
        na.opposite = b_key
        nb.opposite = a_key
        return na, nb

    def merge(self, source: str, target: str) -> Node:
        """Merge duplicate: retarget parents/opposites from source → target, drop source.

        If both nodes have distinct opposite states, those opposites are merged
        in the same step (equal-in/equal-out) so reciprocal links stay coherent.
        """
        src_key, tgt_key = normalize(source), normalize(target)
        if src_key == tgt_key:
            raise RuleError("cannot merge a node into itself")
        src, tgt = self.get(source), self.get(target)
        if src.hemisphere is not tgt.hemisphere:
            raise RuleError("merge only within the same hemisphere")

        if (
            src.opposite
            and tgt.opposite
            and src.opposite != tgt.opposite
        ):
            # Absorb opposite pair first (same hemisphere as each other).
            self._absorb(src.opposite, tgt.opposite)
            # Re-fetch target side after opposite absorb.
            src, tgt = self.get(source), self.get(target)

        return self._absorb(src_key, tgt_key)

    def _absorb(self, source: str, target: str) -> Node:
        src_key, tgt_key = normalize(source), normalize(target)
        src, tgt = self.get(source), self.get(target)
        if src.hemisphere is not tgt.hemisphere:
            raise RuleError("merge only within the same hemisphere")

        for node in self.torus.nodes.values():
            if node.parent == src_key:
                node.parent = tgt_key
            if node.opposite == src_key:
                node.opposite = tgt_key
        if not tgt.opposite and src.opposite and src.opposite != tgt_key:
            tgt.opposite = src.opposite
            # Keep reciprocal if the opposite still pointed at source.
            opp = self.torus.nodes.get(src.opposite)
            if opp and opp.opposite in (src_key, None):
                opp.opposite = tgt_key
        elif tgt.opposite:
            opp = self.torus.nodes.get(tgt.opposite)
            if opp:
                opp.opposite = tgt_key
        del self.torus.nodes[src_key]
        return tgt

    def migrate_link(
        self,
        name: str,
        *,
        new_parent: Optional[str] = None,
        new_opposite: Optional[str] = None,
    ) -> Node:
        """Proven migration: alter parent and/or opposite when a better link holds."""
        node = self.get(name)
        key = normalize(name)
        if new_parent is not None:
            if new_parent == "":
                node.parent = None
            else:
                parent = self.get(new_parent)
                if parent.hemisphere is not node.hemisphere:
                    raise RuleError("parent must stay in the same hemisphere")
                if normalize(new_parent) == key:
                    raise RuleError("node cannot be its own parent")
                node.parent = normalize(new_parent)
        if new_opposite is not None:
            opp = self.get(new_opposite)
            if opp.hemisphere is node.hemisphere:
                raise RuleError("opposite must cross hemispheres")
            old_opp_key = node.opposite
            new_key = normalize(new_opposite)
            # Clear reciprocal on old opposite if it pointed here.
            if old_opp_key and old_opp_key in self.torus.nodes:
                old = self.torus.nodes[old_opp_key]
                if old.opposite == key:
                    old.opposite = None  # briefly orphan — must re-link below
            node.opposite = new_key
            if opp.opposite and opp.opposite != key:
                # steal: clear the other side's old reciprocal
                other = self.torus.nodes.get(opp.opposite)
                if other and other.opposite == new_key:
                    other.opposite = None
            opp.opposite = key
            # If we orphaned someone, fail unless they got a new link.
            self.assert_no_orphans()
        return node

    # --- center + answers ------------------------------------------------

    def center(self, action: CenterAction, topic: Optional[str] = None) -> dict:
        """Record a center navigation act; always frames both hemispheres."""
        payload = {
            "action": action.value,
            "topic": topic,
            "cause_roots": [
                n.name
                for n in self.torus.nodes.values()
                if n.hemisphere is Hemisphere.CAUSE and n.parent is None
            ],
            "effect_roots": [
                n.name
                for n in self.torus.nodes.values()
                if n.hemisphere is Hemisphere.EFFECT and n.parent is None
            ],
        }
        if topic:
            # Dual-hemisphere requirement: refuse single-side framing.
            dual = self.answer(topic)
            payload["dual"] = {
                "cause_paths": dual.cause_paths,
                "effect_paths": dual.effect_paths,
                "between": dual.between,
                "note": dual.note,
            }
        self.torus.center_log.append(payload)
        return payload

    def answer(self, topic: str) -> DualAnswer:
        """Trace both hemisphere paths for a topic. Never one side only."""
        node = self.get(topic)
        if not node.opposite:
            raise RuleError(
                f"cannot answer from one hemisphere alone: {topic!r} has no opposite"
            )
        opp = self.get(node.opposite)
        cause_node = node if node.hemisphere is Hemisphere.CAUSE else opp
        effect_node = node if node.hemisphere is Hemisphere.EFFECT else opp
        cause_path = self.path_to_root(cause_node.name)
        effect_path = self.path_to_root(effect_node.name)
        # Also include direct children as shallow between-space hints.
        between: list[tuple[str, str]] = [(cause_node.name, effect_node.name)]
        for child in self.children(cause_node.name):
            if child.opposite:
                between.append((child.name, child.opposite))
        return DualAnswer(
            topic=node.name,
            cause_paths=[cause_path],
            effect_paths=[effect_path],
            between=between,
            note="Answer resides across both hemispheres; median is the center.",
        )

    def structure_lines(self) -> list[str]:
        out = [f"instance: {self.torus.instance}", "", "cause:"]
        out.extend(self._tree_lines(Hemisphere.CAUSE) or ["  (empty)"])
        out.append("")
        out.append("effect:")
        out.extend(self._tree_lines(Hemisphere.EFFECT) or ["  (empty)"])
        out.append("")
        out.append("opposite links:")
        seen: set[tuple[str, str]] = set()
        for n in sorted(self.torus.nodes.values(), key=lambda x: x.name.lower()):
            if not n.opposite:
                out.append(f"  {n.name} — ORPHAN")
                continue
            a, b = sorted([normalize(n.name), n.opposite])
            if (a, b) in seen:
                continue
            seen.add((a, b))
            other = self.torus.nodes[n.opposite].name
            out.append(f"  {n.name} ↔ {other}")
        return out

    def _tree_lines(self, hemisphere: Hemisphere) -> list[str]:
        roots = [
            n
            for n in self.torus.nodes.values()
            if n.hemisphere is hemisphere and n.parent is None
        ]
        roots.sort(key=lambda n: n.name.lower())
        lines: list[str] = []

        def walk(node: Node, depth: int) -> None:
            opp = f" ↔ {node.opposite}" if node.opposite else " ↔ ?"
            lines.append("  " * depth + f"- {node.name}{opp}")
            kids = sorted(self.children(node.name), key=lambda n: n.name.lower())
            for kid in kids:
                walk(kid, depth + 1)

        for root in roots:
            walk(root, 1)
        return lines
