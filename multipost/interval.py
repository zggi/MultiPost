"""Interval between platform publishes (anti-spam spacing).

A job publishes SEQUENTIALLY; between two targets the engine waits
`interval_seconds` (0 = no wait). With `randomize` on, the actual wait is
uniformly drawn from [50%, 150%] of the base - fixed rhythms are the easiest
bot signal for platforms to spot.
"""

from __future__ import annotations

import random


def next_delay(base_seconds: float, randomize: bool,
               rng: random.Random | None = None) -> float:
    base = max(0.0, float(base_seconds or 0))
    if base <= 0:
        return 0.0
    if not randomize:
        return base
    rng = rng or random
    return round(rng.uniform(base * 0.5, base * 1.5), 1)


def describe(base_seconds: float, randomize: bool) -> str:
    base = max(0.0, float(base_seconds or 0))
    if base <= 0:
        return "tanpa jeda"
    if randomize:
        return f"jeda acak {base * 0.5:g}–{base * 1.5:g} dtk"
    return f"jeda {base:g} dtk"
