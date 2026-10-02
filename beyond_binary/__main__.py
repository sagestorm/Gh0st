"""CLI for Beyond Binary AI — Living Center, cross-domain, embody, autonomy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import bodies
from .center import LivingCenter
from .engine import Engine, RuleError
from .model import CenterAction, Torus
from .seed import (
    seed_domain,
    seed_hot_cold,
    seed_minimal_hot_cold,
    seed_same_center,
)
from . import store


def _add_store(sp: argparse.ArgumentParser) -> None:
    sp.add_argument(
        "--store",
        type=Path,
        default=None,
        help="path to torus JSON (default: data/torus.json)",
    )


def _eng(path: Path | None) -> tuple[Engine, Path]:
    target = store.store_path(path)
    return Engine(store.load(target)), target


def _center(eng: Engine, target: Path) -> LivingCenter:
    history = store.load_activity(target)
    center = LivingCenter(eng, history=history)
    center.mind_store = target
    return center


def cmd_init(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    if target.exists() and not args.force:
        print(f"already exists: {target} (use --force to overwrite)", file=sys.stderr)
        return 1
    torus = Torus(instance="empty")
    store.save(torus, target)
    if args.force:
        store.clear_activity(target)
    print(f"initialized empty torus at {target}")
    return 0


def cmd_seed_minimal(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    if target.exists() and not args.force:
        print(f"already exists: {target} (use --force to overwrite)", file=sys.stderr)
        return 1
    torus = seed_minimal_hot_cold()
    store.save(torus, target)
    store.clear_activity(target)
    print(f"seeded minimal hot↔cold at {target}")
    eng = Engine(torus)
    print("\n".join(eng.structure_lines()))
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    if target.exists() and not args.force:
        print(f"already exists: {target} (use --force to overwrite)", file=sys.stderr)
        return 1
    torus = seed_hot_cold()
    store.save(torus, target)
    store.clear_activity(target)
    print(f"seeded hot/cold cascade at {target}")
    eng = Engine(torus)
    print("\n".join(eng.structure_lines()))
    return 0


def cmd_seed_domain(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    if target.exists() and not args.force:
        print(f"already exists: {target} (use --force to overwrite)", file=sys.stderr)
        return 1
    torus = seed_domain(args.domain, minimal=not args.full)
    store.save(torus, target)
    store.clear_activity(target)
    print(f"seeded domain {args.domain!r} at {target} (minimal={not args.full})")
    eng = Engine(torus)
    print("\n".join(eng.structure_lines()))
    return 0


def cmd_seed_same_center(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    if target.exists() and not args.force:
        print(f"already exists: {target} (use --force to overwrite)", file=sys.stderr)
        return 1
    domains = args.domains or ["thermal", "ontology", "optical"]
    torus = seed_same_center(domains, minimal=not args.full)
    store.save(torus, target)
    store.clear_activity(target)
    print(
        f"seeded same-center domains {list(domains)} at {target} "
        f"(minimal={not args.full})"
    )
    eng = Engine(torus)
    print("\n".join(eng.structure_lines()))
    return 0


def cmd_think(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    if not eng.torus.nodes:
        print(
            "error: empty torus — run seed-minimal / seed-domain first",
            file=sys.stderr,
        )
        return 1
    center = _center(eng, target)
    reports = center.think(args.steps)
    store.save(eng.torus, target)
    log_path = store.append_activity([r.to_dict() for r in reports], target)
    for report in reports:
        grown = next((a for a in report.acts if a.act == "grow"), None)
        repaired = next((a for a in report.acts if a.act == "repair_orphans"), None)
        meta = next((a for a in report.acts if a.act == "metacognize"), None)
        print(
            f"cycle {report.cycle}: nodes {report.nodes_before}→{report.nodes_after}"
            f" grow={grown.detail.get('count', 0) if grown else 0}"
            f" repair={repaired.detail.get('count', 0) if repaired else 0}"
            f" strategy={meta.detail.get('strategy', {}).get('reason') if meta else '?'}"
        )
    print(f"saved torus → {target}")
    print(f"appended {len(reports)} cycle(s) → {log_path}")
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    args.steps = 1
    return cmd_think(args)


def cmd_autonomy(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    center = _center(eng, target)
    result = center.autonomy(
        args.cycles,
        embody_every=args.embody_every,
        embody_domain=args.embody_domain,
        mind_store=target,
    )
    store.save(eng.torus, target)
    store.append_activity(result["cycles"], target)
    print(json.dumps(result, indent=2))
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    center = _center(eng, target)
    result = center.live(
        max_cycles=args.max_cycles,
        embody_every=args.embody_every,
        embody_domain=args.embody_domain,
        mind_store=target,
        stop_when_idle=args.stop_when_idle,
        invent_every=args.invent_every,
        nurture_every=args.nurture_every,
        nurture_max_depth=args.nurture_max_depth,
        nurture_invent=not args.nurture_no_invent,
    )
    store.save(eng.torus, target)
    store.append_activity(result["cycles"], target)
    print(json.dumps(result, indent=2))
    return 0


def cmd_invent(args: argparse.Namespace) -> int:
    from . import mind as mind_mod

    eng, target = _eng(args.store)
    center = _center(eng, target)
    result = mind_mod.invent_domain(eng, target, cycle=center._cycle_index)
    print(json.dumps(result, indent=2))
    return 0 if result.get("invented") else 1


def cmd_synthesize(args: argparse.Namespace) -> int:
    from . import mind as mind_mod

    eng, target = _eng(args.store)
    result = mind_mod.synthesize(eng, args.topic, target)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_nurture(args: argparse.Namespace) -> int:
    from . import mind as mind_mod

    target = store.store_path(args.store)
    result = mind_mod.nurture(
        target,
        steps=args.steps,
        max_depth=args.max_depth,
        allow_invent=args.invent,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from . import verify

    result = verify.run_verification()
    print(json.dumps(result, indent=2))
    # Non-zero while far-vision sentience gate is false
    return 0 if result.get("complete") else 2


def cmd_product_scoreboard(args: argparse.Namespace) -> int:
    """Null-vs-search product honesty adjunct (does not redefine SENTIENCE)."""
    from . import product_scoreboard as scoreboard_mod

    probes = tuple(args.probe) if args.probe else None
    result = scoreboard_mod.run_scoreboard(
        think_steps=args.steps,
        probes=probes,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("meet_or_exceed") else 2


def cmd_embody(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    center = _center(eng, target)
    record = bodies.embody(
        eng,
        name=args.name,
        domain=args.domain,
        mind_store=target,
        cycle=center._cycle_index,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0


def cmd_bodies(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    registry = bodies.load_registry(target)
    print(json.dumps(registry.to_dict(), indent=2))
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    rows = store.load_activity(target)
    if args.limit and args.limit > 0:
        rows = rows[-args.limit :]
    if not rows:
        try:
            eng, _ = _eng(args.store)
            print(
                json.dumps(
                    eng.torus.center_log[-args.limit :]
                    if args.limit
                    else eng.torus.center_log,
                    indent=2,
                )
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0
    print(json.dumps(rows, indent=2))
    return 0


def cmd_add_pair(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    cause, effect = eng.add_pair(args.cause, args.effect)
    store.save(eng.torus, target)
    print(f"added pair: {cause.name} (cause) ↔ {effect.name} (effect)")
    return 0


def cmd_add_under(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    child, opp = eng.add_under(
        args.parent,
        args.child,
        opposite=args.opposite,
        opposite_parent=args.opposite_parent,
        opposite_name=args.opposite_name,
    )
    store.save(eng.torus, target)
    print(f"added under {args.parent}: {child.name} ↔ {opp.name}")
    return 0


def cmd_link_opposite(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    a, b = eng.link_opposite(args.a, args.b)
    store.save(eng.torus, target)
    print(f"linked opposite: {a.name} ↔ {b.name}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    tgt = eng.merge(args.source, args.target)
    eng.assert_no_orphans()
    store.save(eng.torus, target)
    print(f"merged {args.source!r} into {tgt.name!r}")
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    if args.parent is None and args.opposite is None:
        print("provide --parent and/or --opposite", file=sys.stderr)
        return 2
    node = eng.migrate_link(
        args.node,
        new_parent=args.parent,
        new_opposite=args.opposite,
    )
    store.save(eng.torus, target)
    print(
        f"migrated {node.name}: parent={node.parent!r} opposite={node.opposite!r}"
    )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    eng, _ = _eng(args.store)
    print("\n".join(eng.structure_lines()))
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    eng, _ = _eng(args.store)
    dual = eng.answer(args.topic)
    print(
        json.dumps(
            {
                "topic": dual.topic,
                "cause_paths": dual.cause_paths,
                "effect_paths": dual.effect_paths,
                "between": dual.between,
                "note": dual.note,
            },
            indent=2,
        )
    )
    return 0


def cmd_collapse(args: argparse.Namespace) -> int:
    """I1: refuse bit-endgame collapse; always fail-closed (non-zero)."""
    eng, _ = _eng(args.store)
    result = eng.refuse_bit_collapse(args.topic)
    # Also prove answer() refuses bit tokens under pressure.
    bit_refusals: dict[str, str] = {}
    for bit in ("true", "false", "0", "1"):
        try:
            eng.answer(bit)
            bit_refusals[bit] = "UNEXPECTED_OK"
        except RuleError as exc:
            bit_refusals[bit] = str(exc)
    result["answer_bit_refusals"] = bit_refusals
    print(json.dumps(result, indent=2))
    return 1  # collapse never succeeds


def cmd_center(args: argparse.Namespace) -> int:
    eng, target = _eng(args.store)
    try:
        action = CenterAction(args.action)
    except ValueError:
        allowed = ", ".join(a.value for a in CenterAction)
        print(f"unknown action {args.action!r}; choose: {allowed}", file=sys.stderr)
        return 2
    payload = eng.center(action, args.topic)
    store.save(eng.torus, target)
    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    store_parent = argparse.ArgumentParser(add_help=False)
    store_parent.add_argument(
        "--store",
        type=Path,
        default=argparse.SUPPRESS,
        help="path to torus JSON (default: data/torus.json)",
    )

    p = argparse.ArgumentParser(
        prog="beyond_binary",
        description="Beyond Binary AI — Living Center + dual-hemisphere CLI",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--store",
        type=Path,
        default=None,
        help="path to torus JSON (default: data/torus.json)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def bind(name, help_text, func, *, extras=None, aliases=None):
        kwargs = {"help": help_text, "parents": [store_parent]}
        if aliases:
            kwargs["aliases"] = aliases
        sp = sub.add_parser(name, **kwargs)
        if extras:
            extras(sp)
        sp.set_defaults(func=func)
        return sp

    bind("init", "create empty torus store", cmd_init, extras=lambda sp: sp.add_argument("--force", action="store_true"))
    bind("seed-minimal", "minimal hot↔cold poles only", cmd_seed_minimal, extras=lambda sp: sp.add_argument("--force", action="store_true"))
    bind("seed-hot-cold", "load full hot/cold cascade", cmd_seed, extras=lambda sp: sp.add_argument("--force", action="store_true"))

    def domain_extras(sp):
        sp.add_argument("domain", choices=["thermal", "ontology", "optical"])
        sp.add_argument("--force", action="store_true")
        sp.add_argument("--full", action="store_true")

    bind("seed-domain", "seed a domain", cmd_seed_domain, extras=domain_extras)

    def same_center_extras(sp):
        sp.add_argument(
            "--domains",
            nargs="+",
            choices=["thermal", "ontology", "optical"],
            default=None,
            help="domains on one torus (default: thermal ontology optical)",
        )
        sp.add_argument("--force", action="store_true")
        sp.add_argument("--full", action="store_true")

    bind(
        "seed-same-center",
        "seed thermal+ontology+optical poles on one torus (C2)",
        cmd_seed_same_center,
        extras=same_center_extras,
    )
    bind("think", "run N Living Center cycles", cmd_think, extras=lambda sp: sp.add_argument("--steps", type=int, default=5))
    bind("cycle", "run one Living Center cycle", cmd_cycle)

    def autonomy_extras(sp):
        sp.add_argument("--cycles", type=int, default=3)
        sp.add_argument("--embody-every", type=int, default=0)
        sp.add_argument("--embody-domain", default="ontology", choices=["thermal", "ontology", "optical"])

    bind("autonomy", "think→metacognize→optional embody", cmd_autonomy, extras=autonomy_extras)

    def live_extras(sp):
        sp.add_argument("--max-cycles", type=int, default=20)
        sp.add_argument("--embody-every", type=int, default=0)
        sp.add_argument("--embody-domain", default="ontology", choices=["thermal", "ontology", "optical"])
        sp.add_argument("--stop-when-idle", type=int, default=3)
        sp.add_argument("--invent-every", type=int, default=0, help="invent a new domain body every N cycles")
        sp.add_argument("--nurture-every", type=int, default=0, help="nurture bodies every N cycles")
        sp.add_argument("--nurture-max-depth", type=int, default=2, help="recursive nurture depth")
        sp.add_argument(
            "--nurture-no-invent",
            action="store_true",
            help="during nurture, do not let bodies invent further forms",
        )

    bind("live", "continuous autonomy until idle or max-cycles", cmd_live, extras=live_extras)
    bind("invent-domain", "self-invent a domain body not in starter seeds", cmd_invent)
    bind("synthesize", "answer across mind + all bodies", cmd_synthesize, extras=lambda sp: sp.add_argument("topic"))

    def nurture_extras(sp):
        sp.add_argument("--steps", type=int, default=1)
        sp.add_argument("--max-depth", type=int, default=2, help="recurse into child body registries")
        sp.add_argument(
            "--invent",
            action="store_true",
            help="bodies may invent further forms while nurtured",
        )

    bind("nurture", "think (+optional invent) across body lineage", cmd_nurture, extras=nurture_extras)
    bind("verify-far-vision", "honest evidence audit for the far-vision goal", cmd_verify)

    def scoreboard_extras(sp):
        sp.add_argument("--steps", type=int, default=6, help="think cycles per arm")
        sp.add_argument(
            "--probe",
            action="append",
            default=[],
            help="answer probe topic (repeatable; defaults multi-domain product probes)",
        )

    bind(
        "product-scoreboard",
        "Null vs search product meet-or-exceed (readable duals; no LLM)",
        cmd_product_scoreboard,
        extras=scoreboard_extras,
    )

    def embody_extras(sp):
        sp.add_argument("name")
        sp.add_argument("--domain", default="ontology", choices=["thermal", "ontology", "optical"])

    bind("embody", "spawn a new body/form", cmd_embody, extras=embody_extras)
    bind("bodies", "list registered bodies", cmd_bodies)
    bind("log", "show center activity log", cmd_log, extras=lambda sp: sp.add_argument("--limit", type=int, default=0), aliases=["center-history"])
    bind("add-pair", "add antonym pair", cmd_add_pair, extras=lambda sp: (sp.add_argument("cause"), sp.add_argument("effect")))

    def under_extras(sp):
        sp.add_argument("parent")
        sp.add_argument("child")
        sp.add_argument("--opposite")
        sp.add_argument("--opposite-parent")
        sp.add_argument("--opposite-name")

    bind("add-under", "add under pole with opposite", cmd_add_under, extras=under_extras)
    bind("link-opposite", "link opposites", cmd_link_opposite, extras=lambda sp: (sp.add_argument("a"), sp.add_argument("b")))
    bind("merge", "merge source into target", cmd_merge, extras=lambda sp: (sp.add_argument("source"), sp.add_argument("target")))

    def migrate_extras(sp):
        sp.add_argument("node")
        sp.add_argument("--parent")
        sp.add_argument("--opposite")

    bind("migrate-link", "migrate parent/opposite", cmd_migrate, extras=migrate_extras)
    bind("show", "print structure", cmd_show)
    bind("answer", "dual-hemisphere answer", cmd_answer, extras=lambda sp: sp.add_argument("topic"))
    bind(
        "collapse",
        "I1: refuse bit-endgame; dual evidence only (always exits non-zero)",
        cmd_collapse,
        extras=lambda sp: sp.add_argument("topic", nargs="?"),
    )
    bind("center", "center navigation action", cmd_center, extras=lambda sp: (sp.add_argument("action"), sp.add_argument("topic", nargs="?")))
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuleError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
