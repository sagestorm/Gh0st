"""Mutable capability programs — forms interpret evolved op lists.

Body specialty is not a pole-name template. Each body persists a CapProgram
(JSON ops + macros). Experience can *synthesize* new opcodes as microprograms
(data definitions over a primitive ISA), not only select from a hand-authored
handler table.
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


# Primitive ISA — small fixed base. New opcodes are macros over these.
_PRIMITIVE_OPS: dict[str, Callable[..., Any]] = {}
# Synthesized opcodes: name → microprogram body (list of primitive steps).
_MACRO_DEFS: dict[str, list[dict[str, Any]]] = {}
# Unified dispatch (primitives + installed macros).
_OPCODE_IMPLS: dict[str, Callable[..., Any]] = {}


def register_opcode(name: str, fn: Callable[..., Any]) -> None:
    _OPCODE_IMPLS[name] = fn


def known_opcodes() -> set[str]:
    return set(_OPCODE_IMPLS)


def known_macros() -> dict[str, list[dict[str, Any]]]:
    return dict(_MACRO_DEFS)


def _register_primitive(name: str, fn: Callable[..., Any]) -> None:
    _PRIMITIVE_OPS[name] = fn
    register_opcode(name, fn)


@dataclass
class CapProgram:
    body_name: str
    ops: list[dict[str, Any]] = field(default_factory=list)
    program_id: str = field(default_factory=lambda: f"cap-{uuid.uuid4().hex[:8]}")
    revisions: int = 0
    # Per-program synthesized opcode definitions (persisted with the body).
    macros: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "body_name": self.body_name,
            "ops": list(self.ops),
            "revisions": self.revisions,
            "macros": {k: list(v) for k, v in self.macros.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapProgram":
        return cls(
            body_name=str(data.get("body_name", "")),
            ops=list(data.get("ops") or []),
            program_id=str(data.get("program_id") or f"cap-{uuid.uuid4().hex[:8]}"),
            revisions=int(data.get("revisions", 0) or 0),
            macros={
                str(k): list(v)
                for k, v in (data.get("macros") or {}).items()
            },
        )


def capability_path(body_store: Path | str | None) -> Path:
    target = store.store_path(body_store)
    return target.with_name(f"{target.stem}.capability.json")


def load_program(body_store: Path | str | None) -> CapProgram:
    path = capability_path(body_store)
    if not path.exists():
        return CapProgram(body_name=store.store_path(body_store).stem)
    program = CapProgram.from_dict(json.loads(path.read_text(encoding="utf-8")))
    # Reinstall macros into the runtime registry after load.
    for name, body in program.macros.items():
        install_macro(name, body)
    return program


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


def _op_ratio(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    a = str(args.get("a", "n_children_cause"))
    b = str(args.get("b", "node_count"))
    into = str(args.get("into", "ratio"))
    scalars = ctx.setdefault("scalars", {})
    denom = float(scalars.get(b, 0))
    scalars[into] = float(scalars.get(a, 0)) / denom if denom else 0.0


def _op_count_nodes(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    eng: Engine = ctx["eng"]
    ctx.setdefault("scalars", {})["node_count"] = len(eng.torus.nodes)


def _op_count_attr(ctx: dict[str, Any], args: dict[str, Any]) -> None:
    """Generic counter — attr selects which structural set to size."""
    eng: Engine = ctx["eng"]
    attr = str(args.get("attr", "nodes"))
    into = str(args.get("into", f"count_{attr}"))
    if attr == "orphans":
        n = len(eng.orphans())
    elif attr == "leaves":
        n = sum(1 for node in eng.torus.nodes.values() if not eng.children(node.name))
    elif attr == "cause_nodes":
        n = sum(
            1
            for node in eng.torus.nodes.values()
            if node.hemisphere is Hemisphere.CAUSE
        )
    elif attr == "effect_nodes":
        n = sum(
            1
            for node in eng.torus.nodes.values()
            if node.hemisphere is Hemisphere.EFFECT
        )
    else:
        n = len(eng.torus.nodes)
    ctx.setdefault("scalars", {})[into] = n


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


# Register primitive ISA.
_register_primitive("measure_children", _op_measure_children)
_register_primitive("measure_depth", _op_measure_depth)
_register_primitive("dual_answer", _op_dual_answer)
_register_primitive("diff", _op_diff)
_register_primitive("ratio", _op_ratio)
_register_primitive("count_nodes", _op_count_nodes)
_register_primitive("count_attr", _op_count_attr)
_register_primitive("emit", _op_emit)


def _run_steps(ctx: dict[str, Any], steps: list[dict[str, Any]]) -> None:
    for step in steps:
        op = str(step.get("op", ""))
        # Prefer primitive for macro bodies to avoid accidental recursion.
        impl = _PRIMITIVE_OPS.get(op) or _OPCODE_IMPLS.get(op)
        if impl is None:
            continue
        impl(ctx, step)


def install_macro(name: str, body: list[dict[str, Any]]) -> None:
    """Install a synthesized opcode whose semantics are a microprogram (data)."""
    _MACRO_DEFS[name] = list(body)

    def _macro_impl(ctx: dict[str, Any], args: dict[str, Any]) -> None:
        _run_steps(ctx, _MACRO_DEFS[name])

    register_opcode(name, _macro_impl)


def synthesize_opcode(
    program: CapProgram,
    name: str,
    body: list[dict[str, Any]],
) -> bool:
    """Define a new opcode from experience as a macro; return True if new/changed."""
    # Only primitive ops allowed inside macro bodies (closed meta-ISA, open macros).
    for step in body:
        op = str(step.get("op", ""))
        if op not in _PRIMITIVE_OPS:
            return False
    prev = program.macros.get(name)
    if prev == body and name in _OPCODE_IMPLS:
        return False
    program.macros[name] = list(body)
    install_macro(name, body)
    return True


def initial_program_for(eng: Engine, body_name: str) -> CapProgram:
    """Build a starting program from live structure — not a fixed specialty string."""
    cause, effect = _roots(eng)
    ops: list[dict[str, Any]] = [
        {"op": "count_nodes"},
        {"op": "measure_children", "pole": "cause"},
        {"op": "measure_children", "pole": "effect"},
    ]
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
            "fields": [
                "node_count",
                "gradient",
                "n_children_cause",
                "n_children_effect",
                "dual",
            ],
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


def _insert_before_emit(program: CapProgram, step: dict[str, Any]) -> None:
    emit_i = next(
        (i for i, o in enumerate(program.ops) if o.get("op") == "emit"),
        len(program.ops),
    )
    program.ops.insert(emit_i, step)


def _ensure_emit_field(program: CapProgram, field: str) -> None:
    for o in program.ops:
        if o.get("op") == "emit":
            fields = list(o.get("fields") or [])
            if field not in fields:
                fields.append(field)
                o["fields"] = fields


def evolve_program(program: CapProgram, eng: Engine) -> CapProgram:
    """Synthesize new opcodes as macros from structural pressure — experience growth."""
    # Reinstall any persisted macros.
    for name, body in program.macros.items():
        install_macro(name, body)

    op_names = {o.get("op") for o in program.ops}
    changed = False

    orphans = [n.name for n in eng.orphans()]
    if orphans and "syn_orphan_pressure" not in op_names:
        # Synthesize: count orphans via generic count_attr — no hand-written handler.
        body = [
            {"op": "count_attr", "attr": "orphans", "into": "orphan_count"},
        ]
        if synthesize_opcode(program, "syn_orphan_pressure", body):
            _insert_before_emit(program, {"op": "syn_orphan_pressure"})
            _ensure_emit_field(program, "orphan_count")
            program.revisions += 1
            changed = True

    deep = any(_depth_safe(eng, n.name) >= 3 for n in eng.torus.nodes.values())
    if deep and "syn_leaf_load" not in op_names:
        body = [
            {"op": "count_attr", "attr": "leaves", "into": "leaf_count"},
            {"op": "count_nodes"},
            {
                "op": "ratio",
                "a": "leaf_count",
                "b": "node_count",
                "into": "leaf_ratio",
            },
        ]
        if synthesize_opcode(program, "syn_leaf_load", body):
            _insert_before_emit(program, {"op": "syn_leaf_load"})
            _ensure_emit_field(program, "leaf_count")
            _ensure_emit_field(program, "leaf_ratio")
            program.revisions += 1
            changed = True

    # Asymmetry macro when poles diverge.
    cause, effect = _roots(eng)
    if (
        cause
        and effect
        and _child_count_safe(eng, cause) != _child_count_safe(eng, effect)
        and "syn_pole_asymmetry" not in op_names
    ):
        body = [
            {"op": "measure_children", "pole": "cause"},
            {"op": "measure_children", "pole": "effect"},
            {
                "op": "diff",
                "a": "n_children_cause",
                "b": "n_children_effect",
                "into": "pole_asymmetry",
            },
            {"op": "count_nodes"},
            {
                "op": "ratio",
                "a": "pole_asymmetry",
                "b": "node_count",
                "into": "asymmetry_ratio",
            },
        ]
        if synthesize_opcode(program, "syn_pole_asymmetry", body):
            _insert_before_emit(program, {"op": "syn_pole_asymmetry"})
            _ensure_emit_field(program, "pole_asymmetry")
            _ensure_emit_field(program, "asymmetry_ratio")
            program.revisions += 1
            changed = True

    # Hemisphere balance — synthesizable on any dual graph (experience baseline).
    if len(eng.torus.nodes) >= 2 and "syn_hemisphere_balance" not in op_names:
        body = [
            {"op": "count_attr", "attr": "cause_nodes", "into": "cause_count"},
            {"op": "count_attr", "attr": "effect_nodes", "into": "effect_count"},
            {
                "op": "diff",
                "a": "cause_count",
                "b": "effect_count",
                "into": "hemisphere_delta",
            },
        ]
        if synthesize_opcode(program, "syn_hemisphere_balance", body):
            _insert_before_emit(program, {"op": "syn_hemisphere_balance"})
            _ensure_emit_field(program, "hemisphere_delta")
            _ensure_emit_field(program, "cause_count")
            _ensure_emit_field(program, "effect_count")
            program.revisions += 1
            changed = True

    return program


def interpret(program: CapProgram, eng: Engine) -> dict[str, Any]:
    """Run the body's capability program (primitives + synthesized macros)."""
    for name, body in program.macros.items():
        install_macro(name, body)
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
        "macros": sorted(program.macros.keys()),
        "cause_pole": cause,
        "effect_pole": effect,
        "result": ctx.get("emit") or {},
        "capability": "interpret_program",
    }
