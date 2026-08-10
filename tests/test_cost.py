from decimal import Decimal

import pytest

from endstate.telemetry.cost import (
    CostAccountant,
    ModelPrice,
    PriceTable,
    UnknownModelPriceError,
)
from endstate.types import Usage


def table() -> PriceTable:
    return PriceTable(
        prices={
            "m1": ModelPrice(input_per_mtok=Decimal("3"), output_per_mtok=Decimal("15")),
            "m2": ModelPrice(
                input_per_mtok=Decimal("1"),
                output_per_mtok=Decimal("2"),
                cached_input_per_mtok=Decimal("0.1"),
            ),
        }
    )


def test_cost_is_exact() -> None:
    acc = CostAccountant(table())
    acc.record("m1", Usage(input_tokens=1_000_000, output_tokens=1_000_000))
    assert acc.cost_for("m1") == Decimal("18")


def test_cached_tokens_use_the_cached_rate() -> None:
    acc = CostAccountant(table())
    acc.record("m2", Usage(cached_input_tokens=1_000_000))
    assert acc.cost_for("m2") == Decimal("0.1")


def test_usage_accumulates_per_model() -> None:
    acc = CostAccountant(table())
    acc.record("m1", Usage(input_tokens=10, output_tokens=5))
    acc.record("m1", Usage(input_tokens=1, output_tokens=1))
    assert acc.usage_by_model["m1"] == Usage(input_tokens=11, output_tokens=6)
    assert acc.total_usage.total_tokens == 17


def test_unknown_price_raises_instead_of_reporting_zero() -> None:
    acc = CostAccountant(table())
    acc.record("mystery", Usage(input_tokens=100))
    assert acc.unpriced_models() == ["mystery"]
    with pytest.raises(UnknownModelPriceError):
        acc.cost_for("mystery")


def test_total_cost_sums_priced_models() -> None:
    acc = CostAccountant(table())
    acc.record("m1", Usage(input_tokens=1_000_000))
    acc.record("m2", Usage(input_tokens=1_000_000))
    assert acc.total_cost() == Decimal("4")
