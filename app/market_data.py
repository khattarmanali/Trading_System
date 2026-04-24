from __future__ import annotations

import asyncio
import contextlib
import random
from decimal import Decimal

from redis.asyncio import Redis

from app.config import Settings
from app.services import quantize_money


async def seed_market_prices(redis: Redis, settings: Settings) -> None:
    for symbol, initial_price in settings.initial_symbol_prices.items():
        key = f"price:{symbol}"
        if await redis.get(key) is None:
            await redis.set(key, f"{quantize_money(Decimal(str(initial_price)))}")


async def update_market_prices_forever(redis: Redis, settings: Settings) -> None:
    symbols = settings.tracked_symbols
    variation = Decimal(str(settings.price_variation_ratio))

    while True:
        for symbol in symbols:
            key = f"price:{symbol}"
            current_raw = await redis.get(key)
            current_price = Decimal(current_raw or settings.initial_symbol_prices[symbol])
            move = Decimal(str(random.uniform(float(-variation), float(variation))))
            next_price = current_price * (Decimal("1") + move)
            next_price = max(next_price, Decimal("1"))
            await redis.set(key, f"{quantize_money(next_price)}")
        await asyncio.sleep(settings.price_update_interval_seconds)


async def cancel_background_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
