# /// script
# dependencies = ["pygame-ce"]
# ///

"""Launch the standalone game entry point."""

import asyncio

from game import main as run_game


def _run_game_safely(coro):
    """Support desktop and browser-managed event loops."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    loop = asyncio.get_running_loop()
    loop.create_task(coro)


if __name__ == "__main__":
    _run_game_safely(run_game())
