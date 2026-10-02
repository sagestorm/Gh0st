"""CLI for Beyond Binary AI.

Usage:
  python -m beyond_binary init [--store PATH]
  python -m beyond_binary seed-hot-cold [--store PATH]
  python -m beyond_binary add-pair CAUSE EFFECT [--store PATH]
  python -m beyond_binary add-under PARENT CHILD [--opposite NAME] [--opposite-parent P] [--opposite-name N]
  python -m beyond_binary link-opposite A B
  python -m beyond_binary merge SOURCE TARGET
  python -m beyond_binary migrate-link NODE [--parent P] [--opposite O]
  python -m beyond_binary show
  python -m beyond_binary answer TOPIC
  python -m beyond_binary center ACTION [TOPIC]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .engine import Engine, RuleError
from .model import CenterAction, Torus
from .seed import seed_hot_cold
from . import store


def _eng(path: Path | None) -> tuple[Engine, Path]:
    target = store.store_path(path)
    return Engine(store.load(target)), target


def cmd_init(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    if target.exists() and not args.force:
        print(f"already exists: {target} (use --force to overwrite)", file=sys.stderr)
        return 1
    torus = Torus(instance="empty")
    store.save(torus, target)
    print(f"initialized empty torus at {target}")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    target = store.store_path(args.store)
    if target.exists() and not args.force:
        print(f"already exists: {target} (use --force to overwrite)", file=sys.stderr)
        return 1
    torus = seed_hot_cold()
    store.save(torus, target)
    print(f"seeded hot/cold cascade at {target}")
    eng = Engine(torus)
    print("\n".join(eng.structure_lines()))
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
    print(json.dumps({
        "topic": dual.topic,
        "cause_paths": dual.cause_paths,
        "effect_paths": dual.effect_paths,
        "between": dual.between,
        "note": dual.note,
    }, indent=2))
    return 0


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
    p = argparse.ArgumentParser(
        prog="beyond_binary",
        description="Beyond Binary AI — dual-hemisphere CLI (thin slice)",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--store",
        type=Path,
        default=None,
        help="path to torus JSON (default: data/torus.json)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create empty torus store")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    seed = sub.add_parser("seed-hot-cold", help="load first hot/cold cascade instance")
    seed.add_argument("--force", action="store_true")
    seed.set_defaults(func=cmd_seed)

    ap = sub.add_parser("add-pair", help="add antonym pair across cause/effect")
    ap.add_argument("cause")
    ap.add_argument("effect")
    ap.set_defaults(func=cmd_add_pair)

    au = sub.add_parser("add-under", help="add node under a pole; links opposite immediately")
    au.add_argument("parent")
    au.add_argument("child")
    au.add_argument("--opposite", help="existing opposite node")
    au.add_argument("--opposite-parent", help="parent for new opposite node")
    au.add_argument("--opposite-name", help="name for new opposite node")
    au.set_defaults(func=cmd_add_under)

    lo = sub.add_parser("link-opposite", help="link opposite states across hemispheres")
    lo.add_argument("a")
    lo.add_argument("b")
    lo.set_defaults(func=cmd_link_opposite)

    mg = sub.add_parser("merge", help="dedupe: merge source into target")
    mg.add_argument("source")
    mg.add_argument("target")
    mg.set_defaults(func=cmd_merge)

    mv = sub.add_parser("migrate-link", help="migrate parent and/or opposite when proven better")
    mv.add_argument("node")
    mv.add_argument("--parent", help="new parent name, or empty string to clear")
    mv.add_argument("--opposite", help="new opposite node")
    mv.set_defaults(func=cmd_migrate)

    sh = sub.add_parser("show", help="print dual-hemisphere structure")
    sh.set_defaults(func=cmd_show)

    an = sub.add_parser("answer", help="dual-hemisphere answer for a topic")
    an.add_argument("topic")
    an.set_defaults(func=cmd_answer)

    ce = sub.add_parser("center", help="center navigation: review/synthesize/challenge/experiment/add/prune/retrieve/save")
    ce.add_argument("action")
    ce.add_argument("topic", nargs="?")
    ce.set_defaults(func=cmd_center)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuleError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
