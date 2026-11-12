"""Maze cells, procedural generation, pathfinding, and in-maze objects."""

import heapq
import random

import pygame

from .settings import (
    BACKGROUND,
    BOOST_COLOR,
    EXIT_COLOR,
    ITEM_SPAWN_PROBABILITIES,
    LIGHT_COLOR,
    LOCKED_EXIT_COLOR,
    SOUL_COLOR,
    TRAP_COLOR,
    WALL_COLOR,
)


class Cell:
    """One maze tile, represented by four closed wall edges."""

    def __init__(self):
        self.walls = {"top": True, "right": True, "bottom": True, "left": True}
        self.visited = False


class MazeGenerator:
    """Build a perfect maze with randomized depth-first backtracking."""

    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols

    def generate(self):
        grid = [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]
        grid[0][0].visited = True
        stack = [(0, 0)]
        directions = (
            (0, -1, "top", "bottom"),
            (1, 0, "right", "left"),
            (0, 1, "bottom", "top"),
            (-1, 0, "left", "right"),
        )

        # Carve a random unvisited neighbor; popping at dead ends backtracks.
        while stack:
            col, row = stack[-1]
            neighbors = []
            for dx, dy, wall, opposite_wall in directions:
                next_col, next_row = col + dx, row + dy
                if (
                    0 <= next_col < self.cols
                    and 0 <= next_row < self.rows
                    and not grid[next_row][next_col].visited
                ):
                    neighbors.append((next_col, next_row, wall, opposite_wall))

            if not neighbors:
                stack.pop()
                continue

            next_col, next_row, wall, opposite_wall = random.choice(neighbors)
            grid[row][col].walls[wall] = False
            grid[next_row][next_col].walls[opposite_wall] = False
            grid[next_row][next_col].visited = True
            stack.append((next_col, next_row))

        return grid


class Soul:
    """Collectible required to unlock the maze exit."""

    def __init__(self, position):
        self.position = position
        self.collected = False

    def draw(self, screen, cell_size):
        if self.collected:
            return

        col, row = self.position
        center = (col * cell_size + cell_size // 2, row * cell_size + cell_size // 2)
        radius = max(4, cell_size // 5)
        pygame.draw.circle(screen, SOUL_COLOR, center, radius)
        pygame.draw.circle(screen, (135, 174, 220), center, radius, 1)


class MazeItem:
    """A collectible trap, wall-pass boost, or full-light power-up."""

    def __init__(self, kind, position):
        self.kind = kind
        self.position = position

    def draw(self, screen, cell_size):
        col, row = self.position
        center = (col * cell_size + cell_size // 2, row * cell_size + cell_size // 2)
        if self.kind == "beartrap":
            size = max(8, cell_size // 2)
            bounds = (center[0] - size // 2, center[1] - size // 2, size, size)
            pygame.draw.rect(screen, TRAP_COLOR, bounds, border_radius=2)
            pygame.draw.line(screen, (250, 220, 205), bounds[:2], (bounds[0] + size, bounds[1] + size), 2)
            pygame.draw.line(screen, (250, 220, 205), (bounds[0] + size, bounds[1]), (bounds[0], bounds[1] + size), 2)
        elif self.kind == "boost":
            points = (
                (center[0], center[1] - cell_size // 3),
                (center[0] - cell_size // 6, center[1] + 1),
                (center[0], center[1] + 1),
                (center[0], center[1] + cell_size // 3),
                (center[0] + cell_size // 6, center[1] - 2),
                (center[0], center[1] - 2),
            )
            pygame.draw.polygon(screen, BOOST_COLOR, points)
        else:
            pygame.draw.circle(screen, LIGHT_COLOR, center, max(5, cell_size // 5))
            pygame.draw.circle(screen, (255, 250, 210), center, max(3, cell_size // 9))
            pygame.draw.line(
                screen,
                LIGHT_COLOR,
                (center[0], center[1] - cell_size // 3),
                (center[0], center[1] - cell_size // 2),
                2,
            )


class MazeGrid:
    """Own the grid, collectibles, exit state, navigation, and maze drawing."""

    def __init__(self, rows, cols, cell_size, soul_count=3, item_probabilities=None):
        self.rows = rows
        self.cols = cols
        self.cell_size = cell_size
        self.soul_count = soul_count
        self.item_probabilities = dict(item_probabilities or ITEM_SPAWN_PROBABILITIES)
        if sum(self.item_probabilities.values()) > 1:
            raise ValueError("Item spawn probabilities must sum to at most 1")
        self.cells = []
        self.items = []
        self.souls = []
        self.exit_position = (cols // 2, rows // 2)
        self.exit_open = False
        self.regenerate()

    def regenerate(self):
        self.cells = MazeGenerator(self.rows, self.cols).generate()
        self.items.clear()
        self.souls = []
        self.exit_open = False
        available = [
            (col, row)
            for row in range(self.rows)
            for col in range(self.cols)
            if (col, row) not in ((0, 0), self.exit_position)
        ]
        for position in random.sample(available, min(self.soul_count, len(available))):
            soul = Soul(position)
            self.souls.append(soul)
            self.add_item(soul)
        self._spawn_random_items()

    def _spawn_random_items(self):
        occupied = {(0, 0), self.exit_position}
        occupied.update(soul.position for soul in self.souls)
        for row in range(self.rows):
            for col in range(self.cols):
                position = (col, row)
                if position in occupied:
                    continue
                roll = random.random()
                cumulative_probability = 0
                for kind, probability in self.item_probabilities.items():
                    cumulative_probability += probability
                    if roll < cumulative_probability:
                        self.add_item(MazeItem(kind, position))
                        occupied.add(position)
                        break

    @property
    def souls_remaining(self):
        return sum(not soul.collected for soul in self.souls)

    def collect_soul_at(self, col, row):
        for soul in self.souls:
            if not soul.collected and soul.position == (col, row):
                soul.collected = True
                self.exit_open = self.souls_remaining == 0
                return True
        return False

    def collect_item_at(self, col, row):
        for item in self.items:
            if isinstance(item, MazeItem) and item.position == (col, row):
                self.items.remove(item)
                return item.kind
        return None

    def can_move(self, col, row, direction, ignore_walls=False):
        moves = {
            "up": (0, -1, "top"),
            "right": (1, 0, "right"),
            "down": (0, 1, "bottom"),
            "left": (-1, 0, "left"),
        }
        if direction not in moves or not (0 <= col < self.cols and 0 <= row < self.rows):
            return False

        dx, dy, wall = moves[direction]
        next_col = col + dx
        next_row = row + dy
        return (
            0 <= next_col < self.cols
            and 0 <= next_row < self.rows
            and (ignore_walls or not self.cells[row][col].walls[wall])
        )

    def find_path(self, start, goal):
        """Use A* and return the ordered steps after start, or [] if unreachable."""
        if not self._in_bounds(start) or not self._in_bounds(goal) or start == goal:
            return []

        frontier = [(self._heuristic(start, goal), 0, start)]
        came_from = {start: None}
        costs = {start: 0}
        while frontier:
            _, cost, current = heapq.heappop(frontier)
            if cost != costs[current]:
                continue
            if current == goal:
                path = []
                while current != start:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return path

            for neighbor in self._open_neighbors(current):
                next_cost = cost + 1
                if next_cost < costs.get(neighbor, float("inf")):
                    costs[neighbor] = next_cost
                    came_from[neighbor] = current
                    priority = next_cost + self._heuristic(neighbor, goal)
                    heapq.heappush(frontier, (priority, next_cost, neighbor))
        return []

    def _open_neighbors(self, position):
        col, row = position
        for dx, dy, wall in (
            (0, -1, "top"),
            (1, 0, "right"),
            (0, 1, "bottom"),
            (-1, 0, "left"),
        ):
            next_col = col + dx
            next_row = row + dy
            if (
                0 <= next_col < self.cols
                and 0 <= next_row < self.rows
                and not self.cells[row][col].walls[wall]
            ):
                yield next_col, next_row

    def open_neighbors(self, position):
        return list(self._open_neighbors(position))

    def _in_bounds(self, position):
        col, row = position
        return 0 <= col < self.cols and 0 <= row < self.rows

    @staticmethod
    def _heuristic(start, goal):
        return abs(start[0] - goal[0]) + abs(start[1] - goal[1])

    def add_item(self, item):
        self.items.append(item)

    def random_position(self, excluded=()):
        excluded = set(excluded)
        available = [
            (col, row)
            for row in range(self.rows)
            for col in range(self.cols)
            if (col, row) not in excluded
        ]
        return random.choice(available) if available else (0, 0)

    def draw(self, screen):
        self._draw_exit(screen)
        self._draw_cells(screen)
        for item in self.items:
            item.draw(screen, self.cell_size)

    def _draw_exit(self, screen):
        col, row = self.exit_position
        x = col * self.cell_size
        y = row * self.cell_size
        inset = 5
        pygame.draw.rect(
            screen,
            EXIT_COLOR if self.exit_open else LOCKED_EXIT_COLOR,
            (x + inset, y + inset, self.cell_size - inset * 2, self.cell_size - inset * 2),
            border_radius=3,
        )
        pygame.draw.rect(
            screen,
            BACKGROUND,
            (x + self.cell_size // 2 - 3, y + self.cell_size // 2 - 4, 6, 9),
            border_radius=2,
        )

    def _draw_cells(self, screen):
        for row_index, row in enumerate(self.cells):
            for col_index, cell in enumerate(row):
                x = col_index * self.cell_size
                y = row_index * self.cell_size
                if cell.walls["top"]:
                    pygame.draw.line(screen, WALL_COLOR, (x, y), (x + self.cell_size, y), 2)
                if cell.walls["right"]:
                    pygame.draw.line(screen, WALL_COLOR, (x + self.cell_size, y), (x + self.cell_size, y + self.cell_size), 2)
                if cell.walls["bottom"]:
                    pygame.draw.line(screen, WALL_COLOR, (x, y + self.cell_size), (x + self.cell_size, y + self.cell_size), 2)
                if cell.walls["left"]:
                    pygame.draw.line(screen, WALL_COLOR, (x, y), (x, y + self.cell_size), 2)