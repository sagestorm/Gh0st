"""Mutable capability programs — forms interpret evolved op lists.

Body specialty is not a pole-name template. Each body persists a CapProgram
(JSON ops + macros + proposed primitives). Experience can synthesize macros
over the seed ISA **and** propose new *primitive* ops (compiled graph-query
handlers installed into the primitive registry) validated against dual invariants.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .engine import Engine, RuleError, normalize
from .model import Hemisphere
from . import store


# Seed primitive ISA — fixed at boot. Bodies may add prim_* via propose_primitive.
_PRIMITIVE_OPS: dict[str, Callable[..., Any]] = {}
_SEED_PRIMITIVES: set[str] = set()
# Proposed primitive specs: name → declarative query spec (not macro bodies).
_PRIMITIVE_SPECS: dict[str, dict[str, Any]] = {}
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


def seed_primitives() -> set[str]:
    return set(_SEED_PRIMITIVES)


def known_primitive_specs() -> dict[str, dict[str, Any]]:
    return dict(_PRIMITIVE_SPECS)


def _register_primitive(name: str, fn: Callable[..., Any], *, seed: bool = True) -> None:
    _PRIMITIVE_OPS[name] = fn
    register_opcode(name, fn)
    if seed:
        _SEED_PRIMITIVES.add(name)


@dataclass
class CapProgram:
    body_name: str
    ops: list[dict[str, Any]] = field(default_factory=list)
    program_id: str = field(default_factory=lambda: f"cap-{uuid.uuid4().hex[:8]}")
    revisions: int = 0
    # Per-program synthesized opcode definitions (persisted with the body).
    macros: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # Body-proposed primitives: name → query spec (installed into _PRIMITIVE_OPS).
    primitives: dict[str, dict[str, Any]] = field(default_factory=dict)
    primitive_revisions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "body_name": self.body_name,
            "ops": list(self.ops),
            "revisions": self.revisions,
            "macros": {k: list(v) for k, v in self.macros.items()},
            "primitives": {k: dict(v) for k, v in self.primitives.items()},
            "primitive_revisions": self.primitive_revisions,
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
            primitives={
                str(k): dict(v)
                for k, v in (data.get("primitives") or {}).items()
            },
            primitive_revisions=int(data.get("primitive_revisions", 0) or 0),
        )


def capability_path(body_store: Path | str | None) -> Path:
    target = store.store_path(body_store)
    return target.with_name(f"{target.stem}.capability.json")


def load_program(body_store: Path | str | None) -> CapProgram:
    path = capability_path(body_store)
    if not path.exists():
        return CapProgram(body_name=store.store_path(body_store).stem)
    program = CapProgram.from_dict(json.loads(path.read_text(encoding="utf-8")))
    # Reinstall macros + proposed primitives into the runtime registry after load.
    for name, body in program.macros.items():
        install_macro(name, body)
    for name, spec in program.primitives.items():
        install_primitive(name, spec)
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
    # Macro bodies may use seed + proposed primitives (not other macros).
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


def _reduce_values(values: list[float], how: str) -> float:
    if not values:
        return 0.0
    if how == "min":
        return float(min(values))
    if how == "sum":
        return float(sum(values))
    if how == "mean":
        return float(sum(values) / len(values))
    return float(max(values))  # max default


def compile_primitive_spec(spec: dict[str, Any]) -> Callable[..., Any] | None:
    """Compile a declarative graph-query spec into a primitive handler.

    Unlike macros (sequences of existing ops), this produces a *new* primitive
    implementation measuring graph structure the seed ISA does not name.
    """
    kind = str(spec.get("kind", ""))
    into = str(spec.get("into", "prim_out"))

    if kind == "reduce_path":
        select = str(spec.get("select", "depth"))
        over = str(spec.get("over", "dual_causes"))
        reduce = str(spec.get("reduce", "max"))

        def _reduce_path(ctx: dict[str, Any], args: dict[str, Any]) -> None:
            eng: Engine = ctx["eng"]
            values: list[float] = []
            for node in eng.torus.nodes.values():
                if over == "dual_causes":
                    if node.hemisphere is not Hemisphere.CAUSE or not node.opposite:
                        continue
                elif over == "all_causes":
                    if node.hemisphere is not Hemisphere.CAUSE:
                        continue
                elif over == "all_nodes":
                    pass
                else:
                    continue
                if select == "depth":
                    values.append(float(_depth_safe(eng, node.name)))
                elif select == "child_count":
                    values.append(float(_child_count_safe(eng, node.name)))
                elif select == "path_len":
                    try:
                        values.append(float(len(eng.path_to_root(node.name))))
                    except Exception:  # noqa: BLE001
                        values.append(0.0)
            ctx.setdefault("scalars", {})[into] = _reduce_values(values, reduce)

        return _reduce_path

    if kind == "pair_metric":
        metric = str(spec.get("metric", "parent_depth_gap"))

        def _pair_metric(ctx: dict[str, Any], args: dict[str, Any]) -> None:
            eng: Engine = ctx["eng"]
            gaps: list[float] = []
            for node in eng.torus.nodes.values():
                if node.hemisphere is not Hemisphere.CAUSE or not node.opposite:
                    continue
                opp = eng.torus.nodes.get(node.opposite)
                if opp is None:
                    continue
                if metric == "parent_depth_gap":
                    gaps.append(
                        abs(
                            float(_depth_safe(eng, node.name))
                            - float(_depth_safe(eng, opp.name))
                        )
                    )
                elif metric == "child_delta":
                    gaps.append(
                        abs(
                            float(_child_count_safe(eng, node.name))
                            - float(_child_count_safe(eng, opp.name))
                        )
                    )
            ctx.setdefault("scalars", {})[into] = _reduce_values(gaps, "max")

        return _pair_metric

    if kind == "branch_fanout":
        hemi = str(spec.get("hemisphere", "cause"))

        def _fanout(ctx: dict[str, Any], args: dict[str, Any]) -> None:
            eng: Engine = ctx["eng"]
            target = (
                Hemisphere.CAUSE if hemi == "cause" else Hemisphere.EFFECT
            )
            fans = [
                float(_child_count_safe(eng, n.name))
                for n in eng.torus.nodes.values()
                if n.hemisphere is target
            ]
            ctx.setdefault("scalars", {})[into] = _reduce_values(fans, "max")

        return _fanout

    return None


def install_primitive(name: str, spec: dict[str, Any]) -> bool:
    """Install a proposed primitive into the primitive registry (not as a macro)."""
    if not name.startswith("prim_"):
        return False
    if name in _SEED_PRIMITIVES:
        return False
    # SearchSubstrate op_ast — open AST interpreter, not closed prim-spec kinds.
    if str(spec.get("kind")) == "op_ast":
        from . import search_substrate as search_mod

        return search_mod.install_op_ast_primitive(name, dict(spec))
    fn = compile_primitive_spec(spec)
    if fn is None:
        return False
    _PRIMITIVE_SPECS[name] = dict(spec)
    _register_primitive(name, fn, seed=False)
    return True


def validate_primitive_against_duals(
    eng: Engine, name: str, spec: dict[str, Any]
) -> bool:
    """Accept a proposed primitive only if running it preserves dual invariants."""
    if not install_primitive(name, spec):
        return False
    # Snapshot structural health before.
    try:
        eng.assert_no_orphans()
    except RuleError:
        return False
    cause, effect = _roots(eng)
    ctx: dict[str, Any] = {
        "eng": eng,
        "cause": cause,
        "effect": effect,
        "scalars": {},
        "measures": {},
        "emit": {},
    }
    impl = _PRIMITIVE_OPS.get(name)
    if impl is None:
        return False
    try:
        impl(ctx, {"op": name})
    except Exception:  # noqa: BLE001
        return False
    # Dual invariants still hold (read-only primitives must not mutate).
    try:
        eng.assert_no_orphans()
        if cause and eng.exists(cause):
            dual = eng.answer(cause)
            if not dual.cause_paths or not dual.effect_paths:
                return False
    except RuleError:
        return False
    # Must produce a finite scalar for its into key.
    into = str(spec.get("into", ""))
    if into:
        val = ctx.get("scalars", {}).get(into)
        if val is None:
            return False
        try:
            if val != val:  # NaN
                return False
        except Exception:  # noqa: BLE001
            return False
    return True


def propose_primitives_from_structure(
    program: CapProgram, eng: Engine
) -> list[str]:
    """Body proposes new prim_* ops from live structure; validate + install."""
    proposed: list[str] = []
    op_names = {o.get("op") for o in program.ops}

    candidates: list[tuple[str, dict[str, Any]]] = []
    # Dual graphs with nested structure → max dual depth primitive.
    if any(_depth_safe(eng, n.name) >= 1 for n in eng.torus.nodes.values()):
        candidates.append(
            (
                "prim_max_dual_depth",
                {
                    "kind": "reduce_path",
                    "select": "depth",
                    "over": "dual_causes",
                    "reduce": "max",
                    "into": "max_dual_depth",
                    "origin": "body-proposal",
                },
            )
        )
    # Always-available span primitive on any dual graph with ≥4 nodes.
    if len(eng.torus.nodes) >= 4:
        candidates.append(
            (
                "prim_mean_path_len",
                {
                    "kind": "reduce_path",
                    "select": "path_len",
                    "over": "dual_causes",
                    "reduce": "mean",
                    "into": "mean_path_len",
                    "origin": "body-proposal",
                },
            )
        )
    # Dual child asymmetry → pair metric primitive.
    cause, effect = _roots(eng)
    if cause and effect and (
        _child_count_safe(eng, cause) != _child_count_safe(eng, effect)
        or any(
            _child_count_safe(eng, n.name)
            != _child_count_safe(eng, eng.torus.nodes[n.opposite].name)
            for n in eng.torus.nodes.values()
            if n.hemisphere is Hemisphere.CAUSE
            and n.opposite
            and n.opposite in eng.torus.nodes
        )
    ):
        candidates.append(
            (
                "prim_max_child_delta",
                {
                    "kind": "pair_metric",
                    "metric": "child_delta",
                    "into": "max_child_delta",
                    "origin": "body-proposal",
                },
            )
        )
    # Branching → fanout primitive.
    if any(_child_count_safe(eng, n.name) >= 2 for n in eng.torus.nodes.values()):
        candidates.append(
            (
                "prim_cause_fanout",
                {
                    "kind": "branch_fanout",
                    "hemisphere": "cause",
                    "into": "cause_fanout",
                    "origin": "body-proposal",
                },
            )
        )

    for name, spec in candidates:
        if name in program.primitives or name in op_names:
            continue
        if not validate_primitive_against_duals(eng, name, spec):
            continue
        program.primitives[name] = dict(spec)
        program.primitive_revisions += 1
        _insert_before_emit(program, {"op": name})
        into = str(spec.get("into", ""))
        if into:
            _ensure_emit_field(program, into)
        program.revisions += 1
        proposed.append(name)
    return proposed


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
    op_name = str(step.get("op", ""))
    if op_name and any(str(o.get("op", "")) == op_name for o in program.ops):
        return
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
    """Grow macros from pressure, then propose new primitives validated on duals."""
    # Reinstall any persisted macros + primitives.
    for name, body in program.macros.items():
        install_macro(name, body)
    for name, spec in program.primitives.items():
        install_primitive(name, spec)

    op_names = {o.get("op") for o in program.ops}

    orphans = [n.name for n in eng.orphans()]
    if orphans and "syn_orphan_pressure" not in op_names:
        body = [
            {"op": "count_attr", "attr": "orphans", "into": "orphan_count"},
        ]
        if synthesize_opcode(program, "syn_orphan_pressure", body):
            _insert_before_emit(program, {"op": "syn_orphan_pressure"})
            _ensure_emit_field(program, "orphan_count")
            program.revisions += 1

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

    # §4 leap: propose new primitives (not syn macros) validated against duals.
    propose_primitives_from_structure(program, eng)
    # Optional generative substrate for novel form primitives (default off).
    try:
        from . import substrate as substrate_mod
        from . import search_substrate as search_mod

        class _FormHandle:
            pass

        handle = _FormHandle()
        handle._search_program = program  # noqa: SLF001
        handle.engine = eng
        substrate_mod.consult(
            "form",
            {
                "eng": eng,
                "program_id": program.program_id,
                "primitive_count": len(program.primitives),
                "op_count": len(program.ops),
                "node_count": len(eng.torus.nodes),
            },
            center=handle,
        )
        for row in search_mod.drain_pending_form():
            name = str(row.get("name") or "")
            spec = dict(row.get("spec") or {})
            if not name or name in program.primitives:
                continue
            if search_mod.install_op_ast_primitive(name, spec):
                program.primitives[name] = dict(spec)
                program.primitive_revisions += 1
                _insert_before_emit(program, {"op": name})
                into = str(spec.get("into", ""))
                if into:
                    _ensure_emit_field(program, into)
                program.revisions += 1
    except Exception as exc:  # noqa: BLE001
        from . import substrate as _sub

        _sub.record_consult_error("form", exc)
    return program


def interpret(program: CapProgram, eng: Engine) -> dict[str, Any]:
    """Run the body's capability program (seed + proposed primitives + macros)."""
    for name, spec in program.primitives.items():
        install_primitive(name, spec)
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
        "primitives": sorted(program.primitives.keys()),
        "primitive_revisions": program.primitive_revisions,
        "cause_pole": cause,
        "effect_pole": effect,
        "result": ctx.get("emit") or {},
        "capability": "interpret_program",
    }
