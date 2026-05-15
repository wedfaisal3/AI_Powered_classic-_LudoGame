import random
import math
import tkinter as tk
from tkinter import messagebox
import struct

# =========================================================
# SOUND (Windows only, no external files)
# - Dice roll: generated WAV (noise + decay) played once at roll start
# - Countdown: only at 5..1
# - Move: short "click" WAV per step, played AFTER redraw (sync)
# - Win: beep melody
# =========================================================
try:
    import winsound
    SOUND_OK = True
except Exception:
    SOUND_OK = False


def stop_all_sounds():
    if SOUND_OK:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


def beep(freq=800, dur=80):
    if SOUND_OK:
        try:
            winsound.Beep(int(freq), int(dur))
        except Exception:
            pass


def _play_wav_bytes(wav_bytes: bytes):
    if not SOUND_OK:
        return
    try:
        winsound.PlaySound(wav_bytes, winsound.SND_MEMORY | winsound.SND_ASYNC)
    except Exception:
        pass


def _make_wav_mono16(samples, sample_rate=22050):
    data = b"".join(struct.pack("<h", max(-32768, min(32767, int(s)))) for s in samples)
    byte_rate = sample_rate * 2
    block_align = 2
    subchunk2_size = len(data)
    chunk_size = 36 + subchunk2_size

    header = b"RIFF" + struct.pack("<I", chunk_size) + b"WAVE"
    fmt = (b"fmt " + struct.pack("<IHHIIHH",
                                 16, 1, 1,
                                 sample_rate,
                                 byte_rate,
                                 block_align,
                                 16))
    data_hdr = b"data" + struct.pack("<I", subchunk2_size)
    return header + fmt + data_hdr + data


def make_dice_roll_wav(duration_ms=260, sample_rate=22050):
    """Dice-roll-ish: low-passed noise + decay envelope."""
    n = max(1, int(sample_rate * duration_ms / 1000.0))
    out = []
    lp = 0.0
    alpha = 0.12
    for i in range(n):
        x = random.uniform(-1.0, 1.0)
        lp = (1 - alpha) * lp + alpha * x
        t = i / n
        env = (1.0 - t) ** 2.6
        ratt = math.sin(2 * math.pi * (18 + 25 * t) * t) * 0.25
        s = (lp * 0.85 + ratt * 0.15) * env
        out.append(int(s * 17000))
    return _make_wav_mono16(out, sample_rate=sample_rate)


def make_click_wav(duration_ms=18, sample_rate=22050):
    """Short click: tiny noise burst w/ fast decay (non-blocking)."""
    n = max(1, int(sample_rate * duration_ms / 1000.0))
    out = []
    for i in range(n):
        t = i / n
        env = (1.0 - t) ** 5.0
        s = random.uniform(-1.0, 1.0) * env
        out.append(int(s * 12000))
    return _make_wav_mono16(out, sample_rate=sample_rate)


CLICK_WAV = make_click_wav()


def sound_roll():
    stop_all_sounds()
    _play_wav_bytes(make_dice_roll_wav())


def sound_move_click():
    if SOUND_OK:
        _play_wav_bytes(CLICK_WAV)


def sound_countdown(seconds_left: int):
    if 1 <= seconds_left <= 5:
        freq = 720 + (5 - seconds_left) * 140
        beep(freq, 70)


def sound_capture():
    for f in (950, 760, 950):
        beep(f, 55)


def sound_win():
    for f, d in [(880, 120), (990, 120), (1180, 180), (990, 120), (1320, 220)]:
        beep(f, d)


# =========================================================
# LUDO BOARD / RULES
# =========================================================
def roll_dice():
    return random.randint(1, 6)


# Main track (52) mapping (15x15 indices): idx = row*15 + col
PATH_52 = [
    91, 92, 93, 94, 95, 81, 66, 51, 36, 21, 6, 7, 8, 23, 38, 53, 68, 83,
    99, 100, 101, 102, 103, 104, 119, 134, 133, 132, 131, 130, 129, 143,
    158, 173, 188, 203, 218, 217, 216, 201, 186, 171, 156, 141, 125, 124,
    123, 122, 121, 120, 105, 90
]
assert len(PATH_52) == 52 and len(set(PATH_52)) == 52


def idx_to_rc(idx: int):
    return divmod(idx, 15)


PATH_RC = [idx_to_rc(i) for i in PATH_52]

# Safe squares (stars)
STAR_SQUARES = {91, 133, 23, 201}
ENTER_FINISH = {105, 119, 7, 217}
SAFE_MAIN = set(STAR_SQUARES) | set(ENTER_FINISH)

# Finish lanes (vertical under color)
BLUE_FINISH_LINE = [(1, 7), (2, 7), (3, 7), (4, 7), (5, 7)]
BLUE_GOAL = (6, 7)

RED_FINISH_LINE = [(13, 7), (12, 7), (11, 7), (10, 7), (9, 7)]
RED_GOAL = (8, 7)

# Starts (indices in PATH_52)
BLUE_START_IDX = PATH_52.index(23)
RED_START_IDX = PATH_52.index(201)

HOME = -1
GOAL_STEP = 57  # 0..51 main, 52..56 finish, 57 goal


def player_to_defs(player: str):
    if player == "BLUE":
        return {"start_idx": BLUE_START_IDX, "finish_line": BLUE_FINISH_LINE, "goal": BLUE_GOAL}
    return {"start_idx": RED_START_IDX, "finish_line": RED_FINISH_LINE, "goal": RED_GOAL}


def steps_to_board_rc(player: str, steps: int):
    d = player_to_defs(player)
    if steps == HOME:
        return None
    if 0 <= steps <= 51:
        idx = (d["start_idx"] + steps) % 52
        return PATH_RC[idx]
    if 52 <= steps <= 56:
        return d["finish_line"][steps - 52]
    if steps == GOAL_STEP:
        return d["goal"]
    return None


def is_safe_square(player: str, steps: int):
    if steps >= 52 or steps < 0:
        return True
    d = player_to_defs(player)
    idx = (d["start_idx"] + steps) % 52
    return PATH_52[idx] in SAFE_MAIN


def get_valid_moves_for_player(player: str, pieces_steps: list[int], dice: int):
    moves = []
    for i, s in enumerate(pieces_steps):
        if s == HOME:
            if dice == 6:
                moves.append((i, 0))
        else:
            ns = s + dice
            if ns <= GOAL_STEP:
                moves.append((i, ns))
    return moves


def try_capture(mover_player: str, mover_new_steps: int, opp_player: str, opp_pieces_steps: list[int]):
    # capture only on main track and not safe squares
    if mover_new_steps < 0 or mover_new_steps > 51:
        return False
    if is_safe_square(mover_player, mover_new_steps):
        return False

    mover_rc = steps_to_board_rc(mover_player, mover_new_steps)
    if mover_rc is None:
        return False

    captured = False
    for j, os in enumerate(opp_pieces_steps):
        if 0 <= os <= 51 and steps_to_board_rc(opp_player, os) == mover_rc:
            opp_pieces_steps[j] = HOME
            captured = True
    return captured


def check_winner(pieces_steps: list[int]):
    return all(s == GOAL_STEP for s in pieces_steps)


# =========================================================
# UI
# =========================================================
class LudoUI:
    def __init__(self, root):
        self.root = root
        root.title("Classic Ludo (RED vs BLUE) - Clean v8 (Stacked Tokens)")
        root.resizable(False, False)

        self.W, self.H = 1120, 700
        self.canvas = tk.Canvas(root, width=self.W, height=self.H, bg="#F6F7FB", highlightthickness=0)
        self.canvas.pack()

        # Board size
        self.board_px = 600
        self.cell = self.board_px // 15
        self.board_left = 430
        self.board_top = 50

        # Side panel
        self.panel_x1, self.panel_y1 = 30, 50
        self.panel_x2, self.panel_y2 = 390, 650

        # Colors
        self.COL_BORDER = "#D9DDE7"
        self.COL_TEXT = "#1F2430"
        self.COL_SUB = "#5B6273"
        self.COL_TRACK = "#EEF1F7"
        self.COL_TRACK2 = "#E6EAF3"
        self.COL_SAFE = "#45C97B"
        self.RED = "#E44B4B"
        self.BLUE = "#3D6AF2"
        self.GLOW = "#FFB300"

        # Game state
        self.started = False
        self.state = "START"  # START, HUMAN_ROLL, HUMAN_PICK, AI_THINK, ANIMATING

        self.red = [HOME, HOME]   # Human
        self.blue = [HOME, HOME]  # AI

        self.red_dice = None
        self.blue_dice = None

        # Timer
        self.TURN_SECONDS = 15
        self.current_turn = "RED"
        self.time_left = {"RED": self.TURN_SECONDS, "BLUE": self.TURN_SECONDS}
        self._timer_job = None
        self.timer_paused = False

        self.valid_moves = []
        self.msg = "Click START to begin."

        # Click maps
        self.token_hit = {}

        # Stacking offsets map: (player, idx) -> (dx, dy)
        self._offsets = {}

        # Temp override during animation: {("RED",0): steps, ...}
        self._temp_steps = {}

        # Buttons rects
        self.start_rect = (80, 585, 340, 635)
        self.red_roll_rect = (70, 255, 350, 305)
        self.blue_roll_rect = (70, 420, 350, 470)

        self.canvas.bind("<Button-1>", self.on_click)
        self.draw()

    # ---------- Drawing helpers ----------
    def rounded_rect(self, x1, y1, x2, y2, r=14, fill="#fff", outline="#000", width=1):
        pts = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1
        ]
        return self.canvas.create_polygon(pts, smooth=True, splinesteps=24,
                                          fill=fill, outline=outline, width=width)

    def draw_star(self, cx, cy, outer=11, inner=5.5, fill="#45C97B", outline=""):
        points = []
        for i in range(10):
            ang = math.radians(-90 + i * 36)
            r = outer if i % 2 == 0 else inner
            points.extend([cx + r * math.cos(ang), cy + r * math.sin(ang)])
        self.canvas.create_polygon(points, fill=fill, outline=outline)

    def rc_to_xy(self, r, c):
        return self.board_left + c * self.cell, self.board_top + r * self.cell

    def draw_button(self, rect, text, enabled=True, tint="#E9EEF9"):
        x1, y1, x2, y2 = rect
        fill = tint if enabled else "#F1F2F6"
        tcol = self.COL_TEXT if enabled else "#9AA1B2"
        self.rounded_rect(x1, y1, x2, y2, r=16, fill=fill, outline=self.COL_BORDER, width=2)
        self.canvas.create_text((x1+x2)//2, (y1+y2)//2, text=text, fill=tcol, font=("Arial", 13, "bold"))

    def draw_dice(self, x, y, value):
        self.rounded_rect(x, y, x+84, y+84, r=16, fill="#FFFFFF", outline=self.COL_BORDER, width=2)
        if value is None:
            self.canvas.create_text(x+42, y+42, text="—", fill=self.COL_SUB, font=("Arial", 18, "bold"))
            return
        cx, cy = x + 42, y + 42
        d = 16
        spots = {
            1: [(0, 0)],
            2: [(-d, -d), (d, d)],
            3: [(-d, -d), (0, 0), (d, d)],
            4: [(-d, -d), (d, -d), (-d, d), (d, d)],
            5: [(-d, -d), (d, -d), (0, 0), (-d, d), (d, d)],
            6: [(-d, -d), (d, -d), (-d, 0), (d, 0), (-d, d), (d, d)]
        }
        for ox, oy in spots[value]:
            self.canvas.create_oval(cx+ox-6, cy+oy-6, cx+ox+6, cy+oy+6, fill=self.COL_TEXT, outline="")

    def draw_dice_box(self, x, y, label, value, color_tag, time_left, active=False):
        self.rounded_rect(x, y, x+300, y+120, r=18, fill="#FFFFFF", outline=self.COL_BORDER, width=2)
        self.canvas.create_text(x+16, y+16, anchor="w", text=label, fill=color_tag, font=("Arial", 13, "bold"))

        badge = f"{time_left}s"
        badge_fill = "#FFF3D6" if active else "#F3F4F7"
        self.rounded_rect(x+230, y+10, x+290, y+34, r=10, fill=badge_fill, outline=self.COL_BORDER, width=1)
        self.canvas.create_text(x+260, y+22, text=badge, fill=self.COL_SUB, font=("Arial", 11, "bold"))

        self.draw_dice(x+18, y+38, value)

    # ---------- Timer ----------
    def stop_timer(self):
        if self._timer_job is not None:
            try:
                self.root.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None

    def pause_timer(self):
        self.timer_paused = True
        stop_all_sounds()  # stops countdown sound immediately
        self.stop_timer()

    def resume_timer(self):
        if not self.started:
            return
        self.timer_paused = False
        self._schedule_tick()

    def start_turn_timer(self, player):
        self.stop_timer()
        self.current_turn = player
        self.time_left[player] = self.TURN_SECONDS
        self.timer_paused = False
        self._schedule_tick()

    def _schedule_tick(self):
        self.stop_timer()

        def tick():
            if not self.started or self.timer_paused:
                return
            p = self.current_turn
            self.time_left[p] -= 1

            # countdown sound only 5..1
            sound_countdown(self.time_left[p])

            if self.time_left[p] <= 0:
                self.time_left[p] = 0
                self.draw()
                self.on_timeout(p)
                return

            self.draw()
            self._timer_job = self.root.after(1000, tick)

        self.draw()
        self._timer_job = self.root.after(1000, tick)

    def on_timeout(self, player):
        if not self.started:
            return

        if player == "RED":
            if self.state in ("HUMAN_ROLL", "HUMAN_PICK"):
                self.msg = "Time's up (RED)! Turn skipped. AI's turn."
                self.valid_moves = []
                self.state = "AI_THINK"
                self.draw()
                self.start_turn_timer("BLUE")
                self.root.after(450, self.ai_turn)
        else:
            if self.state == "AI_THINK":
                self.msg = "Time's up (BLUE)! Turn skipped. Your turn."
                self.state = "HUMAN_ROLL"
                self.draw()
                self.start_turn_timer("RED")

    # ---------- Board drawing ----------
    def fill_quad(self, r1, c1, r2, c2, color):
        for r in range(r1, r2):
            for c in range(c1, c2):
                x, y = self.rc_to_xy(r, c)
                self.canvas.create_rectangle(x, y, x+self.cell, y+self.cell, fill=color, outline="#E8EAF0")

    def draw_finish_line(self, coords_list, color):
        for (r, c) in coords_list:
            x, y = self.rc_to_xy(r, c)
            self.canvas.create_rectangle(x+2, y+2, x+self.cell-2, y+self.cell-2,
                                         fill=color, outline="#C9CEDB")

    def draw_goal(self, goal_rc, color):
        r, c = goal_rc
        x, y = self.rc_to_xy(r, c)
        self.canvas.create_rectangle(x+2, y+2, x+self.cell-2, y+self.cell-2,
                                     fill="#FFE08A", outline="#C9CEDB")
        cx, cy = x + self.cell//2, y + self.cell//2
        self.canvas.create_oval(cx-10, cy-10, cx+10, cy+10, fill=color, outline="")

    def draw_home_slots(self):
        for (r, c) in [(11, 2), (12, 3)]:
            x, y = self.rc_to_xy(r, c)
            self.canvas.create_oval(x+8, y+8, x+self.cell-8, y+self.cell-8, fill="#FFFFFF", outline=self.RED, width=2)

        for (r, c) in [(2, 12), (3, 11)]:
            x, y = self.rc_to_xy(r, c)
            self.canvas.create_oval(x+8, y+8, x+self.cell-8, y+self.cell-8, fill="#FFFFFF", outline=self.BLUE, width=2)

    def _get_steps(self, player: str, idx: int):
        """Get current steps for a token, considering temp animation overrides."""
        key = (player, idx)
        if key in self._temp_steps:
            return self._temp_steps[key]
        if player == "RED":
            return self.red[idx]
        return self.blue[idx]

    def token_base_center(self, player, piece_idx, steps):
        """Exact center of square (no offsets)."""
        if steps == HOME:
            home_rcs = [(11, 2), (12, 3)] if player == "RED" else [(2, 12), (3, 11)]
            r, c = home_rcs[piece_idx]
            x, y = self.rc_to_xy(r, c)
            return x + self.cell//2, y + self.cell//2

        r, c = steps_to_board_rc(player, steps)
        x, y = self.rc_to_xy(r, c)
        return x + self.cell//2, y + self.cell//2

    def _offset_pattern(self, n: int):
        """Offsets for stacking tokens in same cell. All patterns are centered overall."""
        if n <= 1:
            return [(0, 0)]
        d = 10  # spacing
        if n == 2:
            return [(-d, 0), (d, 0)]
        if n == 3:
            return [(0, -d), (-d, d), (d, d)]
        if n == 4:
            return [(-d, -d), (d, -d), (-d, d), (d, d)]
        # n >= 5 : circle
        R = 12
        return [(int(R * math.cos(2*math.pi*i/n)), int(R * math.sin(2*math.pi*i/n))) for i in range(n)]

    def build_offsets(self):
        """
        Build offsets so tokens sharing same square get separated (not hidden),
        but still centered around the square center.
        """
        groups = {}  # (r,c,zoneType) -> list[(player, idx)]
        all_tokens = [("RED", 0), ("RED", 1), ("BLUE", 0), ("BLUE", 1)]

        for player, idx in all_tokens:
            steps = self._get_steps(player, idx)
            # HOME squares already separated, so ignore grouping there
            if steps == HOME:
                self._offsets[(player, idx)] = (0, 0)
                continue

            rc = steps_to_board_rc(player, steps)
            # safety
            if rc is None:
                self._offsets[(player, idx)] = (0, 0)
                continue

            key = (rc[0], rc[1])
            groups.setdefault(key, []).append((player, idx))

        # Assign offsets per group
        for cell_key, tokens in groups.items():
            # stable order: RED first then BLUE, and by idx
            tokens_sorted = sorted(tokens, key=lambda x: (0 if x[0] == "RED" else 1, x[1]))
            pattern = self._offset_pattern(len(tokens_sorted))
            for (tkn, off) in zip(tokens_sorted, pattern):
                self._offsets[tkn] = off

        # any token not assigned (shouldn't happen)
        for player, idx in all_tokens:
            self._offsets.setdefault((player, idx), (0, 0))

    def draw_token(self, player, idx, steps, highlight=False):
        color = self.RED if player == "RED" else self.BLUE

        cx, cy = self.token_base_center(player, idx, steps)
        dx, dy = self._offsets.get((player, idx), (0, 0))
        x, y = cx + dx, cy + dy

        r = 16
        if highlight:
            self.canvas.create_oval(x-r-9, y-r-9, x+r+9, y+r+9, outline=self.GLOW, width=5)

        shadow = self.canvas.create_oval(x-r+3, y-r+5, x+r+3, y+r+5,
                                         fill="#000000", outline="", stipple="gray50")
        self.canvas.tag_lower(shadow)

        tid = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="#1A1F2A", width=2)
        self.canvas.create_oval(x-r+4, y-r+4, x-r+10, y-r+10, fill="#FFFFFF", outline="")
        # no numbers
        self.token_hit[tid] = (player, idx)

    # ---------- Main draw ----------
    def draw(self):
        self.canvas.delete("all")
        self.token_hit.clear()

        # offsets must be rebuilt every draw (because tokens can share squares)
        self.build_offsets()

        # Panel
        self.rounded_rect(self.panel_x1, self.panel_y1, self.panel_x2, self.panel_y2,
                          r=22, fill="#FFFFFF", outline=self.COL_BORDER, width=2)

        self.canvas.create_text(60, 90, anchor="w", text="LUDO", fill=self.COL_TEXT, font=("Arial", 28, "bold"))
        self.canvas.create_text(60, 120, anchor="w", text="Human (RED) vs AI (BLUE)", fill=self.COL_SUB, font=("Arial", 12))

        self.draw_dice_box(60, 150, "RED Dice (Human)", self.red_dice, self.RED,
                           time_left=self.time_left["RED"], active=(self.started and self.current_turn == "RED"))
        self.draw_button(self.red_roll_rect, "RED ROLL",
                         enabled=(self.started and self.state == "HUMAN_ROLL"),
                         tint="#FFECEC")

        self.draw_dice_box(60, 315, "BLUE Dice (AI)", self.blue_dice, self.BLUE,
                           time_left=self.time_left["BLUE"], active=(self.started and self.current_turn == "BLUE"))
        self.draw_button(self.blue_roll_rect, "BLUE ROLL (AI)", enabled=False, tint="#EAF0FF")

        self.canvas.create_text(60, 500, anchor="w", text="Status", fill=self.COL_TEXT, font=("Arial", 14, "bold"))
        self.rounded_rect(60, 520, 360, 640, r=14, fill="#FAFBFF", outline=self.COL_BORDER, width=2)
        self.canvas.create_text(70, 535, anchor="nw", text=self.msg, fill=self.COL_SUB,
                                font=("Arial", 11), width=270)

        if not self.started:
            self.draw_button(self.start_rect, "START GAME", enabled=True, tint="#E9EEF9")

        # Board container
        self.rounded_rect(self.board_left-20, self.board_top-20,
                          self.board_left+self.board_px+20, self.board_top+self.board_px+20,
                          r=26, fill="#FFFFFF", outline=self.COL_BORDER, width=2)

        # base grid
        for r in range(15):
            for c in range(15):
                x, y = self.rc_to_xy(r, c)
                self.canvas.create_rectangle(x, y, x+self.cell, y+self.cell, fill="#FFFFFF", outline="#E8EAF0")

        # colored quadrants
        self.fill_quad(0, 0, 6, 6, "#EAF7EE")
        self.fill_quad(0, 9, 6, 15, "#EAF0FF")
        self.fill_quad(9, 0, 15, 6, "#FFECEC")
        self.fill_quad(9, 9, 15, 15, "#FFF7DA")
        self.fill_quad(6, 6, 9, 9, "#F5F6FA")

        # main path
        for i, (rr, cc) in enumerate(PATH_RC):
            x, y = self.rc_to_xy(rr, cc)
            fill = self.COL_TRACK if (i % 2 == 0) else self.COL_TRACK2
            self.canvas.create_rectangle(x+2, y+2, x+self.cell-2, y+self.cell-2, fill=fill, outline="#C9CEDB")

        # safe stars
        for idx in SAFE_MAIN:
            rr, cc = idx_to_rc(idx)
            x, y = self.rc_to_xy(rr, cc)
            self.draw_star(x + self.cell//2, y + self.cell//2, outer=11, inner=5.5, fill=self.COL_SAFE)

        # finish lanes
        self.draw_finish_line(RED_FINISH_LINE, self.RED)
        self.draw_finish_line(BLUE_FINISH_LINE, self.BLUE)

        # goals
        self.draw_goal(RED_GOAL, self.RED)
        self.draw_goal(BLUE_GOAL, self.BLUE)

        # home slots
        self.draw_home_slots()

        # highlight movable
        movable = set([m[0] for m in self.valid_moves]) if self.state == "HUMAN_PICK" else set()

        # tokens (use _get_steps so animation override shows properly)
        for i in range(2):
            self.draw_token("RED", i, self._get_steps("RED", i), highlight=(i in movable))
        for i in range(2):
            self.draw_token("BLUE", i, self._get_steps("BLUE", i), highlight=False)

        self.canvas.create_text(self.board_left, self.H-18, anchor="w",
                                text="Stacking enabled: tokens in same square never hide, and each one is clickable.",
                                fill="#6A7285", font=("Arial", 11))

    # ---------- Interaction ----------
    def click_in_rect(self, x, y, rect):
        x1, y1, x2, y2 = rect
        return (x1 <= x <= x2) and (y1 <= y <= y2)

    def on_click(self, event):
        x, y = event.x, event.y

        # Start
        if (not self.started) and self.click_in_rect(x, y, self.start_rect):
            self.start_game()
            return

        if not self.started:
            return

        # Human roll
        if self.state == "HUMAN_ROLL" and self.click_in_rect(x, y, self.red_roll_rect):
            self.human_roll()
            return

        # Human pick
        if self.state != "HUMAN_PICK":
            return

        items = self.canvas.find_overlapping(x, y, x, y)
        clicked = None
        for it in reversed(items):
            if it in self.token_hit:
                clicked = it
                break
        if clicked is None:
            return

        player, idx = self.token_hit[clicked]
        if player != "RED":
            return

        # find move for that piece
        move = None
        for p, ns in self.valid_moves:
            if p == idx:
                move = (p, ns)
                break
        if move is None:
            return

        p, new_steps = move
        old_steps = self.red[p]
        self.animate_steps("RED", p, old_steps, new_steps, lambda: self.after_human_move(p, new_steps))

    # ---------- Start game ----------
    def start_game(self):
        self.started = True
        self.state = "HUMAN_ROLL"

        self.red = [HOME, HOME]
        self.blue = [HOME, HOME]

        self.red_dice = None
        self.blue_dice = None
        self.valid_moves = []

        self.msg = "Your turn (RED): click RED ROLL."
        self.time_left = {"RED": self.TURN_SECONDS, "BLUE": self.TURN_SECONDS}

        self.draw()
        self.start_turn_timer("RED")

    # ---------- Turns ----------
    def human_roll(self):
        # freeze timer while rolling
        self.pause_timer()

        self.red_dice = roll_dice()
        sound_roll()

        self.valid_moves = get_valid_moves_for_player("RED", self.red, self.red_dice)

        if not self.valid_moves:
            self.msg = f"RED rolled {self.red_dice}. No valid moves. AI's turn."
            self.valid_moves = []
            self.state = "AI_THINK"
            self.draw()
            self.start_turn_timer("BLUE")
            self.root.after(450, self.ai_turn)
            return

        # resume timer for decision phase
        self.msg = f"RED rolled {self.red_dice}. Click a glowing RED piece."
        self.state = "HUMAN_PICK"
        self.draw()
        self.resume_timer()

    def after_human_move(self, piece_idx, new_steps):
        self.red[piece_idx] = new_steps

        captured = try_capture("RED", new_steps, "BLUE", self.blue)
        if captured:
            sound_capture()
            self.msg = "Nice! You captured a BLUE piece."
        else:
            self.msg = "RED moved."

        if check_winner(self.red):
            self.stop_timer()
            sound_win()
            messagebox.showinfo("Result", "🎉 RED wins!")
            self.root.destroy()
            return

        if self.red_dice == 6:
            self.msg += " You rolled 6: roll again."
            self.valid_moves = []
            self.state = "HUMAN_ROLL"
            self.draw()
            self.start_turn_timer("RED")
            return

        self.valid_moves = []
        self.state = "AI_THINK"
        self.msg = "AI is thinking..."
        self.draw()
        self.start_turn_timer("BLUE")
        self.root.after(450, self.ai_turn)

    def ai_turn(self):
        if not self.started or self.state != "AI_THINK":
            return

        self.pause_timer()

        self.blue_dice = roll_dice()
        sound_roll()

        moves = get_valid_moves_for_player("BLUE", self.blue, self.blue_dice)

        if not moves:
            self.msg = f"BLUE rolled {self.blue_dice}. No valid moves. Your turn."
            self.state = "HUMAN_ROLL"
            self.draw()
            self.start_turn_timer("RED")
            return

        # heuristic
        best, best_score = None, -10**9
        for p, ns in moves:
            score = 0
            tmp_red = self.red[:]
            if try_capture("BLUE", ns, "RED", tmp_red):
                score += 250
            if is_safe_square("BLUE", ns):
                score += 50
            if self.blue[p] == HOME and ns == 0:
                score += 60
            score += ns
            if score > best_score:
                best_score, best = score, (p, ns)

        p, new_steps = best
        old_steps = self.blue[p]
        self.animate_steps("BLUE", p, old_steps, new_steps, lambda: self.after_ai_move(p, new_steps))

    def after_ai_move(self, piece_idx, new_steps):
        self.blue[piece_idx] = new_steps

        captured = try_capture("BLUE", new_steps, "RED", self.red)
        if captured:
            sound_capture()
            self.msg = f"BLUE rolled {self.blue_dice} and captured you!"
        else:
            self.msg = "BLUE moved."

        if check_winner(self.blue):
            self.stop_timer()
            sound_win()
            messagebox.showinfo("Result", "🤖 BLUE (AI) wins!")
            self.root.destroy()
            return

        if self.blue_dice == 6:
            self.msg += " AI rolled 6: plays again..."
            self.state = "AI_THINK"
            self.draw()
            self.start_turn_timer("BLUE")
            self.root.after(450, self.ai_turn)
            return

        self.state = "HUMAN_ROLL"
        self.draw()
        self.start_turn_timer("RED")

    # ---------- Animation (sync move sound, stacking-safe) ----------
    def animate_steps(self, player, piece_idx, from_steps, to_steps, on_done):
        self.pause_timer()
        self.state = "ANIMATING"
        self.draw()

        if from_steps == HOME:
            path_steps = [to_steps]
        else:
            path_steps = list(range(from_steps + 1, to_steps + 1))

        if not path_steps:
            on_done()
            return

        speed_ms = 55

        def step_anim(k=0):
            # show animated token at step position using temp override
            self._temp_steps[(player, piece_idx)] = path_steps[k]
            self.draw()

            # click AFTER redraw (synced)
            sound_move_click()

            if k < len(path_steps) - 1:
                self.root.after(speed_ms, lambda: step_anim(k + 1))
            else:
                # clear override and finish
                self._temp_steps.pop((player, piece_idx), None)
                on_done()

        step_anim()


if __name__ == "__main__":
    root = tk.Tk()
    app = LudoUI(root)
    root.mainloop()