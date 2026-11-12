import asyncio
import math
import random

import pygame
import MazeGenerator
WIDTH, HEIGHT = 600, 600
CELL_SIZE = 30
COLS = WIDTH // CELL_SIZE
ROWS = HEIGHT // CELL_SIZE
BACKGROUND = (8, 12, 24)
WALL_COLOR = (145, 151, 164)
PLAYER_COLOR = (82, 210, 220)
GHOST_COLOR = (235, 239, 248)
GHOST_EYE_COLOR = (45, 54, 72)
PATH_COLOR = (180, 90, 210)
TEXT_COLOR = (225, 230, 240)
LIGHT_RADIUS = 150
MAX_LIGHT_RADIUS = math.ceil(math.hypot(WIDTH, HEIGHT))
FULL_LIGHT_DURATION_MS = 10000
LIGHT_BOOST_TRANSITION_MS = 700
DARKNESS_ALPHA = 248
FLASHLIGHT_RANGE = 300
FLASHLIGHT_HALF_ANGLE = math.radians(23)
FLASHLIGHT_MAX_CHARGE_MS = 5000
FLASHLIGHT_DRAIN_RATE = 1.0
FLASHLIGHT_RECHARGE_RATE = 0.5
BOSS_LIGHT_RESET_MS = 2000
BOSS_COLOR = (28, 27, 38)
BOSS_EYE_COLOR = (245, 70, 68)
BOSS_PATH_COLOR = (225, 65, 75)
PREDICTION_COLOR = (250, 220, 75)
DIRECTIONS = ("up", "down", "left", "right")
MOVES = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


class MarkovPredictor:
    def __init__(self):
        self.transitions = {direction: {next_direction: 0 for next_direction in DIRECTIONS} for direction in DIRECTIONS}
        self.previous_direction = None
        self.last_direction = None
        self.transition_count = 0

    def record(self, direction):
        if direction not in MOVES:
            return
        if self.previous_direction is not None:
            self.transitions[self.previous_direction][direction] += 1
            self.transition_count += 1
        self.previous_direction = direction
        self.last_direction = direction

    def predict_next(self, direction):
        counts = self.transitions.get(direction)
        if not counts or not any(counts.values()):
            return direction
        return max(DIRECTIONS, key=lambda candidate: counts[candidate])

    def predict_sequence(self, steps=3):
        direction = self.last_direction
        predictions = []
        for _ in range(steps):
            if direction is None:
                break
            direction = self.predict_next(direction)
            predictions.append(direction)
        return predictions


class BossEnemy:
    def __init__(self, position):
        self.col, self.row = position
        self.spawn_position = position
        self.move_interval = 220
        self.move_timer = 0
        self.target = position
        self.path = []
        self.predicted_position = position
        self.light_exposure_ms = 0

    def update(self, elapsed_ms, maze, player, predictor, flashlight_active=False, cursor_position=None):
        if (
            flashlight_active
            and cursor_position is not None
            and point_in_flashlight_cone(
                player,
                cursor_position,
                (self.col, self.row),
            )
        ):
            self.light_exposure_ms += elapsed_ms
            self.path = []
            if self.light_exposure_ms >= BOSS_LIGHT_RESET_MS:
                self.col, self.row = self.spawn_position
                self.light_exposure_ms = 0
            return

        self.light_exposure_ms = 0
        directions = predictor.predict_sequence(steps=3)
        predicted_col, predicted_row = player.col, player.row
        for direction in directions:
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

    def draw(self, screen, cell_size):
        center = (self.col * cell_size + cell_size // 2, self.row * cell_size + cell_size // 2)
        radius = cell_size // 3
        pygame.draw.circle(screen, BOSS_COLOR, center, radius)
        pygame.draw.circle(screen, BOSS_EYE_COLOR, (center[0] - 4, center[1] - 2), 2)
        pygame.draw.circle(screen, BOSS_EYE_COLOR, (center[0] + 4, center[1] - 2), 2)

    def draw_debug(self, screen, cell_size):
        points = [(self.col * cell_size + cell_size // 2, self.row * cell_size + cell_size // 2)]
        points.extend((col * cell_size + cell_size // 2, row * cell_size + cell_size // 2) for col, row in self.path)
        if len(points) > 1:
            pygame.draw.lines(screen, BOSS_PATH_COLOR, False, points, 2)
        col, row = self.predicted_position
        rect = (col * cell_size + 4, row * cell_size + 4, cell_size - 8, cell_size - 8)
        pygame.draw.rect(screen, PREDICTION_COLOR, rect, 2)


class Player:
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

    def disable_full_light(self):
        self.full_light_remaining_ms = 0

    def move(self, direction, maze, predictor=None):
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

    def draw(self, screen):
        center = (
            self.col * CELL_SIZE + CELL_SIZE // 2,
            self.row * CELL_SIZE + CELL_SIZE // 2,
        )
        
        color = (90, 220, 245) if self.boost_remaining_ms > 0 else PLAYER_COLOR
        pygame.draw.circle(screen, color, center, CELL_SIZE // 3)


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
    center = (
        player.col * CELL_SIZE + CELL_SIZE // 2,
        player.row * CELL_SIZE + CELL_SIZE // 2,
    )
    for radius, alpha in (
        (radius, 205),
        (radius * 4 // 5, 145),
        (radius * 3 // 5, 80),
        (radius * 2 // 5, 25),
        (radius // 5, 0),
    ):
        pygame.draw.circle(darkness, (0, 0, 0, alpha), center, radius)
    if flashlight_active and cursor_position is not None:
        _, cone_points, _ = flashlight_cone_points(player, cursor_position)
        pygame.draw.polygon(darkness, (0, 0, 0, 0), cone_points)
    screen.blit(darkness, (0, 0))


def player_screen_position(player):
    return (
        player.col * CELL_SIZE + CELL_SIZE // 2,
        player.row * CELL_SIZE + CELL_SIZE // 2,
    )


def flashlight_cone_points(player, cursor_position, cell_size=CELL_SIZE):
    origin = (
        player.col * cell_size + cell_size // 2,
        player.row * cell_size + cell_size // 2,
    )
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
    return origin, points, angle


def point_in_flashlight_cone(player, cursor_position, cell_position):
    origin_x, origin_y = player_screen_position(player)
    target_x = cell_position[0] * CELL_SIZE + CELL_SIZE // 2
    target_y = cell_position[1] * CELL_SIZE + CELL_SIZE // 2
    to_target_x = target_x - origin_x
    to_target_y = target_y - origin_y
    distance = math.hypot(to_target_x, to_target_y)
    if distance > FLASHLIGHT_RANGE:
        return False

    aim_x = cursor_position[0] - origin_x
    aim_y = cursor_position[1] - origin_y
    if not aim_x and not aim_y:
        return False
    aim_angle = math.atan2(aim_y, aim_x)
    target_angle = math.atan2(to_target_y, to_target_x)
    angle_difference = math.atan2(
        math.sin(target_angle - aim_angle),
        math.cos(target_angle - aim_angle),
    )
    return abs(angle_difference) <= FLASHLIGHT_HALF_ANGLE


def draw_flashlight(screen, player, cursor_position):
    if not player.flashlight_active:
        return
    _, points, _ = flashlight_cone_points(player, cursor_position)
    beam = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(beam, (255, 215, 75, 38), points)
    screen.blit(beam, (0, 0))
    pygame.draw.lines(screen, (255, 224, 120), False, points[1:], 2)


def draw_flashlight_charge(screen, player, font):
    bar_rect = pygame.Rect(14, HEIGHT - 25, 150, 12)
    pygame.draw.rect(screen, (30, 30, 35), bar_rect, border_radius=4)
    charge_ratio = player.flashlight_charge_ms / FLASHLIGHT_MAX_CHARGE_MS
    fill_rect = bar_rect.copy()
    fill_rect.width = round(bar_rect.width * charge_ratio)
    if fill_rect.width:
        pygame.draw.rect(screen, (245, 194, 66), fill_rect, border_radius=4)
    pygame.draw.rect(screen, (220, 220, 225), bar_rect, 1, border_radius=4)
    label = "Flashlight: Space" if not player.flashlight_active else "Flashlight: ON"
    screen.blit(font.render(label, True, TEXT_COLOR), (bar_rect.right + 8, HEIGHT - 29))


class FadeTransition:
    def __init__(self, duration_ms=650):
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
        for radius, alpha in (
            (self.radius, 200),
            (self.radius * 4 // 5, 145),
            (self.radius * 3 // 5, 80),
            (self.radius * 2 // 5, 25),
            (self.radius // 5, 0),
        ):
            pygame.draw.circle(self.overlay, (0, 0, 0, alpha), center, radius)
        screen.blit(self.overlay, (0, 0))


class GhostNPC:
    def __init__(self, position, soul, route=None):
        self.col, self.row = position
        self.start_position = position
        self.soul = soul
        self.target = soul.position
        self.state = "Patrol"
        self.move_interval = 260
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

    def draw(self, screen):
        center = (self.col * CELL_SIZE + CELL_SIZE // 2, self.row * CELL_SIZE + CELL_SIZE // 2)
        radius = CELL_SIZE // 3
        pygame.draw.circle(screen, GHOST_COLOR, center, radius)
        eye_y = center[1] - 2
        pygame.draw.circle(screen, GHOST_EYE_COLOR, (center[0] - 4, eye_y), 2)
        pygame.draw.circle(screen, GHOST_EYE_COLOR, (center[0] + 4, eye_y), 2)

    def draw_path(self, screen):
        points = [(self.col * CELL_SIZE + CELL_SIZE // 2, self.row * CELL_SIZE + CELL_SIZE // 2)]
        points.extend(
            (col * CELL_SIZE + CELL_SIZE // 2, row * CELL_SIZE + CELL_SIZE // 2)
            for col, row in self.path
        )
        if len(points) > 1:
            pygame.draw.lines(screen, PATH_COLOR, False, points, 2)


def create_ghosts(maze):
    ghosts = []
    for soul in maze.souls:
        route = [soul.position] + maze.find_path(soul.position, maze.exit_position)
        ghosts.append(GhostNPC(soul.position, soul, route))
    return ghosts


def create_boss(maze):
    excluded = {(0, 0), maze.exit_position}
    excluded.update(soul.position for soul in maze.souls)
    excluded.update(item.position for item in maze.items if hasattr(item, "position"))
    return BossEnemy(maze.random_position(excluded))


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    font = pygame.font.Font(None, 25)
    pygame.display.set_caption("Labyrinth Game")
    clock = pygame.time.Clock()
    maze = MazeGenerator.MazeGrid(ROWS, COLS, CELL_SIZE)
    player = Player()
    ghosts = create_ghosts(maze)
    predictor = MarkovPredictor()
    boss = create_boss(maze)
    debug_mode = False
    won = False
    game_over = False
    game_over_revealed = False
    fade = FadeTransition()
    running = True

    def reset_game():
        nonlocal player, ghosts, predictor, boss, won, game_over, game_over_revealed
        maze.regenerate()
        player = Player()
        ghosts = create_ghosts(maze)
        predictor = MarkovPredictor()
        boss = create_boss(maze)
        won = False
        game_over = False
        game_over_revealed = False

    def reveal_game_over():
        nonlocal game_over_revealed
        game_over_revealed = True

    while running:
        elapsed_ms = clock.tick(120)
        fade.update(elapsed_ms)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    if fade.phase == "idle":
                        fade.begin(reset_game)
                elif event.key == pygame.K_x:
                    debug_mode = not debug_mode
                elif not fade.phase in ("out",) and not game_over and not won:
                    direction_by_key = {
                        pygame.K_w: "up",
                        pygame.K_d: "right",
                        pygame.K_s: "down",
                        pygame.K_a: "left",
                    }
                    direction = direction_by_key.get(event.key)
                    if direction is not None:
                        player.move(direction, maze, predictor)

        flashlight_held = (
            not won
            and not game_over
            and fade.phase != "out"
            and pygame.key.get_pressed()[pygame.K_SPACE]
        )
        player.update(elapsed_ms, flashlight_held)
        if not won and boss.touches(player):
            if not game_over:
                game_over = True
                player.disable_full_light()
                fade.begin(reveal_game_over)
        if not game_over and not won and fade.phase != "out":
            for ghost in ghosts:
                ghost.update(elapsed_ms, maze, (player.col, player.row))
            cursor_position = pygame.mouse.get_pos()
            boss.update(
                elapsed_ms,
                maze,
                player,
                predictor,
                flashlight_active=player.flashlight_active,
                cursor_position=cursor_position,
            )
            if boss.touches(player):
                game_over = True
                player.disable_full_light()
                fade.begin(reveal_game_over)
        won = won or (maze.exit_open and (player.col, player.row) == maze.exit_position)
        if won:
            player.disable_full_light()
        if won or game_over:
            screen.fill((0, 0, 0))
        else:
            screen.fill(BACKGROUND)
            maze.draw(screen)
            if debug_mode:
                for ghost in ghosts:
                    ghost.draw_path(screen)
            for ghost in ghosts:
                ghost.draw(screen)
            if debug_mode:
                boss.draw_debug(screen, CELL_SIZE)
            boss.draw(screen, CELL_SIZE)
            player.draw(screen)
            cursor_position = pygame.mouse.get_pos()
            draw_darkness(
                screen,
                player,
                flashlight_active=player.flashlight_active,
                cursor_position=cursor_position,
            )
            draw_flashlight(screen, player, cursor_position)
            status = f"Souls: {maze.souls_remaining}/{maze.soul_count}"
            if not maze.exit_open:
                status += "  Collect all souls to unlock the exit"
            if player.stun_remaining_ms > 0:
                status += f"  Stunned: {player.stun_remaining_ms / 1000:.1f}s"
            if player.boost_remaining_ms > 0:
                status += f"  Wall boost: {player.boost_remaining_ms / 1000:.1f}s"
            if player.full_light_remaining_ms > 0:
                status += f"  Full light: {player.full_light_remaining_ms / 1000:.1f}s"
            screen.blit(font.render(status, True, TEXT_COLOR), (10, 8))
            if debug_mode:
                debug_text = (
                    f"X: debug on | Boss target: {boss.predicted_position} | "
                    f"Markov transitions: {predictor.transition_count} | "
                    + ", ".join(ghost.state for ghost in ghosts)
                )
                screen.blit(font.render(debug_text, True, PATH_COLOR), (10, 32))
            draw_flashlight_charge(screen, player, font)
        fade_center = (
            player.col * CELL_SIZE + CELL_SIZE // 2,
            player.row * CELL_SIZE + CELL_SIZE // 2,
        )
        if not won and not game_over:
            fade.draw(screen, fade_center)
        if game_over_revealed:
            title = pygame.font.Font(None, 44).render("THE SHADOW FOUND YOU", True, (245, 90, 90))
            restart_text = pygame.font.Font(None, 26).render("Press R to try again", True, TEXT_COLOR)
            screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 18)))
            screen.blit(restart_text, restart_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))
        elif won:
            title = pygame.font.Font(None, 44).render("YOU ESCAPED", True, (255, 220, 125))
            restart_text = pygame.font.Font(None, 26).render("Press R to play again", True, TEXT_COLOR)
            screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 18)))
            screen.blit(restart_text, restart_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))
        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())