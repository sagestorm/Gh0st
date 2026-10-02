"""JSON persistence for a Torus instance + center activity log beside it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import Torus

DEFAULT_STORE = Path("data/torus.json")


def store_path(path: Path | str | None = None) -> Path:
    return Path(path) if path else DEFAULT_STORE


def activity_log_path(path: Path | str | None = None) -> Path:
    """Activity log lives beside the torus JSON (e.g. data/torus.center.jsonl)."""
    target = store_path(path)
    return target.with_name(f"{target.stem}.center.jsonl")


def save(torus: Torus, path: Path | str | None = None) -> Path:
    target = store_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(torus.to_dict(), indent=2, sort_keys=True) + "\n")
    return target


def load(path: Path | str | None = None) -> Torus:
    target = store_path(path)
    if not target.exists():
        raise FileNotFoundError(
            f"No torus at {target}. Run: python -m beyond_binary init"
        )
    return Torus.from_dict(json.loads(target.read_text()))


def append_activity(
    records: list[dict[str, Any]],
    path: Path | str | None = None,
) -> Path:
    """Append cycle reports to the center activity log (JSON Lines)."""
    target = activity_log_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    return target


def load_activity(path: Path | str | None = None) -> list[dict[str, Any]]:
    target = activity_log_path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def clear_activity(path: Path | str | None = None) -> None:
    target = activity_log_path(path)
    if target.exists():
        target.unlink()
