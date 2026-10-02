"""Generative substrate interface — gated, disabled by default.

Contract: store docs/generative-substrate-contract.md

Pluggable proposal-source boundary. The Living Center remains the authority
for validate / accept / persist.

- Default / unset → ``NullSubstrate`` (inactive)
- ``BEYOND_BINARY_SUBSTRATE=1`` → still Null (fail closed without named impl)
- ``BEYOND_BINARY_SUBSTRATE=search`` → in-process ``SearchSubstrate`` (non-LLM)
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

ENV_FLAG = "BEYOND_BINARY_SUBSTRATE"
STDLIB_PROVENANCE_PREFIX = "stdlib-compiler:"
SEARCH_PROVENANCE_PREFIX = "search-substrate:"

Axis = Literal["invent", "reflect", "goal", "form"]
AXES: frozenset[str] = frozenset({"invent", "reflect", "goal", "form"})

# Reject log for honesty (acceptance rates alone must not flip SENTIENCE).
_REJECT_LOG: list[dict[str, Any]] = []
_ACCEPT_LOG: list[dict[str, Any]] = []


@dataclass(frozen=True)
class Proposal:
    """Opaque substrate proposal — shape is not drawn from stdlib compilers."""

    axis: Axis
    payload: Any
    provenance: str
    proposal_id: str = field(default_factory=lambda: f"prop-{uuid.uuid4().hex[:10]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "axis": self.axis,
            "payload": self.payload,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    reason: str

    @property
    def ok(self) -> bool:
        return self.accepted


def Accept(reason: str = "ok") -> ValidationResult:
    return ValidationResult(True, reason)


def Reject(reason: str) -> ValidationResult:
    return ValidationResult(False, reason)


@runtime_checkable
class GenerativeSubstrate(Protocol):
    """Pluggable proposal source. Center owns validation and persistence."""

    name: str

    def propose(self, context: dict[str, Any]) -> list[Proposal]:
        """Return candidate proposals for the given center context."""

    def validate(self, proposal: Proposal, center: Any) -> ValidationResult:
        """Axis-specific dual / invariant checks (center-authoritative)."""

    def accept(self, proposal: Proposal, *, center: Any = None) -> str | None:
        """Persist an accepted proposal; return artifact id or None."""


class NullSubstrate:
    """Default substrate — no proposals, fail-closed validate/accept."""

    name = "null"

    def propose(self, context: dict[str, Any]) -> list[Proposal]:
        return []

    def validate(self, proposal: Proposal, center: Any) -> ValidationResult:
        return Reject("null substrate: no live generator")

    def accept(self, proposal: Proposal, *, center: Any = None) -> str | None:
        return None


def _flag_raw() -> str:
    return str(os.environ.get(ENV_FLAG, "0")).strip().lower()


def substrate_enabled() -> bool:
    """True when BEYOND_BINARY_SUBSTRATE is explicitly on (1/true/on/search)."""
    return _flag_raw() in {"1", "true", "yes", "on", "search"}


def substrate_impl_name() -> str:
    """Requested implementation name from the env flag."""
    raw = _flag_raw()
    if raw == "search":
        return "search"
    if raw in {"1", "true", "yes", "on"}:
        return "null"  # enable without named live impl → still null
    return "null"


def get_substrate() -> GenerativeSubstrate:
    """Resolve substrate. ``search`` binds SearchSubstrate; else Null."""
    if not substrate_enabled():
        return NullSubstrate()
    if substrate_impl_name() == "search":
        from .search_substrate import SearchSubstrate

        return SearchSubstrate()
    return NullSubstrate()


def is_active() -> bool:
    """True only when enabled *and* a non-null implementation is bound."""
    if not substrate_enabled():
        return False
    return get_substrate().name != "null"


def is_stdlib_provenance(provenance: str) -> bool:
    return str(provenance).startswith(STDLIB_PROVENANCE_PREFIX)


def is_search_provenance(provenance: str) -> bool:
    return str(provenance).startswith(SEARCH_PROVENANCE_PREFIX)


def center_validate(proposal: Proposal, center: Any) -> ValidationResult:
    """Center-authoritative validation. Delegates to live substrate when bound."""
    if proposal.axis not in AXES:
        return Reject(f"unknown axis: {proposal.axis}")
    if is_stdlib_provenance(proposal.provenance):
        return Reject("stdlib-compiler provenance is not substrate evidence")
    if center is None and proposal.axis in {"invent", "form"}:
        return Reject("center/engine required for dual validation")
    sub = get_substrate()
    if sub.name == "null":
        return Reject("no live substrate applicator; fail closed")
    # Live substrate validates (dual / I1 / axis invariants).
    return sub.validate(proposal, center)


def consult(
    axis: Axis,
    context: dict[str, Any] | None = None,
    *,
    center: Any = None,
) -> list[dict[str, Any]]:
    """Optional hook used by invent/policy/goals/capability.

    When the flag is off (default), returns immediately. When on, proposes →
    validates → accept only if validation passes. Rejects are logged.
    """
    if not substrate_enabled():
        return []
    ctx = dict(context or {})
    ctx.setdefault("axis", axis)
    if center is not None:
        ctx.setdefault("center", center)
    sub = get_substrate()
    out: list[dict[str, Any]] = []
    for prop in sub.propose(ctx):
        if prop.axis != axis:
            _REJECT_LOG.append(
                {
                    "proposal_id": prop.proposal_id,
                    "axis": prop.axis,
                    "reason": f"axis mismatch: expected {axis}",
                }
            )
            continue
        # Substrate may self-validate; center always re-checks (authority).
        sub_vr = sub.validate(prop, center)
        if not sub_vr.accepted:
            _REJECT_LOG.append(
                {
                    "proposal_id": prop.proposal_id,
                    "axis": prop.axis,
                    "reason": sub_vr.reason,
                    "provenance": prop.provenance,
                }
            )
            continue
        center_vr = center_validate(prop, center)
        if not center_vr.accepted:
            _REJECT_LOG.append(
                {
                    "proposal_id": prop.proposal_id,
                    "axis": prop.axis,
                    "reason": center_vr.reason,
                    "provenance": prop.provenance,
                }
            )
            continue
        artifact = sub.accept(prop, center=center)
        if artifact is None:
            _REJECT_LOG.append(
                {
                    "proposal_id": prop.proposal_id,
                    "axis": prop.axis,
                    "reason": "accept returned no artifact",
                    "provenance": prop.provenance,
                }
            )
            continue
        dedupe_key = (str(prop.axis), str(artifact))
        if any(
            str(a.get("axis")) == dedupe_key[0]
            and str(a.get("artifact_id")) == dedupe_key[1]
            for a in _ACCEPT_LOG
        ):
            continue
        row = {
            "proposal_id": prop.proposal_id,
            "axis": prop.axis,
            "artifact_id": artifact,
            "provenance": prop.provenance,
        }
        _ACCEPT_LOG.append(dict(row))
        out.append(row)
    return out


def status() -> dict[str, Any]:
    """Honesty snapshot for verify gates."""
    sub = get_substrate()
    non_stdlib_accepts = [
        a
        for a in _ACCEPT_LOG
        if not is_stdlib_provenance(str(a.get("provenance", "")))
    ]
    return {
        "flag": ENV_FLAG,
        "enabled": substrate_enabled(),
        "active": is_active(),
        "implementation": sub.name,
        "rejects": len(_REJECT_LOG),
        "accepts": len(_ACCEPT_LOG),
        "accepted_non_stdlib": list(non_stdlib_accepts),
        "axes_with_non_stdlib_accepts": sorted(
            {str(a.get("axis")) for a in non_stdlib_accepts if a.get("axis")}
        ),
    }


def reset_logs_for_tests() -> None:
    """Clear accept/reject logs (tests only)."""
    _REJECT_LOG.clear()
    _ACCEPT_LOG.clear()
    try:
        from . import search_substrate as ss

        ss.reset_pending_for_tests()
    except Exception:  # noqa: BLE001
        pass


def all_axes_have_non_stdlib_accepts() -> bool:
    """True iff invent|reflect|goal|form each have ≥1 non-stdlib accept."""
    axes = set(status().get("axes_with_non_stdlib_accepts") or [])
    return AXES <= axes
