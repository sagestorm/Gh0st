"""Generative substrate interface — gated, disabled by default.

Contract: store docs/generative-substrate-contract.md

This module is the pluggable proposal-source boundary. The Living Center remains
the authority for validate / accept / persist. No live external generator and no
LLM wrapper ship here — ``NullSubstrate`` always returns empty proposals.

Enable attempts via env ``BEYOND_BINARY_SUBSTRATE=1``. Until an authorized live
implementation is registered, enable still resolves to NullSubstrate.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

ENV_FLAG = "BEYOND_BINARY_SUBSTRATE"
STDLIB_PROVENANCE_PREFIX = "stdlib-compiler:"

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


def substrate_enabled() -> bool:
    """True only when BEYOND_BINARY_SUBSTRATE is explicitly on."""
    raw = os.environ.get(ENV_FLAG, "0")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def get_substrate() -> GenerativeSubstrate:
    """Resolve substrate. Live impls must be authorized; none ship today."""
    if not substrate_enabled():
        return NullSubstrate()
    # Flag on but no registered live generator → still null (fail closed).
    return NullSubstrate()


def is_active() -> bool:
    """True only when enabled *and* a non-null implementation is bound."""
    if not substrate_enabled():
        return False
    return get_substrate().name != "null"


def is_stdlib_provenance(provenance: str) -> bool:
    return str(provenance).startswith(STDLIB_PROVENANCE_PREFIX)


def center_validate(proposal: Proposal, center: Any) -> ValidationResult:
    """Fail-closed center validation stub (no live applicator yet)."""
    if proposal.axis not in AXES:
        return Reject(f"unknown axis: {proposal.axis}")
    if is_stdlib_provenance(proposal.provenance):
        return Reject("stdlib-compiler provenance is not substrate evidence")
    if center is None:
        return Reject("center required for dual validation")
    # Without an authorized applicator, opaque payloads cannot be installed safely.
    return Reject("no live substrate applicator; fail closed")


def consult(
    axis: Axis,
    context: dict[str, Any] | None = None,
    *,
    center: Any = None,
) -> list[dict[str, Any]]:
    """Optional hook used by invent/policy/goals/capability.

    When the flag is off (default), returns immediately with no substrate call
    side effects beyond status bookkeeping. When on, proposes → validates →
    accept only if center validation passes. NullSubstrate yields [].
    """
    if not substrate_enabled():
        return []
    ctx = dict(context or {})
    ctx.setdefault("axis", axis)
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
        row = {
            "proposal_id": prop.proposal_id,
            "axis": prop.axis,
            "artifact_id": artifact,
            "provenance": prop.provenance,
        }
        _ACCEPT_LOG.append(row)
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
