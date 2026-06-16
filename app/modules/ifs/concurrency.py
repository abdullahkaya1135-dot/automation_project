import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any


async def gather_limited(
    items: Sequence[Any],
    worker: Callable[[Any], Awaitable[Any]],
    *,
    concurrency: int,
) -> list[Any]:
    semaphore = asyncio.Semaphore(concurrency)

    async def run(item: Any) -> Any:
        async with semaphore:
            return await worker(item)

    if not items:
        return []
    return list(await asyncio.gather(*(run(item) for item in items)))
