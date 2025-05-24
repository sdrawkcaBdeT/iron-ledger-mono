import pygame
import sys
import math
import random
import os
import csv
from datetime import datetime

##############################
# CONFIGURATION
##############################
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FPS = 60

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")

# Wave parameters
INITIAL_WAVE_SPEED = 1.3
WAVE_SPEED_INCREASE = 0.8
INITIAL_PEAK_MARGIN = 100   # in ms
PEAK_MARGIN_DECREASE = 5
WAVE_PERIOD_PX = 200
WAVE_CREST_OFFSET_PX = 100

# Hits required
MIN_HITS_REQUIRED = 8
MAX_HITS_REQUIRED = 10

# Accuracy thresholds for final rating
ACCURACY_THRESHOLDS = [
    (80,  "Crude"),
    (60,  "Worn"),
    (40,  "Adequate"),
    (25,  "Refined"),
    (10,  "Masterwork"),
    ( 5,  "Perfect")
]

##############################
# FIXED CLICK FEEDBACK TIERS
##############################
CLICK_FEEDBACK_TIERS = [
    (8,   "Perfect"),
    (25,  "Great"),
    (40,  "Good"),
    (80,  "Okay"),
    (9999,"Miss")
]

def map_accuracy_to_rating(average_error_ms):
    """
    Convert an overall average error (all attempts) to a forging rating.
    """
    for threshold, label in ACCURACY_THRESHOLDS:
        if average_error_ms >= threshold:
            return label
    return "Perfect"

def map_click_feedback_fixed_thresholds(error_ms, margin_ms):
    """
    If error_ms > margin_ms => "Miss"
    Else we check the fixed tiers, skipping those > margin_ms.
    """
    if error_ms > margin_ms:
        return "Miss"

    for (threshold, label) in CLICK_FEEDBACK_TIERS:
        if threshold > margin_ms:
            return "Miss"
        if error_ms <= threshold:
            return label
    return "Miss"  # fallback

def load_image(filename, width=None, height=None):
    path = os.path.join(ASSETS_PATH, filename)
    img = pygame.image.load(path).convert_alpha()
    if width and height:
        img = pygame.transform.scale(img, (width, height))
    return img

##############################
# MAIN GAME CLASS
##############################
class ForgingGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Tuning the Steel - Miss Penalty 1.5x Error + Single-Row CSV Log")
        self.clock = pygame.time.Clock()

        # Load background
        self.background = load_image("fishing_background.png", WINDOW_WIDTH, WINDOW_HEIGHT)

        # Required hits
        self.hits_required = random.randint(MIN_HITS_REQUIRED, MAX_HITS_REQUIRED)
        self.hits_done = 0

        # We'll track all attempts (hits + misses)
        # final error for each attempt in attempt_errors_ms
        self.attempt_errors_ms = []

        # Swings log: each is { "error": float, "hit": bool, "label": str }
        self.swings_log = []
        self.swings_done = 0

        # Wave
        self.wave_x = 0.0
        self.wave_speed = INITIAL_WAVE_SPEED
        self.peak_margin_ms = INITIAL_PEAK_MARGIN

        self.running = True
        self.forging_finished = False
        self.final_rating = None

        # Visual
        self.amplitude = 80
        self.y_mid = WINDOW_HEIGHT // 2
        self.font = pygame.font.SysFont(None, 24)

        # For short feedback text each click
        self.click_feedback_text = ""
        self.error_value_text = ""

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            self.handle_events(dt)
            self.update(dt)
            self.draw()
            pygame.display.flip()

        if self.final_rating:
            return ("Weapon", self.final_rating)
        else:
            return ("Weapon", "Canceled")

    def handle_events(self, dt):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if not self.forging_finished:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.attempt_strike()

    def attempt_strike(self):
        wave_mod = self.wave_x % WAVE_PERIOD_PX
        px_error = abs(wave_mod - WAVE_CREST_OFFSET_PX)

        px_per_ms = (self.wave_speed*(FPS/1000.0))
        if px_per_ms == 0:
            raw_error_ms = 9999
        else:
            raw_error_ms = px_error / px_per_ms

        old_margin = self.peak_margin_ms  # store margin now
        is_hit = (raw_error_ms <= old_margin)
        final_error_ms = raw_error_ms
        label = "Miss"  # default

        if is_hit:
            self.hits_done += 1
            label = map_click_feedback_fixed_thresholds(raw_error_ms, old_margin)
            # then shrink margin for next time
            self.wave_speed += WAVE_SPEED_INCREASE
            self.peak_margin_ms = max(5, self.peak_margin_ms - PEAK_MARGIN_DECREASE)
            if self.hits_done >= self.hits_required:
                self.finish_forging()
        else:
            # Miss => 1.5x penalty
            final_error_ms *= 1.5
            label = "Miss"

        # store final_error_ms
        self.attempt_errors_ms.append(final_error_ms)

        # for on-screen feedback
        self.click_feedback_text = label
        self.error_value_text = f"Error: {int(final_error_ms)} ms"

        # store in log
        self.swings_log.append({
            "error": final_error_ms,
            "hit": is_hit,
            "label": label
        })

    def finish_forging(self):
        self.forging_finished = True
        avg_err = self.get_current_average_error() or 9999
        self.final_rating = map_accuracy_to_rating(avg_err)

        # Once forging is done, log data to CSV
        self.log_game_data()

    def log_game_data(self, filename="games/logs/blacksmithing_log.csv"):
        """
        Writes ONE summary row for the entire forging game.
        The final column includes a single string with each swing's error + [o] or [x].
        Example for swings: "30:[o]|160:[x]|12:[o]"
        """
        game_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        final_avg = self.get_current_average_error() or 9999
        # build the swing error list
        # e.g. "30:[o]|160:[x]"
        swing_details_str = []
        for i, swing in enumerate(self.swings_log, start=1):
            is_hit = swing["hit"]
            err_ms = swing["error"]
            mark = "o" if is_hit else "x"
            swing_details_str.append(f"{int(err_ms)}:[{mark}]")

        # join them
        swings_info = "|".join(swing_details_str)

        summary_row = [
            game_id,               # Unique ID
            self.swings_done, 
            self.hits_done,
            self.hits_required,
            f"{final_avg:.1f}",    # final avg error
            self.final_rating,
            swings_info            # single column with all swings
        ]

        file_exists = os.path.isfile(filename)

        # We'll store columns:
        # GameID, Swings, Hits, RequiredHits, FinalAvgErr, FinalRating, SwingDetails
        with open(filename, "a", newline="") as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow([
                    "GameID","Swings","Hits","RequiredHits",
                    "FinalAvgErr","FinalRating","SwingDetails"
                ])

            writer.writerow(summary_row)

    def get_current_average_error(self):
        if not self.attempt_errors_ms:
            return None
        return sum(self.attempt_errors_ms)/len(self.attempt_errors_ms)

    def update(self, dt):
        if not self.forging_finished:
            self.wave_x += self.wave_speed
            self.wave_x = self.wave_x % (WAVE_PERIOD_PX*100000)

    def compute_time_until_crest(self):
        wave_mod = self.wave_x % WAVE_PERIOD_PX
        if wave_mod <= WAVE_CREST_OFFSET_PX:
            px_diff = WAVE_CREST_OFFSET_PX - wave_mod
        else:
            px_diff = (WAVE_PERIOD_PX - wave_mod) + WAVE_CREST_OFFSET_PX

        px_per_ms = (self.wave_speed*(FPS/1000.0))
        if px_per_ms==0:
            return 9999
        return px_diff/px_per_ms

    def draw(self):
        if self.background:
            self.screen.blit(self.background, (0,0))
        else:
            self.screen.fill((30,30,30))

        self.draw_wave()

        cum_error = int(sum(self.attempt_errors_ms)) if self.attempt_errors_ms else 0
        # if we have 0 swings_done, avoid division
        avg_err = self.get_current_average_error() or 9999
        info_text = (f"Swings:{self.swings_done}  |  "
                     f"Hits:{self.hits_done}/{self.hits_required}  |  "
                     f"Speed:{self.wave_speed:.2f}  |  "
                     f"Margin:{self.peak_margin_ms}ms  |  "
                     f"AvgErr: {avg_err:.0f} ms")
        info_img = self.font.render(info_text, True, (255,255,255))
        self.screen.blit(info_img, (20,20))

        hint_text = "WAIT for crest circle at top, THEN click!"
        hint_img = self.font.render(hint_text, True, (180,180,180))
        self.screen.blit(hint_img, (20,50))

        if not self.forging_finished:
            ms_until = self.compute_time_until_crest()
            crest_txt = f"Next crest in ~{int(ms_until)} ms"
            crest_img = self.font.render(crest_txt, True, (230,230,0))
            self.screen.blit(crest_img, (20,80))

            if self.click_feedback_text:
                fb_msg = f"{self.click_feedback_text} | {self.error_value_text}"
                fb_img = self.font.render(fb_msg, True, (255,180,180))
                self.screen.blit(fb_img, (20,110))
        else:
            final_text = (f"Forging Complete! Quality: {self.final_rating} "
                          f"(AvgErr {int(self.get_current_average_error() or 9999)} ms)")
            final_img = self.font.render(final_text, True, (255,200,0))
            self.screen.blit(final_img, (20,80))

            exit_text = "Close window to exit"
            exit_img = self.font.render(exit_text, True, (255,255,255))
            self.screen.blit(exit_img, (20,110))

        self.draw_swings_log()

    def draw_wave(self):
        freq = 0.03
        wave_color = (100,200,255)
        baseline_color = (80,80,80)
        step = 5

        wave_points = []
        for sx in range(0, WINDOW_WIDTH+step, step):
            wv = math.sin((sx + self.wave_x)*freq)
            wave_y = self.y_mid + int(self.amplitude*wv)
            wave_points.append((sx, wave_y))

        if len(wave_points)>1:
            pygame.draw.lines(self.screen, wave_color, False, wave_points, 2)

        wave_mod = self.wave_x % WAVE_PERIOD_PX
        crest_screen_x = (WAVE_CREST_OFFSET_PX - wave_mod) % WAVE_PERIOD_PX
        while crest_screen_x<0:
            crest_screen_x += WAVE_PERIOD_PX
        while crest_screen_x>WINDOW_WIDTH:
            crest_screen_x -= WAVE_PERIOD_PX

        wave_val = math.sin((crest_screen_x + self.wave_x)*freq)
        crest_y = self.y_mid + int(wave_val*self.amplitude)

        color_line = (250,140,0)
        pygame.draw.line(self.screen, color_line,
                         (crest_screen_x, self.y_mid-self.amplitude-20),
                         (crest_screen_x, self.y_mid+self.amplitude+20), 2)

        highlight_color = (255,50,255)
        pygame.draw.circle(self.screen, highlight_color, (int(crest_screen_x), crest_y), 12)

        pygame.draw.line(self.screen, baseline_color,
                         (0,self.y_mid),(WINDOW_WIDTH,self.y_mid),1)

    def draw_swings_log(self):
        start_x = WINDOW_WIDTH - 200
        start_y = 20
        line_height = 20

        label = self.font.render("Swings Log:", True, (255,255,255))
        self.screen.blit(label, (start_x, start_y))
        y_offset = start_y + line_height

        for i, swing in enumerate(self.swings_log, start=1):
            err_ms = swing["error"]
            is_hit = swing["hit"]
            feedback_label = swing["label"]  # stored at time of click
            mark = "[o]" if is_hit else "[x]"
            text_str = f"{i}: {int(err_ms)} ms, {mark}, {feedback_label}"
            line_img = self.font.render(text_str, True, (255,255,255))
            self.screen.blit(line_img, (start_x, y_offset))
            y_offset += line_height

##############################
def main():
    forging = ForgingGame()
    result = forging.run()
    print("Forging ended. Result:", result)

if __name__ == "__main__":
    main()
