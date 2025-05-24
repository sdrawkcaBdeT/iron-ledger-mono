import pygame
import sys
import math
import random
import csv
import os
from time import time

from hauling_routes import get_route_by_index

# -------------------- CONFIGS -------------------- #
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
TILE_SIZE = 40
FPS = 60

MAX_RECLICK_DISTANCE = 40

LOG_FOLDER = "games/logs"
LOG_FILE = "hauling_records.csv"

# Fields for CSV logging
CSV_FIELDS = [
    "timestamp",
    "route_name",
    "seed",
    "start_tile",
    "goal_name_to",
    "goal_tile_to",
    "goal_name_from",
    "goal_tile_from",
    "to_leg_time",
    "to_leg_collisions",
    "to_leg_productivity",
    "from_leg_time",
    "from_leg_collisions",
    "from_leg_productivity",
    "final_productivity",
]

# -------------- HELPER FUNCTIONS -------------- #

def load_route(route_def):
    layout = route_def["layout"]
    rows = len(layout)
    cols = len(layout[0])
    route_grid = []
    for r in range(rows):
        row_data = []
        for c in range(cols):
            row_data.append(layout[r][c])
        route_grid.append(row_data)
    return route_grid

def is_wall(route_grid, x, y):
    col = x // TILE_SIZE
    row = y // TILE_SIZE
    if row < 0 or row >= len(route_grid) or col < 0 or col >= len(route_grid[0]):
        return True
    return (route_grid[row][col] == '#')

def tile_to_pixel(tile_pos):
    (r, c) = tile_pos
    px = c * TILE_SIZE + TILE_SIZE // 2
    py = r * TILE_SIZE + TILE_SIZE // 2
    return (px, py)

def distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def write_log_to_csv(session_log):
    # Ensure the logs folder exists
    os.makedirs(LOG_FOLDER, exist_ok=True)

    file_path = os.path.join(LOG_FOLDER, LOG_FILE)
    file_exists = os.path.isfile(file_path)

    with open(file_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()

        row_data = {
            "timestamp": time(),
            "route_name": session_log["route_name"],
            "seed": session_log["seed"],
            "start_tile": session_log["start_tile"],
            "goal_name_to": session_log["goal_name_to"],
            "goal_tile_to": session_log["goal_tile_to"],
            "goal_name_from": session_log["goal_name_from"],
            "goal_tile_from": session_log["goal_tile_from"],
            "to_leg_time": session_log["to_leg_time"],
            "to_leg_collisions": session_log["to_leg_collisions"],
            "to_leg_productivity": session_log["to_leg_productivity"],
            "from_leg_time": session_log["from_leg_time"],
            "from_leg_collisions": session_log["from_leg_collisions"],
            "from_leg_productivity": session_log["from_leg_productivity"],
            "final_productivity": session_log["final_productivity"],
        }
        writer.writerow(row_data)

# -------------- GAME CLASS -------------- #

class MazeGame:
    def __init__(self, route_index=0, seed=None):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Hauling Mini-Game (Single-Width Corridors w/ Red Collisions)")
        self.clock = pygame.time.Clock()

        # Load route data
        self.route_def = get_route_by_index(route_index)
        self.route_grid = load_route(self.route_def)
        self.route_name = self.route_def["route_name"]

        self.rows = len(self.route_grid)
        self.cols = len(self.route_grid[0])

        self.start_tile = self.route_def["start_position"]
        self.possible_goals = self.route_def["goals"]

        if seed is not None:
            random.seed(seed)

        chosen_goal = random.choice(self.possible_goals)
        self.current_goal_name = chosen_goal["goal_name"]
        self.selected_goal_tile = chosen_goal["position"]

        self.start_pos = tile_to_pixel(self.start_tile)
        self.goal_pos = tile_to_pixel(self.selected_goal_tile)

        self.current_leg = "TO"
        self.show_goal = False
        self.game_state = "WAITING_START"
        self.countdown_start_time = 0
        self.countdown_duration = 3
        self.run_start_time = 0
        self.run_end_time = 0

        # Collision tracking
        self.collision_frames = 0

        # Instead of just points, store segments: [( (x1,y1), (x2,y2), color ), ... ]
        self.path_segments = []
        self.last_point = None  # The last point where the player was drawing

        self.session_log = {
            "route_name": self.route_name,
            "seed": seed,
            "start_tile": self.start_tile,
            "goal_name_to": self.current_goal_name,
            "goal_tile_to": self.selected_goal_tile,
            "goal_name_from": "",
            "goal_tile_from": (),
            "to_leg_time": 0.0,
            "to_leg_collisions": 0,
            "to_leg_productivity": 0.0,
            "from_leg_time": 0.0,
            "from_leg_collisions": 0,
            "from_leg_productivity": 0.0,
            "final_productivity": 0.0,
        }

    def run_game(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouse_down(event.pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

            self.update(dt)
            self.draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def handle_mouse_down(self, mouse_pos):
        if self.game_state == "WAITING_START":
            # Must click near the start to begin countdown
            if distance(mouse_pos, self.start_pos) <= TILE_SIZE // 2:
                self.game_state = "COUNTDOWN"
                self.countdown_start_time = time()

        elif self.game_state == "RUNNING":
            # Re-anchor the path if near the last point or start
            if self.last_point is None:
                # no path yet
                if distance(mouse_pos, self.start_pos) <= MAX_RECLICK_DISTANCE:
                    self.last_point = mouse_pos
            else:
                # must be near the last point
                if distance(mouse_pos, self.last_point) <= MAX_RECLICK_DISTANCE:
                    self.last_point = mouse_pos

    def update(self, dt):
        if self.game_state == "COUNTDOWN":
            elapsed = time() - self.countdown_start_time
            if elapsed >= self.countdown_duration:
                self.game_state = "RUNNING"
                self.show_goal = True
                self.run_start_time = time()

        elif self.game_state == "RUNNING":
            mouse_buttons = pygame.mouse.get_pressed()
            if mouse_buttons[0]:
                mx, my = pygame.mouse.get_pos()
                # If we haven't started drawing yet, we must be near start
                if self.last_point is None:
                    if distance((mx, my), self.start_pos) <= MAX_RECLICK_DISTANCE:
                        self.last_point = (mx, my)
                else:
                    # Must be near the last point to continue
                    if distance((mx, my), self.last_point) <= MAX_RECLICK_DISTANCE:
                        # Determine color based on collision
                        if is_wall(self.route_grid, mx, my):
                            seg_color = (255, 0, 0)  # Red for wall
                            self.collision_frames += 1
                        else:
                            seg_color = (255, 255, 255)  # White for open path

                        new_segment = (self.last_point, (mx, my), seg_color)
                        self.path_segments.append(new_segment)

                        self.last_point = (mx, my)

                # Check goal
                if distance((mx, my), self.goal_pos) < TILE_SIZE * 0.5:
                    self.run_end_time = time()
                    self.finish_leg()

    def finish_leg(self):
        total_time = self.run_end_time - self.run_start_time

        # Adjust baseline time for these mazes
        baseline_time = 40.0
        time_factor = baseline_time / total_time if total_time > 0 else 0
        collision_penalty_factor = 1.0 - (0.01 * self.collision_frames)
        leg_productivity = time_factor * collision_penalty_factor * 100

        if self.current_leg == "TO":
            self.session_log["to_leg_time"] = total_time
            self.session_log["to_leg_collisions"] = self.collision_frames
            self.session_log["to_leg_productivity"] = leg_productivity

            # Prepare second leg
            self.current_leg = "FROM"
            self.game_state = "WAITING_START"
            self.show_goal = False

            # Clear path data
            self.path_segments.clear()
            self.last_point = None
            self.collision_frames = 0

            # Swap start/goal
            old_goal_tile = self.selected_goal_tile

            self.session_log["goal_name_from"] = "Start Point"
            self.session_log["goal_tile_from"] = self.start_tile

            self.selected_goal_tile = self.start_tile
            self.start_tile = old_goal_tile

            self.start_pos = tile_to_pixel(self.start_tile)
            self.goal_pos = tile_to_pixel(self.selected_goal_tile)

        else:
            # FROM leg
            self.session_log["from_leg_time"] = total_time
            self.session_log["from_leg_collisions"] = self.collision_frames
            self.session_log["from_leg_productivity"] = leg_productivity

            final_prod = (
                (self.session_log["to_leg_productivity"] / 100.0)
                * (leg_productivity / 100.0)
            ) * 100.0
            self.session_log["final_productivity"] = final_prod

            self.game_state = "FINISHED"
            print("=== Round Trip Complete ===")
            print(f"TO Leg: time={self.session_log['to_leg_time']:.2f}s, "
                  f"collisions={self.session_log['to_leg_collisions']}, "
                  f"productivity={self.session_log['to_leg_productivity']:.2f}%")
            print(f"FROM Leg: time={self.session_log['from_leg_time']:.2f}s, "
                  f"collisions={self.session_log['from_leg_collisions']}, "
                  f"productivity={self.session_log['from_leg_productivity']:.2f}%")
            print(f"FINAL Productivity: {final_prod:.2f}%")

            # Write to CSV
            write_log_to_csv(self.session_log)

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.draw_maze()
        self.draw_path()
        self.draw_start_and_goal()
        self.draw_gui_text()

        if self.game_state == "COUNTDOWN":
            self.draw_countdown()
        elif self.game_state == "FINISHED":
            self.draw_finished_text()

    def draw_maze(self):
        for r in range(self.rows):
            for c in range(self.cols):
                tile = self.route_grid[r][c]
                x = c * TILE_SIZE
                y = r * TILE_SIZE
                if tile == '#':
                    color = (60, 60, 60)  # wall color
                else:
                    color = (180, 180, 180)  # floor color
                pygame.draw.rect(self.screen, color, (x, y, TILE_SIZE, TILE_SIZE))

    def draw_path(self):
        """Draw each segment in the color it was recorded (white or red)."""
        for segment in self.path_segments:
            (start_pt, end_pt, seg_color) = segment
            pygame.draw.line(self.screen, seg_color, start_pt, end_pt, 3)

    def draw_start_and_goal(self):
        pygame.draw.circle(self.screen, (0, 255, 0), self.start_pos, TILE_SIZE // 2, 2)
        if self.show_goal:
            pygame.draw.circle(self.screen, (255, 0, 0), self.goal_pos, TILE_SIZE // 2, 2)

    def draw_gui_text(self):
        font = pygame.font.SysFont(None, 24)
        route_surface = font.render(f"Route: {self.route_name}", True, (255, 255, 255))
        self.screen.blit(route_surface, (10, 10))

        if self.show_goal and self.current_leg == "TO":
            goal_surface = font.render(f"Goal: {self.current_goal_name}", True, (255, 50, 50))
            self.screen.blit(goal_surface, (10, 35))
        elif self.show_goal and self.current_leg == "FROM":
            goal_surface = font.render("Goal: Return to Start", True, (255, 50, 50))
            self.screen.blit(goal_surface, (10, 35))

    def draw_countdown(self):
        elapsed = time() - self.countdown_start_time
        remaining = max(0, self.countdown_duration - elapsed)
        font = pygame.font.SysFont(None, 48)
        txt_surface = font.render(f"{int(math.ceil(remaining))}", True, (255, 255, 255))
        rect = txt_surface.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(txt_surface, rect)

    def draw_finished_text(self):
        font = pygame.font.SysFont(None, 36)
        final_prod = self.session_log["final_productivity"]
        msg = f"Finished! Final Productivity: {final_prod:.2f}% (Press ESC to quit)"
        txt_surface = font.render(msg, True, (255, 255, 0))
        rect = txt_surface.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(txt_surface, rect)

# -------------------- MAIN -------------------- #
if __name__ == "__main__":
    route_index = 0
    seed_value = None

    game = MazeGame(route_index=route_index, seed=seed_value)
    game.run_game()
