"""Mutable capability programs — forms interpret evolved op lists.

Body specialty is not a pole-name template function body. Each body persists a
capability program (JSON ops). The form runs an interpreter over that program.
Programs can gain ops from structural pressure (evolve_program).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .engine import Engine, normalize
from .model import Hemisphere
from . import store


# Seed opcodes — registry can grow at runtime via register_opcode.
_OPCODE_IMPLS: dict[str, Callable[..., Any]] = {}


def register_opcode(name: str, fn: Callable[..., Any]) -> None:
    _OPCODE_IMPLS[name] = fn


def known_opcodes() -> set[str]:
    return set(_OPCODE_IMPLS)


@dataclass
class CapProgram:
    body_name: str
    ops: list[dict[str, Any]] = field(default_factory=list)
    program_id: str = field(default_factory=lambda: f"cap-{uuid.uuid4().hex[:8]}")
    revisions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "body_name": self.body_name,
            "ops": list(self.ops),
            "revisions": self.revisions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapProgram":
        return cls(
            body_name=str(data.get("body_name", "")),
            ops=list(data.get("ops") or []),
            program_id=str(data.get("program_id") or f"cap-{uuid.uuid4().hex[:8]}"),
            revisions=int(data.get("revisions", 0) or 0),
        )


def capability_path(body_store: Path | str | None) -> Path:
    target = store.store_path(body_store)
    return target.with_name(f"{target.stem}.capability.json")


def load_program(body_store: Path | str | None) -> CapProgram:
    path = capability_path(body_store)
    if not path.exists():
        return CapProgram(body_name=store.store_path(body_store).stem)
    return CapProgram.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_program(program: CapProgram, body_store: Path | str | None) -> Path:
    path = capability_path(body_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(program.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _roots(eng: Engine) -> tuple[str, str]:
    roots_c = [
        n.name
        for n in eng.torus.nodes.values()
        if n.parent is None and n.hemisphere is Hemisphere.CAUSE
    ]
    roots_e = [
        n.name
        for n in eng.torus.nodes.values()
        if n.parent is None and n.hemisphere is Hemisphere.EFFECT
    ]
    cause = roots_c[0] if roots_c else ""
    effect = roots_e[0] if roots_e else ""
    if roots_c:
        node = eng.get(roots_c[0])
        if node.opposite and eng.torus.nodes.get(node.opposite):
            effect = eng.torus.nodes[node.opposite].name
    return cause, effect


def _op_measure_children(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    eng: Engine = ctx["eng"]
    pole = args.get("pole", "cause")
    cause, effect = ctx["cause"], ctx["effect"]
    name = cause if pole == "cause" else effect
    kids = [c.name for c in eng.children(name)] if name else []
    ctx.setdefault("measures", {})[f"children_{pole}"] = kids
    ctx.setdefault("scalars", {})[f"n_children_{pole}"] = len(kids)


def _op_measure_depth(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    eng: Engine = ctx["eng"]
    pole = args.get("pole", "cause")
    cause, effect = ctx["cause"], ctx["effect"]
    name = cause if pole == "cause" else effect
    depth = 0
    if name and eng.exists(name):
        depth = max(0, len(eng.path_to_root(name)) - 1)
    ctx.setdefault("scalars", {})[f"depth_{pole}"] = depth


def _op_dual_answer(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    eng: Engine = ctx["eng"]
    topic = args.get("topic") or ctx["cause"]
    if topic and eng.exists(topic):
        dual = eng.answer(topic)
        ctx["dual"] = {
            "topic": dual.topic,
            "cause_paths": dual.cause_paths,
            "effect_paths": dual.effect_paths,
        }


def _op_diff(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    a = str(args.get("a", "n_children_cause"))
    b = str(args.get("b", "n_children_effect"))
    into = str(args.get("into", "gradient"))
    scalars = ctx.setdefault("scalars", {})
    scalars[into] = float(scalars.get(a, 0)) - float(scalars.get(b, 0))


def _op_count_nodes(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    eng: Engine = ctx["eng"]
    ctx.setdefault("scalars", {})["node_count"] = len(eng.torus.nodes)


def _op_emit(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    fields = list(args.get("fields") or ["gradient", "node_count"])
    out = ctx.setdefault("emit", {})
    scalars = ctx.get("scalars") or {}
    for f in fields:
        if f in scalars:
            out[f] = scalars[f]
        elif f == "dual" and "dual" in ctx:
            out["dual"] = ctx["dual"]
        elif f in (ctx.get("measures") or {}):
            out[f] = ctx["measures"][f]


# Register seed opcodes.
register_opcode("measure_children", _op_measure_children)
register_opcode("measure_depth", _op_measure_depth)
register_opcode("dual_answer", _op_dual_answer)
register_opcode("diff", _op_diff)
register_opcode("count_nodes", _op_count_nodes)
register_opcode("emit", _op_emit)


def initial_program_for(eng: Engine, body_name: str) -> CapProgram:
    """Build a starting program from live structure — not a fixed specialty string."""
    cause, effect = _roots(eng)
    ops: list[dict[str, Any]] = [
        {"op": "count_nodes"},
        {"op": "measure_children", "pole": "cause"},
        {"op": "measure_children", "pole": "effect"},
    ]
    # Structural pressure chooses extra ops (data-driven, not pole-name template).
    if cause and _child_count_safe(eng, cause) != _child_count_safe(eng, effect):
        ops.append(
            {
                "op": "diff",
                "a": "n_children_cause",
                "b": "n_children_effect",
                "into": "gradient",
            }
        )
    if any(_depth_safe(eng, n.name) >= 2 for n in eng.torus.nodes.values()):
        ops.append({"op": "measure_depth", "pole": "cause"})
        ops.append({"op": "measure_depth", "pole": "effect"})
    if cause:
        ops.append({"op": "dual_answer", "topic": cause})
    ops.append(
        {
            "op": "emit",
            "fields": ["node_count", "gradient", "n_children_cause", "n_children_effect", "dual"],
        }
    )
    return CapProgram(body_name=body_name, ops=ops, revisions=0)


def _child_count_safe(eng: Engine, name: str) -> int:
    if not name or not eng.exists(name):
        return 0
    return len(eng.children(name))


def _depth_safe(eng: Engine, name: str) -> int:
    try:
        return max(0, len(eng.path_to_root(name)) - 1)
    except Exception:  # noqa: BLE001
        return 0


def evolve_program(program: CapProgram, eng: Engine) -> CapProgram:
    """Append ops when structure suggests new measurements — grows per body."""
    op_names = {o.get("op") for o in program.ops}
    changed = False
    # If orphans appear, register + use a new opcode dynamically.
    orphans = [n.name for n in eng.orphans()]
    if orphans and "count_orphans" not in op_names:
        if "count_orphans" not in _OPCODE_IMPLS:

            def _count_orphans(ctx: dict[str, Any], args: dict[str, Any]) -> None:
                e: Engine = ctx["eng"]
                ctx.setdefault("scalars", {})["orphan_count"] = len(e.orphans())

            register_opcode("count_orphans", _count_orphans)
        # Insert before emit.
        emit_i = next(
            (i for i, o in enumerate(program.ops) if o.get("op") == "emit"),
            len(program.ops),
        )
        program.ops.insert(emit_i, {"op": "count_orphans"})
        # Ensure emit includes the new field.
        for o in program.ops:
            if o.get("op") == "emit":
                fields = list(o.get("fields") or [])
                if "orphan_count" not in fields:
                    fields.append("orphan_count")
                    o["fields"] = fields
        program.revisions += 1
        changed = True
    # Deep graphs gain leaf-count op.
    if (
        any(_depth_safe(eng, n.name) >= 3 for n in eng.torus.nodes.values())
        and "count_leaves" not in op_names
    ):
        if "count_leaves" not in _OPCODE_IMPLS:

            def _count_leaves(ctx: dict[str, Any], args: dict[str, Any]) -> None:
                e: Engine = ctx["eng"]
                leaves = [
                    n.name
                    for n in e.torus.nodes.values()
                    if not e.children(n.name)
                ]
                ctx.setdefault("scalars", {})["leaf_count"] = len(leaves)

            register_opcode("count_leaves", _count_leaves)
        emit_i = next(
            (i for i, o in enumerate(program.ops) if o.get("op") == "emit"),
            len(program.ops),
        )
        program.ops.insert(emit_i, {"op": "count_leaves"})
        for o in program.ops:
            if o.get("op") == "emit":
                fields = list(o.get("fields") or [])
                if "leaf_count" not in fields:
                    fields.append("leaf_count")
                    o["fields"] = fields
        program.revisions += 1
        changed = True
    if changed:
        return program
    return program


def interpret(program: CapProgram, eng: Engine) -> dict[str, Any]:
    """Run the body's capability program."""
    cause, effect = _roots(eng)
    ctx: dict[str, Any] = {
        "eng": eng,
        "cause": cause,
        "effect": effect,
        "scalars": {},
        "measures": {},
        "emit": {},
    }
    for step in program.ops:
        op = str(step.get("op", ""))
        impl = _OPCODE_IMPLS.get(op)
        if impl is None:
            continue
        impl(ctx, step)
    return {
        "program_id": program.program_id,
        "body": program.body_name,
        "revisions": program.revisions,
        "ops": [o.get("op") for o in program.ops],
        "cause_pole": cause,
        "effect_pole": effect,
        "result": ctx.get("emit") or {},
        "capability": "interpret_program",
    }
