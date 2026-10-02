"""In-process SearchSubstrate — open combinatorial proposals (not an LLM).

Proposals are search-produced ASTs whose *shape* is outside the finite
stdlib-compiler menus (bridge/reparent, meta_prim kinds, 4-act goals,
reduce_path/pair_metric/branch_fanout). Provenance is always
``search-substrate:*``. Accepts require dual / I1 validation.
"""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from .engine import (
    BIT_COLLAPSE_TOKENS,
    Engine,
    RuleError,
    is_bit_collapse_topic,
    normalize,
)
from .model import Hemisphere, Torus
from .substrate import (
    Accept,
    Proposal,
    Reject,
    ValidationResult,
    is_stdlib_provenance,
)

PROVENANCE_PREFIX = "search-substrate:"

# Hand-authored "novel" goal acts from slice 10 — search must mint outside these.
CLOSED_GOAL_ACTS = frozenset(
    {
        "prefer_prune",
        "prefer_grow",
        "prefer_migrate",
        "prefer_invent",
        "prefer_nurture",
        "suppress_grow",
        "invent",
        "nurture",
        "grow",
        "prune",
        "migrate",
        "seek_topology_bridge",
        "retire_invent_pressure",
        "propose_body_primitive",
        "deepen_nurture_lineage",
    }
)

# Finite CapProgram prim-spec kinds — search uses op_ast instead.
CLOSED_PRIM_KINDS = frozenset({"reduce_path", "pair_metric", "branch_fanout"})

# Finite meta_prim compiler kinds — search uses expr_ast instead.
CLOSED_META_KINDS = frozenset(
    {"margin_gate", "signal_ratio", "clamp_signal", "invert_signal"}
)

# Topology stdlib edit kinds — search uses edit_ast instead.
CLOSED_TOPOLOGY_KINDS = frozenset({"bridge", "reparent"})


def _digest(*parts: str, n: int = 8) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return h[:n]


# Opaque search invent poles: sw{hex}… / sc{hex}… / more-sw… / more-sc…
_DIGEST_POLE_RE = re.compile(
    r"^(?:more-)?(?:sw|sc)[0-9a-f]{4,}[a-z0-9]*$",
    re.IGNORECASE,
)


def looks_like_digest_pole(name: str) -> bool:
    """True when a pole label is an opaque sw/sc digest (not human-readable)."""
    return bool(_DIGEST_POLE_RE.match(normalize(name)))


def _clone_engine(eng: Engine) -> Engine:
    return Engine(Torus.from_dict(copy.deepcopy(eng.torus.to_dict())))


def _occupied_names(eng: Engine, reserved: set[str] | None = None) -> set[str]:
    names = {normalize(n) for n in eng.torus.nodes}
    if reserved:
        names |= {normalize(x) for x in reserved}
    return names


def node_domain(eng: Engine, name: str) -> str | None:
    """Walk parent chain to the lexicon domain of a pole (thermal|ontology|optical)."""
    from . import lexicon as lex

    seen: set[str] = set()
    cur = normalize(name)
    while cur and cur not in seen:
        seen.add(cur)
        tagged = lex.pole_domain(cur)
        if tagged:
            return tagged
        node = eng.torus.nodes.get(cur)
        if node is None or not node.parent:
            break
        cur = normalize(node.parent)
    return None


def _is_ancestor(eng: Engine, ancestor: str, node_name: str) -> bool:
    """True when ancestor lies on node_name's parent chain (rehang cycle risk)."""
    target = normalize(ancestor)
    seen: set[str] = set()
    cur = normalize(node_name)
    while cur and cur not in seen:
        if cur == target:
            return True
        seen.add(cur)
        node = eng.torus.nodes.get(cur)
        if node is None or not node.parent:
            break
        cur = normalize(node.parent)
    return False


def _readable_dual_pool(
    eng: Engine,
    reserved: set[str] | None = None,
    *,
    require_domain: str | None = None,
) -> list[tuple[str, str]]:
    """Unused readable antonym pairs: lexicon aliases, cascade poles, invent motifs.

    When ``require_domain`` is set (thermal|ontology|optical), only pairs whose
    both poles carry that lexicon domain are returned — undomain invent motifs
    and foreign typed duals are excluded (typed-parent invent coherence).
    Alias-of-existing poles are also excluded under require_domain so invent
    does not raise unused_path_cost via alias_dups.
    """
    from . import invent as invent_mod
    from . import lexicon as lex

    occupied = _occupied_names(eng, reserved)
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _alias_conflicts_existing(name: str) -> bool:
        """True when name shares an alias group with a pole already on the torus."""
        key = normalize(name)
        for group in lex.alias_groups():
            gset = {normalize(g) for g in group}
            if key not in gset:
                continue
            if any(normalize(g) in occupied or eng.exists(g) for g in group):
                return True
        return False

    def _take(cause: str, effect: str) -> None:
        c, e = cause.strip(), effect.strip()
        if not c or not e:
            return
        if looks_like_digest_pole(c) or looks_like_digest_pole(e):
            return
        if is_bit_collapse_topic(c) or is_bit_collapse_topic(e):
            return
        key = (normalize(c), normalize(e))
        rev = (normalize(e), normalize(c))
        if key in seen or rev in seen:
            return
        if key[0] in occupied or key[1] in occupied:
            return
        if normalize(c) == normalize(e):
            return
        if require_domain is not None:
            dc, de = lex.pole_domain(c), lex.pole_domain(e)
            if dc != require_domain or de != require_domain:
                return
            # Avoid synonym spam that fails the invent score gate.
            if _alias_conflicts_existing(c) or _alias_conflicts_existing(e):
                return
        seen.add(key)
        out.append((c, e))

    # 1) Unused lexicon alias antonyms under known duals (paired group order).
    for node in eng.torus.nodes.values():
        if node.hemisphere is not Hemisphere.CAUSE or not node.opposite:
            continue
        opp = eng.torus.nodes.get(node.opposite)
        if opp is None:
            continue
        cause_group = effect_group = None
        for group in lex.alias_groups():
            gset = {normalize(g) for g in group}
            if normalize(node.name) in gset:
                cause_group = group
            if normalize(opp.name) in gset:
                effect_group = group
        if not cause_group or not effect_group:
            continue
        unused_c = [
            a
            for a in cause_group
            if normalize(a) not in occupied and normalize(a) != normalize(node.name)
        ]
        unused_e = [
            a
            for a in effect_group
            if normalize(a) not in occupied and normalize(a) != normalize(opp.name)
        ]
        for c_alias, e_alias in zip(unused_c, unused_e):
            _take(c_alias, e_alias)

    # 2) Cascade entries whose poles are still free (parents may already exist).
    existing = {n for n in eng.torus.nodes}
    parents = set(existing)
    for entry in lex.pending_expansions(existing, parent_names=parents):
        _take(entry.cause, entry.effect)
    # Also surface cascade poles even when parents are missing — names still readable.
    for entry in lex.all_cascades():
        _take(entry.cause, entry.effect)

    # 3) Domain-tagged invent motifs (non-alias) — preferred under typed parents.
    if require_domain is not None:
        for cause, effect in lex.DOMAIN_INVENT_MOTIFS.get(require_domain, ()):
            _take(cause, effect)
    else:
        for pairs in lex.DOMAIN_INVENT_MOTIFS.values():
            for cause, effect in pairs:
                _take(cause, effect)
        # 4) Undomain seed INVENTABLE — only when parent is untyped.
        for cause, effect, _instance in invent_mod.INVENTABLE:
            _take(cause, effect)

    return out


def mint_readable_dual(
    eng: Engine,
    *,
    reserved: set[str] | None = None,
    salt: str = "",
    require_domain: str | None = None,
) -> tuple[str, str] | None:
    """Pick one unused readable cause/effect pair; None if the pool is exhausted."""
    pool = _readable_dual_pool(eng, reserved, require_domain=require_domain)
    if not pool:
        return None
    if salt:
        # Deterministic rotate so wedge/chain under different sites diverge.
        idx = int(_digest(salt, n=8), 16) % len(pool)
        pool = pool[idx:] + pool[:idx]
    return pool[0]


def edit_ast_poles(ast: list[dict[str, Any]]) -> list[str]:
    """Collect cause/effect pole labels minted or referenced by an edit AST."""
    poles: list[str] = []
    for step in ast:
        if not isinstance(step, dict):
            continue
        for key in ("cause", "effect"):
            val = step.get(key)
            if val:
                poles.append(str(val))
    return poles


def rejects_digest_poles(ast: list[dict[str, Any]]) -> bool:
    """True when any minted/referenced pole looks like an sw/sc digest."""
    return any(looks_like_digest_pole(p) for p in edit_ast_poles(ast))


def _resolve_engine(center: Any) -> Engine | None:
    if center is None:
        return None
    if isinstance(center, Engine):
        return center
    eng = getattr(center, "engine", None)
    return eng if isinstance(eng, Engine) else None


def _validate_dual_i1(eng: Engine) -> bool:
    """Dual coverage + orphans + I1 anti-collapse probe."""
    try:
        eng.assert_no_orphans()
    except RuleError:
        return False
    checked = 0
    for node in eng.torus.nodes.values():
        if node.hemisphere is not Hemisphere.CAUSE:
            continue
        if is_bit_collapse_topic(node.name):
            return False
        try:
            dual = eng.answer(node.name)
        except RuleError:
            return False
        if not dual.cause_paths or not dual.effect_paths:
            return False
        checked += 1
        if checked >= 3:
            break
    if checked == 0:
        return False
    refusal = eng.refuse_bit_collapse()
    return bool(refusal.get("refused")) and not refusal.get("collapsed", True)


def _apply_edit_step(eng: Engine, step: dict[str, Any]) -> bool:
    """Apply one graph-mutation step from an invent edit AST."""
    op = str(step.get("op", ""))
    try:
        if op == "add_dual":
            cause = str(step["cause"])
            effect = str(step["effect"])
            if is_bit_collapse_topic(cause) or is_bit_collapse_topic(effect):
                return False
            eng.add_pair(
                cause,
                effect,
                cause_parent=str(step.get("cause_parent") or "") or None,
                effect_parent=str(step.get("effect_parent") or "") or None,
            )
            return True
        if op == "wedge":
            # Insert new dual between parent and existing child; reparent child under new.
            parent = str(step["parent"])
            child = str(step["child"])
            new_c = str(step["cause"])
            new_e = str(step["effect"])
            if is_bit_collapse_topic(new_c) or is_bit_collapse_topic(new_e):
                return False
            if not eng.exists(parent) or not eng.exists(child):
                return False
            pnode = eng.get(parent)
            cnode = eng.get(child)
            if not pnode.opposite or not cnode.opposite:
                return False
            if normalize(cnode.parent or "") != normalize(parent):
                return False
            opp_parent = eng.torus.nodes[pnode.opposite].name
            opp_child = eng.torus.nodes[cnode.opposite].name
            eng.add_pair(
                new_c,
                new_e,
                cause_parent=parent,
                effect_parent=opp_parent,
            )
            eng.migrate_link(child, new_parent=new_c)
            eng.migrate_link(opp_child, new_parent=new_e)
            return True
        if op == "rehang":
            # Re-attach an existing dual under a *pair* of parents chosen independently
            # (not the stdlib reparent domain-anchor menu).
            cause = str(step["cause"])
            effect = str(step["effect"])
            cp = str(step["cause_parent"])
            ep = str(step["effect_parent"])
            if not all(eng.exists(x) for x in (cause, effect, cp, ep)):
                return False
            eng.migrate_link(cause, new_parent=cp)
            eng.migrate_link(effect, new_parent=ep)
            return True
    except (RuleError, KeyError, TypeError):
        return False
    return False


def apply_edit_ast(eng: Engine, ast: list[dict[str, Any]]) -> bool:
    """Apply a multi-step invent edit AST; False on any failure."""
    if not ast or not isinstance(ast, list):
        return False
    for step in ast:
        if not isinstance(step, dict):
            return False
        if not _apply_edit_step(eng, step):
            return False
    return _validate_dual_i1(eng)


def search_invent_asts(
    eng: Engine,
    *,
    used_instances: set[str] | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Open combinatorial invent search: edit ASTs beyond bridge/reparent.

    Cause/effect poles are human-readable duals (lexicon aliases, cascade
    unused poles, invent motifs). Digests may appear only in instance ids.
    Proposals with sw/sc digest poles are never emitted.
    """
    used = {normalize(x) for x in (used_instances or ())}
    reserved: set[str] = set()
    causes = [
        n
        for n in eng.torus.nodes.values()
        if n.hemisphere is Hemisphere.CAUSE and n.opposite
    ]
    out: list[dict[str, Any]] = []

    # #6: prefer wedge sites off the thermal probe answer spine so invent
    # does not lengthen water/boiling/warm paths by default.
    probe_spine: set[str] = set()
    for topic in ("water", "boiling", "warm"):
        if not eng.exists(topic):
            continue
        try:
            dual = eng.answer(topic)
        except RuleError:
            continue
        for p in (
            list(dual.cause_paths or [])
            + list(dual.effect_paths or [])
            + list(getattr(dual, "between", None) or [])
        ):
            if isinstance(p, (list, tuple)):
                probe_spine.update(normalize(str(x)) for x in p)
            else:
                probe_spine.add(normalize(str(p)))

    wedge_sites = []
    for node in causes:
        if not node.parent or node.parent not in eng.torus.nodes:
            continue
        parent = eng.torus.nodes[node.parent]
        if parent.hemisphere is not Hemisphere.CAUSE or not parent.opposite:
            continue
        on_spine = (
            normalize(parent.name) in probe_spine
            and normalize(node.name) in probe_spine
        )
        wedge_sites.append((1 if on_spine else 0, parent, node))
    wedge_sites.sort(key=lambda row: (row[0], normalize(row[1].name), normalize(row[2].name)))

    # --- Wedge search: insert dual between parent→child ---
    for _spine_rank, parent, node in wedge_sites:
        parent_domain = node_domain(eng, parent.name)
        salt = f"wedge|{normalize(node.name)}|{normalize(parent.name)}"
        pair = mint_readable_dual(
            eng, reserved=reserved, salt=salt, require_domain=parent_domain
        )
        if pair is None:
            # Typed sites with no matching dual left: skip site (don't fall
            # back to undomain motifs). Untyped sites may exhaust the pool.
            continue
        cause, effect = pair
        dig = _digest("wedge", normalize(node.name), normalize(parent.name), cause, effect)
        instance = f"search-wedge-{dig}"
        if normalize(instance) in used:
            reserved.add(normalize(cause))
            reserved.add(normalize(effect))
            continue
        ast = [
            {
                "op": "wedge",
                "parent": parent.name,
                "child": node.name,
                "cause": cause,
                "effect": effect,
            }
        ]
        if rejects_digest_poles(ast):
            reserved.add(normalize(cause))
            reserved.add(normalize(effect))
            continue
        trial = _clone_engine(eng)
        if apply_edit_ast(trial, ast):
            out.append(
                {
                    "kind": "edit_ast",
                    "ast": ast,
                    "cause": cause,
                    "effect": effect,
                    "instance": instance,
                    "why": f"search:wedge:under={normalize(parent.name)}/{normalize(node.name)}",
                }
            )
            used.add(normalize(instance))
            reserved.add(normalize(cause))
            reserved.add(normalize(effect))
            if len(out) >= limit:
                return out
        else:
            reserved.add(normalize(cause))
            reserved.add(normalize(effect))

    # --- Chain search: add_dual then nested add_dual (2-step AST) ---
    dual_pairs = [(c.name, eng.torus.nodes[c.opposite].name) for c in causes[:8]]
    for i, (c1, e1) in enumerate(dual_pairs):
        for c2, e2 in dual_pairs[i + 1 : i + 4]:
            if normalize(c1) == normalize(c2):
                continue
            parent_domain = node_domain(eng, c1)
            salt_mid = f"chain-mid|{normalize(c1)}|{normalize(c2)}"
            mid = mint_readable_dual(
                eng, reserved=reserved, salt=salt_mid, require_domain=parent_domain
            )
            if mid is None:
                if parent_domain is None:
                    return out
                continue
            mid_c, mid_e = mid
            reserved_mid = set(reserved) | {normalize(mid_c), normalize(mid_e)}
            salt_leaf = f"chain-leaf|{normalize(c1)}|{normalize(c2)}|{mid_c}"
            # Leaf nests under mid; mid is domain-matched to parent when typed.
            leaf = mint_readable_dual(
                eng,
                reserved=reserved_mid,
                salt=salt_leaf,
                require_domain=parent_domain,
            )
            if leaf is None:
                reserved.add(normalize(mid_c))
                reserved.add(normalize(mid_e))
                continue
            leaf_c, leaf_e = leaf
            dig = _digest(
                "chain",
                normalize(c1),
                normalize(c2),
                normalize(mid_c),
                normalize(leaf_c),
            )
            instance = f"search-chain-{dig}"
            if normalize(instance) in used:
                reserved.add(normalize(mid_c))
                reserved.add(normalize(mid_e))
                reserved.add(normalize(leaf_c))
                reserved.add(normalize(leaf_e))
                continue
            ast = [
                {
                    "op": "add_dual",
                    "cause": mid_c,
                    "effect": mid_e,
                    "cause_parent": c1,
                    "effect_parent": e1,
                },
                {
                    "op": "add_dual",
                    "cause": leaf_c,
                    "effect": leaf_e,
                    "cause_parent": mid_c,
                    "effect_parent": mid_e,
                },
            ]
            why = (
                f"search:chain:base={normalize(c1)}/{normalize(e1)},"
                f"alt={normalize(c2)}/{normalize(e2)}"
            )
            if rejects_digest_poles(ast):
                reserved.add(normalize(mid_c))
                reserved.add(normalize(mid_e))
                reserved.add(normalize(leaf_c))
                reserved.add(normalize(leaf_e))
                continue
            trial = _clone_engine(eng)
            if apply_edit_ast(trial, ast):
                out.append(
                    {
                        "kind": "edit_ast",
                        "ast": ast,
                        "cause": leaf_c,
                        "effect": leaf_e,
                        "instance": instance,
                        "why": why,
                    }
                )
                used.add(normalize(instance))
                reserved.add(normalize(mid_c))
                reserved.add(normalize(mid_e))
                reserved.add(normalize(leaf_c))
                reserved.add(normalize(leaf_e))
                if len(out) >= limit:
                    return out
            else:
                reserved.add(normalize(mid_c))
                reserved.add(normalize(mid_e))
                reserved.add(normalize(leaf_c))
                reserved.add(normalize(leaf_e))

    # --- Rehang search: re-attach non-root dual under independently chosen parents ---
    for node in causes:
        if not node.parent:
            continue
        opp = eng.torus.nodes.get(node.opposite)
        if opp is None:
            continue
        if looks_like_digest_pole(node.name) or looks_like_digest_pole(opp.name):
            continue
        for host in causes:
            if not host.opposite or normalize(host.name) == normalize(node.name):
                continue
            if host.parent is None and node.parent and normalize(host.name) == normalize(node.parent):
                continue
            # Refuse rehang onto a descendant — creates parent cycles.
            if _is_ancestor(eng, node.name, host.name):
                continue
            hopp = eng.torus.nodes[host.opposite]
            if normalize(host.name) == normalize(node.parent or ""):
                continue
            lab = _digest("rehang", normalize(node.name), normalize(host.name))
            instance = f"rehang-{lab}"
            if normalize(instance) in used:
                continue
            ast = [
                {
                    "op": "rehang",
                    "cause": node.name,
                    "effect": opp.name,
                    "cause_parent": host.name,
                    "effect_parent": hopp.name,
                }
            ]
            if rejects_digest_poles(ast):
                continue
            trial = _clone_engine(eng)
            if apply_edit_ast(trial, ast):
                out.append(
                    {
                        "kind": "edit_ast",
                        "ast": ast,
                        "cause": node.name,
                        "effect": opp.name,
                        "instance": instance,
                        "why": (
                            f"search:rehang:node={normalize(node.name)},"
                            f"under={normalize(host.name)}"
                        ),
                    }
                )
                used.add(normalize(instance))
                if len(out) >= limit:
                    return out

    return out


# ---- Reflect: expression-tree ASTs over journal signals ----

_EXPR_OPS = frozenset({"sig", "const", "add", "sub", "mul", "div", "gt", "gte", "lt", "and", "or", "not"})


def eval_expr_ast(tree: Any, vec: dict[str, float]) -> float | None:
    """Evaluate an open expression AST; None on failure / non-finite."""
    if not isinstance(tree, dict):
        return None
    op = str(tree.get("op", ""))
    if op not in _EXPR_OPS:
        return None
    try:
        if op == "sig":
            k = str(tree.get("k", ""))
            if k in BIT_COLLAPSE_TOKENS:
                return None
            return float(vec.get(k, 0.0))
        if op == "const":
            return float(tree.get("v", 0.0))
        if op == "not":
            v = eval_expr_ast(tree.get("arg"), vec)
            return None if v is None else (0.0 if v else 1.0)
        if op in {"and", "or"}:
            args = tree.get("args") or []
            if not isinstance(args, list) or not args:
                return None
            vals = [eval_expr_ast(a, vec) for a in args]
            if any(v is None for v in vals):
                return None
            if op == "and":
                return 1.0 if all(vals) else 0.0
            return 1.0 if any(vals) else 0.0
        left = eval_expr_ast(tree.get("left"), vec)
        right = eval_expr_ast(tree.get("right"), vec)
        if left is None or right is None:
            return None
        if op == "add":
            return left + right
        if op == "sub":
            return left - right
        if op == "mul":
            return left * right
        if op == "div":
            return left / right if right else 0.0
        if op == "gt":
            return 1.0 if left > right else 0.0
        if op == "gte":
            return 1.0 if left >= right else 0.0
        if op == "lt":
            return 1.0 if left < right else 0.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return None


def search_reflect_asts(
    vec: dict[str, float], *, limit: int = 3
) -> list[dict[str, Any]]:
    """Compose expression trees over empirical signals (not meta_prim kinds)."""
    keys = [
        k
        for k, v in sorted(vec.items())
        if k not in BIT_COLLAPSE_TOKENS and abs(float(v)) > 0
    ]
    if not keys:
        keys = ["fruitful", "stalled", "flags", "node_delta", "grow_count"]
    out: list[dict[str, Any]] = []

    # Combinatorial binary trees over signal pairs.
    for i, a in enumerate(keys[:6]):
        for b in keys[i + 1 : i + 4]:
            trees = [
                {
                    "op": "gt",
                    "left": {
                        "op": "sub",
                        "left": {"op": "sig", "k": a},
                        "right": {"op": "sig", "k": b},
                    },
                    "right": {"op": "const", "v": 0},
                },
                {
                    "op": "and",
                    "args": [
                        {
                            "op": "gte",
                            "left": {"op": "sig", "k": a},
                            "right": {"op": "const", "v": 1},
                        },
                        {
                            "op": "lt",
                            "left": {"op": "sig", "k": b},
                            "right": {"op": "const", "v": 3},
                        },
                    ],
                },
                {
                    "op": "mul",
                    "left": {
                        "op": "add",
                        "left": {"op": "sig", "k": a},
                        "right": {"op": "sig", "k": b},
                    },
                    "right": {
                        "op": "sub",
                        "left": {"op": "const", "v": 1},
                        "right": {
                            "op": "div",
                            "left": {"op": "sig", "k": "flags"} if "flags" in vec else {"op": "const", "v": 0},
                            "right": {"op": "const", "v": 4},
                        },
                    },
                },
            ]
            for tree in trees:
                val = eval_expr_ast(tree, vec)
                if val is None or val != val:
                    continue
                name = f"search_refl_{_digest(a, b, str(tree.get('op')))}"
                out.append(
                    {
                        "kind": "expr_ast",
                        "name": name,
                        "tree": tree,
                        "into": "pred",
                        "sample": val,
                    }
                )
                if len(out) >= limit:
                    return out
    return out


# ---- Goal: act ASTs from outcome traces ----


def search_goal_asts(
    context: dict[str, Any], *, limit: int = 3
) -> list[dict[str, Any]]:
    """Mint act ASTs from outcome pressures — outside the hand-authored 4-act vocab."""
    fruitful = float(context.get("fruitful", 0) or 0)
    stalled = float(context.get("stalled", 0) or 0)
    flags = float(context.get("flags", 0) or 0)
    summary = dict(context.get("invent_summary") or {})
    abandoned = float(summary.get("abandoned_count", 0) or 0)
    prefer = str(summary.get("prefer_source") or "")

    # Outcome-conditioned templates → unique act_kind digests (not closed names).
    candidates: list[tuple[dict[str, Any], float]] = []
    if stalled >= 1 or flags >= 1:
        dig = _digest("cool", str(stalled), str(flags), prefer)
        candidates.append(
            (
                {
                    "kind": "act_ast",
                    "act_kind": f"search_act_cool_{dig}",
                    "target": "pressure",
                    "tree": {
                        "op": "when",
                        "cond": {
                            "op": "or",
                            "args": [
                                {"op": "gte", "sig": "stalled", "v": 1},
                                {"op": "gte", "sig": "flags", "v": 1},
                            ],
                        },
                        "then": {"op": "bias", "channel": "migrate", "delta": 0.4},
                        "else": {"op": "bias", "channel": "grow", "delta": 0.1},
                    },
                    "reason": f"search:outcome:stalled={stalled},flags={flags}",
                },
                1.2,
            )
        )
    if fruitful >= 1 and flags == 0:
        dig = _digest("deepen", str(fruitful), prefer or "none")
        candidates.append(
            (
                {
                    "kind": "act_ast",
                    "act_kind": f"search_act_deepen_{dig}",
                    "target": "structure",
                    "tree": {
                        "op": "seq",
                        "acts": [
                            {"op": "bias", "channel": "invent", "delta": 0.35},
                            {
                                "op": "when",
                                "cond": {"op": "gte", "sig": "fruitful", "v": 2},
                                "then": {"op": "bias", "channel": "nurture", "delta": 0.3},
                            },
                        ],
                    },
                    "reason": f"search:outcome:fruitful={fruitful}",
                },
                1.3,
            )
        )
    if abandoned >= 1 or prefer:
        dig = _digest("retarget", prefer, str(abandoned))
        candidates.append(
            (
                {
                    "kind": "act_ast",
                    "act_kind": f"search_act_retarget_{dig}",
                    "target": prefer or "open",
                    "tree": {
                        "op": "prefer_source",
                        "source_hint": prefer or "search",
                        "abandon_menu": True,
                    },
                    "reason": f"search:outcome:abandoned={abandoned},prefer={prefer}",
                },
                1.4,
            )
        )
    # Always offer a residual explore act when any pressure exists.
    if fruitful + stalled + flags + abandoned > 0:
        dig = _digest("explore", str(fruitful), str(stalled), str(flags))
        candidates.append(
            (
                {
                    "kind": "act_ast",
                    "act_kind": f"search_act_explore_{dig}",
                    "target": "open-search",
                    "tree": {
                        "op": "explore",
                        "weights": {
                            "invent": round(0.2 + 0.1 * fruitful, 3),
                            "nurture": round(0.15 + 0.1 * abandoned, 3),
                            "migrate": round(0.1 + 0.1 * stalled, 3),
                        },
                    },
                    "reason": "search:outcome:residual_explore",
                },
                1.0,
            )
        )

    out: list[dict[str, Any]] = []
    for payload, priority in candidates:
        act = str(payload.get("act_kind", ""))
        if act in CLOSED_GOAL_ACTS:
            continue
        if not act.startswith("search_act_"):
            continue
        payload = dict(payload)
        payload["priority"] = priority
        out.append(payload)
        if len(out) >= limit:
            break
    return out


def eval_goal_ast_ok(tree: Any) -> bool:
    """Structural check for goal act ASTs (open ops, not closed act names)."""
    if not isinstance(tree, dict):
        return False
    op = str(tree.get("op", ""))
    if op in {"when", "seq", "bias", "prefer_source", "explore"}:
        if op == "when":
            return isinstance(tree.get("cond"), dict) and (
                isinstance(tree.get("then"), dict) or tree.get("then") is None
            )
        if op == "seq":
            acts = tree.get("acts") or []
            return isinstance(acts, list) and all(isinstance(a, dict) for a in acts)
        return True
    return False


def _eval_goal_cond(node: Any, signals: dict[str, float]) -> bool:
    """Evaluate compact goal-condition nodes (``{op,sig,v}`` / and/or)."""
    if not isinstance(node, dict):
        return False
    op = str(node.get("op", ""))
    if op in {"and", "or"}:
        args = node.get("args") or []
        if not isinstance(args, list) or not args:
            return False
        vals = [_eval_goal_cond(a, signals) for a in args]
        return all(vals) if op == "and" else any(vals)
    if op == "not":
        return not _eval_goal_cond(node.get("arg"), signals)
    sig = str(node.get("sig", "") or "")
    actual = float(signals.get(sig, 0.0) or 0.0)
    thresh = float(node.get("v", 0) or 0)
    if op == "gte":
        return actual >= thresh
    if op == "gt":
        return actual > thresh
    if op == "lt":
        return actual < thresh
    if op == "lte":
        return actual <= thresh
    if op == "eq":
        return actual == thresh
    return False


def apply_goal_ast(
    tree: Any, signals: dict[str, float] | None = None
) -> dict[str, Any]:
    """Interpret a search act AST into strategy deltas (bar §3 bridge).

    Returns keys: want_invent, want_nurture, suppress_invent,
    invent_prefer_source, channel_bias.
    """
    out: dict[str, Any] = {
        "want_invent": False,
        "want_nurture": False,
        "suppress_invent": False,
        "invent_prefer_source": "",
        "channel_bias": {},
    }
    if not isinstance(tree, dict):
        return out
    sig = dict(signals or {})

    def _bias(channel: str, delta: float) -> None:
        ch = str(channel or "")
        if not ch:
            return
        bias: dict[str, float] = out["channel_bias"]
        bias[ch] = bias.get(ch, 0.0) + float(delta)
        if ch in {"invent", "prefer_invent"} and delta > 0:
            out["want_invent"] = True
        if ch in {"nurture", "prefer_nurture"} and delta > 0:
            out["want_nurture"] = True
        if ch in {"migrate", "prefer_migrate"} and delta > 0 and not out["invent_prefer_source"]:
            out["invent_prefer_source"] = "search"

    def _apply(node: Any) -> None:
        if not isinstance(node, dict):
            return
        op = str(node.get("op", ""))
        if op == "bias":
            _bias(str(node.get("channel", "")), float(node.get("delta", 0) or 0))
            return
        if op == "prefer_source":
            hint = str(node.get("source_hint") or "search")
            out["invent_prefer_source"] = hint
            out["want_invent"] = True
            if node.get("abandon_menu"):
                # Prefer open search over closed invent-menu pressure.
                out["want_invent"] = True
            return
        if op == "explore":
            weights = dict(node.get("weights") or {})
            for ch, w in weights.items():
                _bias(str(ch), float(w or 0))
            return
        if op == "when":
            cond = node.get("cond")
            branch = node.get("then") if _eval_goal_cond(cond, sig) else node.get("else")
            if isinstance(branch, dict):
                _apply(branch)
            return
        if op == "seq":
            for act in node.get("acts") or []:
                _apply(act)
            return

    _apply(tree)
    return out


# ---- Form: CapProgram op ASTs beyond closed prim-spec kinds ----

_OP_AST_STEPS = frozenset(
    {
        "foreach_dual",
        "map_attr",
        "filter_gt",
        "fold_sum",
        "fold_max",
        "fold_mean",
        "ratio",
        "emit",
    }
)


def run_op_ast(eng: Engine, body: list[dict[str, Any]]) -> dict[str, float] | None:
    """Interpret an open measurement AST over the live dual graph."""
    lists: dict[str, list[float]] = {}
    scalars: dict[str, float] = {}
    try:
        for step in body:
            if not isinstance(step, dict):
                return None
            op = str(step.get("op", ""))
            if op not in _OP_AST_STEPS:
                return None
            if op == "foreach_dual":
                dest = str(step.get("into_list", "duals"))
                attr = str(step.get("attr", "depth"))
                vals: list[float] = []
                for node in eng.torus.nodes.values():
                    if node.hemisphere is not Hemisphere.CAUSE or not node.opposite:
                        continue
                    if attr == "depth":
                        try:
                            vals.append(float(len(eng.path_to_root(node.name)) - 1))
                        except Exception:  # noqa: BLE001
                            vals.append(0.0)
                    elif attr == "child_count":
                        vals.append(float(len(eng.children(node.name))))
                    elif attr == "path_len":
                        try:
                            vals.append(float(len(eng.path_to_root(node.name))))
                        except Exception:  # noqa: BLE001
                            vals.append(0.0)
                    else:
                        return None
                lists[dest] = vals
            elif op == "map_attr":
                # Alias of foreach_dual for alternate naming in searched ASTs.
                dest = str(step.get("into_list", "duals"))
                attr = str(step.get("attr", "depth"))
                vals: list[float] = []
                for node in eng.torus.nodes.values():
                    if node.hemisphere is not Hemisphere.CAUSE or not node.opposite:
                        continue
                    if attr == "depth":
                        try:
                            vals.append(float(len(eng.path_to_root(node.name)) - 1))
                        except Exception:  # noqa: BLE001
                            vals.append(0.0)
                    elif attr == "child_count":
                        vals.append(float(len(eng.children(node.name))))
                    elif attr == "path_len":
                        try:
                            vals.append(float(len(eng.path_to_root(node.name))))
                        except Exception:  # noqa: BLE001
                            vals.append(0.0)
                    else:
                        return None
                lists[dest] = vals
            elif op == "filter_gt":
                src = str(step.get("from_list", ""))
                dest = str(step.get("into_list", src))
                thresh = float(step.get("v", 0))
                src_list = lists.get(src)
                if src_list is None:
                    return None
                lists[dest] = [x for x in src_list if x > thresh]
            elif op in {"fold_sum", "fold_max", "fold_mean"}:
                src = str(step.get("from_list", ""))
                dest = str(step.get("into", "out"))
                src_list = lists.get(src) or []
                if not src_list:
                    scalars[dest] = 0.0
                elif op == "fold_sum":
                    scalars[dest] = float(sum(src_list))
                elif op == "fold_max":
                    scalars[dest] = float(max(src_list))
                else:
                    scalars[dest] = float(sum(src_list) / len(src_list))
            elif op == "ratio":
                a = str(step.get("a", ""))
                b = str(step.get("b", ""))
                dest = str(step.get("into", "ratio"))
                if a not in scalars or b not in scalars:
                    return None
                bv = scalars[b]
                scalars[dest] = scalars[a] / bv if bv else 0.0
            elif op == "emit":
                fields = step.get("fields") or list(scalars.keys())
                return {str(f): float(scalars.get(str(f), 0.0)) for f in fields}
        return scalars
    except (TypeError, ValueError, RuleError):
        return None


def search_form_asts(eng: Engine, *, limit: int = 3) -> list[dict[str, Any]]:
    """Search CapProgram measurement ASTs outside reduce_path/pair_metric/branch_fanout."""
    if len(eng.torus.nodes) < 2:
        return []
    programs: list[list[dict[str, Any]]] = [
        [
            {"op": "foreach_dual", "attr": "depth", "into_list": "depths"},
            {"op": "fold_sum", "from_list": "depths", "into": "sum_depth"},
            {"op": "emit", "fields": ["sum_depth"]},
        ],
        [
            {"op": "foreach_dual", "attr": "child_count", "into_list": "kids"},
            {"op": "filter_gt", "from_list": "kids", "into_list": "branchy", "v": 1},
            {"op": "fold_max", "from_list": "branchy", "into": "max_branch"},
            {"op": "fold_mean", "from_list": "kids", "into": "mean_kids"},
            {
                "op": "ratio",
                "a": "max_branch",
                "b": "mean_kids",
                "into": "branch_ratio",
            },
            {"op": "emit", "fields": ["branch_ratio", "max_branch", "mean_kids"]},
        ],
        [
            {"op": "foreach_dual", "attr": "path_len", "into_list": "paths"},
            {"op": "foreach_dual", "attr": "depth", "into_list": "depths"},
            {"op": "fold_mean", "from_list": "paths", "into": "mean_path"},
            {"op": "fold_sum", "from_list": "depths", "into": "sum_depth"},
            {"op": "ratio", "a": "sum_depth", "b": "mean_path", "into": "depth_path_ratio"},
            {"op": "emit", "fields": ["depth_path_ratio"]},
        ],
    ]
    out: list[dict[str, Any]] = []
    for body in programs:
        result = run_op_ast(eng, body)
        if result is None:
            continue
        into = next(iter(result)) if result else "out"
        name = f"prim_search_{_digest(str(body), into)}"
        out.append(
            {
                "kind": "op_ast",
                "name": name,
                "body": body,
                "into": into,
                "sample": result,
                "origin": "search-substrate",
            }
        )
        if len(out) >= limit:
            break
    return out


def install_op_ast_primitive(name: str, spec: dict[str, Any]) -> bool:
    """Install an op_ast primitive into the capability registry."""
    from . import capability as cap_mod

    if not name.startswith("prim_"):
        return False
    if str(spec.get("kind")) != "op_ast":
        return False
    if str(spec.get("kind")) in CLOSED_PRIM_KINDS:
        return False
    body = list(spec.get("body") or [])
    into = str(spec.get("into", "out"))

    def _impl(ctx: dict[str, Any], args: dict[str, Any]) -> None:
        eng: Engine = ctx["eng"]
        result = run_op_ast(eng, body) or {}
        ctx.setdefault("scalars", {}).update(result)
        if into in result:
            ctx["scalars"][into] = result[into]

    # Bypass compile_primitive_spec (finite kinds) — register directly.
    if name in cap_mod.seed_primitives():
        return False
    cap_mod._PRIMITIVE_SPECS[name] = dict(spec)  # noqa: SLF001
    cap_mod._register_primitive(name, _impl, seed=False)  # noqa: SLF001
    return True


class SearchSubstrate:
    """Live in-process generative substrate via open combinatorial search."""

    name = "search"

    def propose(self, context: dict[str, Any]) -> list[Proposal]:
        axis = str(context.get("axis") or "")
        out: list[Proposal] = []
        if axis == "invent":
            eng = context.get("eng")
            if not isinstance(eng, Engine):
                eng = _resolve_engine(context.get("center"))
            if eng is None:
                return []
            used = set(context.get("used_instances") or [])
            for row in search_invent_asts(eng, used_instances=used, limit=3):
                out.append(
                    Proposal(
                        axis="invent",
                        payload=row,
                        provenance=f"{PROVENANCE_PREFIX}invent:{row.get('why', 'edit')}",
                    )
                )
        elif axis == "reflect":
            vec = dict(context.get("vec") or {})
            for row in search_reflect_asts(vec, limit=3):
                out.append(
                    Proposal(
                        axis="reflect",
                        payload=row,
                        provenance=f"{PROVENANCE_PREFIX}reflect:{row.get('name')}",
                    )
                )
        elif axis == "goal":
            for row in search_goal_asts(context, limit=3):
                out.append(
                    Proposal(
                        axis="goal",
                        payload=row,
                        provenance=f"{PROVENANCE_PREFIX}goal:{row.get('act_kind')}",
                    )
                )
        elif axis == "form":
            eng = context.get("eng")
            if not isinstance(eng, Engine):
                eng = _resolve_engine(context.get("center"))
            if eng is None:
                return []
            for row in search_form_asts(eng, limit=3):
                out.append(
                    Proposal(
                        axis="form",
                        payload=row,
                        provenance=f"{PROVENANCE_PREFIX}form:{row.get('name')}",
                    )
                )
        return out

    def validate(self, proposal: Proposal, center: Any) -> ValidationResult:
        if is_stdlib_provenance(proposal.provenance):
            return Reject("stdlib-compiler provenance forbidden")
        if not str(proposal.provenance).startswith(PROVENANCE_PREFIX):
            return Reject("provenance must be search-substrate:*")
        payload = proposal.payload
        if not isinstance(payload, dict):
            return Reject("payload must be a dict")

        if proposal.axis == "invent":
            if str(payload.get("kind")) in CLOSED_TOPOLOGY_KINDS:
                return Reject("stdlib topology kind")
            if str(payload.get("kind")) != "edit_ast":
                return Reject("invent payload must be edit_ast")
            ast = list(payload.get("ast") or [])
            if rejects_digest_poles(ast):
                return Reject("digest poles forbidden as user-facing invent labels")
            for pole in (payload.get("cause"), payload.get("effect")):
                if pole and looks_like_digest_pole(str(pole)):
                    return Reject("digest poles forbidden as user-facing invent labels")
            eng = _resolve_engine(center)
            if eng is None:
                return Reject("engine required for invent dual validation")
            trial = _clone_engine(eng)
            if not apply_edit_ast(trial, ast):
                return Reject("edit_ast failed dual/I1 validation")
            return Accept("invent edit_ast dual+I1 ok")

        if proposal.axis == "reflect":
            if str(payload.get("kind")) in CLOSED_META_KINDS:
                return Reject("stdlib meta_prim kind")
            if str(payload.get("kind")) != "expr_ast":
                return Reject("reflect payload must be expr_ast")
            vec = {}
            # Prefer center-provided vec via last context — fall back to empty.
            if center is not None and isinstance(getattr(center, "_search_vec", None), dict):
                vec = dict(center._search_vec)  # noqa: SLF001
            # Payload sample already evaluated; re-check tree.
            tree = payload.get("tree")
            # Use a neutral vec if needed: ensure finite.
            probe = {"fruitful": 1.0, "stalled": 0.0, "flags": 0.0, "node_delta": 2.0}
            probe.update(vec)
            val = eval_expr_ast(tree, probe)
            if val is None or val != val:
                return Reject("expr_ast non-finite")
            return Accept("reflect expr_ast ok")

        if proposal.axis == "goal":
            act = str(payload.get("act_kind", ""))
            if act in CLOSED_GOAL_ACTS:
                return Reject("closed goal act vocabulary")
            if str(payload.get("kind")) != "act_ast":
                return Reject("goal payload must be act_ast")
            if not act.startswith("search_act_"):
                return Reject("act_kind must be search-minted")
            if not eval_goal_ast_ok(payload.get("tree")):
                return Reject("act_ast structure invalid")
            return Accept("goal act_ast ok")

        if proposal.axis == "form":
            if str(payload.get("kind")) in CLOSED_PRIM_KINDS:
                return Reject("stdlib prim-spec kind")
            if str(payload.get("kind")) != "op_ast":
                return Reject("form payload must be op_ast")
            eng = _resolve_engine(center)
            if eng is None:
                return Reject("engine required for form dual validation")
            try:
                eng.assert_no_orphans()
            except RuleError:
                return Reject("orphans before form validate")
            result = run_op_ast(eng, list(payload.get("body") or []))
            if result is None:
                return Reject("op_ast failed")
            into = str(payload.get("into", ""))
            if into and into not in result:
                return Reject("op_ast missing into")
            if not _validate_dual_i1(eng):
                return Reject("form dual/I1 failed after op_ast")
            return Accept("form op_ast dual+I1 ok")

        return Reject(f"unknown axis {proposal.axis}")

    def accept(self, proposal: Proposal, *, center: Any = None) -> str | None:
        """Persist accepted proposal into the live center artifacts."""
        payload = proposal.payload
        if not isinstance(payload, dict):
            return None

        if proposal.axis == "invent":
            registry = None
            if center is not None:
                registry = getattr(center, "_search_invent_registry", None)
            # Also allow payload-side stash via proposal — callers set on context object.
            if registry is None:
                # Stash on a module-level pending list for invent.refresh to merge.
                _PENDING_INVENT.append(dict(payload))
                return f"search-invent-{payload.get('instance', proposal.proposal_id)}"
            from .invent import InventCandidate

            registry.candidates.append(
                InventCandidate(
                    cause=str(payload.get("cause", "")),
                    effect=str(payload.get("effect", "")),
                    instance=str(payload.get("instance", "")),
                    source="search",
                    why=str(payload.get("why", "search-substrate")),
                    edit={
                        "kind": "edit_ast",
                        "ast": list(payload.get("ast") or []),
                    },
                    priority=2.5,
                )
            )
            return f"search-invent-{payload.get('instance')}"

        if proposal.axis == "reflect":
            policy = getattr(center, "_search_policy", None) if center else None
            name = str(payload.get("name") or f"search_refl_{proposal.proposal_id}")
            definition = {
                "kind": "expr_ast",
                "tree": payload.get("tree"),
                "into": payload.get("into", "pred"),
                "origin": "search-substrate",
            }
            if policy is not None:
                policy.condition_kinds[name] = definition
                policy.kind_revisions += 1
                # Also keep a runnable meta marker (not closed meta_prim kind).
                policy.meta_primitives[f"meta_search_{name}"] = {
                    "kind": "expr_ast",
                    "tree": payload.get("tree"),
                    "into": payload.get("into", "pred"),
                    "origin": "search-substrate",
                }
                policy.meta_isa_revisions += 1
            else:
                _PENDING_REFLECT.append({"name": name, **definition})
            return f"search-reflect-{name}"

        if proposal.axis == "goal":
            board = getattr(center, "_search_goal_board", None) if center else None
            from .goals import Goal

            tree = payload.get("tree")
            goal = Goal(
                goal_id=f"sg-{proposal.proposal_id[-6:]}",
                act_kind=str(payload.get("act_kind")),
                target=str(payload.get("target", "open")),
                reason=str(payload.get("reason", "search-substrate")),
                priority=float(payload.get("priority", 1.0) or 1.0),
                origin="search-substrate",
                tree=dict(tree) if isinstance(tree, dict) else None,
            )
            if board is not None:
                # Dedupe by act_kind — keep highest priority + ensure tree persists.
                existing = next(
                    (
                        g
                        for g in board.goals
                        if g.act_kind == goal.act_kind and not g.abandoned
                    ),
                    None,
                )
                if existing is not None:
                    if goal.priority >= existing.priority:
                        existing.priority = goal.priority
                        existing.reason = goal.reason
                        existing.target = goal.target
                        if goal.tree is not None:
                            existing.tree = dict(goal.tree)
                    elif existing.tree is None and goal.tree is not None:
                        existing.tree = dict(goal.tree)
                    board.revisions += 1
                else:
                    board.goals.append(goal)
                    board.revisions += 1
            else:
                _PENDING_GOALS.append(goal.to_dict())
            return f"search-goal-{goal.act_kind}"

        if proposal.axis == "form":
            program = getattr(center, "_search_program", None) if center else None
            name = str(payload.get("name") or f"prim_search_{proposal.proposal_id}")
            spec = {
                "kind": "op_ast",
                "body": list(payload.get("body") or []),
                "into": str(payload.get("into", "out")),
                "origin": "search-substrate",
            }
            if not install_op_ast_primitive(name, spec):
                return None
            if program is not None:
                program.primitives[name] = dict(spec)
                program.primitive_revisions += 1
                # Insert before emit if possible.
                from . import capability as cap_mod

                cap_mod._insert_before_emit(program, {"op": name})  # noqa: SLF001
                into = str(spec.get("into", ""))
                if into:
                    cap_mod._ensure_emit_field(program, into)  # noqa: SLF001
                program.revisions += 1
            else:
                _PENDING_FORM.append({"name": name, "spec": spec})
            return f"search-form-{name}"

        return None


# Pending queues when accept has no live registry/policy/board/program handle.
_PENDING_INVENT: list[dict[str, Any]] = []
_PENDING_REFLECT: list[dict[str, Any]] = []
_PENDING_GOALS: list[dict[str, Any]] = []
_PENDING_FORM: list[dict[str, Any]] = []


def drain_pending_invent() -> list[dict[str, Any]]:
    rows = list(_PENDING_INVENT)
    _PENDING_INVENT.clear()
    return rows


def drain_pending_reflect() -> list[dict[str, Any]]:
    rows = list(_PENDING_REFLECT)
    _PENDING_REFLECT.clear()
    return rows


def drain_pending_goals() -> list[dict[str, Any]]:
    rows = list(_PENDING_GOALS)
    _PENDING_GOALS.clear()
    return rows


def drain_pending_form() -> list[dict[str, Any]]:
    rows = list(_PENDING_FORM)
    _PENDING_FORM.clear()
    return rows


def reset_pending_for_tests() -> None:
    _PENDING_INVENT.clear()
    _PENDING_REFLECT.clear()
    _PENDING_GOALS.clear()
    _PENDING_FORM.clear()


def snapshot_pending() -> dict[str, list[dict[str, Any]]]:
    """Copy pending invent/reflect/goal/form queues (nested harness restore)."""
    return {
        "invent": [dict(r) for r in _PENDING_INVENT],
        "reflect": [dict(r) for r in _PENDING_REFLECT],
        "goals": [dict(r) for r in _PENDING_GOALS],
        "form": [dict(r) for r in _PENDING_FORM],
    }


def restore_pending(snap: dict[str, list[dict[str, Any]]] | None) -> None:
    """Replace pending queues with a prior snapshot (or clear when snap is None)."""
    reset_pending_for_tests()
    if not snap:
        return
    _PENDING_INVENT.extend(dict(r) for r in snap.get("invent") or [])
    _PENDING_REFLECT.extend(dict(r) for r in snap.get("reflect") or [])
    _PENDING_GOALS.extend(dict(r) for r in snap.get("goals") or [])
    _PENDING_FORM.extend(dict(r) for r in snap.get("form") or [])
