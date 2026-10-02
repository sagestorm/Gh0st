"""First instance seed: hot / cold synonym cascade.

Cascade (outline): hot → boiling → water → condensation
  - hot (cause) ↔ cold (effect)
  - boiling under hot ↔ freezing under cold  (each state gets an antonym)
  - water under boiling ↔ condensation under cold  (water links condensation)
"""

from __future__ import annotations

from .engine import Engine
from .model import Torus


def seed_hot_cold(torus: Torus | None = None) -> Torus:
    torus = torus or Torus()
    torus.instance = "hot-cold"
    eng = Engine(torus)

    eng.add_pair("hot", "cold")
    eng.add_under(
        "hot",
        "boiling",
        opposite_name="freezing",
        opposite_parent="cold",
    )
    eng.add_under(
        "boiling",
        "water",
        opposite_name="condensation",
        opposite_parent="cold",
    )
    eng.assert_no_orphans()
    return torus
