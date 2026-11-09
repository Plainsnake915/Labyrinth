import pygame
import asyncio
WIDTH, HEIGHT = 900, 600
async def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Labyrinth Game")
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        screen.fill((8, 12, 24))
        pygame.display.flip()

        clock.tick(120) 
        await asyncio.sleep(0)  # Allow other tasks to run
    pygame.quit()
asyncio.run(main())