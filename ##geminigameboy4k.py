import tkinter as tk
import random
import time
import datetime

# --- Configuration & Constants ---
SCALE = 2
SCREEN_WIDTH_PX = 160
SCREEN_HEIGHT_PX = 144
SCREEN_WIDTH = SCREEN_WIDTH_PX * SCALE
SCREEN_HEIGHT = SCREEN_HEIGHT_PX * SCALE
FPS = 60
FRAME_DELAY = int(1000 / FPS)

# Gameboy Palette (Classic Green)
COLOR_GB_LIGHTEST = "#9bbc0f"
COLOR_GB_LIGHT = "#8bac0f"
COLOR_GB_DARK = "#306230"
COLOR_GB_DARKEST = "#0f380f"

# UI Colors
COLOR_BODY = "#c0c0c0"
COLOR_SCREEN_BORDER = "#777777"
COLOR_BUTTON_AB = "#8b0000"
COLOR_BUTTON_DPAD = "#222222"
COLOR_BUTTON_SS = "#555555" # Start/Select

# Snake Game Constants
GRID_SIZE = 8 * SCALE
GRID_W = SCREEN_WIDTH // GRID_SIZE
GRID_H = SCREEN_HEIGHT // GRID_SIZE

# App States
STATE_MENU = "MENU"
STATE_SNAKE = "SNAKE"
STATE_CLOCK = "CLOCK"
STATE_NOTES = "NOTES"
STATE_CALC = "CALC"

class GameboySimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Gameboy Simulator")
        self.root.resizable(False, False)
        
        # Determine window size based on casing
        self.case_width = 400
        self.case_height = 650
        
        # Main Canvas for drawing the case and screen
        self.canvas = tk.Canvas(root, width=self.case_width, height=self.case_height, bg="white", highlightthickness=0)
        self.canvas.pack()

        # Input State
        self.keys = {"UP": False, "DOWN": False, "LEFT": False, "RIGHT": False, "A": False, "B": False, "START": False, "SELECT": False}
        self.prev_keys = self.keys.copy() # To detect single presses
        self.mouse_pressed_btn = None # Track mouse input
        
        # System State
        self.current_state = STATE_MENU
        self.menu_items = ["SNAKE", "CLOCK", "NOTES", "CALC"]
        self.menu_index = 0

        # Snake State
        self.game_running = False
        self.game_over = False
        self.snake = []
        self.food = None
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.score = 0
        self.speed_counter = 0
        self.update_rate = 8

        # Notepad State
        self.note_content = ""
        self.note_char_idx = 1 # Start at 'A'
        self.CHAR_SET = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?.-"

        # Calculator State
        self.calc_val = "0"
        self.calc_left_op = 0
        self.calc_op = None
        self.calc_new_entry = True
        self.calc_cursor = 0
        self.calc_buttons = [
            '7', '8', '9', '/',
            '4', '5', '6', '*',
            '1', '2', '3', '-',
            'C', '0', '=', '+'
        ]

        # Initialization
        self.draw_casing()
        self.setup_bindings()
        self.reset_snake()
        
        # Start the loop
        self.game_loop()

    def draw_casing(self):
        """Draws the Gameboy body, buttons, and screen bezel."""
        c = self.canvas
        w, h = self.case_width, self.case_height

        # 1. Main Body
        c.create_rectangle(20, 20, w-20, h-20, fill=COLOR_BODY, outline=COLOR_BUTTON_DPAD, width=2)
        c.create_arc(w-60, h-60, w-20, h-20, start=-90, extent=90, fill=COLOR_BODY, outline=COLOR_BODY)

        # 2. Screen Bezel
        bezel_x, bezel_y = 40, 50
        bezel_w = w - 80
        bezel_h = SCREEN_HEIGHT + 60 
        c.create_rectangle(bezel_x, bezel_y, bezel_x+bezel_w, bezel_y+bezel_h, fill=COLOR_SCREEN_BORDER, outline="black")
        
        # Battery LED
        c.create_oval(bezel_x + 10, bezel_y + 100, bezel_x + 20, bezel_y + 110, fill="red", outline="red")
        c.create_text(bezel_x + 35, bezel_y + 105, text="BATTERY", font=("Arial", 6), fill="black")

        # 3. LCD Screen Area
        self.screen_offset_x = bezel_x + (bezel_w - SCREEN_WIDTH) // 2
        self.screen_offset_y = bezel_y + 30
        
        c.create_rectangle(
            self.screen_offset_x, self.screen_offset_y,
            self.screen_offset_x + SCREEN_WIDTH, self.screen_offset_y + SCREEN_HEIGHT,
            fill=COLOR_GB_LIGHTEST, outline=COLOR_GB_DARKEST, width=3, tags="screen_bg"
        )

        # 4. Logos
        c.create_text(w//2, bezel_y + bezel_h - 20, text="Nintendo GAMEBOY", font=("Arial", 10, "bold", "italic"), fill="#303080")

        # 5. Controls
        dpad_center_y = bezel_y + bezel_h + 60
        dpad_x = 90
        d_size = 30
        
        # D-Pad
        c.create_rectangle(dpad_x - d_size, dpad_center_y, dpad_x + d_size*2, dpad_center_y + d_size, fill=COLOR_BUTTON_DPAD, outline="black")
        c.create_rectangle(dpad_x, dpad_center_y - d_size, dpad_x + d_size, dpad_center_y + d_size*2, fill=COLOR_BUTTON_DPAD, outline="black")
        c.create_oval(dpad_x + 2, dpad_center_y + 2, dpad_x + d_size - 2, dpad_center_y + d_size - 2, fill="#333", outline="")

        # A/B Buttons
        btn_y = dpad_center_y + 10
        btn_a_x = w - 70
        btn_b_x = w - 120
        c.create_oval(btn_a_x, btn_y, btn_a_x+40, btn_y+40, fill=COLOR_BUTTON_AB, outline="black")
        c.create_text(btn_a_x+20, btn_y+55, text="A", font=("Arial", 12, "bold"), fill="#303080")
        c.create_oval(btn_b_x, btn_y+20, btn_b_x+40, btn_y+60, fill=COLOR_BUTTON_AB, outline="black")
        c.create_text(btn_b_x+20, btn_y+75, text="B", font=("Arial", 12, "bold"), fill="#303080")

        # Start/Select
        ss_y = h - 80
        ss_w, ss_h = 50, 15
        c.create_rectangle(140, ss_y, 140+ss_w, ss_y+ss_h, fill=COLOR_BUTTON_SS, outline="black") 
        c.create_text(165, ss_y+25, text="SELECT", font=("Arial", 8, "bold"), fill="#303080")
        c.create_rectangle(210, ss_y, 210+ss_w, ss_y+ss_h, fill=COLOR_BUTTON_SS, outline="black")
        c.create_text(235, ss_y+25, text="START", font=("Arial", 8, "bold"), fill="#303080")

    def setup_bindings(self):
        # Keyboard bindings
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        
        # Mouse bindings (Clickable buttons)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        print("Controls:\nArrow Keys: D-Pad\nZ or A: A Button (Confirm)\nX or B: B Button (Back)\nEnter: Start\nShift: Select\n*You can also click the buttons with your mouse!*")

    def on_key_press(self, event):
        k = event.keysym.upper()
        if k == "UP": self.keys["UP"] = True
        elif k == "DOWN": self.keys["DOWN"] = True
        elif k == "LEFT": self.keys["LEFT"] = True
        elif k == "RIGHT": self.keys["RIGHT"] = True
        elif k == "Z" or k == "A": self.keys["A"] = True
        elif k == "X" or k == "BACKSPACE" or k == "B": self.keys["B"] = True
        elif k == "RETURN": self.keys["START"] = True
        elif k == "SHIFT_L" or k == "SHIFT_R": self.keys["SELECT"] = True

    def on_key_release(self, event):
        k = event.keysym.upper()
        if k == "UP": self.keys["UP"] = False
        elif k == "DOWN": self.keys["DOWN"] = False
        elif k == "LEFT": self.keys["LEFT"] = False
        elif k == "RIGHT": self.keys["RIGHT"] = False
        elif k == "Z" or k == "A": self.keys["A"] = False
        elif k == "X" or k == "BACKSPACE" or k == "B": self.keys["B"] = False
        elif k == "RETURN": self.keys["START"] = False
        elif k == "SHIFT_L" or k == "SHIFT_R": self.keys["SELECT"] = False

    def get_button_at_pos(self, x, y):
        """Hitbox detection for on-screen buttons."""
        # D-Pad (Center around 90, 458)
        if 90 <= x <= 120 and 428 <= y < 458: return "UP"
        if 90 <= x <= 120 and 488 < y <= 518: return "DOWN"
        if 60 <= x < 90 and 458 <= y <= 488: return "LEFT"
        if 120 < x <= 150 and 458 <= y <= 488: return "RIGHT"
        if 90 <= x <= 120 and 458 <= y <= 488: return None # Deadzone center
        
        # A Button (330, 468, 40x40)
        if 330 <= x <= 370 and 468 <= y <= 508: return "A"
        
        # B Button (280, 488, 40x40)
        if 280 <= x <= 320 and 488 <= y <= 528: return "B"
        
        # Select (140, 570, 50x15)
        if 140 <= x <= 190 and 570 <= y <= 585: return "SELECT"
        
        # Start (210, 570, 50x15)
        if 210 <= x <= 260 and 570 <= y <= 585: return "START"
        
        return None

    def on_mouse_down(self, event):
        btn = self.get_button_at_pos(event.x, event.y)
        if btn:
            self.keys[btn] = True
            self.mouse_pressed_btn = btn

    def on_mouse_up(self, event):
        if self.mouse_pressed_btn:
            self.keys[self.mouse_pressed_btn] = False
            self.mouse_pressed_btn = None

    def is_pressed(self, key):
        return self.keys[key] and not self.prev_keys[key]

    def beep(self):
        self.root.bell()

    # --- Snake Logic ---
    def reset_snake(self):
        self.snake = [(5, 5), (4, 5), (3, 5)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.game_over = False
        self.score = 0
        self.spawn_food()
        self.game_running = False

    def spawn_food(self):
        while True:
            x = random.randint(0, GRID_W - 1)
            y = random.randint(0, GRID_H - 1)
            if (x, y) not in self.snake:
                self.food = (x, y)
                break

    def update_snake_logic(self):
        if not self.game_running or self.game_over: return
        
        self.direction = self.next_direction
        hx, hy = self.snake[0]
        dx, dy = self.direction
        nx, ny = hx + dx, hy + dy

        if nx < 0 or nx >= GRID_W or ny < 0 or ny >= GRID_H or (nx, ny) in self.snake:
            self.game_over = True
            self.beep()
            return

        self.snake.insert(0, (nx, ny))
        if (nx, ny) == self.food:
            self.score += 10
            self.beep()
            self.spawn_food()
        else:
            self.snake.pop()

    # --- Input Handling ---
    def handle_input(self):
        if self.is_pressed("START"):
            # Universal "Home" button
            self.current_state = STATE_MENU
            self.beep()
            return

        if self.current_state == STATE_MENU:
            if self.is_pressed("UP"):
                self.menu_index = (self.menu_index - 1) % len(self.menu_items)
            elif self.is_pressed("DOWN"):
                self.menu_index = (self.menu_index + 1) % len(self.menu_items)
            elif self.is_pressed("A"):
                self.beep()
                selected = self.menu_items[self.menu_index]
                if selected == "SNAKE":
                    self.current_state = STATE_SNAKE
                    self.reset_snake()
                elif selected == "CLOCK":
                    self.current_state = STATE_CLOCK
                elif selected == "NOTES":
                    self.current_state = STATE_NOTES
                elif selected == "CALC":
                    self.current_state = STATE_CALC

        elif self.current_state == STATE_SNAKE:
            # Game Start
            if not self.game_running and self.is_pressed("A"):
                self.game_running = True
                self.game_over = False
                self.reset_snake()
                self.game_running = True
            
            # Direction
            dx, dy = self.direction
            if self.keys["UP"] and dy == 0: self.next_direction = (0, -1)
            elif self.keys["DOWN"] and dy == 0: self.next_direction = (0, 1)
            elif self.keys["LEFT"] and dx == 0: self.next_direction = (-1, 0)
            elif self.keys["RIGHT"] and dx == 0: self.next_direction = (1, 0)

        elif self.current_state == STATE_CLOCK:
            if self.is_pressed("B"):
                self.current_state = STATE_MENU

        elif self.current_state == STATE_NOTES:
            # Typewriter style: Up/Down cycles char, A writes, B deletes
            if self.is_pressed("UP"):
                self.note_char_idx = (self.note_char_idx + 1) % len(self.CHAR_SET)
            elif self.is_pressed("DOWN"):
                self.note_char_idx = (self.note_char_idx - 1) % len(self.CHAR_SET)
            elif self.is_pressed("A"): # Add char
                self.note_content += self.CHAR_SET[self.note_char_idx]
                self.beep()
            elif self.is_pressed("B"): # Backspace
                self.note_content = self.note_content[:-1]
                self.beep()

        elif self.current_state == STATE_CALC:
            # Grid Navigation
            r, c = divmod(self.calc_cursor, 4)
            if self.is_pressed("RIGHT"): c = (c + 1) % 4
            elif self.is_pressed("LEFT"): c = (c - 1) % 4
            elif self.is_pressed("UP"): r = (r - 1) % 4
            elif self.is_pressed("DOWN"): r = (r + 1) % 4
            self.calc_cursor = r * 4 + c
            
            if self.is_pressed("A"):
                self.beep()
                char = self.calc_buttons[self.calc_cursor]
                if char in "0123456789":
                    if self.calc_new_entry:
                        self.calc_val = char
                        self.calc_new_entry = False
                    else:
                        if len(self.calc_val) < 8: # Limit length
                            self.calc_val += char
                elif char == "C":
                    self.calc_val = "0"
                    self.calc_left_op = 0
                    self.calc_op = None
                    self.calc_new_entry = True
                elif char in "+-*/":
                    self.calc_left_op = float(self.calc_val)
                    self.calc_op = char
                    self.calc_new_entry = True
                elif char == "=":
                    if self.calc_op:
                        right = float(self.calc_val)
                        res = 0
                        if self.calc_op == "+": res = self.calc_left_op + right
                        elif self.calc_op == "-": res = self.calc_left_op - right
                        elif self.calc_op == "*": res = self.calc_left_op * right
                        elif self.calc_op == "/": 
                            res = self.calc_left_op / right if right != 0 else 0
                        
                        # Format result
                        if res.is_integer():
                            self.calc_val = str(int(res))
                        else:
                            self.calc_val = str(round(res, 5))
                        self.calc_op = None
                        self.calc_new_entry = True

    # --- Rendering ---
    def render_screen(self):
        self.canvas.delete("game_obj")
        ox, oy = self.screen_offset_x, self.screen_offset_y

        # Global Status Bar (Time)
        now = datetime.datetime.now().strftime("%H:%M")
        self.draw_pixel_text(now, ox + SCREEN_WIDTH - 50, oy + SCREEN_HEIGHT - 15, 1)

        if self.current_state == STATE_MENU:
            self.draw_pixel_text("- MAIN MENU -", ox + 10, oy + 10, 2)
            for i, item in enumerate(self.menu_items):
                prefix = "> " if i == self.menu_index else "  "
                self.draw_pixel_text(prefix + item, ox + 20, oy + 40 + (i*20), 2)
            self.draw_pixel_text("A: SELECT", ox + 10, oy + SCREEN_HEIGHT - 30, 1)

        elif self.current_state == STATE_SNAKE:
            if not self.game_running:
                self.draw_pixel_text("SNAKE", ox + 40, oy + 40, 4)
                self.draw_pixel_text("PRESS A", ox + 40, oy + 80, 2)
                return
            if self.game_over:
                self.draw_pixel_text("GAME OVER", ox + 30, oy + 40, 3)
                self.draw_pixel_text(f"SCORE: {self.score}", ox + 40, oy + 80, 2)
                return
            
            # Draw Snake Game
            fx, fy = self.food
            self.canvas.create_oval(ox + fx*GRID_SIZE, oy + fy*GRID_SIZE, ox + (fx+1)*GRID_SIZE, oy + (fy+1)*GRID_SIZE, fill=COLOR_GB_DARKEST, tags="game_obj")
            for x, y in self.snake:
                self.canvas.create_rectangle(ox + x*GRID_SIZE, oy + y*GRID_SIZE, ox + (x+1)*GRID_SIZE, oy + (y+1)*GRID_SIZE, fill=COLOR_GB_DARKEST, outline=COLOR_GB_LIGHT, width=1, tags="game_obj")
            self.draw_pixel_text(str(self.score), ox+5, oy+5, 1)

        elif self.current_state == STATE_CLOCK:
            full_time = datetime.datetime.now().strftime("%H:%M:%S")
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            self.draw_pixel_text("CLOCK", ox + 50, oy + 10, 2)
            self.draw_pixel_text(full_time, ox + 10, oy + 50, 4)
            self.draw_pixel_text(date_str, ox + 20, oy + 90, 2)
            self.draw_pixel_text("B: BACK", ox + 10, oy + SCREEN_HEIGHT - 30, 1)

        elif self.current_state == STATE_NOTES:
            self.draw_pixel_text("NOTEPAD", ox + 40, oy + 5, 2)
            # Draw content (simple wrap)
            lines = [self.note_content[i:i+18] for i in range(0, len(self.note_content), 18)]
            for i, line in enumerate(lines[-6:]): # Show last 6 lines
                self.draw_pixel_text(line, ox + 5, oy + 30 + (i*15), 2)
            
            # Draw "Keyboard" area
            char = self.CHAR_SET[self.note_char_idx]
            self.draw_pixel_text(f"TYPE: [{char}]", ox + 5, oy + SCREEN_HEIGHT - 40, 2)
            self.draw_pixel_text("A:Add B:Del ^v:Chr", ox + 5, oy + SCREEN_HEIGHT - 20, 1)

        elif self.current_state == STATE_CALC:
            # Display
            self.canvas.create_rectangle(ox+5, oy+5, ox+SCREEN_WIDTH-5, oy+35, fill=COLOR_GB_LIGHT, outline=COLOR_GB_DARKEST, tags="game_obj")
            self.draw_pixel_text(self.calc_val[-10:], ox+10, oy+10, 3) # Right align approx
            
            # Grid
            start_y = 45
            w = (SCREEN_WIDTH - 10) / 4
            h = (SCREEN_HEIGHT - 55) / 4
            for i, btn in enumerate(self.calc_buttons):
                r, c = divmod(i, 4)
                bx = ox + 5 + c*w
                by = oy + start_y + r*h
                
                # Highlight cursor
                fill = COLOR_GB_DARK if i == self.calc_cursor else COLOR_GB_LIGHT
                text_col = "white" if i == self.calc_cursor else COLOR_GB_DARKEST
                
                self.canvas.create_rectangle(bx, by, bx+w-2, by+h-2, fill=fill, outline=COLOR_GB_DARKEST, tags="game_obj")
                self.canvas.create_text(bx+w/2, by+h/2, text=btn, font=("Courier", 12, "bold"), fill=text_col, tags="game_obj")

    def draw_pixel_text(self, text, x, y, size):
        self.canvas.create_text(x, y, text=text, anchor="nw", font=("Courier", int(size*5), "bold"), fill=COLOR_GB_DARKEST, tags="game_obj")

    def game_loop(self):
        start_time = time.time()

        # Update Keys (Store previous frame for single-press detection)
        self.handle_input()
        self.prev_keys = self.keys.copy()

        # Game Logic
        self.speed_counter += 1
        threshold = self.update_rate
        if self.keys["A"]: threshold //= 2
        
        if self.current_state == STATE_SNAKE and self.speed_counter >= threshold:
            self.update_snake_logic()
            self.speed_counter = 0

        self.render_screen()

        elapsed = (time.time() - start_time) * 1000
        wait = int(FRAME_DELAY - elapsed)
        if wait < 1: wait = 1
        self.root.after(wait, self.game_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = GameboySimulator(root)
    # Center window
    w, h = 420, 700
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = (ws/2) - (w/2)
    y = (hs/2) - (h/2)
    root.geometry('%dx%d+%d+%d' % (w, h, x, y))
    
    root.mainloop()
