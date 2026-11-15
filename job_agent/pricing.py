"""
16d: what a run cost, from prices YOU enter.

The run log has every run's tokens, but no prices: providers change them, and
a price written into the app would be wrong soon after. So the price of a
cloud model (per million input and output tokens, as the provider's pricing
page states it) is typed into Settings once, and Evals multiplies.

    cost = input tokens / 1,000,000 x input price
         + output tokens / 1,000,000 x output price

A model without a price has no cost shown (never a guess). A local model
has none either: it runs on your PC.

Saved as ONE setting, MODEL_PRICES, e.g.  "gpt-x=0.15/0.6;claude-haiku-5-5=1/5"
(a settings file keeps one value per line, and a model name may hold ":"
or "." or "-", so "=", "/" and ";" are the separators).

NO LLM here. Tests: tests/test_pricing.py.
"""

import os

SETTING = "MODEL_PRICES"
MAX_PRICE = 10_000.0  # per million tokens: far above any real price, catches a typo like 150000


def parse(text: str | None) -> dict[str, tuple[float, float]]:
    """ "gpt-x=0.15/0.6;..." -> {"gpt-x": (0.15, 0.6)}. Anything unreadable is skipped."""
    prices = {}
    for part in (text or "").split(";"):
        model, _, pair = part.partition("=")
        try:
            price_in, price_out = (float(x) for x in pair.split("/"))
        except ValueError:
            continue
        if model.strip() and price_in >= 0 and price_out >= 0:
            prices[model.strip()] = (price_in, price_out)
    return prices


def dump(prices: dict[str, tuple[float, float]]) -> str:
    return ";".join(f"{model}={price_in:g}/{price_out:g}" for model, (price_in, price_out) in sorted(prices.items()))


def saved() -> dict[str, tuple[float, float]]:
    return parse(os.getenv(SETTING, ""))


def with_price(prices: dict, model: str, price_in, price_out) -> dict:
    """`prices` with this model's price set; both None or "" removes it.
    Raises ValueError with a message for the Settings form."""
    model = (model or "").strip()
    if not model:
        raise ValueError("Choose a model before entering its price.")
    if any(ch in model for ch in "=;\n\r"):
        raise ValueError("This model's name can't be used for a price (it has = or ; in it).")
    out = dict(prices)
    if price_in in (None, "") and price_out in (None, ""):
        out.pop(model, None)
        return out
    try:
        price_in, price_out = float(price_in), float(price_out)
    except (TypeError, ValueError):
        raise ValueError("Enter both prices as numbers, for example 0.15 and 0.60.") from None
    if not (0 <= price_in <= MAX_PRICE and 0 <= price_out <= MAX_PRICE):
        raise ValueError(f"A price per million tokens must be between 0 and {MAX_PRICE:,.0f}.")
    out[model] = (price_in, price_out)
    return out


def cost(prices: dict, model: str | None, tokens_in, tokens_out) -> float | None:
    """What these tokens cost with this model, or None if it has no price."""
    price = prices.get(model or "")
    if price is None:
        return None
    return (float(tokens_in or 0) * price[0] + float(tokens_out or 0) * price[1]) / 1_000_000
