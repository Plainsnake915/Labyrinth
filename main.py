"""Launch Haunted Maze from the repository root."""

import asyncio

from haunted_maze.game import main as run_game


if __name__ == "__main__":
    asyncio.run(run_game())