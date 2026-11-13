"""Pygame application loop and coordination for Haunted Maze systems."""

import asyncio

import pygame

from ai import MarkovPredictor
from enemies import create_boss, create_ghosts
from lighting import FadeTransition, draw_darkness, draw_flashlight, draw_flashlight_charge
from maze import MazeGrid
from player import Player
from settings import BACKGROUND, CELL_SIZE, COLS, HEIGHT, PATH_COLOR, ROWS, TEXT_COLOR, WIDTH


class Game:
    """Own the active run and coordinate input, simulation, and rendering."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Labyrinth Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 25)
        self.title_font = pygame.font.Font(None, 44)
        self.prompt_font = pygame.font.Font(None, 26)
        self.debug_mode = False
        self.fade = FadeTransition()
        self.predictor = MarkovPredictor()
        self.reset_world()

    def reset_world(self):
        """Build a fresh maze and reset all run-specific state."""
        self.maze = MazeGrid(ROWS, COLS, CELL_SIZE)
        self.player = Player()
        self.ghosts = create_ghosts(self.maze)
        self.boss = create_boss(self.maze)
        self.won = False
        self.game_over = False
        self.game_over_revealed = False

    def _reveal_game_over(self):
        self.game_over_revealed = True

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_r:
                if self.fade.phase == "idle":
                    self.fade.begin(self.reset_world)
                continue
            if event.key == pygame.K_x:
                self.debug_mode = not self.debug_mode
                continue
            if self.fade.phase == "out" or self.game_over or self.won:
                continue

            direction_by_key = {
                pygame.K_w: "up",
                pygame.K_d: "right",
                pygame.K_s: "down",
                pygame.K_a: "left",
            }
            direction = direction_by_key.get(event.key)
            if direction is not None:
                self.player.move(direction, self.maze, self.predictor)
        return True

    def update(self, elapsed_ms):
        self.fade.update(elapsed_ms)
        flashlight_held = (
            not self.won
            and not self.game_over
            and self.fade.phase != "out"
            and pygame.key.get_pressed()[pygame.K_SPACE]
        )
        self.player.update(elapsed_ms, flashlight_held)

        if not self.won and self.boss.touches(self.player):
            self._end_run_as_loss()

        if not self.game_over and not self.won and self.fade.phase != "out":
            player_position = (self.player.col, self.player.row)
            for ghost in self.ghosts:
                ghost.update(elapsed_ms, self.maze, player_position)

            cursor_position = pygame.mouse.get_pos()
            self.boss.update(
                elapsed_ms,
                self.maze,
                self.player,
                self.predictor,
                flashlight_active=self.player.flashlight_active,
                cursor_position=cursor_position,
            )
            if self.boss.touches(self.player):
                self._end_run_as_loss()

        self.won = self.won or (
            self.maze.exit_open
            and (self.player.col, self.player.row) == self.maze.exit_position
        )
        if self.won:
            self.player.disable_full_light()

    def _end_run_as_loss(self):
        if self.game_over:
            return
        self.game_over = True
        self.player.disable_full_light()
        self.fade.begin(self._reveal_game_over)

    def _draw_gameplay(self):
        self.screen.fill(BACKGROUND)
        self.maze.draw(self.screen)
        if self.debug_mode:
            for ghost in self.ghosts:
                ghost.draw_path(self.screen, CELL_SIZE)
        for ghost in self.ghosts:
            ghost.draw(self.screen, CELL_SIZE)
        if self.debug_mode:
            self.boss.draw_debug(self.screen, CELL_SIZE)
        self.boss.draw(self.screen, CELL_SIZE)
        self.player.draw(self.screen)

        cursor_position = pygame.mouse.get_pos()
        draw_darkness(
            self.screen,
            self.player,
            flashlight_active=self.player.flashlight_active,
            cursor_position=cursor_position,
        )
        draw_flashlight(self.screen, self.player, cursor_position)
        self._draw_hud()

    def _draw_hud(self):
        status = f"Souls: {self.maze.souls_remaining}/{self.maze.soul_count}"
        if not self.maze.exit_open:
            status += "  Collect all souls to unlock the exit"
        if self.player.stun_remaining_ms > 0:
            status += f"  Stunned: {self.player.stun_remaining_ms / 1000:.1f}s"
        if self.player.boost_remaining_ms > 0:
            status += f"  Wall boost: {self.player.boost_remaining_ms / 1000:.1f}s"
        if self.player.full_light_remaining_ms > 0:
            status += f"  Full light: {self.player.full_light_remaining_ms / 1000:.1f}s"
        self.screen.blit(self.font.render(status, True, TEXT_COLOR), (10, 8))
        if self.debug_mode:
            debug_lines = (
                f"Boss target: {self.boss.predicted_position}",
                f"Markov transitions: {self.predictor.transition_count}",
                "Ghost states: " + ", ".join(ghost.state for ghost in self.ghosts),
            )
            for index, line in enumerate(debug_lines):
                self.screen.blit(self.font.render(line, True, PATH_COLOR), (10, 32 + index * 22))
        draw_flashlight_charge(self.screen, self.player, self.font)
        self.screen.blit(
            self.font.render("X: debug  |  WASD: move  |  R: restart  |  Space: flashlight", True, TEXT_COLOR),
            (8, HEIGHT - 58),
        )

    def draw(self):
        if self.won or self.game_over:
            self.screen.fill((0, 0, 0))
        else:
            self._draw_gameplay()
            center = (
                self.player.col * CELL_SIZE + CELL_SIZE // 2,
                self.player.row * CELL_SIZE + CELL_SIZE // 2,
            )
            self.fade.draw(self.screen, center)

        if self.game_over_revealed:
            self._draw_end_screen("THE SHADOW FOUND YOU", "Press R to try again", (245, 90, 90))
        elif self.won:
            self._draw_end_screen("YOU ESCAPED", "Press R to play again", (255, 220, 125))

    def _draw_end_screen(self, title, prompt, color):
        title_surface = self.title_font.render(title, True, color)
        prompt_surface = self.prompt_font.render(prompt, True, TEXT_COLOR)
        self.screen.blit(title_surface, title_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 18)))
        self.screen.blit(prompt_surface, prompt_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))

    async def run(self):
        """Run the nonblocking Pygame loop until the user quits."""
        running = True
        while running:
            elapsed_ms = self.clock.tick(120)
            running = self.handle_events()
            self.update(elapsed_ms)
            self.draw()
            pygame.display.flip()
            await asyncio.sleep(0)
        pygame.quit()


async def main():
    """Compatibility entry point used by the root launcher."""
    await Game().run()