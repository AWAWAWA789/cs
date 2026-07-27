"""Risk management helpers for the MVP strategy.

The MVP uses a simple fixed-fractional risk model:
- Stop loss is placed just below the most recent swing low.
- Take profits are placed at Fibonacci extension levels from the swing low
  to the swing high that preceded the entry.
"""

from __future__ import annotations

from src.features.fibonacci import extension_levels


def stop_loss(entry_price: float, swing_low: float, buffer: float = 0.002) -> float:
    """Return a stop-loss price slightly below ``swing_low``.

    Args:
        entry_price: Entry price (used only as a sanity floor).
        swing_low: Recent swing low price.
        buffer: Fractional buffer below the swing low.

    Returns:
        Stop-loss price, never higher than ``entry_price``.
    """
    sl = swing_low * (1 - buffer)
    return min(sl, entry_price)


def take_profit_levels(
    swing_low: float, swing_high: float, targets: tuple[str, ...] = ("1.272", "1.618")
) -> dict[str, float]:
    """Return selected Fibonacci extension levels above the swing high.

    Args:
        swing_low: Recent swing low.
        swing_high: Recent swing high.
        targets: Subset of extension level names to return.

    Returns:
        Mapping of level name to price.
    """
    levels = extension_levels(swing_low, swing_high)
    return {name: levels[name] for name in targets if name in levels}


def position_size(
    capital: float,
    risk_fraction: float,
    entry_price: float,
    stop_loss_price: float,
) -> float:
    """Return the number of units to buy for a fixed-fraction risk.

    Args:
        capital: Current account equity.
        risk_fraction: Fraction of capital to risk (e.g. 0.02 for 2%).
        entry_price: Planned entry price.
        stop_loss_price: Planned stop-loss price.

    Returns:
        Position size in units. Returns ``0.0`` when the risk distance is
        non-positive.
    """
    risk_amount = capital * risk_fraction
    risk_per_unit = entry_price - stop_loss_price
    if risk_per_unit <= 0:
        return 0.0
    return risk_amount / risk_per_unit
