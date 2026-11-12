"""Ghost FSMs and the Markov-predictive shadow boss."""

import random

import pygame

from .lighting import point_in_flashlight_cone
from .settings import (
    BOSS_COLOR,
    BOSS_EYE_COLOR,
    BOSS_MOVE_INTERVAL_MS,
    BOSS_PATH_COLOR,
    BOSS_LIGHT_RESET_MS,
    CELL_SIZE,
    GHOST_COLOR,
    GHOST_EYE_COLOR,
    GHOST_MOVE_INTERVAL_MS,
    MOVES,
    PATH_COLOR,
    PREDICTION_COLOR,
)


class BossEnemy:
    """Predict player movement, navigate toward an ambush, and retreat from light."""

    def __init__(self, position):
        self.col, self.row = position
        self.spawn_position = position
        self.move_interval = BOSS_MOVE_INTERVAL_MS
        self.move_timer = 0
        self.target = position
        self.path = []
        self.predicted_position = position
        self.light_exposure_ms = 0

    def update(
        self,
        elapsed_ms,
        maze,
        player,
        predictor,
        flashlight_active=False,
        cursor_position=None,
    ):
        if (
            flashlight_active
            and cursor_position is not None
            and point_in_flashlight_cone(player, cursor_position, (self.col, self.row))
        ):
            self.light_exposure_ms += elapsed_ms
            self.path = []
            if self.light_exposure_ms >= BOSS_LIGHT_RESET_MS:
                self.col, self.row = self.spawn_position
                self.light_exposure_ms = 0
            return

        self.light_exposure_ms = 0
        predicted_col, predicted_row = player.col, player.row
        for direction in predictor.predict_sequence(steps=3):
            if maze.can_move(
                predicted_col,
                predicted_row,
                direction,
                ignore_walls=player.boost_remaining_ms > 0,
            ):
                dx, dy = MOVES[direction]
                predicted_col += dx
                predicted_row += dy

        self.predicted_position = (predicted_col, predicted_row)
        self.target = self.predicted_position
        self.path = maze.find_path((self.col, self.row), self.target)
        self.move_timer += elapsed_ms
        if self.move_timer >= self.move_interval:
            self.move_timer = 0
            if self.path:
                self.col, self.row = self.path.pop(0)
                self.path = maze.find_path((self.col, self.row), self.target)

    def touches(self, player):
        return (self.col, self.row) == (player.col, player.row)

    @property
    def visual_scale(self):
        exposure = min(self.light_exposure_ms / BOSS_LIGHT_RESET_MS, 1.0)
        return 1.0 - exposure * 0.9

    def draw(self, screen, cell_size=CELL_SIZE):
        center = (self.col * cell_size + cell_size // 2, self.row * cell_size + cell_size // 2)
        scale = self.visual_scale
        pygame.draw.circle(screen, BOSS_COLOR, center, max(1, round(cell_size // 3 * scale)))
        eye_radius = max(1, round(2 * scale))
        eye_offset = max(1, round(4 * scale))
        eye_y = max(1, round(2 * scale))
        pygame.draw.circle(screen, BOSS_EYE_COLOR, (center[0] - eye_offset, center[1] - eye_y), eye_radius)
        pygame.draw.circle(screen, BOSS_EYE_COLOR, (center[0] + eye_offset, center[1] - eye_y), eye_radius)

    def draw_debug(self, screen, cell_size=CELL_SIZE):
        points = [(self.col * cell_size + cell_size // 2, self.row * cell_size + cell_size // 2)]
        points.extend((col * cell_size + cell_size // 2, row * cell_size + cell_size // 2) for col, row in self.path)
        if len(points) > 1:
            pygame.draw.lines(screen, BOSS_PATH_COLOR, False, points, 2)
        col, row = self.predicted_position
        pygame.draw.rect(
            screen,
            PREDICTION_COLOR,
            (col * cell_size + 4, row * cell_size + 4, cell_size - 8, cell_size - 8),
            2,
        )


class GhostNPC:
    """A soul-assigned ghost that follows a route, chases, or wanders."""

    def __init__(self, position, soul, route=None):
        self.col, self.row = position
        self.start_position = position
        self.soul = soul
        self.target = soul.position
        self.state = "Patrol"
        self.move_interval = GHOST_MOVE_INTERVAL_MS
        self.move_timer = 0
        self.path = []
        self.route = list(route) if route else []
        self.route_index = self.route.index(position) if position in self.route else None

    def update(self, elapsed_ms, maze, player_position):
        position = (self.col, self.row)
        if self.soul.collected:
            if self.state != "Wander":
                self.target = None
            self.state = "Wander"
            if self.target is None or position == self.target:
                self.target = maze.random_position(excluded=(position, maze.exit_position))
        else:
            if not self.route:
                self.route = [self.soul.position] + maze.find_path(
                    self.soul.position, maze.exit_position
                )
            if self.route_index is None and position in self.route:
                self.route_index = self.route.index(position)
            if player_position in self.route:
                self.state = "Chase"
                self.target = self.soul.position
            else:
                self.state = "Patrol"
                self.target = maze.exit_position

        self.move_timer += elapsed_ms
        if self.move_timer < self.move_interval:
            return
        self.move_timer = 0

        if self.state == "Wander":
            neighbors = maze.open_neighbors(position)
            self.path = [random.choice(neighbors)] if neighbors else []
        elif self.route_index is not None:
            if self.state == "Chase":
                self.path = list(reversed(self.route[:self.route_index]))
            else:
                self.path = self.route[self.route_index + 1:]
        else:
            self.path = maze.find_path(position, self.target)

        if self.path:
            self.col, self.row = self.path.pop(0)
            if self.route and (self.col, self.row) in self.route:
                self.route_index = self.route.index((self.col, self.row))
            if self.state != "Wander" and (self.col, self.row) == self.target:
                if self.state == "Chase":
                    self.col, self.row = maze.exit_position
                    self.route_index = len(self.route) - 1
                else:
                    self.col, self.row = self.start_position
                    if self.start_position in self.route:
                        self.route_index = self.route.index(self.start_position)
                self.path = []

    def draw(self, screen, cell_size=CELL_SIZE):
        center = (self.col * cell_size + cell_size // 2, self.row * cell_size + cell_size // 2)
        pygame.draw.circle(screen, GHOST_COLOR, center, cell_size // 3)
        pygame.draw.circle(screen, GHOST_EYE_COLOR, (center[0] - 4, center[1] - 2), 2)
        pygame.draw.circle(screen, GHOST_EYE_COLOR, (center[0] + 4, center[1] - 2), 2)

    def draw_path(self, screen, cell_size=CELL_SIZE):
        points = [(self.col * cell_size + cell_size // 2, self.row * cell_size + cell_size // 2)]
        points.extend((col * cell_size + cell_size // 2, row * cell_size + cell_size // 2) for col, row in self.path)
        if len(points) > 1:
            pygame.draw.lines(screen, PATH_COLOR, False, points, 2)


def create_ghosts(maze):
    """Create exactly one ghost per soul, starting at that soul's cell."""
    ghosts = []
    for soul in maze.souls:
        route = [soul.position] + maze.find_path(soul.position, maze.exit_position)
        ghosts.append(GhostNPC(soul.position, soul, route))
    return ghosts


def create_boss(maze):
    """Place the boss away from the player, exit, souls, and other pickups."""
    excluded = {(0, 0), maze.exit_position}
    excluded.update(soul.position for soul in maze.souls)
    excluded.update(item.position for item in maze.items if hasattr(item, "position"))
    return BossEnemy(maze.random_position(excluded))