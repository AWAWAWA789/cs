"""Fibonacci retracement and extension level utilities.

The module works with explicit price levels so it stays independent of any
specific swing-detection algorithm. Callers typically combine it with
``src.features.swing`` to pick the relevant high/low anchors.
"""

from __future__ import annotations

import pandas as pd


_RETRACEMENT_RATIOS = {
    "0.0": 0.0,
    "0.236": 0.236,
    "0.382": 0.382,
    "0.5": 0.5,
    "0.618": 0.618,
    "0.786": 0.786,
    "1.0": 1.0,
}

_EXTENSION_RATIOS = {
    "1.0": 1.0,
    "1.272": 1.272,
    "1.618": 1.618,
    "2.0": 2.0,
    "2.618": 2.618,
}


def retracement_levels(low: float, high: float) -> dict[str, float]:
    """Return Fibonacci retracement levels between ``low`` and ``high``.

    Levels are linearly interpolated from ``high`` (0.0) down to ``low``
    (1.0). When ``low > high`` the labels are still consistent: 0.0 maps to
    the first argument and 1.0 to the second.
    """
    diff = high - low
    return {name: high - ratio * diff for name, ratio in _RETRACEMENT_RATIOS.items()}


def extension_levels(low: float, high: float) -> dict[str, float]:
    """Return Fibonacci extension levels projected beyond ``high``.

    The 1.0 level equals ``high``; higher multiples project upward from the
    ``low -> high`` range. If the range is downward (``low > high``), the
    values project downward.
    """
    diff = high - low
    return {name: low + ratio * diff for name, ratio in _EXTENSION_RATIOS.items()}


def nearest_level(price: float, levels: dict[str, float]) -> tuple[str, float]:
    """Return the level name and absolute price distance closest to ``price``.

    Raises:
        ValueError: if ``levels`` is empty.
    """
    if not levels:
        raise ValueError("levels must not be empty")

    nearest_name = min(levels, key=lambda name: abs(levels[name] - price))
    distance = abs(levels[nearest_name] - price)
    return nearest_name, distance


def is_near_level(
    price: float,
    levels: dict[str, float],
    tolerance: float = 0.005,
    target_levels: tuple[str, ...] | None = None,
) -> tuple[bool, str | None, float]:
    """Check whether ``price`` is within a relative tolerance of a target level.

    Args:
        price: Current price.
        levels: Mapping of level names to prices.
        tolerance: Relative tolerance as a fraction of the high-low range.
            The absolute tolerance is computed from the range spanned by
            ``levels``.
        target_levels: Optional subset of level names to consider. If None,
            all provided levels are considered.

    Returns:
        A tuple ``(is_near, level_name, distance)``. ``level_name`` is None
        when no level is near.
    """
    candidates = levels
    if target_levels is not None:
        candidates = {name: levels[name] for name in target_levels if name in levels}

    if not candidates:
        return False, None, 0.0

    # Tolerance is relative to the full high-low range, not just the subset.
    all_values = list(levels.values())
    range_size = max(all_values) - min(all_values)
    abs_tolerance = tolerance * range_size if range_size > 0 else tolerance

    best_name: str | None = None
    best_distance = float("inf")
    for name, level_price in candidates.items():
        distance = abs(level_price - price)
        if distance < best_distance:
            best_distance = distance
            best_name = name

    if best_name is not None and best_distance <= abs_tolerance:
        return True, best_name, best_distance
    return False, None, best_distance
