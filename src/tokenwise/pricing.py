"""
Anthropic model pricing — last verified 2026-04-29.
Prices are per 1 million tokens (USD).
Source: https://www.anthropic.com/pricing
Run `tokenwise update-prices` stub when Anthropic updates their page.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input: float  # $/MTok
    output: float  # $/MTok
    cache_write: float  # $/MTok  (prompt cache write)
    cache_read: float  # $/MTok  (prompt cache read)


def _p(i: float, o: float, cw: float, cr: float) -> ModelPrice:
    return ModelPrice(input=i, output=o, cache_write=cw, cache_read=cr)


# fmt: off
PRICES: dict[str, ModelPrice] = {
    # Claude 4.x  ────────────────────────────── input   output  cw      cr
    "claude-opus-4-7":            _p(15.00, 75.00, 18.75, 1.50),
    "claude-sonnet-4-6":          _p( 3.00, 15.00,  3.75, 0.30),
    "claude-haiku-4-5":           _p( 0.80,  4.00,  1.00, 0.08),
    "claude-haiku-4-5-20251001":  _p( 0.80,  4.00,  1.00, 0.08),

    # Claude 3.x  ────────────────────────────── input   output  cw      cr
    "claude-3-5-sonnet-20241022": _p( 3.00, 15.00,  3.75, 0.30),
    "claude-3-5-sonnet-20240620": _p( 3.00, 15.00,  3.75, 0.30),
    "claude-3-5-haiku-20241022":  _p( 0.80,  4.00,  1.00, 0.08),
    "claude-3-opus-20240229":     _p(15.00, 75.00, 18.75, 1.50),
    "claude-3-haiku-20240307":    _p( 0.25,  1.25,  0.30, 0.03),
    "claude-3-sonnet-20240229":   _p( 3.00, 15.00,  3.75, 0.30),
}

# Fallback for unknown / future model names — matched by prefix
_PREFIX_FALLBACKS: list[tuple[str, ModelPrice]] = [
    ("claude-opus",   PRICES["claude-opus-4-7"]),
    ("claude-sonnet", PRICES["claude-sonnet-4-6"]),
    ("claude-haiku",  PRICES["claude-haiku-4-5"]),
]
# fmt: on

_MTok = 1_000_000


def get_price(model: str) -> ModelPrice:
    if model in PRICES:
        return PRICES[model]
    for prefix, price in _PREFIX_FALLBACKS:
        if model.startswith(prefix):
            return price
    # Unknown model — use Sonnet as a conservative estimate
    return PRICES["claude-sonnet-4-6"]


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
) -> float:
    p = get_price(model)
    return (
        input_tokens * p.input / _MTok
        + output_tokens * p.output / _MTok
        + cache_write_tokens * p.cache_write / _MTok
        + cache_read_tokens * p.cache_read / _MTok
    )
