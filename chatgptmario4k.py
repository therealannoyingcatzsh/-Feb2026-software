
import sys, random, math
import pygame

# Ultra Platformer 1.0 (original demo) - 60 FPS fixed-step, 600x400 window.
# NOTE: This is NOT a 1:1 clone of any commercial game; all levels are procedural & original.

WINDOW_W, WINDOW_H = 600, 400
LOGICAL_W, LOGICAL_H = 300, 200   # rendered to a smaller surface then scaled 2x -> 600x400 (pixel-crisp)
SCALE = 2

FPS = 60
DT = 1.0 / FPS

TILE = 10  # logical pixels per tile
ROWS = LOGICAL_H // TILE  # 20
COLS_VIEW = LOGICAL_W // TILE  # 30

# Physics (tweak these to taste)
GRAVITY = 1400.0             # px/s^2
WALK_ACCEL = 1100.0          # px/s^2
RUN_ACCEL = 1500.0           # px/s^2
GROUND_FRICTION = 1700.0     # px/s^2
AIR_FRICTION = 200.0         # px/s^2

MAX_WALK = 120.0             # px/s
MAX_RUN = 180.0              # px/s

JUMP_VEL = -420.0            # px/s
RUN_JUMP_BONUS = -40.0       # px/s (extra jump when running)

ENEMY_SPEED = 60.0           # px/s

# Tiles
EMPTY = 0
GROUND = 1
BRICK = 2
PLATFORM = 3
GOAL = 4  # non-solid; touching completes stage

SOLID_TILES = {GROUND, BRICK, PLATFORM}

def clamp(x, a, b):
    return a if x < a else b if x > b else x

def sign(x):
    return -1 if x < 0 else 1 if x > 0 else 0

class Player:
    def __init__(self, x, y):
        self.w = 8
        self.h = 14
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.dead_timer = 0.0
        self.facing = 1  # -1 left, +1 right

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

class Walker:
    def __init__(self, x, y, direction=-1):
        self.w = 10
        self.h = 10
        self.x = float(x)
        self.y = float(y)
        self.vx = ENEMY_SPEED * direction
        self.vy = 0.0
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

class Stage:
    def __init__(self, world, stage):
        self.world = world
        self.stage = stage
        self.id = f"{world}-{stage}"
        self.height = ROWS
        # Width grows with world/stage a bit, capped for performance.
        base = 170
        self.width = int(clamp(base + world * 8 + stage * 6, 170, 240))  # tiles
        self.grid = [[EMPTY for _ in range(self.width)] for _ in range(self.height)]
        self.walkers = []
        self.goal_x = (self.width - 4) * TILE
        self.spawn_x = 2 * TILE
        self.spawn_y = (self.ground_row() - 3) * TILE
        self._generate()

    def ground_row(self):
        # second-to-last row; falling below LOGICAL_H kills.
        return self.height - 2

    def in_bounds(self, tx, ty):
        return 0 <= tx < self.width and 0 <= ty < self.height

    def tile_at(self, tx, ty):
        if not self.in_bounds(tx, ty):
            return EMPTY
        return self.grid[ty][tx]

    def set_tile(self, tx, ty, t):
        if self.in_bounds(tx, ty):
            self.grid[ty][tx] = t

    def _generate(self):
        rng = random.Random(1337 + self.world * 1000 + self.stage * 97)

        g = self.ground_row()

        # Start with solid ground
        for x in range(self.width):
            self.grid[g][x] = GROUND

        # Carve gaps (pits)
        x = 12
        while x < self.width - 18:
            # Skip a little at the start; later worlds have more pits
            if rng.random() < (0.10 + 0.02 * self.world + 0.01 * self.stage):
                gap = rng.randint(2, 4 + self.world // 2)
                for gx in range(x, min(self.width, x + gap)):
                    self.grid[g][gx] = EMPTY
                x += gap + rng.randint(6, 14)
            else:
                x += rng.randint(6, 12)

        # Add platforms / brick clusters
        for _ in range(35 + self.world * 6):
            px = rng.randint(10, self.width - 15)
            py = rng.choice([g - 3, g - 4, g - 5, g - 6])
            length = rng.randint(2, 7)
            t = rng.choice([BRICK, PLATFORM])
            for i in range(length):
                self.set_tile(px + i, py, t)

        # Add some "columns" (pipes-like but generic)
        for _ in range(5 + self.world // 2):
            cx = rng.randint(18, self.width - 18)
            h = rng.randint(2, 5)
            for k in range(h):
                self.set_tile(cx, g - 1 - k, BRICK)
                self.set_tile(cx + 1, g - 1 - k, BRICK)

        # Stairs near the end (classic platformer trope; original layout)
        stair_base = self.width - 22
        stair_h = 3 + self.world // 2
        for i in range(1, stair_h + 1):
            for k in range(i):
                self.set_tile(stair_base + i, g - 1 - k, BRICK)

        # Goal marker (non-solid column)
        goal_tx = self.width - 4
        for yy in range(g - 7, g):
            if 0 <= yy < self.height:
                self.set_tile(goal_tx, yy, GOAL)
        self.set_tile(goal_tx + 1, g - 1, BRICK)  # small base

        # Enemies
        for _ in range(6 + self.world):
            ex = rng.randint(18, self.width - 28) * TILE
            # only place on solid ground
            if self.grid[g][ex // TILE] == GROUND:
                self.walkers.append(Walker(ex, (g * TILE) - 10, direction=rng.choice([-1, 1])))

    def is_solid_at_pixel(self, px, py):
        tx = int(px) // TILE
        ty = int(py) // TILE
        return self.tile_at(tx, ty) in SOLID_TILES

    def rect_collide_solids(self, rect):
        # iterate tiles overlapped by rect
        left = rect.left // TILE
        right = (rect.right - 1) // TILE
        top = rect.top // TILE
        bottom = (rect.bottom - 1) // TILE
        hits = []
        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                t = self.tile_at(tx, ty)
                if t in SOLID_TILES:
                    hits.append(pygame.Rect(tx * TILE, ty * TILE, TILE, TILE))
        return hits

    def rect_hits_goal(self, rect):
        left = rect.left // TILE
        right = (rect.right - 1) // TILE
        top = rect.top // TILE
        bottom = (rect.bottom - 1) // TILE
        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                if self.tile_at(tx, ty) == GOAL:
                    return True
        # Also treat reaching the far right as completion
        return rect.right >= self.goal_x

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Ultra Platformer 1.0 (Original) — 60 FPS, 600x400")
        self.window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.surface = pygame.Surface((LOGICAL_W, LOGICAL_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 18)

        self.stage_order = [f"{w}-{s}" for w in range(1, 9) for s in range(1, 5)]
        self.stage_index = 0

        self.stage = None
        self.player = None
        self.camera_x = 0.0
        self.message_timer = 0.0
        self.completed = False
        self.complete_timer = 0.0

        self.load_stage(self.stage_order[self.stage_index])

    def parse_stage_id(self, sid):
        w, s = sid.split("-")
        return int(w), int(s)

    def load_stage(self, sid):
        w, s = self.parse_stage_id(sid)
        self.stage = Stage(w, s)
        self.player = Player(self.stage.spawn_x, self.stage.spawn_y)
        self.camera_x = 0.0
        self.completed = False
        self.complete_timer = 0.0

    def restart_stage(self):
        self.load_stage(self.stage_order[self.stage_index])

    def next_stage(self):
        self.stage_index = (self.stage_index + 1) % len(self.stage_order)
        self.load_stage(self.stage_order[self.stage_index])

    def prev_stage(self):
        self.stage_index = (self.stage_index - 1) % len(self.stage_order)
        self.load_stage(self.stage_order[self.stage_index])

    def run(self):
        accumulator = 0.0
        running = True
        while running:
            # Time management
            frame_ms = self.clock.tick(FPS)
            accumulator += frame_ms / 1000.0
            accumulator = min(accumulator, 0.25)  # avoid spiral of death

            # Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.restart_stage()
                    elif event.key == pygame.K_n:
                        self.next_stage()
                    elif event.key == pygame.K_b:
                        self.prev_stage()

            # Fixed-step update
            while accumulator >= DT:
                self.update(DT)
                accumulator -= DT

            self.draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def update(self, dt):
        keys = pygame.key.get_pressed()

        if self.completed:
            self.complete_timer += dt
            if self.complete_timer >= 1.0:
                self.next_stage()
            return

        # Player input
        left = keys[pygame.K_LEFT]
        right = keys[pygame.K_RIGHT]
        run = keys[pygame.K_x] or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        jump_pressed = keys[pygame.K_z] or keys[pygame.K_SPACE]

        accel = RUN_ACCEL if run else WALK_ACCEL
        max_speed = MAX_RUN if run else MAX_WALK

        # Horizontal acceleration / friction
        if left ^ right:
            direction = -1 if left else 1
            self.player.facing = direction
            self.player.vx += direction * accel * dt
        else:
            # friction
            fric = GROUND_FRICTION if self.player.on_ground else AIR_FRICTION
            if abs(self.player.vx) <= fric * dt:
                self.player.vx = 0.0
            else:
                self.player.vx -= sign(self.player.vx) * fric * dt

        self.player.vx = clamp(self.player.vx, -max_speed, max_speed)

        # Jump (edge-triggered)
        if not hasattr(self, "_jump_was_down"):
            self._jump_was_down = False
        if jump_pressed and not self._jump_was_down and self.player.on_ground:
            bonus = RUN_JUMP_BONUS if run else 0.0
            self.player.vy = JUMP_VEL + bonus
            self.player.on_ground = False
        self._jump_was_down = jump_pressed

        # Gravity
        self.player.vy += GRAVITY * dt
        self.player.vy = clamp(self.player.vy, -900.0, 900.0)

        # Move & collide (X then Y)
        self.move_entity(self.player, dt)

        # Death by falling
        if self.player.y > LOGICAL_H + 100:
            self.restart_stage()
            return

        # Update enemies
        for w in self.stage.walkers:
            if not w.alive:
                continue
            w.vy += GRAVITY * dt
            w.vy = clamp(w.vy, -900.0, 900.0)
            self.move_walker(w, dt)

        # Player-enemy interaction
        pr = self.player.rect
        for w in self.stage.walkers:
            if not w.alive:
                continue
            if pr.colliderect(w.rect):
                # Stomp if falling and above enemy
                if self.player.vy > 0 and pr.bottom - w.rect.top < 10:
                    w.alive = False
                    self.player.vy = JUMP_VEL * 0.6
                else:
                    self.restart_stage()
                    return

        # Goal
        if self.stage.rect_hits_goal(self.player.rect):
            self.completed = True
            self.complete_timer = 0.0

        # Camera follow
        stage_px_w = self.stage.width * TILE
        target = self.player.x + self.player.w * 0.5 - LOGICAL_W * 0.4
        self.camera_x = clamp(target, 0.0, max(0.0, stage_px_w - LOGICAL_W))

    def move_entity(self, ent, dt):
        # Horizontal
        ent.x += ent.vx * dt
        rect = ent.rect
        hits = self.stage.rect_collide_solids(rect)
        for tile_rect in hits:
            if ent.vx > 0:
                rect.right = tile_rect.left
                ent.x = rect.x
                ent.vx = 0.0
            elif ent.vx < 0:
                rect.left = tile_rect.right
                ent.x = rect.x
                ent.vx = 0.0

        # Vertical
        ent.y += ent.vy * dt
        rect = ent.rect
        hits = self.stage.rect_collide_solids(rect)
        ent.on_ground = False
        for tile_rect in hits:
            if ent.vy > 0:
                rect.bottom = tile_rect.top
                ent.y = rect.y
                ent.vy = 0.0
                ent.on_ground = True
            elif ent.vy < 0:
                rect.top = tile_rect.bottom
                ent.y = rect.y
                ent.vy = 0.0

    def move_walker(self, w, dt):
        # Horizontal
        w.x += w.vx * dt
        rect = w.rect
        hits = self.stage.rect_collide_solids(rect)
        for tile_rect in hits:
            if w.vx > 0:
                rect.right = tile_rect.left
                w.x = rect.x
                w.vx *= -1
            elif w.vx < 0:
                rect.left = tile_rect.right
                w.x = rect.x
                w.vx *= -1

        # Edge turn-around: if no ground ahead, flip direction
        ahead_x = (rect.centerx + sign(w.vx) * (w.w // 2 + 2))
        foot_y = rect.bottom + 1
        if not self.stage.is_solid_at_pixel(ahead_x, foot_y):
            w.vx *= -1

        # Vertical
        w.y += w.vy * dt
        rect = w.rect
        hits = self.stage.rect_collide_solids(rect)
        for tile_rect in hits:
            if w.vy > 0:
                rect.bottom = tile_rect.top
                w.y = rect.y
                w.vy = 0.0
            elif w.vy < 0:
                rect.top = tile_rect.bottom
                w.y = rect.y
                w.vy = 0.0

    def draw(self):
        # Colors
        SKY = (40, 60, 110)
        GROUND_C = (60, 160, 80)
        BRICK_C = (170, 90, 60)
        PLATFORM_C = (120, 120, 160)
        GOAL_C = (240, 240, 120)
        PLAYER_C = (230, 230, 255)
        ENEMY_C = (255, 140, 140)

        self.surface.fill(SKY)

        # Draw tiles in view
        start_tx = int(self.camera_x) // TILE
        end_tx = min(self.stage.width, start_tx + COLS_VIEW + 2)

        for ty in range(self.stage.height):
            for tx in range(start_tx, end_tx):
                t = self.stage.grid[ty][tx]
                if t == EMPTY:
                    continue
                x = tx * TILE - int(self.camera_x)
                y = ty * TILE
                r = pygame.Rect(x, y, TILE, TILE)
                if t == GROUND:
                    pygame.draw.rect(self.surface, GROUND_C, r)
                elif t == BRICK:
                    pygame.draw.rect(self.surface, BRICK_C, r)
                elif t == PLATFORM:
                    pygame.draw.rect(self.surface, PLATFORM_C, r)
                elif t == GOAL:
                    pygame.draw.rect(self.surface, GOAL_C, r)

        # Draw enemies
        for w in self.stage.walkers:
            if not w.alive:
                continue
            r = w.rect.move(-int(self.camera_x), 0)
            pygame.draw.rect(self.surface, ENEMY_C, r)

        # Draw player
        pr = self.player.rect.move(-int(self.camera_x), 0)
        pygame.draw.rect(self.surface, PLAYER_C, pr)

        # HUD
        sid = self.stage.id
        txt = f"Stage {sid}  |  60 FPS fixed-step  |  Controls: ← → move, Z/Space jump, X/Shift run | N next, B prev, R restart"
        hud = self.font.render(txt, True, (255, 255, 255))
        self.surface.blit(hud, (6, 6))

        if self.completed:
            done = self.font.render("Stage clear! Loading next…", True, (255, 255, 255))
            self.surface.blit(done, (6, 24))

        # Scale up to window (nearest neighbor)
        pygame.transform.scale(self.surface, (WINDOW_W, WINDOW_H), self.window)

if __name__ == "__main__":
    Game().run()
