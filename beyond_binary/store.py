"""JSON persistence for a Torus instance."""

from __future__ import annotations

import json
from pathlib import Path

from .model import Torus

DEFAULT_STORE = Path("data/torus.json")


def store_path(path: Path | str | None = None) -> Path:
    return Path(path) if path else DEFAULT_STORE


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
