import pygame
import sys
import os
import random
import csv
from datetime import datetime

##############################
# CONFIGURATION
##############################
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 1000
FPS = 60

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")

# Probability distribution for spawning trees:
# 80% for Oak, 20% for Mahogany
OAK_PROBABILITY = 0.80

# Clicks required
OAK_CLICKS = 20
MAHOGANY_CLICKS = 45

# Time limit (seconds)
TIME_LIMIT = 30.0

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
RED   = (255, 0, 0)

# Display time (seconds) for the "plus" and "log" sprite 
DISPLAY_LOOT_TIME = 0.75  # can adjust if you'd like

##############################
# HELPER FUNCTIONS
##############################
def load_image(filename, width=None, height=None):
    """
    Utility to load an image from the assets folder, optionally scale it.
    """
    path = os.path.join(ASSETS_PATH, filename)
    img = pygame.image.load(path).convert_alpha()
    if width and height:
        img = pygame.transform.scale(img, (width, height))
    return img

def draw_bar(surface, x, y, width, height, current_value, max_value, bar_color=GREEN, back_color=BLACK):
    """
    Draws a horizontal bar (like a health/time bar).
    """
    pygame.draw.rect(surface, back_color, (x-2, y-2, width+4, height+4), 2)

    ratio = min(max(current_value / max_value, 0), 1)
    fill_w = int(ratio * width)
    pygame.draw.rect(surface, bar_color, (x, y, fill_w, height))

##############################
# CLASSES
##############################
class Tree:
    """
    Represents a single tree (Oak or Mahogany).
    """
    def __init__(self, x, y, tree_type, tree_image, clicks_needed):
        self.x = x
        self.y = y
        self.type = tree_type
        self.clicks_needed = clicks_needed
        self.max_clicks = clicks_needed
        self.image = tree_image
        self.rect = self.image.get_rect(center=(x, y))

    def handle_cut_press(self):
        """Decrement clicks_needed by 1. Returns True if felled, False otherwise."""
        self.clicks_needed -= 1
        return (self.clicks_needed <= 0)

##############################
# MAIN GAME CLASS
##############################
class WoodcuttingGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Woodcutting - Key Press Spam + Loot Display")
        self.clock = pygame.time.Clock()

        # Load background
        self.background = load_image("background_woodcutting.png", WINDOW_WIDTH, WINDOW_HEIGHT)

        # Load tree sprites
        self.oak_image = load_image("oak_tree.png")
        self.mahogany_image = load_image("mahogany_tree.png")

        # Load the plus icon and log sprites
        self.plus_image = load_image("plus.png")  # indicates + logs
        self.oak_log_image = load_image("Oak Log.png")
        self.mahogany_log_image = load_image("Mahogany Log.png")

        # Track how many oak vs. mahogany trees have been cut
        self.oak_cut_count = 0
        self.mahogany_cut_count = 0
        self.trees_cut = 0

        # Current tree
        self.current_tree = None
        self.used_E_already = False
        self.current_key = None

        # For briefly displaying the loot images after a tree is felled
        self.display_loot = False
        self.loot_type = None    # "Oak" or "Mahogany"
        self.loot_timer = 0.0    # how long we've displayed them
        self.loot_max_time = DISPLAY_LOOT_TIME

        # Time limit
        self.time_remaining = TIME_LIMIT
        self.game_over = False

        self.running = True

        self.spawn_new_tree()

    def spawn_new_tree(self):
        """Decide if new tree is Oak or Mahogany, spawn at center, choose key to press."""
        if random.random() < OAK_PROBABILITY:
            tree_type = "Oak"
            tree_image = self.oak_image
            clicks_needed = OAK_CLICKS
        else:
            tree_type = "Mahogany"
            tree_image = self.mahogany_image
            clicks_needed = MAHOGANY_CLICKS

        center_x = WINDOW_WIDTH // 2
        center_y = WINDOW_HEIGHT // 2
        self.current_tree = Tree(center_x, center_y, tree_type, tree_image, clicks_needed)

        # Decide key: 'E' first time, random letter after
        if not self.used_E_already:
            self.current_key = pygame.K_e
            self.used_E_already = True
        else:
            rand_code = random.randint(97, 122)  # 'a'..'z'
            self.current_key = rand_code

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                if not self.game_over and event.type == pygame.KEYDOWN:
                    if event.key == self.current_key and self.current_tree and not self.display_loot:
                        # This counts as a "cut"
                        felled = self.current_tree.handle_cut_press()
                        if felled:
                            # Tree is felled
                            self.trees_cut += 1
                            if self.current_tree.type == "Oak":
                                self.oak_cut_count += 1
                            else:
                                self.mahogany_cut_count += 1

                            # Now we display loot images briefly before next tree
                            self.display_loot = True
                            self.loot_type = self.current_tree.type
                            self.loot_timer = 0.0

                            # Hide the current tree so we see the plus/log
                            self.current_tree = None

            # Decrement time
            if not self.game_over:
                self.time_remaining -= dt
                if self.time_remaining <= 0:
                    self.time_remaining = 0
                    self.game_over = True

            # If we are displaying loot, update timer
            if self.display_loot:
                self.loot_timer += dt
                if self.loot_timer >= self.loot_max_time:
                    # done displaying, spawn new tree
                    self.display_loot = False
                    self.spawn_new_tree()

            self.draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def draw(self):
        self.screen.blit(self.background, (0, 0))

        # If we are displaying loot, show plus icon and log sprite
        if self.display_loot and self.loot_type is not None:
            # We'll center them in the same place the tree was
            center_x = WINDOW_WIDTH // 2
            center_y = WINDOW_HEIGHT // 2

            # 1) draw plus.png
            plus_rect = self.plus_image.get_rect(center=(center_x-350, center_y))
            self.screen.blit(self.plus_image, plus_rect)

            # 2) draw log sprite
            if self.loot_type == "Oak":
                log_img = self.oak_log_image
            else:
                log_img = self.mahogany_log_image

            log_rect = log_img.get_rect(center=(center_x, center_y + 30))
            self.screen.blit(log_img, log_rect)

        else:
            # Draw the current tree if present
            if self.current_tree:
                self.screen.blit(self.current_tree.image, self.current_tree.rect)
                # health bar
                bar_width = 150
                bar_height = 15
                bar_x = self.current_tree.rect.centerx - bar_width // 2
                bar_y = self.current_tree.rect.bottom + 10
                draw_bar(
                    surface=self.screen,
                    x=bar_x,
                    y=bar_y,
                    width=bar_width,
                    height=bar_height,
                    current_value=self.current_tree.clicks_needed,
                    max_value=self.current_tree.max_clicks,
                    bar_color=RED,
                    back_color=BLACK
                )

        # stats
        self.draw_text(f"Trees cut: {self.trees_cut}", 20, 20)
        self.draw_text(f"Oak cut: {self.oak_cut_count}", 20, 50)
        self.draw_text(f"Mahogany cut: {self.mahogany_cut_count}", 20, 80)

        # show which key
        if not self.display_loot and self.current_key is not None and self.current_tree:
            if self.current_key == pygame.K_e:
                displayed_char = "E"
            else:
                displayed_char = chr(self.current_key)
            self.draw_text(f"Press '{displayed_char.upper()}' to cut!", 20, 110)

        # time bar
        time_bar_width = 200
        time_bar_height = 20
        time_bar_x = 20
        time_bar_y = 150
        draw_bar(
            surface=self.screen,
            x=time_bar_x,
            y=time_bar_y,
            width=time_bar_width,
            height=time_bar_height,
            current_value=self.time_remaining,
            max_value=TIME_LIMIT,
            bar_color=GREEN,
            back_color=BLACK
        )

        if self.game_over:
            self.draw_text("TIME'S UP!", 20, 190, font_size=32, color=RED)

    def draw_text(self, text, x, y, font_size=24, color=WHITE):
        font = pygame.font.SysFont(None, font_size)
        img = font.render(text, True, color)
        self.screen.blit(img, (x, y))

##############################
def main():
    game = WoodcuttingGame()
    game.run()

if __name__ == "__main__":
    main()