import pygame
import sys
import random
import math
import os

# ---------------------------------------------------------------------------
# CONFIGURATION / CONSTANTS
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FPS = 60

REQUIRED_CASTS = 4

RED_RADIUS = 5
YELLOW_RADIUS = 20

# Power bar size: 70% of the screen width
BAR_WIDTH = int(0.7 * WINDOW_WIDTH)
BAR_HEIGHT = 25
BAR_X = (WINDOW_WIDTH - BAR_WIDTH) // 2
BAR_Y = WINDOW_HEIGHT - 50

# Power bar speed & acceleration
POWER_BAR_INITIAL_SPEED = 1.0
POWER_BAR_ACCELERATION  = 0.5

ZONE_POOR_MAX = 0.8
ZONE_OK_MAX   = 0.95

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")

# --- NEW OR CHANGED CODE ---
TIME_LIMIT = 18.0        # The total time in seconds for the micro-game
TIME_BAR_WIDTH = 200     # Width of the time bar
TIME_BAR_HEIGHT = 20
TIME_BAR_X = 20          # Top-left corner
TIME_BAR_Y = 20

# Optional: define numeric values for fish types
FISH_VALUES = {
    "sardine": 1,
    "salmon": 2,
    "swordfish": 3
}

# ---------------------------------------------------------------------------
# DATA CLASSES
# ---------------------------------------------------------------------------
class FishingSpot:
    def __init__(self, x, y):
        self.original_x = x
        self.original_y = y

        # The image for the fishing spot
        self.spot_image = pygame.image.load(os.path.join(ASSETS_PATH, "fishing_spot.png")).convert_alpha()

        self.image = self.spot_image
        self.rect = self.image.get_rect(center=(x, y))

        self.casts_done = 0
        self.cast_accuracies = []
        self.is_spot_depleted = False

    def calculate_fish(self):
        """Return a string (fish type) based on the average accuracy."""
        if not self.cast_accuracies:
            return "sardine"
        avg_accuracy = sum(self.cast_accuracies) / len(self.cast_accuracies)
        if avg_accuracy < 0.3:
            return "sardine"
        elif avg_accuracy < 0.7:
            return "salmon"
        else:
            return "swordfish"

    def deplete_spot(self):
        """Mark the fishing spot as fully used/fished out."""
        self.is_spot_depleted = True
        # You could change the image to a "fished out" icon here, if you want:
        # self.image = pygame.image.load(os.path.join(ASSETS_PATH, "fished_out.png")).convert_alpha()

    def reset(self):
        """Reset the fishing spot for a new round (but not the global timer)."""
        self.is_spot_depleted = False
        self.casts_done = 0
        self.cast_accuracies = []
        self.image = self.spot_image
        self.rect = self.image.get_rect(center=(self.original_x, self.original_y))

class Player:
    def __init__(self):
        # Track total fish points or fish count
        self.fish_count = 0

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------
def draw_text(surface, text, x, y, font_size=24, color=(255, 255, 255)):
    font = pygame.font.SysFont(None, font_size)
    img = font.render(text, True, color)
    surface.blit(img, (x, y))

def get_new_target(spot):
    """Return a random offset from the fishing spot center."""
    offset_x = random.randint(-50, 50)
    offset_y = random.randint(-50, 50)
    return (spot.rect.centerx + offset_x, spot.rect.centery + offset_y)

def get_click_location_accuracy(mx, my, tx, ty):
    """Click accuracy logic, same as before but thematically a 'cast' accuracy."""
    dist = math.hypot(mx - tx, my - ty)
    if dist <= RED_RADIUS:
        return 1.0
    elif dist <= YELLOW_RADIUS:
        return 0.7
    else:
        return 0.0

def compute_bar_accuracy(bar_value):
    """Return an accuracy multiplier based on the power bar's zone."""
    if bar_value < ZONE_POOR_MAX:
        return 0.0
    elif bar_value < ZONE_OK_MAX:
        return 0.7
    else:
        return 1.0

def get_bar_color(bar_value):
    """Return a color depending on where the bar_value stands."""
    if bar_value < ZONE_POOR_MAX:
        return (255, 0, 0)
    elif bar_value < ZONE_OK_MAX:
        return (255, 255, 0)
    else:
        return (0, 255, 0)

def draw_time_bar(surface, time_remaining, x, y, width, height):
    """
    Draws a time bar that represents how much time is left.
    If time_remaining is 0, the bar is empty. If time_remaining is full,
    the bar is at max width.
    """
    # Compute ratio (0 to 1)
    ratio = max(time_remaining, 0) / TIME_LIMIT
    fill_width = int(ratio * width)

    # Draw a simple black border
    pygame.draw.rect(surface, (0, 0, 0), (x-2, y-2, width+4, height+4), 2)

    # Fill the inside (green as time remains, red could also be used)
    pygame.draw.rect(surface, (0, 255, 0), (x, y, fill_width, height))

# ---------------------------------------------------------------------------
# MAIN GAME LOOP
# ---------------------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Fishing Micro-Game with Global Timer")
    clock = pygame.time.Clock()

    # Load background
    background = pygame.image.load(os.path.join(ASSETS_PATH, "fishing_background.png")).convert()
    background = pygame.transform.scale(background, (WINDOW_WIDTH, WINDOW_HEIGHT))

    # Create our fishing spot & player
    spot = FishingSpot(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
    player = Player()

    # Pick the first target location
    target_x, target_y = get_new_target(spot)

    # Power bar variables
    power_bar_value = 0.0
    power_bar_speed = 0.0
    direction = 0
    charging = False
    clicked_in_zone = False

    # Global time
    time_remaining = TIME_LIMIT
    game_over = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if not game_over:
                # Only process casting events if game isn't over
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not spot.is_spot_depleted:
                        mx, my = pygame.mouse.get_pos()
                        loc_acc = get_click_location_accuracy(mx, my, target_x, target_y)
                        if loc_acc > 0.0:
                            clicked_in_zone = True
                            charging = True
                            direction = 1
                            power_bar_speed = POWER_BAR_INITIAL_SPEED

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if charging and not spot.is_spot_depleted and clicked_in_zone:
                        charging = False
                        mx, my = pygame.mouse.get_pos()
                        loc_acc = get_click_location_accuracy(mx, my, target_x, target_y)
                        bar_acc = compute_bar_accuracy(power_bar_value)
                        final_cast_acc = loc_acc * bar_acc

                        # Store that cast’s accuracy
                        spot.cast_accuracies.append(final_cast_acc)
                        spot.casts_done += 1

                        # Reset the power bar
                        power_bar_value = 0.0
                        power_bar_speed = 0.0
                        direction = 0
                        clicked_in_zone = False

                        # Check if we've done enough casts
                        if spot.casts_done >= REQUIRED_CASTS:
                            fish_caught = spot.calculate_fish()
                            # Add fish to player's total
                            player.fish_count += FISH_VALUES[fish_caught]
                            spot.deplete_spot()
                        else:
                            # Move target for the next cast
                            target_x, target_y = get_new_target(spot)

        # Press 'R' to reset the fishing spot (but *do not* reset the timer)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_r]:
            spot.reset()
            power_bar_value = 0.0
            power_bar_speed = 0.0
            direction = 0
            charging = False
            clicked_in_zone = False
            target_x, target_y = get_new_target(spot)
            # We do NOT reset time_remaining or game_over here

        # Decrement the global time if not over
        if not game_over:
            time_remaining -= dt
            if time_remaining <= 0:
                time_remaining = 0
                game_over = True

        # Update the bar if charging (same logic as before)
        if charging and not spot.is_spot_depleted and not game_over:
            power_bar_speed += POWER_BAR_ACCELERATION * dt
            power_bar_value += direction * power_bar_speed * dt
            if power_bar_value >= 1.0:
                power_bar_value = 1.0
                direction = -1
            if power_bar_value <= 0.0:
                power_bar_value = 0.0
                charging = False
                direction = 0
                # Forced finalize at 0
                mx, my = pygame.mouse.get_pos()
                loc_acc = get_click_location_accuracy(mx, my, target_x, target_y)
                final_cast_acc = loc_acc * 0.0
                spot.cast_accuracies.append(final_cast_acc)
                spot.casts_done += 1

                if spot.casts_done >= REQUIRED_CASTS:
                    fish_caught = spot.calculate_fish()
                    player.fish_count += FISH_VALUES[fish_caught]
                    spot.deplete_spot()
                else:
                    target_x, target_y = get_new_target(spot)

        # Rendering
        screen.blit(background, (0, 0))
        screen.blit(spot.image, spot.rect)

        # Draw target circles if the spot is not depleted
        if not spot.is_spot_depleted:
            pygame.draw.circle(screen, (255, 255, 0), (target_x, target_y), YELLOW_RADIUS, 2)
            pygame.draw.circle(screen, (255, 0, 0), (target_x, target_y), RED_RADIUS, 2)
            draw_text(screen, f"Casts: {spot.casts_done}/{REQUIRED_CASTS}", 20, 80)
        else:
            draw_text(screen, "Fishing spot depleted! Press R to reset.", 20, 80)

        # Display how many fish (points) we've caught so far
        draw_text(screen, f"Fish: {player.fish_count}", 20, 110)

        # Draw the time bar if the game is not over
        if not game_over:
            draw_time_bar(screen, time_remaining, TIME_BAR_X, TIME_BAR_Y, TIME_BAR_WIDTH, TIME_BAR_HEIGHT)
        else:
            draw_text(screen, "Time's up!", TIME_BAR_X, TIME_BAR_Y + 2, font_size=24, color=(255, 0, 0))

        # Draw power bar outline
        pygame.draw.rect(screen, (0, 0, 0), (BAR_X - 2, BAR_Y - 2, BAR_WIDTH + 4, BAR_HEIGHT + 4), 2)
        bar_color = get_bar_color(power_bar_value)
        fill_width = int(power_bar_value * BAR_WIDTH)
        pygame.draw.rect(screen, bar_color, (BAR_X, BAR_Y, fill_width, BAR_HEIGHT))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
