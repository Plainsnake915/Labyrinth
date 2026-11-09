import asyncio
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


class Player:
    def __init__(self, col=0, row=0):
        self.col = col
        self.row = row

    def move(self, direction, maze):
        if not maze.can_move(self.col, self.row, direction):
            return False

        moves = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}
        dx, dy = moves[direction]
        self.col += dx
        self.row += dy
        return True

    def draw(self, screen):
        center = (
            self.col * CELL_SIZE + CELL_SIZE // 2,
            self.row * CELL_SIZE + CELL_SIZE // 2,
        )
        pygame.draw.circle(screen, PLAYER_COLOR, center, CELL_SIZE // 3)


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


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    font = pygame.font.Font(None, 25)
    pygame.display.set_caption("Labyrinth Game")
    clock = pygame.time.Clock()
    maze = MazeGenerator.MazeGrid(ROWS, COLS, CELL_SIZE)
    player = Player()
    ghosts = create_ghosts(maze)
    
    debug_mode = False
    won = False
    running = True

    while running:
        elapsed_ms = clock.tick(120)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    maze.regenerate()
                    player = Player()
                    ghosts = create_ghosts(maze)
                    won = False
                elif event.key == pygame.K_x:
                    debug_mode = not debug_mode
                elif event.key == pygame.K_w:
                    player.move("up", maze)
                    maze.collect_soul_at(player.col, player.row)
                elif event.key == pygame.K_d:
                    player.move("right", maze)
                    maze.collect_soul_at(player.col, player.row)
                elif event.key == pygame.K_s:
                    player.move("down", maze)
                    maze.collect_soul_at(player.col, player.row)
                elif event.key == pygame.K_a:
                    player.move("left", maze)
                    maze.collect_soul_at(player.col, player.row)

        for ghost in ghosts:
            ghost.update(elapsed_ms, maze, (player.col, player.row))
        won = won or (maze.exit_open and (player.col, player.row) == maze.exit_position)
        screen.fill(BACKGROUND)
        maze.draw(screen)
        if debug_mode:
            for ghost in ghosts:
                ghost.draw_path(screen)
        for ghost in ghosts:
            ghost.draw(screen)
        player.draw(screen)
        status = f"Souls: {maze.souls_remaining}/{maze.soul_count}"
        if won:
            status = "The exit is open. You escaped!"
        elif not maze.exit_open:
            status += "  Collect all souls to unlock the exit"
        screen.blit(font.render(status, True, TEXT_COLOR), (10, 8))
        if debug_mode:
            debug_text = "X: debug on | " + ", ".join(ghost.state for ghost in ghosts)
            screen.blit(font.render(debug_text, True, PATH_COLOR), (10, 32))
        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())