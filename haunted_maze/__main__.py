"""Allow running the game with ``python -m haunted_maze``."""

import asyncio

from .game import main


if __name__ == "__main__":
    asyncio.run(main())