"""Self-invention — compose new domains from Living Center structure.

Hardcoded INVENTABLE is only a seed fallback. Primary path:
  harvest known opposite pairs → compose / promote → persist invent registry → embody.
Opposite stays opposite-state: composed poles keep dual reciprocity
(A∘C ↔ B∘D when A↔B and C↔D are known).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .engine import Engine, normalize
from .model import Hemisphere, Torus
from . import bodies
from .seed import seed_custom


def seed_body_from_search_edit(
    edit: dict[str, Any] | None,
    *,
    instance: str,
    cause: str,
    effect: str,
) -> Torus:
    """Seed an embodied body whose dual structure reflects search invent edit_ast.

    Mind-graph parents are remapped onto a body-local dual scaffold so the body
    stays dual/I1-safe while CapProgram specialty can differ by invent ops —
    not only by pole labels from seed_custom(cause, effect).
    """
    if not edit or edit.get("kind") != "edit_ast":
        return seed_custom(cause, effect, instance=instance)
    ast = [s for s in list(edit.get("ast") or []) if isinstance(s, dict)]
    ops = [str(s.get("op", "")) for s in ast]
    if not ops:
        return seed_custom(cause, effect, instance=instance)

    dig = normalize(instance).replace("rehang-", "")[:10]
    torus = Torus()
    torus.instance = instance
    eng = Engine(torus)

    if len(ops) == 1 and ops[0] == "wedge":
        # Root scaffold + invent dual wedged underneath (depth structure).
        root_c, root_e = f"iw{dig}rc", f"iw{dig}re"
        leaf_c = str(ast[0].get("cause") or cause)
        leaf_e = str(ast[0].get("effect") or effect)
        eng.add_pair(root_c, root_e)
        eng.add_pair(leaf_c, leaf_e, cause_parent=root_c, effect_parent=root_e)
        eng.assert_no_orphans()
        return torus

    if ops and all(o == "add_dual" for o in ops):
        # Nested chain: first invent dual is body root; later steps nest under prior.
        for i, step in enumerate(ast):
            c = str(step.get("cause") or "")
            e = str(step.get("effect") or "")
            if not c or not e:
                return seed_custom(cause, effect, instance=instance)
            if i == 0:
                eng.add_pair(c, e)
            else:
                prev_c = str(ast[i - 1].get("cause") or "")
                prev_e = str(ast[i - 1].get("effect") or "")
                eng.add_pair(c, e, cause_parent=prev_c, effect_parent=prev_e)
        eng.assert_no_orphans()
        return torus

    if len(ops) == 1 and ops[0] == "rehang":
        # Distinct from wedge: two host duals under a root; leaf starts under
        # host A then migrates under host B (rehang signature).
        root_c, root_e = f"ir{dig}rc", f"ir{dig}re"
        ha_c, ha_e = f"ir{dig}ac", f"ir{dig}ae"
        hb_c, hb_e = f"ir{dig}bc", f"ir{dig}be"
        leaf_c, leaf_e = f"ir{dig}lc", f"ir{dig}le"
        eng.add_pair(root_c, root_e)
        eng.add_pair(ha_c, ha_e, cause_parent=root_c, effect_parent=root_e)
        eng.add_pair(hb_c, hb_e, cause_parent=root_c, effect_parent=root_e)
        eng.add_pair(leaf_c, leaf_e, cause_parent=ha_c, effect_parent=ha_e)
        eng.migrate_link(leaf_c, new_parent=hb_c)
        eng.migrate_link(leaf_e, new_parent=hb_e)
        eng.assert_no_orphans()
        return torus

    return seed_custom(cause, effect, instance=instance)


# Seed catalog only — used when composition finds nothing unused.
INVENTABLE: tuple[tuple[str, str, str], ...] = (
    ("open", "closed", "open-closed"),
    ("begin", "end", "begin-end"),
    ("inner", "outer", "inner-outer"),
    ("chaos", "order", "chaos-order"),
    ("self", "other", "self-other"),
    ("signal", "noise", "signal-noise"),
    ("question", "answer", "question-answer"),
)


@dataclass(frozen=True)
class Invention:
    cause: str
    effect: str
    instance: str
    body_name: str
    source: str = "seed"  # topology | concept | primitive | compose | promote | seed
    why: str = ""
    edit: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "cause": self.cause,
            "effect": self.effect,
            "instance": self.instance,
            "body_name": self.body_name,
            "source": self.source,
            "why": self.why,
        }
        if self.edit:
            row["edit"] = self.edit
        return row


@dataclass
class InventCandidate:
    cause: str
    effect: str
    instance: str
    source: str
    used: bool = False
    why: str = ""
    edit: dict[str, Any] | None = None  # topology edit plan
    priority: float = 1.0
    abandoned: bool = False
    outcome_score: float = 0.0  # cumulative from journal traces

    def to_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "cause": self.cause,
            "effect": self.effect,
            "instance": self.instance,
            "source": self.source,
            "used": self.used,
            "why": self.why,
            "priority": self.priority,
            "abandoned": self.abandoned,
            "outcome_score": self.outcome_score,
        }
        if self.edit:
            row["edit"] = self.edit
        return row

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InventCandidate":
        return cls(
            cause=data["cause"],
            effect=data["effect"],
            instance=data["instance"],
            source=str(data.get("source", "seed")),
            used=bool(data.get("used", False)),
            why=str(data.get("why", "")),
            edit=dict(data["edit"]) if data.get("edit") else None,
            priority=float(data.get("priority", 1.0) or 1.0),
            abandoned=bool(data.get("abandoned", False)),
            outcome_score=float(data.get("outcome_score", 0.0) or 0.0),
        )


@dataclass
class InventRegistry:
    candidates: list[InventCandidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"candidates": [c.to_dict() for c in self.candidates]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InventRegistry":
        return cls(
            candidates=[
                InventCandidate.from_dict(row) for row in data.get("candidates", [])
            ]
        )


def invent_registry_path(mind_store: Path | str | None = None) -> Path:
    from . import store

    target = store.store_path(mind_store)
    return target.with_name(f"{target.stem}.invent.json")


def load_invent_registry(mind_store: Path | str | None = None) -> InventRegistry:
    path = invent_registry_path(mind_store)
    if not path.exists():
        return InventRegistry()
    return InventRegistry.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_invent_registry(
    registry: InventRegistry, mind_store: Path | str | None = None
) -> Path:
    path = invent_registry_path(mind_store)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Dedupe by instance key; prefer unused topology/concept over seed.
    seen: dict[str, InventCandidate] = {}
    source_rank = {
        "topology": 6,
        "concept": 5,
        "primitive": 4,
        "compose": 3,
        "promote": 2,
        "seed": 1,
    }
    for cand in registry.candidates:
        key = normalize(cand.instance)
        prev = seen.get(key)
        if prev is None:
            seen[key] = cand
            continue
        used = prev.used or cand.used
        abandoned = prev.abandoned or cand.abandoned
        winner = (
            cand
            if source_rank.get(cand.source, 0) > source_rank.get(prev.source, 0)
            else prev
        )
        seen[key] = InventCandidate(
            cause=winner.cause,
            effect=winner.effect,
            instance=winner.instance,
            source=winner.source,
            used=used,
            why=winner.why or prev.why,
            edit=winner.edit or prev.edit,
            priority=max(prev.priority, cand.priority, winner.priority),
            abandoned=abandoned,
            outcome_score=prev.outcome_score + cand.outcome_score
            if prev is not winner
            else winner.outcome_score,
        )
    registry.candidates = list(seen.values())
    path.write_text(
        json.dumps(registry.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def already_used_poles(eng: Engine, registry_bodies: Iterable[dict]) -> set[str]:
    used = {normalize(n) for n in eng.torus.nodes}
    for body in registry_bodies:
        used.add(normalize(body.get("domain", "")))
        used.add(normalize(body.get("name", "")))
        inst = body.get("parent_instance") or ""
        for part in inst.replace("_", "-").split("-"):
            if part:
                used.add(normalize(part))
        store_path = body.get("store_path")
        if store_path:
            try:
                from . import store

                torus = store.load(store_path)
                used.update(normalize(k) for k in torus.nodes)
                used.add(normalize(torus.instance))
            except Exception:  # noqa: BLE001
                pass
    return used


def already_used_instances(eng: Engine, registry_bodies: Iterable[dict]) -> set[str]:
    """Instances/domains/body names already claimed — not every nested node."""
    used = {normalize(eng.torus.instance)} if eng.torus.instance else set()
    for body in registry_bodies:
        if body.get("domain"):
            used.add(normalize(body["domain"]))
        if body.get("name"):
            used.add(normalize(body["name"]))
        store_path = body.get("store_path")
        if store_path:
            try:
                from . import store

                torus = store.load(store_path)
                used.add(normalize(torus.instance))
            except Exception:  # noqa: BLE001
                pass
    return used


def harvest_pairs(eng: Engine, registry_bodies: Iterable[dict]) -> list[tuple[str, str]]:
    """Collect reciprocal cause↔effect pairs from mind + bodies (structure only)."""
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _from_engine(engine: Engine) -> None:
        for node in engine.torus.nodes.values():
            if node.hemisphere is not Hemisphere.CAUSE:
                continue
            if not node.opposite:
                continue
            opp = engine.torus.nodes.get(node.opposite)
            if opp is None or opp.hemisphere is not Hemisphere.EFFECT:
                continue
            key = (normalize(node.name), normalize(opp.name))
            if key in seen:
                continue
            # Skip template generative stacking as domain poles.
            if node.name.lower().startswith("more-") or opp.name.lower().startswith(
                "more-"
            ):
                continue
            if node.name.lower().startswith("not-") or opp.name.lower().startswith(
                "not-"
            ):
                continue
            seen.add(key)
            pairs.append((node.name, opp.name))

    _from_engine(eng)
    for body in registry_bodies:
        store_path = body.get("store_path")
        if not store_path:
            continue
        try:
            from . import store

            _from_engine(Engine(store.load(store_path)))
        except Exception:  # noqa: BLE001
            continue
    return pairs


def _slug_pair(cause: str, effect: str) -> str:
    return f"{normalize(cause)}-{normalize(effect)}"


def compose_candidates(
    known_pairs: list[tuple[str, str]],
    used_poles: set[str],
    used_instances: set[str],
    *,
    limit: int = 12,
) -> list[InventCandidate]:
    """Compose new opposite-state domains from known pairs (A∘C ↔ B∘D)."""
    out: list[InventCandidate] = []
    roots = known_pairs[:8]  # prefer earlier / root-ish harvest order
    for i, (a, b) in enumerate(roots):
        for c, d in roots[i + 1 :]:
            # Product of opposites preserves opposite-state.
            cause = f"{a}-{c}"
            effect = f"{b}-{d}"
            if normalize(cause) == normalize(effect):
                continue
            if normalize(cause) in used_poles or normalize(effect) in used_poles:
                continue
            # Avoid stacking already-composed tokens too deep.
            if cause.count("-") > 2 or effect.count("-") > 2:
                continue
            instance = _slug_pair(cause, effect)
            if normalize(instance) in used_instances:
                continue
            if any(normalize(x.instance) == normalize(instance) for x in out):
                continue
            out.append(
                InventCandidate(
                    cause=cause, effect=effect, instance=instance, source="compose"
                )
            )
            if len(out) >= limit:
                return out
    return out


def promote_candidates(
    known_pairs: list[tuple[str, str]],
    eng: Engine,
    used_instances: set[str],
    *,
    limit: int = 8,
) -> list[InventCandidate]:
    """Promote non-root reciprocal pairs already in the graph into inventable domains."""
    out: list[InventCandidate] = []
    for cause, effect in known_pairs:
        if not eng.exists(cause):
            continue
        node = eng.get(cause)
        if node.parent is None:
            continue  # roots are already domains / poles
        instance = _slug_pair(cause, effect)
        if normalize(instance) in used_instances:
            continue
        if any(normalize(x.instance) == normalize(instance) for x in out):
            continue
        out.append(
            InventCandidate(
                cause=cause, effect=effect, instance=instance, source="promote"
            )
        )
        if len(out) >= limit:
            break
    return out


def seed_candidates(used_poles: set[str], used_instances: set[str]) -> list[InventCandidate]:
    out: list[InventCandidate] = []
    for cause, effect, instance in INVENTABLE:
        if normalize(cause) in used_poles or normalize(effect) in used_poles:
            continue
        if normalize(instance) in used_instances:
            continue
        out.append(
            InventCandidate(
                cause=cause, effect=effect, instance=instance, source="seed"
            )
        )
    return out


def closed_invent_alphabet(eng: Engine, registry_bodies: Iterable[dict]) -> set[str]:
    """Labels reachable by seed/compose/promote — primitives must fall outside."""
    alpha = already_used_poles(eng, registry_bodies)
    for cause, effect, instance in INVENTABLE:
        alpha.add(normalize(cause))
        alpha.add(normalize(effect))
        alpha.add(normalize(instance))
    known = harvest_pairs(eng, registry_bodies)
    for i, (a, b) in enumerate(known[:8]):
        for c, d in known[i + 1 :]:
            alpha.add(normalize(f"{a}-{c}"))
            alpha.add(normalize(f"{b}-{d}"))
            alpha.add(normalize(f"{normalize(a)}-{normalize(c)}-{normalize(b)}-{normalize(d)}"))
    for cause, effect in known:
        if eng.exists(cause):
            node = eng.get(cause)
            if node.parent is not None:
                alpha.add(normalize(cause))
                alpha.add(normalize(effect))
                alpha.add(normalize(f"{normalize(cause)}-{normalize(effect)}"))
    return alpha


def pressure_stems(
    activity: list[dict[str, Any]] | None,
    journal_rows: list[Any] | None = None,
) -> list[tuple[str, str]]:
    """Collect (stem, why) from challenge/synthesize pressure + journal."""
    stems: list[tuple[str, str]] = []
    for row in (activity or [])[-12:]:
        for act in row.get("acts") or []:
            if not isinstance(act, dict):
                continue
            name = act.get("act")
            detail = act.get("detail") or {}
            if name == "challenge":
                for flag in detail.get("flags") or []:
                    if isinstance(flag, dict) and flag.get("node"):
                        stems.append(
                            (str(flag["node"]), f"challenge:{flag.get('flag')}")
                        )
            elif name == "synthesize_check":
                for topic in detail.get("refused") or []:
                    stems.append((str(topic), "synthesize_refused"))
    for entry in (journal_rows or [])[-8:]:
        reflection = (
            entry.reflection
            if hasattr(entry, "reflection")
            else (entry.get("reflection") if isinstance(entry, dict) else "")
        )
        if reflection == "challenge_pressure":
            stems.append(("tension", "journal:challenge_pressure"))
        elif reflection == "growth_stalled":
            stems.append(("drift", "journal:growth_stalled"))
    return stems


def mint_primitive_candidate(
    stem: str,
    why: str,
    alphabet: set[str],
    used_instances: set[str],
) -> Optional[InventCandidate]:
    """Mint a new opposite-state pole pair outside the closed invent alphabet."""
    import re

    from .engine import is_bit_collapse_topic

    base = re.sub(r"[^a-z0-9]+", "", normalize(stem))[:10]
    if len(base) < 2:
        return None
    trials = [
        (f"{base}ure", f"un{base}ure"),
        (f"proto{base}", f"ecto{base}"),
        (f"{base}al", f"{base}less"),
        (f"{base}ive", f"{base}iveopp"),
    ]
    for cause, effect in trials:
        if is_bit_collapse_topic(cause) or is_bit_collapse_topic(effect):
            continue
        if normalize(cause) == normalize(effect):
            continue
        if normalize(cause) in alphabet or normalize(effect) in alphabet:
            continue
        instance = f"{normalize(cause)}-{normalize(effect)}"
        if normalize(instance) in used_instances or normalize(instance) in alphabet:
            continue
        return InventCandidate(
            cause=cause,
            effect=effect,
            instance=instance,
            source="primitive",
            why=why,
        )
    return None


def primitive_candidates(
    eng: Engine,
    registry_bodies: Iterable[dict],
    *,
    activity: list[dict[str, Any]] | None = None,
    journal_rows: list[Any] | None = None,
    used_instances: set[str] | None = None,
    limit: int = 4,
) -> list[InventCandidate]:
    alphabet = closed_invent_alphabet(eng, registry_bodies)
    used_inst = set(used_instances or ())
    out: list[InventCandidate] = []
    seen: set[str] = set()
    for stem, why in pressure_stems(activity, journal_rows):
        cand = mint_primitive_candidate(stem, why, alphabet, used_inst)
        if cand is None:
            continue
        key = normalize(cand.instance)
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
        if len(out) >= limit:
            break
    return out


def concept_candidates(
    eng: Engine,
    registry_bodies: Iterable[dict],
    *,
    used_instances: set[str] | None = None,
    limit: int = 3,
) -> list[InventCandidate]:
    """Structural concept formation — preferred over pressure-suffix primitives."""
    from . import concepts as concepts_mod

    alphabet = closed_invent_alphabet(eng, registry_bodies)
    used_inst = set(used_instances or ())
    out: list[InventCandidate] = []
    for proposal in concepts_mod.form_concepts(
        eng, alphabet=alphabet, used_instances=used_inst, limit=limit
    ):
        out.append(
            InventCandidate(
                cause=proposal.cause,
                effect=proposal.effect,
                instance=proposal.instance,
                source="concept",
                why=proposal.why,
            )
        )
    return out


def topology_candidates(
    eng: Engine,
    registry_bodies: Iterable[dict],
    *,
    used_instances: set[str] | None = None,
    limit: int = 4,
) -> list[InventCandidate]:
    """Cross-domain bridge/re-parent edits validated under dual invariants."""
    from . import topology as topology_mod

    alphabet = closed_invent_alphabet(eng, registry_bodies)
    used_inst = set(used_instances or ())
    edits = topology_mod.search_topology_edits(
        eng, alphabet=alphabet, used_instances=used_inst, limit=limit
    )
    out: list[InventCandidate] = []
    for row in topology_mod.edits_to_proposals(edits, used_instances=used_inst):
        out.append(
            InventCandidate(
                cause=row["cause"],
                effect=row["effect"],
                instance=row["instance"],
                source="topology",
                why=row["why"],
                edit=row.get("edit"),
                priority=2.0,  # topology preferred when available
            )
        )
        used_inst.add(normalize(row["instance"]))
    return out


def revise_targets_from_outcomes(
    registry: InventRegistry,
    journal_rows: list[Any],
    *,
    inventions_fired: int = 0,
) -> InventRegistry:
    """Abandon / reprioritize invent targets from journal outcome traces.

    Used inventions followed by stalled/challenge pressure get abandoned.
    Unused candidates whose source differs from abandoned ones get boosted.
    """
    from .journal import JournalEntry

    if not journal_rows and inventions_fired <= 0:
        return registry
    normalized: list[JournalEntry] = []
    for row in journal_rows[-16:]:
        if isinstance(row, JournalEntry):
            normalized.append(row)
        else:
            try:
                normalized.append(JournalEntry.from_dict(row))
            except Exception:  # noqa: BLE001
                continue

    fruitful = sum(1 for e in normalized if e.reflection == "growth_fruitful")
    stalled = sum(1 for e in normalized if e.reflection == "growth_stalled")
    flags = sum(
        1
        for e in normalized
        if e.reflection == "challenge_pressure"
        or int((e.signals or {}).get("flags", 0) or 0) > 0
    )
    invent_hints = sum(1 for e in normalized if e.strategy_hint == "invent")
    invent_hints += max(0, int(inventions_fired))

    used = [c for c in registry.candidates if c.used]
    abandoned_sources: set[str] = set()

    # Penalize used targets when invent met adverse outcomes (outcome traces).
    if used and (stalled >= 1 or flags >= 1) and invent_hints >= 1:
        for cand in used:
            cand.outcome_score -= 1.0 + 0.5 * stalled + 0.5 * flags
            if cand.outcome_score <= -1.5:
                cand.abandoned = True
                abandoned_sources.add(cand.source)
                cand.priority = min(cand.priority, 0.1)

    # Reward fruitful aftermath for used non-abandoned.
    if used and fruitful >= 2 and flags == 0:
        for cand in used:
            if cand.abandoned:
                continue
            cand.outcome_score += 0.5 * fruitful
            cand.priority = min(3.0, cand.priority + 0.25)

    # Reprioritize unused: boost sources unlike abandoned; demote same-source.
    for cand in registry.candidates:
        if cand.used or cand.abandoned:
            continue
        if cand.source in abandoned_sources:
            cand.priority = max(0.05, cand.priority * 0.4)
            cand.outcome_score -= 0.5
        else:
            # Prefer topology/concept when something was abandoned.
            if abandoned_sources:
                bump = 0.8 if cand.source in {"topology", "concept"} else 0.3
                cand.priority = min(3.0, cand.priority + bump)
                cand.outcome_score += 0.25
    return registry


def refresh_invent_registry(
    eng: Engine,
    mind_store,
    *,
    activity: list[dict[str, Any]] | None = None,
    journal_rows: list[Any] | None = None,
) -> InventRegistry:
    """Harvest topology + concepts + pressure into dynamic invent registry."""
    from . import journal as journal_mod
    from . import store

    body_registry = bodies.load_registry(mind_store)
    body_dicts = [b.to_dict() for b in body_registry.bodies]
    used_poles = already_used_poles(eng, body_dicts)
    used_instances = already_used_instances(eng, body_dicts)
    registry = load_invent_registry(mind_store)
    for cand in registry.candidates:
        if cand.used:
            used_instances.add(normalize(cand.instance))
            used_poles.add(normalize(cand.cause))
            used_poles.add(normalize(cand.effect))
        if cand.abandoned:
            used_instances.add(normalize(cand.instance))
    known = harvest_pairs(eng, body_dicts)

    if activity is None:
        try:
            activity = store.load_activity(mind_store)
        except Exception:  # noqa: BLE001
            activity = []
    if journal_rows is None:
        try:
            journal_rows = journal_mod.load_journal(mind_store)
        except Exception:  # noqa: BLE001
            journal_rows = []

    existing_keys = {normalize(c.instance) for c in registry.candidates}

    for cand in (
        topology_candidates(eng, body_dicts, used_instances=used_instances)
        + concept_candidates(eng, body_dicts, used_instances=used_instances)
        + primitive_candidates(
            eng,
            body_dicts,
            activity=activity,
            journal_rows=journal_rows,
            used_instances=used_instances,
        )
        + compose_candidates(known, used_poles, used_instances)
        + promote_candidates(known, eng, used_instances)
        + seed_candidates(used_poles, used_instances)
    ):
        key = normalize(cand.instance)
        if key in existing_keys:
            continue
        registry.candidates.append(cand)
        existing_keys.add(key)

    registry = revise_targets_from_outcomes(registry, journal_rows or [])
    # Optional generative substrate (default off → NullSubstrate / no-op).
    try:
        from . import substrate as substrate_mod
        from . import search_substrate as search_mod

        # Handle for SearchSubstrate.accept to append into this registry.
        handle = substrate_mod.InventConsultContext(
            engine=eng,
            invent_registry=registry,
        )
        substrate_mod.consult(
            "invent",
            {
                "eng": eng,
                "used_poles": sorted(used_poles),
                "used_instances": sorted(used_instances),
                "candidate_count": len(registry.candidates),
                "journal_len": len(journal_rows or []),
            },
            center=handle,
        )
        # Merge any pending invent payloads (accept without handle).
        for row in search_mod.drain_pending_invent():
            key = normalize(str(row.get("instance", "")))
            if not key or key in existing_keys:
                continue
            registry.candidates.append(
                InventCandidate(
                    cause=str(row.get("cause", "")),
                    effect=str(row.get("effect", "")),
                    instance=str(row.get("instance", "")),
                    source="search",
                    why=str(row.get("why", "search-substrate")),
                    edit={
                        "kind": "edit_ast",
                        "ast": list(row.get("ast") or []),
                    },
                    priority=2.5,
                )
            )
            existing_keys.add(key)
    except Exception as exc:  # noqa: BLE001
        from . import substrate as _sub

        _sub.record_consult_error("invent", exc)
    save_invent_registry(registry, mind_store)
    return registry


def next_invention(
    eng: Engine,
    mind_store,
    *,
    activity: list[dict[str, Any]] | None = None,
    journal_rows: list[Any] | None = None,
    skip_instances: set[str] | None = None,
) -> Optional[Invention]:
    registry = refresh_invent_registry(
        eng, mind_store, activity=activity, journal_rows=journal_rows
    )
    body_registry = bodies.load_registry(mind_store)
    used_names = {normalize(b.name) for b in body_registry.bodies}
    body_dicts = [b.to_dict() for b in body_registry.bodies]
    used_poles = already_used_poles(eng, body_dicts)
    used_instances = already_used_instances(eng, body_dicts)
    alphabet = closed_invent_alphabet(eng, body_dicts)
    skip = {normalize(x) for x in (skip_instances or ())}

    # Prefer high priority; topology > concept > … ; skip abandoned.
    source_order = {
        "search": 0,
        "topology": 1,
        "concept": 2,
        "primitive": 3,
        "compose": 4,
        "promote": 5,
        "seed": 6,
    }
    unused = [
        c for c in registry.candidates if not c.used and not c.abandoned
    ]
    unused.sort(
        key=lambda c: (-c.priority, source_order.get(c.source, 9), c.instance)
    )

    for cand in unused:
        if normalize(cand.instance) in skip:
            continue
        if cand.source in {"primitive", "concept", "topology", "search"}:
            if cand.source == "topology" and cand.edit and cand.edit.get("kind") == "reparent":
                # Re-parent uses existing poles — alphabet check on instance only.
                pass
            elif cand.source == "search" and cand.edit and cand.edit.get("kind") == "edit_ast":
                # Search edit_ast may rehang existing poles or mint new names.
                pass
            elif (
                normalize(cand.cause) in alphabet
                or normalize(cand.effect) in alphabet
            ):
                continue
        elif cand.source != "promote":
            if normalize(cand.cause) in used_poles or normalize(cand.effect) in used_poles:
                continue
        if normalize(cand.instance) in used_instances:
            continue
        body_name = f"inv-{cand.instance}"
        if len(body_name) > 48:
            body_name = f"inv-{normalize(cand.cause)[:16]}-{normalize(cand.effect)[:16]}"
        if normalize(body_name) in used_names:
            continue
        return Invention(
            cause=cand.cause,
            effect=cand.effect,
            instance=cand.instance,
            body_name=body_name,
            source=cand.source,
            why=cand.why,
            edit=cand.edit,
        )
    return None


def mark_used(instance: str, mind_store) -> None:
    registry = load_invent_registry(mind_store)
    key = normalize(instance)
    for cand in registry.candidates:
        if normalize(cand.instance) == key:
            cand.used = True
    save_invent_registry(registry, mind_store)


def mark_abandoned(instance: str, mind_store, *, why: str = "") -> None:
    registry = load_invent_registry(mind_store)
    key = normalize(instance)
    for cand in registry.candidates:
        if normalize(cand.instance) == key:
            cand.abandoned = True
            if why:
                cand.why = f"{cand.why}|abandoned:{why}" if cand.why else f"abandoned:{why}"
    save_invent_registry(registry, mind_store)


def search_edit_score_acceptable(before, after) -> bool:
    """Quality gate for applying search invent to the mind torus.

    Accept when StructuralScore.better_than holds, OR when dual_coverage and
    link_symmetry do not worsen and unused_path_cost does not rise. Node-count
    growth alone must not veto a structurally sound readable invent.
    """
    if after.better_than(before):
        return True
    return (
        after.dual_coverage >= before.dual_coverage
        and after.link_symmetry >= before.link_symmetry
        and after.unused_path_cost <= before.unused_path_cost
    )


# Fallback when live torus has no answerable cascade poles yet.
PRODUCT_PROBES: tuple[str, ...] = (
    "water",
    "boiling",
    "warm",
    "steam",
    "absence",
    "bright",
)


def product_probes_for(eng: Engine) -> tuple[str, ...]:
    """#8: present lexicon cascade cause/effect poles that exist + are answerable.

    Fixed PRODUCT_PROBES let invent lengthen unlisted cascade children (e.g. empty).
    Trial + scoreboard use this live set; falls back to PRODUCT_PROBES if empty.
    """
    from . import lexicon as lex
    from .engine import RuleError

    out: list[str] = []
    seen: set[str] = set()
    for entry in lex.all_cascades():
        for pole in (entry.cause, entry.effect):
            key = normalize(pole)
            if key in seen:
                continue
            if not eng.exists(pole):
                continue
            try:
                dual = eng.answer(pole)
            except RuleError:
                continue
            if not (dual.cause_paths and dual.effect_paths):
                continue
            seen.add(key)
            node = eng.torus.nodes.get(pole) or eng.torus.nodes.get(key)
            out.append(node.name if node is not None else pole)
    return tuple(out) if out else PRODUCT_PROBES


def _flatten_dual_path_names(dual: Any) -> list[str]:
    flat: list[str] = []
    for p in (
        list(getattr(dual, "cause_paths", None) or [])
        + list(getattr(dual, "effect_paths", None) or [])
        + list(getattr(dual, "between", None) or [])
    ):
        if isinstance(p, (list, tuple)):
            flat.extend(str(x) for x in p)
        else:
            flat.append(str(p))
    return flat


def _probe_answer_path_len(eng: Engine, topic: str) -> int | None:
    """Total cause+effect path hop count for a probe; None if missing/unanswerable."""
    from .engine import RuleError

    if not eng.exists(topic):
        return None
    try:
        dual = eng.answer(topic)
    except RuleError:
        return None
    if not (dual.cause_paths and dual.effect_paths):
        return None
    total = 0
    for p in list(dual.cause_paths or []) + list(dual.effect_paths or []):
        total += len(p) if isinstance(p, (list, tuple)) else 1
    return total


def _typed_probe_domain_ok(before_eng: Engine, after_eng: Engine) -> bool:
    """#5/#7/#8: typed probe paths must stay domain-coherent.

    For each live cascade probe with a lexicon/inherited domain D, answer-path
    poles must all carry D (no undomain motifs, no foreign typed domains).
    """
    from . import lexicon as lex
    from . import search_substrate as search_mod
    from .engine import RuleError, normalize as norm

    for topic in product_probes_for(before_eng):
        if not before_eng.exists(topic) or not after_eng.exists(topic):
            continue
        try:
            after_dual = after_eng.answer(topic)
        except RuleError:
            return False
        topic_domain = lex.pole_domain(topic) or search_mod.node_domain(after_eng, topic)
        if topic_domain is None:
            continue
        for name in _flatten_dual_path_names(after_dual):
            d = lex.pole_domain(norm(name))
            if d != topic_domain:
                return False
    return True


def _probe_path_economy_ok(before_eng: Engine, after_eng: Engine) -> bool:
    """#6/#7/#8: refuse invent that lengthens any present cascade probe path."""
    for topic in product_probes_for(before_eng):
        before_len = _probe_answer_path_len(before_eng, topic)
        after_len = _probe_answer_path_len(after_eng, topic)
        if before_len is None:
            continue
        if after_len is None:
            return False
        if after_len > before_len:
            return False
    return True


def product_exceed_reasons(
    before_eng: Engine,
    after_eng: Engine,
    pre: Any,
    post: Any,
) -> list[str]:
    """#9: ways invent strictly exceeds pre-invent product metrics.

    Exceeds (any one is enough):
    - shorter path on a present cascade probe, or lower probe_path_len_total
    - StructuralScore.better_than (coverage / symmetry / unused cost / leaner)
    - more answerable cascade probes (usable coverage) without lengthening paths
    """
    reasons: list[str] = []
    if post is not None and pre is not None and post.better_than(pre):
        reasons.append("structural_score")

    before_total = 0
    after_total = 0
    measured = 0
    for topic in product_probes_for(before_eng):
        before_len = _probe_answer_path_len(before_eng, topic)
        after_len = _probe_answer_path_len(after_eng, topic)
        if before_len is None:
            continue
        measured += 1
        before_total += before_len
        if after_len is None:
            continue
        after_total += after_len
        if after_len < before_len:
            reasons.append(f"probe_path_shorter:{normalize(topic)}")
    if measured and after_total < before_total:
        reasons.append("probe_path_len_total")

    # Usable coverage: more present answerable cascade poles, paths not longer.
    before_probes = product_probes_for(before_eng)
    after_probes = product_probes_for(after_eng)
    if len(after_probes) > len(before_probes) and _probe_path_economy_ok(
        before_eng, after_eng
    ):
        reasons.append("usable_probe_coverage")
    return reasons


def search_has_product_exceed_candidate(
    eng: Engine,
    *,
    used_instances: set[str] | None = None,
    limit: int = 6,
) -> bool:
    """#10: True when search still has ≥1 invent AST that earns a product exceed."""
    from . import search_substrate as search_mod
    from .center import LivingCenter

    pre = LivingCenter(eng).score()
    for row in search_mod.search_invent_asts(
        eng, used_instances=used_instances, limit=limit
    ):
        ast = list(row.get("ast") or [])
        if not ast:
            continue
        trial = search_mod._clone_engine(eng)
        if not search_mod.apply_edit_ast(trial, ast):
            continue
        post = LivingCenter(trial).score()
        if product_exceed_reasons(eng, trial, pre, post):
            return True
    return False


def _trial_search_edit(eng: Engine, edit: dict[str, Any]) -> tuple[bool, Any, Any, str]:
    """Trial-apply search edit_ast; return (ok, pre_score, post_score, reason)."""
    from . import search_substrate as search_mod
    from .center import LivingCenter

    ast = list(edit.get("ast") or [])
    if search_mod.rejects_digest_poles(ast):
        return False, None, None, "digest_poles"
    pre = LivingCenter(eng).score()
    trial = search_mod._clone_engine(eng)
    if not search_mod.apply_edit_ast(trial, ast):
        return False, pre, None, "dual_i1_failed"
    post = LivingCenter(trial).score()
    if not search_edit_score_acceptable(pre, post):
        return False, pre, post, "score_gate"
    # #5/#7: domain-coherent typed probe paths.
    if not _typed_probe_domain_ok(eng, trial):
        return False, pre, post, "domain_probe_path"
    # #6/#7: probe path length must not regress on any measured probe.
    if not _probe_path_economy_ok(eng, trial):
        return False, pre, post, "probe_path_len"
    # #9/#10: product exceed always ok; meet-only only when no exceed remains (C4).
    if product_exceed_reasons(eng, trial, pre, post):
        return True, pre, post, "ok"
    if search_has_product_exceed_candidate(eng):
        return False, pre, post, "meet_only_while_exceed"
    return True, pre, post, "ok"


def invent_and_embody(
    eng: Engine,
    mind_store,
    *,
    cycle: int | None = None,
    parent_body: str | None = None,
    activity: list[dict[str, Any]] | None = None,
    journal_rows: list[Any] | None = None,
):
    """Invent a new domain body; topology inventions also edit the mind graph."""
    from . import topology as topology_mod
    from .engine import Engine as Eng
    from . import store
    from .center import LivingCenter

    # Search invent may reject via score/digest gate; try a few candidates.
    # #10: defer meet-only (skip, do not abandon) while an exceed candidate remains
    # so C4 invent_domain can still apply path-neutral meet after exceeds are gone.
    proposal = None
    skipped_meet_only: set[str] = set()
    for _attempt in range(8):
        proposal = next_invention(
            eng,
            mind_store,
            activity=activity,
            journal_rows=journal_rows,
            skip_instances=skipped_meet_only,
        )
        if proposal is None:
            return None
        if not (
            proposal.source == "search"
            and proposal.edit
            and proposal.edit.get("kind") == "edit_ast"
        ):
            break
        ok, pre, post, reason = _trial_search_edit(eng, proposal.edit)
        if ok:
            break
        detail = {
            "act": "search_invent_reject",
            "instance": proposal.instance,
            "cause": proposal.cause,
            "effect": proposal.effect,
            "reason": reason,
            "score_before": pre.to_dict() if pre is not None else None,
            "score_after": post.to_dict() if post is not None else None,
            "provenance": "search-substrate:invent",
        }
        store.append_activity([detail], mind_store)
        if reason == "meet_only_while_exceed":
            # Keep candidate available for a later invent once no exceed remains.
            skipped_meet_only.add(normalize(proposal.instance))
        else:
            mark_abandoned(proposal.instance, mind_store, why=reason)
        proposal = None
    if proposal is None:
        return None

    mind_path = store.store_path(mind_store)
    body_path = mind_path.with_name(f"{mind_path.stem}.body.{proposal.body_name}.json")
    if body_path.exists():
        return None

    topology_applied = False
    if proposal.source == "topology" and proposal.edit:
        topology_applied = topology_mod.apply_topology_edit(eng, proposal.edit)
        if topology_applied:
            store.save(eng.torus, mind_path)
    elif proposal.source == "search" and proposal.edit and proposal.edit.get("kind") == "edit_ast":
        from . import search_substrate as search_mod

        topology_applied = search_mod.apply_edit_ast(eng, list(proposal.edit.get("ast") or []))
        if topology_applied:
            store.save(eng.torus, mind_path)

    # Body seed: search invent projects edit_ast into dual-safe body structure;
    # topology reparent uses digest poles; other invent sources keep seed_custom.
    if (
        proposal.source == "search"
        and proposal.edit
        and proposal.edit.get("kind") == "edit_ast"
    ):
        torus = seed_body_from_search_edit(
            proposal.edit,
            instance=proposal.instance,
            cause=proposal.cause,
            effect=proposal.effect,
        )
    elif proposal.source == "topology" and proposal.edit and proposal.edit.get("kind") == "reparent":
        # Fresh opposite pair named from the reparent instance digest — body still dual.
        digest = normalize(proposal.instance).replace("reparent-", "")[:8]
        body_cause = f"rc{digest}"
        body_effect = f"re{digest}"
        torus = seed_custom(body_cause, body_effect, instance=proposal.instance)
    else:
        torus = seed_custom(proposal.cause, proposal.effect, instance=proposal.instance)
    store.save(torus, body_path)
    store.clear_activity(body_path)

    body_eng = Eng(store.load(body_path))
    center = LivingCenter(body_eng)
    center.mind_store = body_path
    # Body warm-up must not re-enter primary-path invent (#2 / search).
    reports = center.think(3, allow_primary_invent=False)
    store.save(body_eng.torus, body_path)
    store.append_activity([r.to_dict() for r in reports], body_path)

    record = bodies.BodyRecord(
        name=proposal.body_name,
        store_path=str(body_path),
        domain=proposal.instance,
        parent_instance=eng.torus.instance,
        created_from_cycle=cycle,
        parent_body=parent_body,
    )
    invent_edit = (
        proposal.edit
        if proposal.source == "search"
        and proposal.edit
        and proposal.edit.get("kind") == "edit_ast"
        else None
    )
    form_path = bodies.write_form_module(
        record, mind_path, engine=body_eng, invent_edit=invent_edit
    )
    record.form_path = str(form_path)
    registry = bodies.load_registry(mind_path)
    registry.bodies.append(record)
    bodies.save_registry(registry, mind_path)
    mark_used(proposal.instance, mind_path)
    return {
        "invention": {
            "cause": proposal.cause,
            "effect": proposal.effect,
            "instance": proposal.instance,
            "source": proposal.source,
            "why": proposal.why,
            "edit": proposal.edit,
            "topology_applied": topology_applied,
        },
        "body": record.to_dict(),
    }
