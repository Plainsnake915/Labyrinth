"""Player position, movement rules, pickups, and timed effects."""

import pygame

from .settings import (
    CELL_SIZE,
    FLASHLIGHT_DRAIN_RATE,
    FLASHLIGHT_MAX_CHARGE_MS,
    FLASHLIGHT_RECHARGE_RATE,
    FULL_LIGHT_DURATION_MS,
    LIGHT_BOOST_TRANSITION_MS,
    LIGHT_RADIUS,
    MAX_LIGHT_RADIUS,
    PLAYER_COLOR,
)


class Player:
    """Grid-based player with timed trap, boots, and light effects."""

    def __init__(self, col=0, row=0):
        self.col = col
        self.row = row
        self.stun_remaining_ms = 0
        self.boost_remaining_ms = 0
        self.full_light_remaining_ms = 0
        self.flashlight_charge_ms = FLASHLIGHT_MAX_CHARGE_MS
        self.flashlight_held = False

    def update(self, elapsed_ms, flashlight_held=False):
        self.stun_remaining_ms = max(0, self.stun_remaining_ms - elapsed_ms)
        self.boost_remaining_ms = max(0, self.boost_remaining_ms - elapsed_ms)
        self.full_light_remaining_ms = max(0, self.full_light_remaining_ms - elapsed_ms)
        self.flashlight_held = flashlight_held and self.flashlight_charge_ms > 0
        if self.flashlight_held:
            self.flashlight_charge_ms = max(
                0,
                self.flashlight_charge_ms - elapsed_ms * FLASHLIGHT_DRAIN_RATE,
            )
            if self.flashlight_charge_ms == 0:
                self.flashlight_held = False
        else:
            self.flashlight_charge_ms = min(
                FLASHLIGHT_MAX_CHARGE_MS,
                self.flashlight_charge_ms + elapsed_ms * FLASHLIGHT_RECHARGE_RATE,
            )

    @property
    def flashlight_active(self):
        return self.flashlight_held and self.flashlight_charge_ms > 0

    @property
    def light_radius(self):
        if self.full_light_remaining_ms <= 0:
            return LIGHT_RADIUS

        elapsed_ms = FULL_LIGHT_DURATION_MS - self.full_light_remaining_ms
        if elapsed_ms < LIGHT_BOOST_TRANSITION_MS:
            progress = elapsed_ms / LIGHT_BOOST_TRANSITION_MS
        elif self.full_light_remaining_ms < LIGHT_BOOST_TRANSITION_MS:
            progress = self.full_light_remaining_ms / LIGHT_BOOST_TRANSITION_MS
        else:
            progress = 1.0
        return int(LIGHT_RADIUS + (MAX_LIGHT_RADIUS - LIGHT_RADIUS) * progress)

    def disable_full_light(self):
        self.full_light_remaining_ms = 0

    def move(self, direction, maze, predictor=None):
        """Move one cell; blocked moves do not update pickup or prediction data."""
        if self.stun_remaining_ms > 0:
            return False
        if not maze.can_move(
            self.col,
            self.row,
            direction,
            ignore_walls=self.boost_remaining_ms > 0,
        ):
            return False

        moves = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}
        dx, dy = moves[direction]
        self.col += dx
        self.row += dy
        if predictor is not None:
            predictor.record(direction)
        maze.collect_soul_at(self.col, self.row)
        item_kind = maze.collect_item_at(self.col, self.row)
        if item_kind == "beartrap":
            self.stun_remaining_ms = 2000
        elif item_kind == "boost":
            self.boost_remaining_ms = 10000
        elif item_kind == "light":
            self.full_light_remaining_ms = FULL_LIGHT_DURATION_MS
        return True

    def draw(self, screen):
        center = (
            self.col * CELL_SIZE + CELL_SIZE // 2,
            self.row * CELL_SIZE + CELL_SIZE // 2,
        )
        color = (90, 220, 245) if self.boost_remaining_ms > 0 else PLAYER_COLOR
        pygame.draw.circle(screen, color, center, CELL_SIZE // 3)