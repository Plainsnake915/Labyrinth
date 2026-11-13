"""Darkness, flashlight rendering, beam geometry, and scene transitions."""

import math

import pygame

from settings import (
    CELL_SIZE,
    DARKNESS_ALPHA,
    FADE_DURATION_MS,
    FLASHLIGHT_HALF_ANGLE,
    FLASHLIGHT_MAX_CHARGE_MS,
    FLASHLIGHT_RANGE,
    HEIGHT,
    LIGHT_RADIUS,
    MAX_LIGHT_RADIUS,
    TEXT_COLOR,
    WIDTH,
)


def player_screen_position(player, cell_size=CELL_SIZE):
    return (
        player.col * cell_size + cell_size // 2,
        player.row * cell_size + cell_size // 2,
    )


def flashlight_cone_points(player, cursor_position, cell_size=CELL_SIZE):
    origin = player_screen_position(player, cell_size)
    aim_x = cursor_position[0] - origin[0]
    aim_y = cursor_position[1] - origin[1]
    angle = math.atan2(aim_y, aim_x) if aim_x or aim_y else -math.pi / 2
    segments = 14
    points = [origin]
    for index in range(segments + 1):
        spread = -FLASHLIGHT_HALF_ANGLE + 2 * FLASHLIGHT_HALF_ANGLE * index / segments
        points.append((
            round(origin[0] + math.cos(angle + spread) * FLASHLIGHT_RANGE),
            round(origin[1] + math.sin(angle + spread) * FLASHLIGHT_RANGE),
        ))
    return origin, points


def point_in_flashlight_cone(player, cursor_position, cell_position, cell_size=CELL_SIZE):
    origin_x, origin_y = player_screen_position(player, cell_size)
    target_x = cell_position[0] * cell_size + cell_size // 2
    target_y = cell_position[1] * cell_size + cell_size // 2
    to_target_x = target_x - origin_x
    to_target_y = target_y - origin_y
    if math.hypot(to_target_x, to_target_y) > FLASHLIGHT_RANGE:
        return False

    aim_x = cursor_position[0] - origin_x
    aim_y = cursor_position[1] - origin_y
    if not aim_x and not aim_y:
        return False
    aim_angle = math.atan2(aim_y, aim_x)
    target_angle = math.atan2(to_target_y, to_target_x)
    difference = math.atan2(
        math.sin(target_angle - aim_angle),
        math.cos(target_angle - aim_angle),
    )
    return abs(difference) <= FLASHLIGHT_HALF_ANGLE


def draw_darkness(
    screen,
    player,
    light_radius=None,
    flashlight_active=False,
    cursor_position=None,
):
    radius = player.light_radius if light_radius is None else light_radius
    if radius >= MAX_LIGHT_RADIUS:
        return

    darkness = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    darkness.fill((0, 0, 0, DARKNESS_ALPHA))
    center = player_screen_position(player)
    for ring_radius, alpha in (
        (radius, 205),
        (radius * 4 // 5, 145),
        (radius * 3 // 5, 80),
        (radius * 2 // 5, 25),
        (radius // 5, 0),
    ):
        pygame.draw.circle(darkness, (0, 0, 0, alpha), center, ring_radius)
    if flashlight_active and cursor_position is not None:
        _, cone_points = flashlight_cone_points(player, cursor_position)
        pygame.draw.polygon(darkness, (0, 0, 0, 0), cone_points)
    screen.blit(darkness, (0, 0))


def draw_flashlight(screen, player, cursor_position):
    if not player.flashlight_active:
        return
    _, points = flashlight_cone_points(player, cursor_position)
    beam = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(beam, (255, 215, 75, 38), points)
    screen.blit(beam, (0, 0))
    pygame.draw.lines(screen, (255, 224, 120), False, points[1:], 2)


def draw_flashlight_charge(screen, player, font):
    bar_rect = pygame.Rect(14, HEIGHT - 25, 150, 12)
    pygame.draw.rect(screen, (30, 30, 35), bar_rect, border_radius=4)
    ratio = player.flashlight_charge_ms / FLASHLIGHT_MAX_CHARGE_MS
    fill_rect = bar_rect.copy()
    fill_rect.width = round(bar_rect.width * ratio)
    if fill_rect.width:
        pygame.draw.rect(screen, (245, 194, 66), fill_rect, border_radius=4)
    pygame.draw.rect(screen, (220, 220, 225), bar_rect, 1, border_radius=4)
    label = "Flashlight: Space" if not player.flashlight_active else "Flashlight: ON"
    screen.blit(font.render(label, True, TEXT_COLOR), (bar_rect.right + 8, HEIGHT - 29))


class FadeTransition:
    """Reveal or conceal a scene through a circular aperture."""

    def __init__(self, duration_ms=FADE_DURATION_MS):
        self.duration_ms = duration_ms
        self.radius = 0
        self.phase = "in"
        self.elapsed_ms = 0
        self.start_radius = 0
        self.on_black = None
        self.overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    def begin(self, callback=None):
        if self.phase == "out":
            return False
        self.phase = "out"
        self.elapsed_ms = 0
        self.start_radius = self.radius
        self.on_black = callback
        return True

    def update(self, elapsed_ms):
        if self.phase == "idle":
            return

        self.elapsed_ms += elapsed_ms
        progress = min(1.0, self.elapsed_ms / self.duration_ms)
        if self.phase == "out":
            self.radius = round(self.start_radius * (1.0 - progress))
            if progress >= 1.0:
                self.radius = 0
                callback = self.on_black
                self.on_black = None
                if callback is not None:
                    callback()
                self.phase = "in"
                self.elapsed_ms = 0
        else:
            self.radius = round(MAX_LIGHT_RADIUS * progress)
            if progress >= 1.0:
                self.radius = MAX_LIGHT_RADIUS
                self.phase = "idle"

    def draw(self, screen, center):
        if self.radius >= MAX_LIGHT_RADIUS:
            return
        self.overlay.fill((0, 0, 0, 255))
        for ring_radius, alpha in (
            (self.radius, 200),
            (self.radius * 4 // 5, 145),
            (self.radius * 3 // 5, 80),
            (self.radius * 2 // 5, 25),
            (self.radius // 5, 0),
        ):
            pygame.draw.circle(self.overlay, (0, 0, 0, alpha), center, ring_radius)
        screen.blit(self.overlay, (0, 0))