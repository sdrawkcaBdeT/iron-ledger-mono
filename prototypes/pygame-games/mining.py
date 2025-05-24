import pygame
import sys
import random
import math
import os
from collections import defaultdict

# ---------------------------------------------------------------------------
# CONFIGURATION / CONSTANTS
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 800
FPS = 60

# Grid for big tiles (3x3)
BIG_GRID_ROWS = 3
BIG_GRID_COLS = 3
BIG_TILE_SIZE = 200
BIG_TILE_CLICKS_REQUIRED = 5

# Each big tile has a 3x3 subgrid of small ore tiles
SMALL_GRID_SIZE = 3
SMALL_TILE_SIZE = 50
SMALL_GRID_SPACING = 5  # spacing between small tiles in the subgrid

# Ores, now equally likely
ORE_TYPES = ["Iron", "Copper", "Tin", "Coal", "Gold", "Silver"]

# Time limit in seconds
TIME_LIMIT = 60.0

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")

# Colors
WHITE = (255, 255, 255)
RED   = (255,   0,   0)

def load_image(filename, width=None, height=None):
    path = os.path.join(ASSETS_PATH, filename)
    img = pygame.image.load(path).convert_alpha()
    if width and height:
        img = pygame.transform.scale(img, (width, height))
    return img

# ---------------------------------------------------------------------------
# DATA CLASSES
# ---------------------------------------------------------------------------
class SmallTile:
    """
    Represents one small ore tile in the subgrid.
      - ore_type: which ore (Coal, Copper, etc.)
      - revealed: whether it is currently face-up
      - matched: whether this tile is permanently matched (stays face-up)
      - rect: for click detection
    """
    def __init__(self, ore_type, x, y, unknown_image, ore_images):
        self.ore_type = ore_type
        self.revealed = False
        self.matched = False
        self.rect = pygame.Rect(x, y, SMALL_TILE_SIZE, SMALL_TILE_SIZE)

        self.unknown_image = unknown_image
        self.ore_images = ore_images

    def draw(self, surface):
        """Draw either the unknown ore sprite or the actual ore sprite."""
        if self.matched or self.revealed:
            ore_img = self.ore_images[self.ore_type]
            surface.blit(ore_img, self.rect)
        else:
            surface.blit(self.unknown_image, self.rect)

class BigTile:
    """
    Represents one big tile in the 3x3 top-level grid.
      - subtiles: 3x3 small tiles behind it
      - clicks: how many clicks so far
      - broken: whether it's fully removed
      - broken_time: timestamp when it got broken (or None if not broken or already processed)
    """
    def __init__(self, row, col, big_tile_image, x, y):
        self.row = row
        self.col = col
        self.clicks = 0
        self.broken = False
        self.broken_time = None  # store the moment we break it
        self.big_tile_image = big_tile_image
        self.rect = pygame.Rect(x, y, BIG_TILE_SIZE, BIG_TILE_SIZE)
        self.subtiles = []

    def add_subtiles(self, subtiles):
        self.subtiles = subtiles

    def draw(self, surface):
        """Draw the big tile if it's not broken."""
        if not self.broken:
            surface.blit(self.big_tile_image, self.rect)

    def handle_click(self, current_time):
        """Increment click count for breaking progress."""
        self.clicks += 1
        if self.clicks >= BIG_TILE_CLICKS_REQUIRED and not self.broken:
            self.broken = True
            self.broken_time = current_time
            # Reveal subtiles for a 1-second peek
            for st in self.subtiles:
                if not st.matched:
                    st.revealed = True

    def update(self, current_time):
        """
        Called each frame. If the tile was just broken and 1 second has passed,
        hide subtiles again (unless they're matched).
        """
        if self.broken and self.broken_time is not None:
            if (current_time - self.broken_time) > 1.0:
                # Hide all subtiles that are not matched
                for st in self.subtiles:
                    if not st.matched:
                        st.revealed = False
                self.broken_time = None  # no longer do this check repeatedly

# ---------------------------------------------------------------------------
# MAIN GAME CLASS
# ---------------------------------------------------------------------------
class MiningGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Mining Micro-Game")
        self.clock = pygame.time.Clock()

        # Load images
        self.background = load_image("background_woodcutting.png", WINDOW_WIDTH, WINDOW_HEIGHT)
        self.big_tile_image = load_image("Unknown Ore Big.png", BIG_TILE_SIZE, BIG_TILE_SIZE)
        self.unknown_small_image = load_image("Unknown Ore.png", SMALL_TILE_SIZE, SMALL_TILE_SIZE)

        self.ore_images = {}
        for ore in ORE_TYPES:
            filename = f"{ore}.png"
            self.ore_images[ore] = load_image(filename, SMALL_TILE_SIZE, SMALL_TILE_SIZE)

        # Center the 3x3 big-tile grid
        self.grid_total_width = BIG_GRID_COLS * BIG_TILE_SIZE
        self.grid_total_height = BIG_GRID_ROWS * BIG_TILE_SIZE
        self.GRID_OFFSET_X = (WINDOW_WIDTH - self.grid_total_width) // 2
        self.GRID_OFFSET_Y = (WINDOW_HEIGHT - self.grid_total_height) // 2

        self.big_tiles = []
        self.create_big_tiles()

        self.time_remaining = TIME_LIMIT
        self.game_over = False

        # For match-3 flips
        self.current_flips = []
        self.inventory = defaultdict(int)

        # If 3 flips don't match, store them in mismatch_tiles
        self.mismatch_tiles = []

    def create_big_tiles(self):
        """Create the 3x3 array of BigTile objects, each with a 3x3 subgrid."""
        for row in range(BIG_GRID_ROWS):
            for col in range(BIG_GRID_COLS):
                x = self.GRID_OFFSET_X + col * BIG_TILE_SIZE
                y = self.GRID_OFFSET_Y + row * BIG_TILE_SIZE
                big_tile = BigTile(row, col, self.big_tile_image, x, y)

                # create subtiles behind it
                subtiles = []
                for r in range(SMALL_GRID_SIZE):
                    for c in range(SMALL_GRID_SIZE):
                        sx = x + 25 + c * (SMALL_TILE_SIZE + SMALL_GRID_SPACING)
                        sy = y + 25 + r * (SMALL_TILE_SIZE + SMALL_GRID_SPACING)
                        # equal chance for each ore
                        ore_type = random.choice(ORE_TYPES)
                        tile = SmallTile(ore_type, sx, sy, self.unknown_small_image, self.ore_images)
                        subtiles.append(tile)

                big_tile.add_subtiles(subtiles)
                self.big_tiles.append(big_tile)

    def run(self):
        """Main loop."""
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            current_time = pygame.time.get_ticks() / 1000.0  # in seconds

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if not self.game_over:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        mouse_pos = pygame.mouse.get_pos()

                        # If there's a mismatch, flip them back on this click
                        if self.mismatch_tiles:
                            for tile in self.mismatch_tiles:
                                tile.revealed = False
                            self.mismatch_tiles = []
                            # Now handle the actual click
                            self.handle_click(mouse_pos, current_time)
                        else:
                            self.handle_click(mouse_pos, current_time)

            # Update timer
            if not self.game_over:
                self.time_remaining -= dt
                if self.time_remaining <= 0:
                    self.time_remaining = 0
                    self.game_over = True

            # Update big tiles (check if we should hide subtiles after 1s)
            for bt in self.big_tiles:
                bt.update(current_time)

            # Render
            self.draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def handle_click(self, mouse_pos, current_time):
        """Process a single left-click at mouse_pos."""
        # Check big tiles first
        for big_tile in self.big_tiles:
            if not big_tile.broken and big_tile.rect.collidepoint(mouse_pos):
                big_tile.handle_click(current_time)
                return

        # Otherwise, check subtiles of broken big tiles
        for big_tile in self.big_tiles:
            if big_tile.broken:
                for subtile in big_tile.subtiles:
                    if not subtile.matched and subtile.rect.collidepoint(mouse_pos):
                        self.flip_subtile(subtile)
                        return

    def flip_subtile(self, subtile):
        """Flip a small tile face-up. If we have 3 flips, check match."""
        if subtile.revealed:
            return
        subtile.revealed = True
        self.current_flips.append(subtile)

        if len(self.current_flips) == 3:
            self.check_match()

    def check_match(self):
        """Called after exactly 3 tiles are flipped."""
        t1, t2, t3 = self.current_flips
        if t1.ore_type == t2.ore_type == t3.ore_type:
            # It's a match
            for tile in self.current_flips:
                tile.matched = True
            self.inventory[t1.ore_type] += 1
        else:
            # Not a match - store them in mismatch_tiles for flipping back next click
            self.mismatch_tiles = [t1, t2, t3]

        self.current_flips = []

    def draw(self):
        # Background
        self.screen.blit(self.background, (0, 0))

        # Draw subtiles first (so big tile covers them if not broken)
        for big_tile in self.big_tiles:
            if big_tile.broken:
                for subtile in big_tile.subtiles:
                    subtile.draw(self.screen)

        # Draw big tiles
        for big_tile in self.big_tiles:
            big_tile.draw(self.screen)
            if not big_tile.broken:
                self.draw_text_centered(
                    f"{big_tile.clicks}/{BIG_TILE_CLICKS_REQUIRED}",
                    big_tile.rect.centerx,
                    big_tile.rect.centery,
                    font_size=16,
                    color=WHITE
                )

        # Draw timer
        self.draw_text(f"Time: {int(self.time_remaining)}", 20, 10)

        # Draw inventory
        y_offset = 40
        self.draw_text("Matched Sets:", 20, y_offset)
        y_offset += 25
        for ore_type in ORE_TYPES:
            count = self.inventory[ore_type]
            if count > 0:
                self.draw_text(f"{ore_type}: {count}", 20, y_offset)
                y_offset += 20

        # If game over, show message
        if self.game_over:
            self.draw_text_centered("TIME'S UP!", WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2, 50, RED)

    def draw_text(self, text, x, y, font_size=24, color=WHITE):
        font = pygame.font.SysFont(None, font_size)
        img = font.render(text, True, color)
        self.screen.blit(img, (x, y))

    def draw_text_centered(self, text, cx, cy, font_size=24, color=WHITE):
        font = pygame.font.SysFont(None, font_size)
        img = font.render(text, True, color)
        rect = img.get_rect(center=(cx, cy))
        self.screen.blit(img, rect)

def main():
    game = MiningGame()
    game.run()

if __name__ == "__main__":
    main()
