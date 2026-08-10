"""Token cost accounting.

Prices are data, not code. They change often and vary by region and contract, so
they live in a user-editable table rather than being hardcoded into logic. Ship
with an empty default and require the user to supply prices for any model they
want costed: a wrong number is worse than a missing one.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field

from endstate.types import Usage


class ModelPrice(BaseModel):
    """USD per million tokens."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cached_input_per_mtok: Decimal | None = None

    def cost(self, usage: Usage) -> Decimal:
        cached_rate = (
            self.cached_input_per_mtok
            if self.cached_input_per_mtok is not None
            else self.input_per_mtok
        )
        million = Decimal(1_000_000)
        return (
            Decimal(usage.input_tokens) * self.input_per_mtok / million
            + Decimal(usage.output_tokens) * self.output_per_mtok / million
            + Decimal(usage.cached_input_tokens) * cached_rate / million
        )


class PriceTable(BaseModel):
    """Maps model id -> price. Load from JSON so it can be updated without a release."""

    prices: dict[str, ModelPrice] = Field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> PriceTable:
        data = json.loads(Path(path).read_text())
        return cls(prices={k: ModelPrice(**v) for k, v in data.items()})

    def get(self, model: str) -> ModelPrice | None:
        return self.prices.get(model)


class UnknownModelPriceError(KeyError):
    """Raised when a cost is requested for a model with no price entry."""


class CostAccountant:
    """Accumulates usage and converts it to money.

    Usage is always tracked. Cost is only reported for models with a known price;
    `total_cost` raises rather than silently under-reporting.
    """

    def __init__(self, price_table: PriceTable | None = None) -> None:
        self.price_table = price_table or PriceTable()
        self._usage_by_model: dict[str, Usage] = {}

    def record(self, model: str, usage: Usage) -> None:
        self._usage_by_model[model] = self._usage_by_model.get(model, Usage()) + usage

    @property
    def usage_by_model(self) -> dict[str, Usage]:
        return dict(self._usage_by_model)

    @property
    def total_usage(self) -> Usage:
        total = Usage()
        for usage in self._usage_by_model.values():
            total = total + usage
        return total

    def cost_for(self, model: str) -> Decimal:
        price = self.price_table.get(model)
        if price is None:
            raise UnknownModelPriceError(model)
        return price.cost(self._usage_by_model.get(model, Usage()))

    def total_cost(self) -> Decimal:
        return sum((self.cost_for(m) for m in self._usage_by_model), Decimal(0))

    def priced_models(self) -> list[str]:
        return [m for m in self._usage_by_model if self.price_table.get(m) is not None]

    def unpriced_models(self) -> list[str]:
        return [m for m in self._usage_by_model if self.price_table.get(m) is None]
