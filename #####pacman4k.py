import pygame
import sys
import random
import math
import array
import struct

# --- Constants ---
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 400
FPS = 60
BLOCK_SIZE = 20
GRID_WIDTH = SCREEN_WIDTH // BLOCK_SIZE
GRID_HEIGHT = SCREEN_HEIGHT // BLOCK_SIZE

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)
PINK = (255, 182, 193)
CYAN = (0, 255, 255)
ORANGE = (255, 165, 0)
NAMCO_RED = (228, 0, 43)
PURPLE = (147, 112, 219) # Frightened ghost

# Game States
STATE_MENU = 0
STATE_PLAYING = 1
STATE_HOW_TO = 2
STATE_CREDITS = 3
STATE_GAMEOVER = 4
STATE_KILL_SCREEN = 5

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
STOP = (0, 0)

# Ghost Modes
MODE_SCATTER = 0
MODE_CHASE = 1
MODE_FRIGHTENED = 2

# Sound Manager
class SoundManager:
    def __init__(self):
        self.sounds = {}
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.generate_sounds()
            self.enabled = True
        except Exception as e:
            print(f"Sound initialization failed: {e}")
            self.enabled = False

    def generate_sounds(self):
        # Generate synthetic chiptune sounds
        self.sounds['waka'] = self.make_sound(400, 0.1, 0.1, 'square')
        self.sounds['eat_ghost'] = self.make_sound(800, 0.1, 0.2, 'square')
        self.sounds['death'] = self.make_slide(1000, 100, 1.0, 0.2)
        self.sounds['start'] = self.make_arpeggio([440, 554, 659, 880], 0.1, 0.2)
        self.sounds['power'] = self.make_sound(300, 0.5, 0.1, 'sine')

    def make_sound(self, freq, duration, vol, type='square'):
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = float(i) / sample_rate
            if type == 'square':
                val = 1 if (int(t * freq * 2) % 2) == 0 else -1
            else:
                val = math.sin(2 * math.pi * freq * t)
            buf.append(int(val * vol * 32767))
        return pygame.mixer.Sound(buffer=buf)

    def make_slide(self, start_freq, end_freq, duration, vol):
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = float(i) / sample_rate
            progress = i / n_samples
            freq = start_freq + (end_freq - start_freq) * progress
            val = 1 if (int(t * freq * 2) % 2) == 0 else -1
            buf.append(int(val * vol * 32767))
        return pygame.mixer.Sound(buffer=buf)
        
    def make_arpeggio(self, freqs, note_len, vol):
        sample_rate = 44100
        total_samples = int(sample_rate * note_len * len(freqs))
        buf = array.array('h')
        samples_per_note = int(sample_rate * note_len)
        
        for i in range(total_samples):
            note_idx = (i // samples_per_note) % len(freqs)
            freq = freqs[note_idx]
            t = float(i) / sample_rate
            val = 1 if (int(t * freq * 2) % 2) == 0 else -1
            buf.append(int(val * vol * 32767))
        return pygame.mixer.Sound(buffer=buf)

    def play(self, name):
        if self.enabled and name in self.sounds:
            self.sounds[name].play()

# Map Layout (0: Empty, 1: Wall, 2: Pellet, 3: Power Pellet)
def generate_map():
    layout = []
    for y in range(GRID_HEIGHT):
        row = []
        for x in range(GRID_WIDTH):
            if x == 0 or x == GRID_WIDTH - 1 or y == 0 or y == GRID_HEIGHT - 1:
                row.append(1) # Border
            elif x % 4 == 0 and y % 4 == 0:
                row.append(1) # Pillars
            elif (x == 1 or x == GRID_WIDTH - 2) and (y == 1 or y == GRID_HEIGHT - 2):
                row.append(3) # Power Pellet
            else:
                row.append(2) # Pellet
        layout.append(row)
    
    # Clear center for ghost house
    cx, cy = GRID_WIDTH // 2, GRID_HEIGHT // 2
    for y in range(cy - 2, cy + 2):
        for x in range(cx - 3, cx + 3):
            layout[y][x] = 0
    
    # Ghost house door
    layout[cy - 2][cx] = 0
    
    return layout

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("PAC-MAN HDR 4K - BANDAI NAMCO")
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("Arial", 48, bold=True)
        self.font_med = pygame.font.SysFont("Arial", 32, bold=True)
        self.font_small = pygame.font.SysFont("Courier New", 20)
        
        self.sfx = SoundManager()
        self.state = STATE_MENU
        self.menu_options = ["PLAY GAME", "HOW TO PLAY", "CREDITS", "EXIT GAME"]
        self.selected_option = 0
        
        self.reset_game()
        
    def reset_game(self):
        self.score = 0
        self.level = 1
        self.lives = 3
        self.grid = generate_map()
        self.pacman = Entity(GRID_WIDTH // 2, GRID_HEIGHT // 2 + 4, YELLOW, is_pacman=True)
        self.ghosts = [
            Ghost(GRID_WIDTH // 2, GRID_HEIGHT // 2 - 2, RED, "blinky"),
            Ghost(GRID_WIDTH // 2 - 1, GRID_HEIGHT // 2, PINK, "pinky"),
            Ghost(GRID_WIDTH // 2 + 1, GRID_HEIGHT // 2, CYAN, "inky"),
            Ghost(GRID_WIDTH // 2, GRID_HEIGHT // 2, ORANGE, "clyde")
        ]
        self.mode_timer = 0
        self.ghost_mode = MODE_SCATTER
        self.frightened_timer = 0

    def run(self):
        while True:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.KEYDOWN:
                if self.state == STATE_MENU:
                    if event.key == pygame.K_UP:
                        self.selected_option = (self.selected_option - 1) % len(self.menu_options)
                    elif event.key == pygame.K_DOWN:
                        self.selected_option = (self.selected_option + 1) % len(self.menu_options)
                    elif event.key == pygame.K_RETURN:
                        self.execute_menu_action()
                        
                elif self.state == STATE_PLAYING:
                    if event.key == pygame.K_UP: self.pacman.next_dir = UP
                    elif event.key == pygame.K_DOWN: self.pacman.next_dir = DOWN
                    elif event.key == pygame.K_LEFT: self.pacman.next_dir = LEFT
                    elif event.key == pygame.K_RIGHT: self.pacman.next_dir = RIGHT
                    elif event.key == pygame.K_ESCAPE: self.state = STATE_MENU
                    
                    if event.key == pygame.K_k:
                        self.level = 255
                        self.next_level()

                elif self.state in [STATE_HOW_TO, STATE_CREDITS, STATE_GAMEOVER, STATE_KILL_SCREEN]:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN:
                        self.state = STATE_MENU

    def execute_menu_action(self):
        if self.selected_option == 0: # PLAY GAME
            self.reset_game()
            self.state = STATE_PLAYING
            self.sfx.play('start')
        elif self.selected_option == 1: # HOW TO PLAY
            self.state = STATE_HOW_TO
        elif self.selected_option == 2: # CREDITS
            self.state = STATE_CREDITS
        elif self.selected_option == 3: # EXIT
            pygame.quit()
            sys.exit()

    def update(self):
        if self.state == STATE_PLAYING:
            # Ghost Mode Logic (Scatter/Chase alternation)
            if self.ghost_mode != MODE_FRIGHTENED:
                self.mode_timer += 1
                if self.mode_timer > 600: # 10 seconds per mode swap approx
                    self.ghost_mode = MODE_CHASE if self.ghost_mode == MODE_SCATTER else MODE_SCATTER
                    self.mode_timer = 0
                    # Reverse ghost directions on mode switch
                    for ghost in self.ghosts:
                        ghost.reverse()
            else:
                self.frightened_timer -= 1
                if self.frightened_timer <= 0:
                    self.ghost_mode = MODE_CHASE
                    self.mode_timer = 0

            self.pacman.update(self.grid)
            
            # Update Ghosts
            blinky = self.ghosts[0]
            for ghost in self.ghosts:
                ghost.update_ai(self.grid, self.pacman, blinky, self.ghost_mode)
                
                # Collision Check
                pac_rect = pygame.Rect(self.pacman.x * BLOCK_SIZE + 4, self.pacman.y * BLOCK_SIZE + 4, 12, 12)
                ghost_rect = pygame.Rect(ghost.x * BLOCK_SIZE + 4, ghost.y * BLOCK_SIZE + 4, 12, 12)
                
                if pac_rect.colliderect(ghost_rect):
                    if self.ghost_mode == MODE_FRIGHTENED:
                        # Eat Ghost
                        ghost.reset_pos()
                        self.score += 200
                        self.sfx.play('eat_ghost')
                    else:
                        # Death
                        self.lives -= 1
                        self.sfx.play('death')
                        self.pacman.reset_pos()
                        for g in self.ghosts: g.reset_pos()
                        pygame.time.delay(1000)
                        if self.lives <= 0:
                            self.state = STATE_GAMEOVER
            
            # Eat pellets
            px, py = int(self.pacman.x + 0.5), int(self.pacman.y + 0.5)
            if self.grid[py][px] == 2:
                self.grid[py][px] = 0
                self.score += 10
                self.sfx.play('waka')
            elif self.grid[py][px] == 3: # Power Pellet
                self.grid[py][px] = 0
                self.score += 50
                self.ghost_mode = MODE_FRIGHTENED
                self.frightened_timer = 600 # 10 seconds
                self.sfx.play('power')
                
            # Check level complete
            if not any(2 in row for row in self.grid) and not any(3 in row for row in self.grid):
                self.next_level()
    
    def next_level(self):
        self.level += 1
        if self.level >= 256:
            self.state = STATE_KILL_SCREEN
        else:
            self.grid = generate_map()
            self.pacman.reset_pos()
            for ghost in self.ghosts:
                ghost.reset_pos()

    def draw(self):
        self.screen.fill(BLACK)
        
        if self.state == STATE_MENU:
            self.draw_menu()
        elif self.state == STATE_PLAYING:
            self.draw_game()
        elif self.state == STATE_HOW_TO:
            self.draw_text_screen("HOW TO PLAY", ["Arrow Keys to Move", "Eat all pellets", "Power Pellets = Eat Ghosts", "REAL SFX: ON", "ENGINE: COMPLETE"])
        elif self.state == STATE_CREDITS:
            self.draw_text_screen("CREDITS", ["Created by: USER & TRAE", "BANDAI NAMCO (C) 1980", "AC COMPUTING", "Engine: KOOPA ENGINE 4K"])
        elif self.state == STATE_GAMEOVER:
            self.draw_text_screen("GAME OVER", [f"FINAL SCORE: {self.score}", "Press ENTER to Main Menu"])
        elif self.state == STATE_KILL_SCREEN:
            self.draw_kill_screen()
            
        pygame.display.flip()

    def draw_menu(self):
        title = self.font_big.render("PAC-MAN HDR 4K", True, YELLOW)
        subtitle = self.font_med.render("BANDAI NAMCO", True, NAMCO_RED)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 50))
        self.screen.blit(subtitle, (SCREEN_WIDTH//2 - subtitle.get_width()//2, 110))
        
        for i, option in enumerate(self.menu_options):
            color = WHITE if i == self.selected_option else (100, 100, 100)
            prefix = "> " if i == self.selected_option else "  "
            text = self.font_med.render(prefix + option, True, color)
            self.screen.blit(text, (SCREEN_WIDTH//2 - 100, 200 + i * 40))
            
        footer = self.font_small.render("REAL SFX | FULL ENGINE", True, CYAN)
        self.screen.blit(footer, (SCREEN_WIDTH//2 - footer.get_width()//2, 360))

    def draw_game(self):
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x] == 1:
                    pygame.draw.rect(self.screen, BLUE, (x*BLOCK_SIZE, y*BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 1)
                elif self.grid[y][x] == 2:
                    pygame.draw.circle(self.screen, PINK, (x*BLOCK_SIZE + BLOCK_SIZE//2, y*BLOCK_SIZE + BLOCK_SIZE//2), 2)
                elif self.grid[y][x] == 3:
                    if (pygame.time.get_ticks() // 200) % 2 == 0: # Blink
                        pygame.draw.circle(self.screen, WHITE, (x*BLOCK_SIZE + BLOCK_SIZE//2, y*BLOCK_SIZE + BLOCK_SIZE//2), 6)
        
        self.pacman.draw(self.screen)
        for ghost in self.ghosts:
            ghost.draw(self.screen, self.ghost_mode)
            
        score_text = self.font_small.render(f"SCORE: {self.score}", True, WHITE)
        level_text = self.font_small.render(f"LVL: {self.level}", True, WHITE)
        lives_text = self.font_small.render(f"LIVES: {self.lives}", True, WHITE)
        self.screen.blit(score_text, (10, 5))
        self.screen.blit(level_text, (SCREEN_WIDTH//2 - 20, 5))
        self.screen.blit(lives_text, (SCREEN_WIDTH - 100, 5))

    def draw_text_screen(self, title_str, lines):
        title = self.font_big.render(title_str, True, YELLOW)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 50))
        for i, line in enumerate(lines):
            text = self.font_small.render(line, True, WHITE)
            self.screen.blit(text, (SCREEN_WIDTH//2 - text.get_width()//2, 150 + i * 30))

    def draw_kill_screen(self):
        self.screen.fill(BLACK)
        for _ in range(100):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            w = random.randint(10, 50)
            h = random.randint(10, 50)
            color = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
            pygame.draw.rect(self.screen, color, (x, y, w, h))
            char = chr(random.randint(33, 126))
            text = self.font_small.render(char, True, WHITE)
            self.screen.blit(text, (random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT)))
        msg = self.font_big.render("LEVEL 256 FATAL ERROR", True, RED)
        self.screen.blit(msg, (SCREEN_WIDTH//2 - msg.get_width()//2, SCREEN_HEIGHT//2))

class Entity:
    def __init__(self, x, y, color, is_pacman=False):
        self.start_x = x
        self.start_y = y
        self.x = x
        self.y = y
        self.color = color
        self.is_pacman = is_pacman
        self.dir = STOP
        self.next_dir = STOP
        self.speed = 0.15 if is_pacman else 0.1
        self.move_counter = 0

    def reset_pos(self):
        self.x = self.start_x
        self.y = self.start_y
        self.dir = STOP
        self.next_dir = STOP

    def update(self, grid):
        if self.next_dir != STOP:
            # Only turn if centered on tile
            if abs(self.x - round(self.x)) < 0.1 and abs(self.y - round(self.y)) < 0.1:
                check_x = int(round(self.x) + self.next_dir[0])
                check_y = int(round(self.y) + self.next_dir[1])
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    if grid[check_y][check_x] != 1:
                        self.x = round(self.x) # Snap to grid
                        self.y = round(self.y)
                        self.dir = self.next_dir
                        self.next_dir = STOP

        if self.dir != STOP:
            new_x = self.x + self.dir[0] * self.speed
            new_y = self.y + self.dir[1] * self.speed
            
            center_x = int(new_x + 0.5)
            center_y = int(new_y + 0.5)
            
            if 0 <= center_x < GRID_WIDTH and 0 <= center_y < GRID_HEIGHT:
                if grid[center_y][center_x] != 1:
                    self.x = new_x
                    self.y = new_y
                else:
                    self.x = round(self.x)
                    self.y = round(self.y)
            else:
                self.x = new_x % GRID_WIDTH
                self.y = new_y % GRID_HEIGHT

    def draw(self, screen):
        px = int(self.x * BLOCK_SIZE + BLOCK_SIZE // 2)
        py = int(self.y * BLOCK_SIZE + BLOCK_SIZE // 2)
        radius = BLOCK_SIZE // 2 - 2
        pygame.draw.circle(screen, self.color, (px, py), radius)

class Ghost(Entity):
    def __init__(self, x, y, color, name):
        super().__init__(x, y, color, is_pacman=False)
        self.name = name
        self.speed = 0.1
        self.dir = LEFT # Initial move
        
    def reverse(self):
        self.dir = (-self.dir[0], -self.dir[1])
        
    def update_ai(self, grid, pacman, blinky, mode):
        # Move forward
        new_x = self.x + self.dir[0] * self.speed
        new_y = self.y + self.dir[1] * self.speed
        
        # Check if centered on tile (decision point)
        if abs(self.x - round(self.x)) < 0.1 and abs(self.y - round(self.y)) < 0.1:
            self.x = round(self.x)
            self.y = round(self.y)
            
            # Choose next direction
            possible_dirs = []
            for d in [UP, DOWN, LEFT, RIGHT]:
                # Don't reverse immediately
                if d == (-self.dir[0], -self.dir[1]): continue
                
                check_x = int(self.x + d[0])
                check_y = int(self.y + d[1])
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    if grid[check_y][check_x] != 1:
                        possible_dirs.append(d)
            
            if possible_dirs:
                if mode == MODE_FRIGHTENED:
                    self.dir = random.choice(possible_dirs)
                else:
                    target = self.get_target(pacman, blinky, mode)
                    best_dir = possible_dirs[0]
                    min_dist = float('inf')
                    
                    for d in possible_dirs:
                        tx = self.x + d[0]
                        ty = self.y + d[1]
                        dist = (tx - target[0])**2 + (ty - target[1])**2
                        if dist < min_dist:
                            min_dist = dist
                            best_dir = d
                    self.dir = best_dir
            else:
                 # Dead end (shouldn't happen in standard maze)
                 self.reverse()
                 
            # Apply move
            self.x += self.dir[0] * self.speed
            self.y += self.dir[1] * self.speed
        else:
            # Continue moving
            self.x = new_x
            self.y = new_y
            
            # Warp
            self.x = self.x % GRID_WIDTH
            self.y = self.y % GRID_HEIGHT

    def get_target(self, pacman, blinky, mode):
        if mode == MODE_SCATTER:
            # Corners
            if self.name == "blinky": return (GRID_WIDTH-2, -2)
            if self.name == "pinky": return (2, -2)
            if self.name == "inky": return (GRID_WIDTH-1, GRID_HEIGHT-1)
            if self.name == "clyde": return (0, GRID_HEIGHT-1)
        
        # Chase Mode
        px, py = pacman.x, pacman.y
        pd_x, pd_y = pacman.dir
        
        if self.name == "blinky":
            return (px, py)
        elif self.name == "pinky":
            return (px + pd_x * 4, py + pd_y * 4)
        elif self.name == "inky":
            vec_x = (px + pd_x * 2) - blinky.x
            vec_y = (py + pd_y * 2) - blinky.y
            return (blinky.x + vec_x * 2, blinky.y + vec_y * 2)
        elif self.name == "clyde":
            dist = (self.x - px)**2 + (self.y - py)**2
            if dist > 64: # 8 tiles squared
                return (px, py)
            else:
                return (0, GRID_HEIGHT-1) # Scatter target
        return (px, py)

    def draw(self, screen, mode):
        px = int(self.x * BLOCK_SIZE + BLOCK_SIZE // 2)
        py = int(self.y * BLOCK_SIZE + BLOCK_SIZE // 2)
        radius = BLOCK_SIZE // 2 - 2
        
        color = PURPLE if mode == MODE_FRIGHTENED else self.color
        pygame.draw.rect(screen, color, (px - radius, py - radius, radius*2, radius*2))
        
        # Eyes
        pygame.draw.circle(screen, WHITE, (px - 4, py - 2), 3)
        pygame.draw.circle(screen, WHITE, (px + 4, py - 2), 3)
        pygame.draw.circle(screen, BLUE, (px - 4 + self.dir[0]*2, py - 2 + self.dir[1]*2), 1)
        pygame.draw.circle(screen, BLUE, (px + 4 + self.dir[0]*2, py - 2 + self.dir[1]*2), 1)

if __name__ == "__main__":
    game = Game()
    game.run()
