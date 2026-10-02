"""Graph model for dual hemispheres + center.

Provisional hemisphere jobs (easy to rename later — outline still open):
  - cause: initiating / generative pole of an antonym pair
  - effect: reciprocal / consequent pole of that pair

Answers and center traces must always span both hemispheres.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class Hemisphere(str, Enum):
    CAUSE = "cause"
    EFFECT = "effect"

    @classmethod
    def other(cls, value: "Hemisphere") -> "Hemisphere":
        return cls.EFFECT if value is cls.CAUSE else cls.CAUSE


class CenterAction(str, Enum):
    """Center (the hole) — navigation / process moves, not bit-collapse."""

    REVIEW = "review"
    SYNTHESIZE = "synthesize"
    CHALLENGE = "challenge"
    EXPERIMENT = "experiment"
    ADD = "add"
    PRUNE = "prune"
    RETRIEVE = "retrieve"
    SAVE = "save"


@dataclass
class Node:
    """A named state living in one hemisphere, nested under a parent when branched."""

    name: str
    hemisphere: Hemisphere
    parent: Optional[str] = None  # parent node name (nesting)
    opposite: Optional[str] = None  # opposite-state link (required after add)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "hemisphere": self.hemisphere.value,
            "parent": self.parent,
            "opposite": self.opposite,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        return cls(
            name=data["name"],
            hemisphere=Hemisphere(data["hemisphere"]),
            parent=data.get("parent"),
            opposite=data.get("opposite"),
        )


@dataclass
class Torus:
    """Dual hemispheres + center metadata. Nodes are keyed by normalized name."""

    nodes: dict[str, Node] = field(default_factory=dict)
    # Center is not a node store — it is navigation over both hemispheres.
    center_log: list[dict[str, Any]] = field(default_factory=list)
    instance: str = "untitled"

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance": self.instance,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "center_log": list(self.center_log),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Torus":
        nodes = {
            k: Node.from_dict(v) for k, v in data.get("nodes", {}).items()
        }
        return cls(
            nodes=nodes,
            center_log=list(data.get("center_log", [])),
            instance=data.get("instance", "untitled"),
        )

    def as_jsonable(self) -> dict[str, Any]:
        return asdict(self)  # unused; prefer to_dict for enums
