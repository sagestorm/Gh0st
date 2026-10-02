"""Living Center — autonomous cycle that grows and maintains the torus.

Ordered acts per cycle (Phase 2 plan):
  review → repair orphans → grow (lexicon) → dedupe/merge →
  synthesize check → challenge → experiment/migrate → prune → log
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .engine import Engine, RuleError, normalize
from . import lexicon
from .model import CenterAction, Hemisphere, Node


# Economy caps — grow paired with dedupe/prune; no sprawl.
MAX_NEW_PAIRS_PER_CYCLE = 1
MAX_NODES_SOFT_CAP = 24  # domain-capped instance; prune pressure above this


@dataclass
class ActRecord:
    """One center act within a cycle (inspectable navigation)."""

    act: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"act": self.act, "detail": self.detail}


@dataclass
class CycleReport:
    cycle: int
    acts: list[ActRecord] = field(default_factory=list)
    nodes_before: int = 0
    nodes_after: int = 0
    score_before: dict[str, float] = field(default_factory=dict)
    score_after: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle,
            "acts": [a.to_dict() for a in self.acts],
            "nodes_before": self.nodes_before,
            "nodes_after": self.nodes_after,
            "score_before": self.score_before,
            "score_after": self.score_after,
        }


@dataclass
class StructuralScore:
    """Provisional structural scores (no world feedback in Phase 2)."""

    dual_coverage: float  # fraction of nodes with a cross-hemisphere opposite
    link_symmetry: float  # fraction of reciprocal opposite links
    unused_path_cost: float  # orphan + alias-duplicate pressure (lower is better)
    node_count: int

    def to_dict(self) -> dict[str, float]:
        return {
            "dual_coverage": self.dual_coverage,
            "link_symmetry": self.link_symmetry,
            "unused_path_cost": self.unused_path_cost,
            "node_count": float(self.node_count),
        }

    def better_than(self, other: "StructuralScore") -> bool:
        """Prefer full dual coverage + symmetry, then lower unused cost, then leaner graph."""
        if self.dual_coverage != other.dual_coverage:
            return self.dual_coverage > other.dual_coverage
        if self.link_symmetry != other.link_symmetry:
            return self.link_symmetry > other.link_symmetry
        if self.unused_path_cost != other.unused_path_cost:
            return self.unused_path_cost < other.unused_path_cost
        return self.node_count < other.node_count


@dataclass
class Strategy:
    """Metacognitive bias derived from center activity history."""

    grow_budget: int = MAX_NEW_PAIRS_PER_CYCLE
    prefer_prune: bool = False
    prefer_migrate: bool = False
    reason: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "grow_budget": self.grow_budget,
            "prefer_prune": self.prefer_prune,
            "prefer_migrate": self.prefer_migrate,
            "reason": self.reason,
        }


class LivingCenter:
    """The hole in the torus: decide grow/repair/dedupe/prune from the median."""

    def __init__(
        self,
        engine: Engine,
        *,
        max_new_pairs_per_cycle: int = MAX_NEW_PAIRS_PER_CYCLE,
        max_nodes_soft_cap: int = MAX_NODES_SOFT_CAP,
        history: list[dict[str, Any]] | None = None,
    ):
        self.engine = engine
        self.max_new_pairs_per_cycle = max_new_pairs_per_cycle
        self.max_nodes_soft_cap = max_nodes_soft_cap
        self._cycle_index = 0
        self.activity: list[dict[str, Any]] = []
        self.strategy = Strategy(grow_budget=max_new_pairs_per_cycle)
        self.mind_store: Any = None  # optional path for learned/body persistence
        if history:
            self.sync_cycle_index(history)
            self.strategy = self.metacognize(history)

    def sync_cycle_index(self, history: list[dict[str, Any]] | None) -> None:
        """Continue numbering from persisted activity (Sourcery fix)."""
        if not history:
            # Also honor in-torus center_log length as a weak hint.
            self._cycle_index = len(self.engine.torus.center_log)
            return
        max_cycle = 0
        for row in history:
            try:
                max_cycle = max(max_cycle, int(row.get("cycle", 0)))
            except (TypeError, ValueError):
                continue
        self._cycle_index = max_cycle

    def metacognize(self, history: list[dict[str, Any]] | None = None) -> Strategy:
        """Read center log and change grow/prune/migrate bias (Phase 4)."""
        rows = history if history is not None else self.activity
        if not rows:
            self.strategy = Strategy(
                grow_budget=self.max_new_pairs_per_cycle,
                reason="no_history",
            )
            return self.strategy

        grow_total = 0
        prune_total = 0
        flag_total = 0
        node_deltas: list[int] = []
        for row in rows[-12:]:
            before = int(row.get("nodes_before", 0) or 0)
            after = int(row.get("nodes_after", 0) or 0)
            node_deltas.append(after - before)
            for act in row.get("acts", []):
                name = act.get("act") if isinstance(act, dict) else None
                detail = act.get("detail", {}) if isinstance(act, dict) else {}
                if name == "grow":
                    grow_total += int(detail.get("count", 0) or 0)
                elif name == "prune":
                    prune_total += int(detail.get("count", 0) or 0)
                elif name == "challenge" and detail.get("one_sided"):
                    flag_total += 1

        # If growth stalled and challenges are clear → keep growing.
        # If many flags or node churn with little grow payoff → prefer prune.
        # If grow kept adding but scores flat in last rows → prefer migrate.
        recent_growth = sum(1 for d in node_deltas[-5:] if d > 0)
        if flag_total >= 2 or (prune_total == 0 and len(self.engine.torus.nodes) > self.max_nodes_soft_cap):
            self.strategy = Strategy(
                grow_budget=0,
                prefer_prune=True,
                prefer_migrate=False,
                reason="challenge_or_over_cap",
            )
        elif grow_total >= 3 and recent_growth == 0:
            self.strategy = Strategy(
                grow_budget=0,
                prefer_prune=False,
                prefer_migrate=True,
                reason="stalled_after_growth",
            )
        elif grow_total == 0 and flag_total == 0:
            self.strategy = Strategy(
                grow_budget=max(1, self.max_new_pairs_per_cycle),
                prefer_prune=False,
                prefer_migrate=False,
                reason="hungry_for_structure",
            )
        else:
            self.strategy = Strategy(
                grow_budget=self.max_new_pairs_per_cycle,
                prefer_prune=False,
                prefer_migrate=recent_growth > 2,
                reason="balanced",
            )
        return self.strategy

    # --- scoring ---------------------------------------------------------

    def score(self) -> StructuralScore:
        nodes = list(self.engine.torus.nodes.values())
        n = len(nodes) or 1
        dual = 0
        sym = 0
        for node in nodes:
            if not node.opposite:
                continue
            opp = self.engine.torus.nodes.get(node.opposite)
            if opp is None:
                continue
            if opp.hemisphere is not node.hemisphere:
                dual += 1
            if opp.opposite == normalize(node.name):
                sym += 1
        orphans = len(self.engine.orphans())
        alias_dups = self._alias_duplicate_count()
        return StructuralScore(
            dual_coverage=dual / n,
            link_symmetry=sym / n,
            unused_path_cost=float(orphans + alias_dups),
            node_count=len(nodes),
        )

    def _alias_duplicate_count(self) -> int:
        count = 0
        for group in lexicon.alias_groups():
            present = [g for g in group if self.engine.exists(g)]
            if len(present) > 1:
                count += len(present) - 1
        return count

    # --- cycle -----------------------------------------------------------

    def cycle(self) -> CycleReport:
        # Refresh strategy from accumulated activity each cycle (metacognition).
        self.metacognize(self.activity)
        # If lexicon is exhausted but generative work remains, keep a unit of growth.
        if self.strategy.grow_budget == 0 and not self.strategy.prefer_prune:
            from . import generate
            from . import lexicon as lex

            existing = set(self.engine.torus.nodes.keys())
            if not lex.pending_expansions(existing, parent_names=existing):
                if generate.pending_generative(
                    self.engine, mind_store=self.mind_store, limit=1
                ):
                    self.strategy = Strategy(
                        grow_budget=1,
                        prefer_prune=False,
                        prefer_migrate=self.strategy.prefer_migrate,
                        reason="generative_available",
                    )
        self._cycle_index += 1
        report = CycleReport(
            cycle=self._cycle_index,
            nodes_before=len(self.engine.torus.nodes),
            score_before=self.score().to_dict(),
        )

        report.acts.append(
            ActRecord("metacognize", {"strategy": self.strategy.to_dict()})
        )
        report.acts.append(self._act_review())
        report.acts.append(self._act_repair_orphans())
        report.acts.append(self._act_grow())
        report.acts.append(self._act_dedupe())
        report.acts.append(self._act_synthesize_check())
        report.acts.append(self._act_challenge())
        report.acts.append(self._act_experiment_migrate())
        report.acts.append(self._act_prune())
        report.acts.append(self._act_log(report))

        report.nodes_after = len(self.engine.torus.nodes)
        report.score_after = self.score().to_dict()
        self.activity.append(report.to_dict())
        return report

    def think(self, steps: int) -> list[CycleReport]:
        if steps < 1:
            raise RuleError("think steps must be >= 1")
        return [self.cycle() for _ in range(steps)]

    def autonomy(
        self,
        cycles: int,
        *,
        embody_every: int = 0,
        embody_domain: str = "ontology",
        mind_store: Any = None,
    ) -> dict[str, Any]:
        """Persistent loop: metacognize → think cycles → optional embody (C6)."""
        from . import bodies

        if mind_store is not None:
            self.mind_store = mind_store
        reports = self.think(cycles)
        embodied = None
        if embody_every and cycles >= embody_every:
            try:
                embodied = bodies.embody(
                    self.engine,
                    name=f"auto-{self._cycle_index}",
                    domain=embody_domain,
                    mind_store=self.mind_store,
                    cycle=self._cycle_index,
                ).to_dict()
            except Exception as exc:  # noqa: BLE001 — record, don't abort autonomy
                embodied = {"error": str(exc)}
        return {
            "cycles": [r.to_dict() for r in reports],
            "strategy": self.strategy.to_dict(),
            "embodied": embodied,
        }

    def live(
        self,
        *,
        max_cycles: int = 20,
        embody_every: int = 0,
        embody_domain: str = "ontology",
        mind_store: Any = None,
        stop_when_idle: int = 3,
    ) -> dict[str, Any]:
        """Continuous autonomy until max_cycles or idle streak (no growth)."""
        if mind_store is not None:
            self.mind_store = mind_store
        reports = []
        idle = 0
        embodied_list: list[dict[str, Any]] = []
        for i in range(max_cycles):
            report = self.cycle()
            reports.append(report)
            grown = next((a for a in report.acts if a.act == "grow"), None)
            count = int(grown.detail.get("count", 0) or 0) if grown else 0
            idle = idle + 1 if count == 0 else 0
            if embody_every and (i + 1) % embody_every == 0:
                from . import bodies

                try:
                    embodied_list.append(
                        bodies.embody(
                            self.engine,
                            name=f"live-{self._cycle_index}",
                            domain=embody_domain,
                            mind_store=self.mind_store,
                            cycle=self._cycle_index,
                        ).to_dict()
                    )
                except Exception as exc:  # noqa: BLE001
                    embodied_list.append({"error": str(exc)})
            if stop_when_idle and idle >= stop_when_idle:
                break
        return {
            "cycles": [r.to_dict() for r in reports],
            "strategy": self.strategy.to_dict(),
            "embodied": embodied_list,
            "stopped": "idle" if idle >= stop_when_idle else "max_cycles",
            "cycle_count": len(reports),
        }

    # --- ordered acts ----------------------------------------------------

    def _act_review(self) -> ActRecord:
        payload = self.engine.center(CenterAction.REVIEW)
        orphans = [n.name for n in self.engine.orphans()]
        return ActRecord(
            "review",
            {
                "node_count": len(self.engine.torus.nodes),
                "orphans": orphans,
                "cause_roots": payload["cause_roots"],
                "effect_roots": payload["effect_roots"],
            },
        )

    def _act_repair_orphans(self) -> ActRecord:
        repaired: list[dict[str, str]] = []
        # Snapshot names — repair mutates the graph.
        for orphan in list(self.engine.orphans()):
            pair = self._repair_one_orphan(orphan)
            if pair:
                repaired.append(pair)
        self.engine.center(CenterAction.ADD, repaired[0]["name"] if repaired else None)
        return ActRecord("repair_orphans", {"repaired": repaired, "count": len(repaired)})

    def _repair_one_orphan(self, orphan: Node) -> Optional[dict[str, str]]:
        """Link orphan to opposite state immediately (lexicon antonym or not-<name>)."""
        key = normalize(orphan.name)
        # May already have been repaired as someone else's opposite.
        if orphan.opposite:
            return None
        if key not in self.engine.torus.nodes:
            return None

        hint = lexicon.antonym_for(orphan.name)
        if hint and self.engine.exists(hint):
            other = self.engine.get(hint)
            if (
                other.hemisphere is not orphan.hemisphere
                and (not other.opposite or other.opposite == key)
            ):
                self.engine.link_opposite(orphan.name, other.name)
                return {
                    "name": orphan.name,
                    "opposite": other.name,
                    "via": "lexicon-existing",
                }

        # Choose a fresh opposite name.
        candidates: list[str] = []
        if hint and not self.engine.exists(hint):
            candidates.append(hint)
        candidates.append(f"not-{orphan.name}")
        candidates.append(f"not-{orphan.name}-{key[:4]}")

        opp_name: Optional[str] = None
        for cand in candidates:
            if not self.engine.exists(cand):
                opp_name = cand
                break
            other = self.engine.get(cand)
            if other.hemisphere is not orphan.hemisphere and (
                not other.opposite or other.opposite == key
            ):
                self.engine.link_opposite(orphan.name, other.name)
                return {"name": orphan.name, "opposite": other.name, "via": "existing"}

        if opp_name is None:
            return None

        other_h = Hemisphere.other(orphan.hemisphere)
        roots = [
            n
            for n in self.engine.torus.nodes.values()
            if n.hemisphere is other_h and n.parent is None
        ]
        opp_parent = roots[0].name if roots else None
        if orphan.parent:
            parent = self.engine.torus.nodes.get(orphan.parent)
            if parent and parent.opposite:
                opp_parent = parent.opposite

        opp_key = normalize(opp_name)
        opp_node = Node(
            name=opp_name,
            hemisphere=other_h,
            parent=normalize(opp_parent) if opp_parent else None,
            opposite=key,
        )
        self.engine.torus.nodes[opp_key] = opp_node
        orphan.opposite = opp_key
        return {"name": orphan.name, "opposite": opp_node.name, "via": "created"}

    def _act_grow(self) -> ActRecord:
        from . import generate
        from . import lexicon as lex

        added: list[dict[str, str]] = []
        budget = self.strategy.grow_budget
        if self.strategy.prefer_prune:
            budget = 0
        if len(self.engine.torus.nodes) >= self.max_nodes_soft_cap:
            return ActRecord(
                "grow",
                {
                    "added": [],
                    "skipped": "soft_cap",
                    "cap": self.max_nodes_soft_cap,
                    "strategy": self.strategy.to_dict(),
                },
            )
        if budget <= 0:
            return ActRecord(
                "grow",
                {
                    "added": [],
                    "skipped": "strategy_budget_zero",
                    "strategy": self.strategy.to_dict(),
                },
            )

        existing = set(self.engine.torus.nodes.keys())
        parents = set(self.engine.torus.nodes.keys())
        pending = lex.pending_expansions(existing, parent_names=parents)
        source = "lexicon"
        if not pending:
            pending = generate.pending_generative(
                self.engine, mind_store=self.mind_store, limit=budget
            )
            source = "generative" if pending else "none"

        for entry in pending:
            if budget <= 0:
                break
            if len(self.engine.torus.nodes) + 2 > self.max_nodes_soft_cap:
                break
            try:
                child, opp = self.engine.add_under(
                    entry.cause_parent,
                    entry.cause,
                    opposite_name=entry.effect,
                    opposite_parent=entry.effect_parent,
                )
            except RuleError as exc:
                added.append(
                    {
                        "cause": entry.cause,
                        "effect": entry.effect,
                        "error": str(exc),
                    }
                )
                continue
            added.append(
                {
                    "cause": child.name,
                    "effect": opp.name,
                    "cause_parent": entry.cause_parent,
                    "effect_parent": entry.effect_parent,
                }
            )
            budget -= 1

        if added and self.mind_store is not None:
            generate.remember_growth(added, self.mind_store)

        topic = added[0]["cause"] if added else None
        self.engine.center(CenterAction.ADD, topic)
        return ActRecord(
            "grow",
            {
                "added": added,
                "count": len(added),
                "source": source,
                "strategy": self.strategy.to_dict(),
            },
        )

    def _act_dedupe(self) -> ActRecord:
        merged: list[dict[str, str]] = []
        for group in lexicon.alias_groups():
            canon = group[0]
            if not self.engine.exists(canon):
                # Promote first present alias to canonical by renaming via merge target:
                # pick first present as temporary target; skip rename — merge others into it.
                present = [g for g in group if self.engine.exists(g)]
                if len(present) <= 1:
                    continue
                target = present[0]
                for src in present[1:]:
                    if not self.engine.exists(src):
                        continue
                    try:
                        self.engine.merge(src, target)
                        merged.append({"source": src, "target": target})
                    except RuleError as exc:
                        merged.append(
                            {"source": src, "target": target, "error": str(exc)}
                        )
                continue
            for alias in group[1:]:
                if not self.engine.exists(alias):
                    continue
                try:
                    self.engine.merge(alias, canon)
                    merged.append({"source": alias, "target": canon})
                except RuleError as exc:
                    merged.append(
                        {"source": alias, "target": canon, "error": str(exc)}
                    )
        self.engine.center(CenterAction.PRUNE if merged else CenterAction.REVIEW)
        return ActRecord("dedupe", {"merged": merged, "count": len(merged)})

    def _act_synthesize_check(self) -> ActRecord:
        checked: list[dict[str, Any]] = []
        refused: list[str] = []
        # Sample poles + a few nested topics.
        topics: list[str] = []
        for n in self.engine.torus.nodes.values():
            if n.parent is None:
                topics.append(n.name)
        for n in self.engine.torus.nodes.values():
            if n.parent and n.name not in topics:
                topics.append(n.name)
            if len(topics) >= 8:
                break
        for topic in topics:
            try:
                dual = self.engine.answer(topic)
                checked.append(
                    {
                        "topic": topic,
                        "ok": True,
                        "cause": dual.cause_paths,
                        "effect": dual.effect_paths,
                    }
                )
            except RuleError as exc:
                refused.append(topic)
                checked.append({"topic": topic, "ok": False, "error": str(exc)})
        if checked:
            self.engine.center(
                CenterAction.SYNTHESIZE,
                next((c["topic"] for c in checked if c.get("ok")), None),
            )
        return ActRecord(
            "synthesize_check",
            {
                "checked": len(checked),
                "ok": sum(1 for c in checked if c.get("ok")),
                "refused": refused,
                "samples": checked[:4],
            },
        )

    def _act_challenge(self) -> ActRecord:
        """Refuse/flag one-sided structures (orphans or broken reciprocals)."""
        flags: list[dict[str, str]] = []
        for node in self.engine.torus.nodes.values():
            if not node.opposite:
                flags.append({"node": node.name, "flag": "orphan"})
                continue
            opp = self.engine.torus.nodes.get(node.opposite)
            if opp is None:
                flags.append({"node": node.name, "flag": "dangling_opposite"})
            elif opp.hemisphere is node.hemisphere:
                flags.append({"node": node.name, "flag": "same_hemisphere_opposite"})
            elif opp.opposite != normalize(node.name):
                flags.append({"node": node.name, "flag": "asymmetric_link"})

        # Sourcery fix: never pass dangling topics into engine.center/answer.
        safe_topic = None
        for flag in flags:
            if flag["flag"] == "dangling_opposite":
                continue
            if self.engine.exists(flag["node"]):
                node = self.engine.get(flag["node"])
                if node.opposite and self.engine.torus.nodes.get(node.opposite):
                    safe_topic = flag["node"]
                    break
        try:
            self.engine.center(CenterAction.CHALLENGE, safe_topic)
        except RuleError:
            self.engine.center(CenterAction.CHALLENGE, None)

        return ActRecord(
            "challenge",
            {
                "flags": flags,
                "one_sided": len(flags) > 0,
                "status": "flagged" if flags else "clear",
            },
        )

    def _act_experiment_migrate(self) -> ActRecord:
        """Try lexicon-aligned parent placement; keep only if structural score improves."""
        experiments: list[dict[str, Any]] = []
        for entry in lexicon.all_cascades():
            if not self.engine.exists(entry.cause):
                continue
            node = self.engine.get(entry.cause)
            desired_parent = normalize(entry.cause_parent)
            if node.parent == desired_parent:
                continue
            if not self.engine.exists(entry.cause_parent):
                continue
            if not self.strategy.prefer_migrate and experiments:
                break
            before = self.score()
            old_parent = node.parent
            try:
                self.engine.migrate_link(entry.cause, new_parent=entry.cause_parent)
            except RuleError as exc:
                experiments.append(
                    {
                        "node": entry.cause,
                        "attempt": "parent",
                        "to": entry.cause_parent,
                        "kept": False,
                        "error": str(exc),
                    }
                )
                continue
            after = self.score()
            kept = after.better_than(before) or after.dual_coverage >= before.dual_coverage
            if not kept:
                try:
                    self.engine.migrate_link(
                        entry.cause,
                        new_parent=old_parent if old_parent else "",
                    )
                except RuleError:
                    pass
            experiments.append(
                {
                    "node": entry.cause,
                    "attempt": "parent",
                    "from": old_parent,
                    "to": entry.cause_parent,
                    "kept": kept,
                    "score_before": before.to_dict(),
                    "score_after": after.to_dict(),
                    "provisional": True,
                }
            )
            break

        # Also align effect-side parents when cause was skipped.
        if not experiments:
            for entry in lexicon.all_cascades():
                if not self.engine.exists(entry.effect):
                    continue
                node = self.engine.get(entry.effect)
                desired_parent = normalize(entry.effect_parent)
                if node.parent == desired_parent:
                    continue
                if not self.engine.exists(entry.effect_parent):
                    continue
                before = self.score()
                old_parent = node.parent
                try:
                    self.engine.migrate_link(
                        entry.effect, new_parent=entry.effect_parent
                    )
                except RuleError as exc:
                    experiments.append(
                        {
                            "node": entry.effect,
                            "attempt": "parent",
                            "to": entry.effect_parent,
                            "kept": False,
                            "error": str(exc),
                        }
                    )
                    break
                after = self.score()
                kept = (
                    after.better_than(before)
                    or after.dual_coverage >= before.dual_coverage
                )
                if not kept:
                    try:
                        self.engine.migrate_link(
                            entry.effect,
                            new_parent=old_parent if old_parent else "",
                        )
                    except RuleError:
                        pass
                experiments.append(
                    {
                        "node": entry.effect,
                        "attempt": "parent",
                        "from": old_parent,
                        "to": entry.effect_parent,
                        "kept": kept,
                        "score_before": before.to_dict(),
                        "score_after": after.to_dict(),
                        "provisional": True,
                    }
                )
                break

        topic = experiments[0]["node"] if experiments else None
        self.engine.center(CenterAction.EXPERIMENT, topic)
        return ActRecord(
            "experiment_migrate",
            {"experiments": experiments, "count": len(experiments)},
        )

    def _act_prune(self) -> ActRecord:
        """Light prune: drop unused auto not-* leaves when over soft cap and redundant."""
        pruned: list[str] = []
        if len(self.engine.torus.nodes) <= self.max_nodes_soft_cap:
            # Still prune clear alias leftovers (already handled in dedupe).
            self.engine.center(CenterAction.PRUNE)
            return ActRecord(
                "prune",
                {"pruned": [], "reason": "under_cap", "node_count": len(self.engine.torus.nodes)},
            )

        # Over cap: remove leaf not-* nodes whose opposite has children or a lexicon name.
        candidates = [
            n
            for n in self.engine.torus.nodes.values()
            if n.name.lower().startswith("not-")
            and not self.engine.children(n.name)
        ]
        for node in candidates:
            if len(self.engine.torus.nodes) <= self.max_nodes_soft_cap:
                break
            if not node.opposite:
                continue
            opp = self.engine.torus.nodes.get(node.opposite)
            if opp is None:
                continue
            # Only prune if opposite can be re-paired via lexicon hint.
            hint = lexicon.antonym_for(opp.name)
            if not hint or self.engine.exists(hint):
                # Re-link opposite to hint if exists, then drop not-*
                if hint and self.engine.exists(hint) and normalize(hint) != normalize(node.name):
                    try:
                        # Clear links carefully
                        key = normalize(node.name)
                        opp.opposite = None
                        del self.engine.torus.nodes[key]
                        try:
                            self.engine.link_opposite(opp.name, hint)
                        except RuleError:
                            # Restore if link fails — put node back
                            self.engine.torus.nodes[key] = node
                            opp.opposite = key
                            continue
                        pruned.append(node.name)
                    except Exception:
                        continue
        self.engine.center(CenterAction.PRUNE)
        try:
            self.engine.assert_no_orphans()
        except RuleError:
            pass  # challenge will flag; repair runs next cycle
        return ActRecord(
            "prune",
            {
                "pruned": pruned,
                "count": len(pruned),
                "node_count": len(self.engine.torus.nodes),
            },
        )

    def _act_log(self, report: CycleReport) -> ActRecord:
        summary = {
            "cycle": report.cycle,
            "acts": [a.act for a in report.acts],
            "nodes_before": report.nodes_before,
            "nodes_after": len(self.engine.torus.nodes),
        }
        self.engine.center(CenterAction.SAVE)
        return ActRecord("log", summary)
