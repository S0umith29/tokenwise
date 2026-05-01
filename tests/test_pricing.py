"""Tests for the pricing module."""

import pytest

from tokenwise.pricing import PRICES, ModelPrice, compute_cost, get_price

_MTok = 1_000_000


# ---------------------------------------------------------------------------
# get_price — exact model lookup
# ---------------------------------------------------------------------------


def test_get_price_known_model_sonnet():
    price = get_price("claude-sonnet-4-6")
    assert price is PRICES["claude-sonnet-4-6"]
    assert price.input == 3.00
    assert price.output == 15.00
    assert price.cache_write == 3.75
    assert price.cache_read == 0.30


def test_get_price_known_model_opus():
    price = get_price("claude-opus-4-7")
    assert price.input == 15.00
    assert price.output == 75.00


def test_get_price_known_model_haiku():
    price = get_price("claude-haiku-4-5")
    assert price.input == 0.80


def test_get_price_known_model_haiku_dated():
    price = get_price("claude-haiku-4-5-20251001")
    assert price == PRICES["claude-haiku-4-5"]


# ---------------------------------------------------------------------------
# get_price — prefix fallback
# ---------------------------------------------------------------------------


def test_get_price_prefix_fallback_sonnet():
    price = get_price("claude-sonnet-99-future")
    assert price == PRICES["claude-sonnet-4-6"]


def test_get_price_prefix_fallback_opus():
    price = get_price("claude-opus-99-future")
    assert price == PRICES["claude-opus-4-7"]


def test_get_price_prefix_fallback_haiku():
    price = get_price("claude-haiku-99-future")
    assert price == PRICES["claude-haiku-4-5"]


# ---------------------------------------------------------------------------
# get_price — unknown model fallback
# ---------------------------------------------------------------------------


def test_get_price_unknown_model_falls_back_to_sonnet():
    price = get_price("some-completely-unknown-model")
    assert price == PRICES["claude-sonnet-4-6"]


def test_get_price_empty_string_falls_back_to_sonnet():
    price = get_price("")
    assert price == PRICES["claude-sonnet-4-6"]


# ---------------------------------------------------------------------------
# ModelPrice is a frozen dataclass
# ---------------------------------------------------------------------------


def test_model_price_is_frozen():
    price = get_price("claude-sonnet-4-6")
    with pytest.raises((AttributeError, TypeError)):
        price.input = 999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# All prices have positive values
# ---------------------------------------------------------------------------


def test_all_prices_have_positive_values():
    for model, price in PRICES.items():
        assert price.input > 0, f"{model}: input price must be > 0"
        assert price.output > 0, f"{model}: output price must be > 0"
        assert price.cache_write > 0, f"{model}: cache_write price must be > 0"
        assert price.cache_read > 0, f"{model}: cache_read price must be > 0"


# ---------------------------------------------------------------------------
# compute_cost
# ---------------------------------------------------------------------------


def test_compute_cost_zero_tokens():
    assert compute_cost("claude-sonnet-4-6", 0, 0, 0, 0) == 0.0


def test_compute_cost_input_only():
    cost = compute_cost("claude-sonnet-4-6", _MTok, 0, 0, 0)
    assert abs(cost - 3.00) < 1e-9


def test_compute_cost_output_only():
    cost = compute_cost("claude-sonnet-4-6", 0, _MTok, 0, 0)
    assert abs(cost - 15.00) < 1e-9


def test_compute_cost_cache_write_only():
    cost = compute_cost("claude-sonnet-4-6", 0, 0, _MTok, 0)
    assert abs(cost - 3.75) < 1e-9


def test_compute_cost_cache_read_only():
    cost = compute_cost("claude-sonnet-4-6", 0, 0, 0, _MTok)
    assert abs(cost - 0.30) < 1e-9


def test_compute_cost_all_token_types():
    cost = compute_cost("claude-sonnet-4-6", _MTok, _MTok, _MTok, _MTok)
    expected = 3.00 + 15.00 + 3.75 + 0.30
    assert abs(cost - expected) < 1e-9


def test_compute_cost_opus_model():
    cost = compute_cost("claude-opus-4-7", _MTok, 0, 0, 0)
    assert abs(cost - 15.00) < 1e-9


def test_compute_cost_unknown_model_uses_sonnet_pricing():
    cost_unknown = compute_cost("mystery-model", _MTok, 0, 0, 0)
    cost_sonnet = compute_cost("claude-sonnet-4-6", _MTok, 0, 0, 0)
    assert abs(cost_unknown - cost_sonnet) < 1e-9


def test_compute_cost_small_token_count():
    cost = compute_cost("claude-sonnet-4-6", 100, 50, 0, 0)
    expected = 100 * 3.00 / _MTok + 50 * 15.00 / _MTok
    assert abs(cost - expected) < 1e-12
