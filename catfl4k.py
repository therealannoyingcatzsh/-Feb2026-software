#!/usr/bin/env python3
"""
Cat's Studio 26 — The Future of Meow-sic
Built with: sounddevice + numpy + tkinter (No Scipy needed!)
Aesthetics: "FL Studio 26" Blue/Silver Hyper-Dark Mode
Layout: Authentic FL Workflow (Mixer Bottom, Playlist Top)

(C) 2026 Flames Co. / Team Flames
"""

import sys
import subprocess
import threading
import math
import time
import os
import wave
import struct
import random
from tkinter import simpledialog, colorchooser

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 0: AUTO-DEPENDENCY INSTALLER
# ═══════════════════════════════════════════════════════════════════════════════

def install_dependencies():
    print("🐱 Cat's Studio 26 is installing audio engines...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy", "sounddevice"])
        print("✅ Installation complete! Launching Studio...")
    except Exception as e:
        print(f"❌ Auto-install failed: {e}")
        print("Please run: pip install numpy sounddevice")
        sys.exit(1)

try:
    import numpy as np
    import sounddevice as sd
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, Canvas
except ImportError:
    install_dependencies()
    # Retry imports after install
    import numpy as np
    import sounddevice as sd
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, Canvas

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: AUDIO ENGINE CORE (Standardized for stability)
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_RATE = 44100
BLOCK_SIZE = 512
MAX_VOICES = 64

# ─── DSP / Synthesis ──────────────────────────────────────────────────────────

def _butter_filter(data, cutoff, sr, btype='high', order=4):
    """Numpy-based FFT filter to replace scipy."""
    n = len(data)
    if n == 0: return data
    freqs = np.fft.rfftfreq(n, d=1/sr)
    epsilon = 1e-10
    
    if btype == 'low':
        gain = 1.0 / np.sqrt(1.0 + (freqs / (cutoff + epsilon))**(2 * order))
    else:
        with np.errstate(divide='ignore', invalid='ignore'):
            gain = 1.0 / np.sqrt(1.0 + ((cutoff) / (freqs + epsilon))**(2 * order))
        gain[0] = 0.0

    spectrum = np.fft.rfft(data)
    filtered = np.fft.irfft(spectrum * gain, n=n)
    return filtered.astype(np.float32)

def synth_kick(duration=0.5):
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n) / SAMPLE_RATE
    # Pitch envelope
    freq = 150 * np.exp(-t / 0.07) + 50
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    sig = np.sin(phase) * np.exp(-t / 0.3)
    # Transient
    click = np.random.normal(0, 1, int(0.005 * SAMPLE_RATE)) * 0.5
    sig[:len(click)] += click
    max_val = np.max(np.abs(sig))
    return (sig / max_val).astype(np.float32) if max_val > 0 else sig

def synth_snare(duration=0.25):
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n) / SAMPLE_RATE
    tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.05)
    noise = np.random.normal(0, 1, n) * np.exp(-t / 0.12)
    noise = _butter_filter(noise, 1000, SAMPLE_RATE, 'high')
    sig = 0.4 * tone + 0.6 * noise
    max_val = np.max(np.abs(sig))
    return (sig / max_val).astype(np.float32) if max_val > 0 else sig

def synth_hat(duration=0.08, open_hat=False):
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n) / SAMPLE_RATE
    # Metallic noise
    sig = np.random.normal(0, 1, n)
    # Add square waves for metallic body
    for f in [300, 540, 800]:
        sig += np.sign(np.sin(2 * np.pi * f * t)) * 0.2
    sig = _butter_filter(sig, 7000, SAMPLE_RATE, 'high')
    decay = 0.3 if open_hat else 0.04
    sig *= np.exp(-t / decay)
    max_val = np.max(np.abs(sig))
    return (sig / max_val).astype(np.float32) if max_val > 0 else sig

def synth_clap(duration=0.4):
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n) / SAMPLE_RATE
    noise = np.random.normal(0, 1, n)
    noise = _butter_filter(noise, 1200, SAMPLE_RATE, 'high')
    # Burst envelope
    env = np.zeros(n)
    for i in range(4):
        st = int(i * 0.012 * SAMPLE_RATE)
        if st < n:
            env[st:] += np.exp(-np.arange(n-st)/ (SAMPLE_RATE*0.005))
    if np.max(env) > 0: env /= np.max(env)
    sig = noise * env * np.exp(-t/0.2)
    max_val = np.max(np.abs(sig))
    return (sig / max_val).astype(np.float32) if max_val > 0 else sig

# ─── Audio Engine Logic ───────────────────────────────────────────────────────

class Voice:
    __slots__ = ['data', 'pos', 'vol', 'pan']
    def __init__(self, data, vol=1.0, pan=0.5):
        self.data = data
        self.pos = 0
        self.vol = vol
        self.pan = pan

class AudioEngine:
    def __init__(self):
        self.bpm = 140
        self.playing = False
        self.song_mode = False # False=Pat, True=Song
        self.recording = False
        self.sample_pos = 0
        self.stream = None
        self.channels = [] 
        self.voices = []
        self.meter_levels = [0.0] * 10
        self.current_step = 0
        
    def load_kit(self):
        # Create standard "Trap/HipHop" kit
        self.channels = [
            {'name': 'Kick',      'data': synth_kick(),          'color': '#2962FF', 'steps': [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0], 'vol': 0.9, 'pan': 0.5},
            {'name': 'Clap',      'data': synth_clap(),          'color': '#455A64', 'steps': [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0], 'vol': 0.8, 'pan': 0.5},
            {'name': 'Hat (C)',   'data': synth_hat(0.08),       'color': '#00B0FF', 'steps': [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1], 'vol': 0.6, 'pan': 0.4},
            {'name': 'Hat (O)',   'data': synth_hat(0.4, True),  'color': '#80D8FF', 'steps': [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0], 'vol': 0.6, 'pan': 0.6},
            {'name': 'Snare',     'data': synth_snare(),         'color': '#00E5FF', 'steps': [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1], 'vol': 0.8, 'pan': 0.5},
        ]
        self.meter_levels = [0.0] * (len(self.channels) + 1) # +1 for Master

    def callback(self, outdata, frames, time, status):
        out = np.zeros((frames, 2), dtype=np.float32)
        
        if self.playing:
            sps = (60 / self.bpm / 4) * SAMPLE_RATE
            start = self.sample_pos
            end = start + frames
            
            # Sequencer Logic
            start_step = int(start / sps)
            end_step = int(end / sps)
            
            for s in range(start_step, end_step + 1):
                trigger_time = int(s * sps)
                if start <= trigger_time < end:
                    offset = trigger_time - start
                    step_idx = s % 16
                    self.current_step = step_idx
                    
                    # Pattern Mode looping logic (Song mode placeholder)
                    for ch in self.channels:
                        if ch['steps'][step_idx]:
                            # In song mode we would check playlist, here we assume PAT mode for audio engine demo
                            self.voices.append(Voice(ch['data'], ch['vol'], ch['pan']))
                            
            self.sample_pos += frames

        # Render Voices
        active = []
        mix_energy = [0.0] * len(self.meter_levels)
        
        for v in self.voices:
            remain = len(v.data) - v.pos
            if remain <= 0: continue
            
            count = min(frames, remain)
            chunk = v.data[v.pos:v.pos+count] * v.vol
            
            # Panning
            l_gain = np.cos(v.pan * np.pi / 2)
            r_gain = np.sin(v.pan * np.pi / 2)
            
            out[:count, 0] += chunk * l_gain
            out[:count, 1] += chunk * r_gain
            
            v.pos += count
            if v.pos < len(v.data):
                active.append(v)
            
            # Metering (Approximate)
            peak = np.max(np.abs(chunk))
            # Find channel index (slow lookup but fine for 5 chans)
            for i, ch in enumerate(self.channels):
                if ch['data'] is v.data:
                    mix_energy[i] = max(mix_energy[i], peak)
        
        self.voices = active
        
        # Master Meter
        master_peak = np.max(np.abs(out)) if len(out) > 0 else 0
        mix_energy[-1] = master_peak
        
        # Update shared meter state with decay
        for i in range(len(self.meter_levels)):
            self.meter_levels[i] = max(mix_energy[i], self.meter_levels[i] * 0.9)

        # Soft clip
        np.clip(out, -1.0, 1.0, out=out)
        outdata[:] = out

    def start(self):
        try:
            self.stream = sd.OutputStream(channels=2, callback=self.callback, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE)
            self.stream.start()
        except:
            print("Audio Device Error - Running in silent mode")
        
    def play_stop(self):
        if self.playing:
            self.playing = False
            self.sample_pos = 0
            self.current_step = 0
            self.voices = []
        else:
            self.playing = True
            
    def export_wav(self, path):
        # Render 4 loops
        sps = int((60 / self.bpm / 4) * SAMPLE_RATE)
        total_len = sps * 16 * 4
        out = np.zeros((total_len, 2), dtype=np.float32)
        
        for bar in range(4):
            for s in range(16):
                time_idx = (bar * 16 + s) * sps
                for ch in self.channels:
                    if ch['steps'][s]:
                        l_gain = np.cos(ch['pan'] * np.pi / 2)
                        r_gain = np.sin(ch['pan'] * np.pi / 2)
                        
                        slen = len(ch['data'])
                        if time_idx + slen < total_len:
                            out[time_idx:time_idx+slen, 0] += ch['data'] * ch['vol'] * l_gain
                            out[time_idx:time_idx+slen, 1] += ch['data'] * ch['vol'] * r_gain

        # Normalize and save
        m = np.max(np.abs(out))
        if m > 0: out /= m
        
        with wave.open(path, 'w') as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(SAMPLE_RATE)
            f.writeframes((out * 32767).astype(np.int16).tobytes())

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: UI (FL STUDIO 26 AESTHETIC)
# ═══════════════════════════════════════════════════════════════════════════════

class CatStudio26:
    # ── THEME 26 ──────────────────────────────────────────────────────────────
    C = {
        "bg_main":    "#121417",  # FL Charcoal
        "bg_dark":    "#0B0C0E",  # Deep Background
        "bg_rack":    "#1D2026",  # Channel Rack BG
        "bg_step_off":"#37474F",  # Step Off (Dark Slate)
        "bg_step_on": "#2979FF",  # Electric Blue (Active)
        "bg_step_alt":"#ECEFF1",  # Silver (Active Alt)
        "accent":     "#00E5FF",  # Cyan Accent
        "knob":       "#B0BEC5",  # Knob Silver
        "text_main":  "#E0E0E0",
        "text_dim":   "#78909C",
        "panel_grad": "#263238",  # Toolbar BG
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Cat's Studio 26")
        self.root.geometry("1480x950")
        self.root.configure(bg=self.C["bg_main"])
        
        # Engine
        self.engine = AudioEngine()
        self.engine.load_kit()
        self.engine.start()
        
        # UI State
        self.meter_ids = []
        self.step_ids = {} # (ch, step) -> id
        self.knob_ids = {} # (ch, type) -> id
        self.playhead_id = None
        self.playlist_playhead_id = None
        self.scope_line = None
        self.cpu_line = None
        
        # Toolstrip State
        self.pat_mode_btn = None
        self.song_mode_btn = None
        self.rec_btn = None
        
        self.build_ui()
        self.animate()
        
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        # ── REAL MENUBAR (The "File Edit..." strip) ──
        menubar = tk.Menu(self.root, bg=self.C["bg_dark"], fg=self.C["text_main"], activebackground=self.C["accent"], activeforeground="black")
        self.root.config(menu=menubar)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.C["bg_dark"], fg=self.C["text_main"])
        file_menu.add_command(label="New Project", command=lambda: messagebox.showinfo("File", "New Project created!"))
        file_menu.add_command(label="Open...", command=lambda: messagebox.showinfo("File", "Open Dialog..."))
        file_menu.add_command(label="Save", command=lambda: messagebox.showinfo("File", "Project Saved!"))
        file_menu.add_command(label="Save As...", command=lambda: messagebox.showinfo("File", "Save As Dialog..."))
        file_menu.add_separator()
        file_menu.add_command(label="Export to WAV", command=self.do_export)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="FILE", menu=file_menu)

        # Edit Menu
        edit_menu = tk.Menu(menubar, tearoff=0, bg=self.C["bg_dark"], fg=self.C["text_main"])
        edit_menu.add_command(label="Undo", command=lambda: None)
        edit_menu.add_command(label="Cut", command=lambda: None)
        edit_menu.add_command(label="Copy", command=lambda: None)
        edit_menu.add_command(label="Paste", command=lambda: None)
        menubar.add_cascade(label="EDIT", menu=edit_menu)

        # Tools Menu
        tools_menu = tk.Menu(menubar, tearoff=0, bg=self.C["bg_dark"], fg=self.C["text_main"])
        tools_menu.add_command(label="Audio Settings", command=lambda: messagebox.showinfo("Settings", "Audio Device: SoundDevice\nLatency: 11ms"))
        tools_menu.add_command(label="General Settings", command=lambda: None)
        menubar.add_cascade(label="OPTIONS", menu=tools_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0, bg=self.C["bg_dark"], fg=self.C["text_main"])
        help_menu.add_command(label="About Cat's Studio", command=lambda: messagebox.showinfo("About", "Cat's Studio 26\n(C) 2026 Flames Co."))
        menubar.add_cascade(label="HELP", menu=help_menu)

        # ── TOP TOOLBAR (The Control Center) ──
        toolbar = tk.Frame(self.root, bg=self.C["panel_grad"], height=80, bd=0)
        toolbar.pack(fill="x", side="top", pady=1)
        
        # 1. Transport Panel
        trans = tk.Frame(toolbar, bg=self.C["panel_grad"], padx=10)
        trans.pack(side="left")
        
        # Pat/Song Mode (Mutually Exclusive Logic)
        self.pat_mode_btn = self.make_mode_btn(trans, "PAT", self.C["accent"], "#000", lambda: self.set_mode(False))
        self.song_mode_btn = self.make_mode_btn(trans, "SONG", "#000", "#546E7A", lambda: self.set_mode(True))
        
        # Play/Stop/Rec
        self.make_big_btn(trans, "▶", "#000000", "#2979FF", self.toggle_play) # Blue Play
        self.make_big_btn(trans, "■", "#000000", "#B0BEC5", self.toggle_play) # Silver Stop
        self.rec_btn = self.make_big_btn(trans, "●", "#000000", "#555", self.toggle_rec) # Rec (Start grey)

        # 2. LCD Panel (Time, BPM, CPU)
        lcd_bg = "#000000"
        lcd = tk.Frame(toolbar, bg=lcd_bg, padx=2, pady=2, bd=1, relief="sunken")
        lcd.pack(side="left", padx=20, pady=10)
        
        # Time - FIXED: Assigned to self.lbl_time
        self.lbl_time = tk.Label(lcd, text="001:01:00", bg=lcd_bg, fg="#2979FF", font=("Consolas", 22, "bold"), width=9)
        self.lbl_time.pack(side="left", padx=5)
        
        # BPM & CPU box
        stats = tk.Frame(lcd, bg=lcd_bg)
        stats.pack(side="left", padx=5)
        
        # BPM
        bpm_f = tk.Frame(stats, bg=lcd_bg)
        bpm_f.pack(side="top", anchor="w")
        tk.Label(bpm_f, text="BPM", bg=lcd_bg, fg=self.C["text_dim"], font=("Arial", 6)).pack(side="left")
        self.ent_bpm = tk.Entry(bpm_f, bg=lcd_bg, fg="#FFFFFF", font=("Consolas", 10), width=4, bd=0, insertbackground="white")
        self.ent_bpm.insert(0, "140")
        self.ent_bpm.bind("<Return>", self.update_bpm)
        self.ent_bpm.pack(side="left")
        
        # CPU
        cpu_f = tk.Canvas(stats, width=60, height=15, bg="#111", highlightthickness=0)
        cpu_f.pack(side="bottom", pady=2)
        self.cpu_line = cpu_f.create_line(0,15,0,15, fill="#F50057", width=1)
        self.cpu_cv = cpu_f 

        # 3. Oscilloscope (Visualizer)
        self.cv_scope = Canvas(toolbar, width=300, height=60, bg="#050505", highlightthickness=1, highlightbackground="#333")
        self.cv_scope.pack(side="right", padx=15, pady=10)
        # Grid lines
        self.cv_scope.create_line(0, 30, 300, 30, fill="#222")
        self.cv_scope.create_line(150, 0, 150, 60, fill="#222")
        self.scope_line = self.cv_scope.create_line(0,30,300,30, fill=self.C["accent"], width=2)
        tk.Label(toolbar, text="Cat's Monitor", bg=self.C["panel_grad"], fg="#555", font=("Arial", 7)).pack(side="right")

        # ── MAIN SPLIT (FL Workflow: Browser Left, Rest Right) ──
        main_h_split = tk.PanedWindow(self.root, orient="horizontal", bg="#000", sashwidth=4, sashrelief="flat")
        main_h_split.pack(fill="both", expand=True)
        
        # 1. BROWSER (Left)
        browser = tk.Frame(main_h_split, bg=self.C["bg_dark"])
        b_head = tk.Frame(browser, bg="#1E1E1E", height=25)
        b_head.pack(fill="x")
        tk.Label(b_head, text="Browser - All", bg="#1E1E1E", fg="#AAA", font=("Arial", 8, "bold")).pack(side="left", padx=5)
        
        tree = ttk.Treeview(browser, show="tree", padding=5)
        tree.pack(fill="both", expand=True)
        root_packs = tree.insert("", "end", text="Packs", open=True)
        drums = tree.insert(root_packs, "end", text="Drums (ModeAudio)", open=True)
        for d in ["Kick 808", "Snare Trap", "Hat Closed", "Percs", "Claps"]:
            tree.insert(drums, "end", text=d)
        inst = tree.insert(root_packs, "end", text="Instruments")
        tree.insert(inst, "end", text="Sytrus Presets")
        
        btn_exp = tk.Button(browser, text="EXPORT WAV", bg="#111", fg=self.C["accent"], bd=0, command=self.do_export)
        btn_exp.pack(fill="x", pady=0)
        main_h_split.add(browser, width=240) # Wider browser

        # 2. WORKSPACE (Right: Top=Rack/Playlist, Bottom=Mixer)
        workspace_split = tk.PanedWindow(main_h_split, orient="vertical", bg="#000", sashwidth=4, sashrelief="flat")
        main_h_split.add(workspace_split)

        # -- TOP AREA: Channel Rack | Playlist --
        top_area = tk.PanedWindow(workspace_split, orient="horizontal", bg="#000", sashwidth=4, sashrelief="flat")
        workspace_split.add(top_area, height=500) # Give top area more space

        # Channel Rack (Left of top)
        rack_frame = tk.Frame(top_area, bg=self.C["bg_rack"], bd=1, relief="solid")
        r_head = tk.Frame(rack_frame, bg="#2A2D35", height=24)
        r_head.pack(fill="x")
        tk.Label(r_head, text="Channel Rack", bg="#2A2D35", fg="#EEE", font=("Arial", 9, "bold")).pack(side="left", padx=5)
        
        self.cv_rack = Canvas(rack_frame, bg=self.C["bg_rack"], height=300, highlightthickness=0)
        self.cv_rack.pack(fill="both", expand=True, padx=5, pady=5)
        self.draw_rack()
        top_area.add(rack_frame, width=400) # Rack gets decent width

        # Playlist (Right of top)
        play_frame = tk.Frame(top_area, bg="#101010", bd=1, relief="solid")
        p_head = tk.Frame(play_frame, bg="#222", height=24)
        p_head.pack(fill="x")
        tk.Label(p_head, text="Playlist - Arrangement", bg="#222", fg="#EEE", font=("Arial", 9, "bold")).pack(side="left", padx=5)
        
        self.cv_playlist = Canvas(play_frame, bg="#141414", highlightthickness=0)
        self.cv_playlist.pack(fill="both", expand=True)
        self.draw_playlist()
        top_area.add(play_frame) # Playlist takes remaining width

        # -- BOTTOM AREA: Mixer --
        mixer_frame = tk.Frame(workspace_split, bg=self.C["bg_dark"], bd=1, relief="solid")
        m_head = tk.Frame(mixer_frame, bg="#1E1E1E", height=25)
        m_head.pack(fill="x")
        tk.Label(m_head, text="Mixer - Master", bg="#1E1E1E", fg="#AAA", font=("Arial", 8, "bold")).pack(side="left", padx=5)
        
        self.cv_mixer = Canvas(mixer_frame, bg=self.C["bg_dark"], highlightthickness=0)
        self.cv_mixer.pack(fill="both", expand=True)
        self.draw_mixer()
        workspace_split.add(mixer_frame, height=350) # Mixer at bottom

    # ── WIDGET FACTORIES ──

    def make_mode_btn(self, parent, text, bg, fg, cmd):
        b = tk.Button(parent, text=text, bg=bg, fg=fg, bd=0, font=("Arial", 7, "bold"), width=5, command=cmd)
        b.pack(side="left", padx=1, pady=1)
        return b

    def make_big_btn(self, parent, text, bg, fg, cmd):
        b = tk.Button(parent, text=text, bg=bg, fg=fg, activebackground=fg, activeforeground="#000",
                  font=("Arial", 14), bd=0, width=4, height=1, command=cmd)
        b.pack(side="left", padx=2)
        return b

    def draw_knob(self, canvas, x, y, val, color, tags):
        canvas.create_oval(x-9, y-9, x+9, y+9, fill="#222", outline="#444", tags=tags)
        angle = 135 + (val * 270)
        rad = math.radians(angle)
        ix = x + 8 * math.cos(rad)
        iy = y + 8 * math.sin(rad)
        canvas.create_line(x, y, ix, iy, fill=color, width=2, tags=tags)

    # ── DRAWING & INTERACTION ──

    def draw_rack(self):
        self.cv_rack.delete("all")
        y = 15
        
        for i in range(16):
            x = 220 + i * 32
            col = "#FF5252" if i % 4 == 0 else "#666" 
            self.cv_rack.create_text(x+14, y-10, text=str(i+1), fill=col, font=("Arial", 7))
        y += 5

        for i, ch in enumerate(self.engine.channels):
            tags_ch = f"ch_name_{i}"
            self.cv_rack.create_rectangle(60, y, 210, y+26, fill="#34373F", outline="#000", tags=tags_ch)
            self.cv_rack.create_rectangle(205, y+2, 208, y+24, fill=ch['color'], outline="", tags=tags_ch)
            self.cv_rack.create_text(70, y+13, text=ch['name'], fill="white", anchor="w", font=("Segoe UI", 9, "bold"), tags=tags_ch)
            
            self.cv_rack.tag_bind(tags_ch, "<Button-3>", lambda e, ci=i: self.on_channel_right_click(e, ci))

            self.draw_knob(self.cv_rack, 20, y+13, ch['pan'], self.C["knob"], (f"knob_pan_{i}", "knob"))
            self.draw_knob(self.cv_rack, 45, y+13, ch['vol'], self.C["knob"], (f"knob_vol_{i}", "knob"))
            
            self.cv_rack.tag_bind(f"knob_pan_{i}", "<Button-3>", lambda e, ci=i: self.reset_knob(ci, 'pan'))
            self.cv_rack.tag_bind(f"knob_vol_{i}", "<Button-3>", lambda e, ci=i: self.reset_knob(ci, 'vol'))

            for s in range(16):
                x = 220 + s * 32
                is_on = ch['steps'][s]
                grp = (s // 4) % 2
                
                if is_on:
                    fill_col = self.C["bg_step_on"] if grp == 0 else self.C["bg_step_alt"]
                else:
                    fill_col = self.C["bg_step_off"] if grp == 0 else "#263238"
                
                tags_step = f"step_{i}_{s}"
                rid = self.cv_rack.create_rectangle(x, y, x+28, y+26, fill=fill_col, outline="#111", width=1, tags=tags_step)
                
                self.cv_rack.tag_bind(rid, "<Button-1>", lambda e, ci=i, si=s: self.step_action(ci, si, True))
                self.cv_rack.tag_bind(rid, "<Button-3>", lambda e, ci=i, si=s: self.step_action(ci, si, False))
                self.step_ids[(i, s)] = rid

            y += 36

        self.playhead_id = self.cv_rack.create_line(220, 0, 220, y, fill="#FFF", width=2, stipple="gray50")

    def draw_playlist(self):
        cv = self.cv_playlist
        cv.delete("all")
        w = 1500
        h = 600
        
        # Grid lines (Measures)
        beat_w = 40
        for i in range(32): # Draw more measures
             x = 60 + i * beat_w
             col = "#333" if i % 4 == 0 else "#222"
             cv.create_line(x, 0, x, h, fill=col)
             if i % 4 == 0:
                 cv.create_text(x+5, 10, text=str(i//4 + 1), fill="#555", font=("Arial", 8))
        
        # Track Lanes
        for t in range(10):
            y = 25 + t * 40
            cv.create_rectangle(0, y, 60, y+40, fill="#1E1E1E", outline="#333")
            cv.create_text(30, y+20, text=f"Track {t+1}", fill="#777", font=("Arial", 8))
            cv.create_line(0, y+40, w, y+40, fill="#222")
            
            # Pattern Clips (Simulation)
            if t == 0:
                # Pattern 1 placed at bar 1, length 2 bars
                cv.create_rectangle(60, y, 60+(beat_w*16), y+40, fill="#2962FF", outline="#000", stipple="gray50")
                cv.create_text(70, y+12, text="Pattern 1", fill="#FFF", anchor="w", font=("Arial", 8, "bold"))
            if t == 1:
                # Pattern 2 placed at bar 3
                cv.create_rectangle(60+(beat_w*16), y, 60+(beat_w*32), y+40, fill="#455A64", outline="#000", stipple="gray50")
                cv.create_text(70+(beat_w*16), y+12, text="Pattern 2", fill="#FFF", anchor="w", font=("Arial", 8, "bold"))

        # Playlist Playhead
        self.playlist_playhead_id = cv.create_line(60, 0, 60, h, fill="#00FF00", width=1)

    def draw_mixer(self):
        cv = self.cv_mixer
        cv.delete("all")
        self.meter_ids = []
        start_x = 20
        width = 45 # Wider faders
        gap = 5
        
        # FX Rack Area (Right Side Dock simulation)
        # We'll just draw strips here, user requested Bottom Mixer
        
        for i in range(10): # Draw 10 Mixer Tracks
            x = start_x + i * (width + gap)
            is_master = (i == 0) # Master on left in FL often, or extreme right. Let's put left for visibility
            
            # Strip Background
            cv.create_rectangle(x, 10, x+width, 300, fill="#191A1D", outline="#333")
            
            # Label
            lbl = "M" if is_master else str(i)
            cv.create_text(x+width/2, 25, text=lbl, fill="#888", font=("Arial", 8, "bold"))

            # FX Slots Mini Visual
            for fx in range(3):
                fy = 40 + fx * 12
                cv.create_rectangle(x+4, fy, x+width-4, fy+10, fill="#222", outline="")

            # Meter BG
            meter_x = x + width - 12
            cv.create_rectangle(meter_x, 90, meter_x+8, 280, fill="#080808", outline="")
            
            # Active Meter (We map 6 audio channels to 10 strips)
            mid = cv.create_rectangle(meter_x, 280, meter_x+8, 280, fill=self.C["accent"], outline="")
            
            # Map logical channel to mixer strip
            # Master = 0, Chan 0-4 = Strip 1-5
            if is_master:
                self.meter_ids.append((mid, -1)) # -1 index for master logic
            elif i <= 5:
                self.meter_ids.append((mid, i-1)) # audio chan index
            else:
                self.meter_ids.append((mid, None)) # Unused

            # Fader Track line
            cv.create_line(x+15, 90, x+15, 280, fill="#000", width=2)
            
            # Fader Cap
            fader_y = 220 if is_master else 240
            cv.create_rectangle(x+5, fader_y, x+25, fader_y+35, fill="#B0BEC5", outline="#000")
            cv.create_line(x+5, fader_y+17, x+25, fader_y+17, fill="#444")

            # Name at bottom
            name = "Master" if is_master else (self.engine.channels[i-1]['name'] if i <= 5 else f"Insert {i}")
            cv.create_text(x+width/2, 290, text=name[:6], fill="#666", font=("Arial", 7))

    # ── LOGIC ──

    def set_mode(self, is_song):
        self.engine.song_mode = is_song
        if is_song:
            self.song_mode_btn.config(bg=self.C["accent"], fg="#000")
            self.pat_mode_btn.config(bg="#000", fg=self.C["accent"])
        else:
            self.song_mode_btn.config(bg="#000", fg="#546E7A")
            self.pat_mode_btn.config(bg=self.C["accent"], fg="#000")

    def toggle_rec(self):
        self.engine.recording = not self.engine.recording
        col = "#FF1744" if self.engine.recording else "#555"
        self.rec_btn.config(fg=col)

    def toggle_play(self):
        self.engine.play_stop()

    def step_action(self, ch_idx, step_idx, is_left_click):
        if is_left_click:
            val = self.engine.channels[ch_idx]['steps'][step_idx]
            self.engine.channels[ch_idx]['steps'][step_idx] = 1 - val
        else:
            self.engine.channels[ch_idx]['steps'][step_idx] = 0
        self.update_step_visual(ch_idx, step_idx)

    def update_step_visual(self, ch_idx, step_idx):
        val = self.engine.channels[ch_idx]['steps'][step_idx]
        grp = (step_idx // 4) % 2
        if val: 
            fill_col = self.C["bg_step_on"] if grp == 0 else self.C["bg_step_alt"]
        else:
            fill_col = self.C["bg_step_off"] if grp == 0 else "#263238"
        rid = self.step_ids.get((ch_idx, step_idx))
        if rid: self.cv_rack.itemconfig(rid, fill=fill_col)

    def on_channel_right_click(self, event, ch_idx):
        m = tk.Menu(self.root, tearoff=0, bg="#111", fg="#EEE")
        m.add_command(label="Rename...", command=lambda: self.rename_channel(ch_idx))
        m.add_command(label="Change Color...", command=lambda: self.color_channel(ch_idx))
        m.tk_popup(event.x_root, event.y_root)

    def rename_channel(self, ch_idx):
        new_name = simpledialog.askstring("Rename", "New Name:", parent=self.root)
        if new_name:
            self.engine.channels[ch_idx]['name'] = new_name
            self.draw_rack() # Redraw to update name

    def color_channel(self, ch_idx):
        col = colorchooser.askcolor(title="Choose Channel Color", parent=self.root)[1]
        if col:
            self.engine.channels[ch_idx]['color'] = col
            self.draw_rack()

    def reset_knob(self, ch_idx, k_type):
        if k_type == 'vol': self.engine.channels[ch_idx]['vol'] = 0.8
        elif k_type == 'pan': self.engine.channels[ch_idx]['pan'] = 0.5
        self.draw_rack()

    def update_bpm(self, e):
        try: self.engine.bpm = int(self.ent_bpm.get())
        except: pass
            
    def do_export(self):
        f = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("Wave", "*.wav")])
        if f:
            self.engine.export_wav(f)
            messagebox.showinfo("Cat's Studio 26", "Export Complete! 🎵")

    def animate(self):
        # 1. Update Mixer Meters
        for mid, ch_idx in self.meter_ids:
            if ch_idx is None: continue
            
            # Map engine meter index. Master is -1 in engine, but here we store logic differently
            if ch_idx == -1: # Master
                level = self.engine.meter_levels[-1]
            else:
                level = self.engine.meter_levels[ch_idx]
                
            h = level * 190
            coords = self.cv_mixer.coords(mid)
            if coords:
                self.cv_mixer.coords(mid, coords[0], 280 - h, coords[2], 280)

        # 2. Update Rack Playhead
        if self.engine.playing:
            s = self.engine.current_step
            x = 220 + s * 32
            self.cv_rack.coords(self.playhead_id, x, 0, x, 220)
            
            # Move playlist playhead (simulation)
            px = 60 + (self.engine.sample_pos / 44100) * 100 # Arbitrary speed
            px = px % 1000 # loop visually
            self.cv_playlist.coords(self.playlist_playhead_id, px, 0, px, 600)
            
            mins, secs = divmod(int(self.engine.sample_pos / 44100), 60)
            self.lbl_time.config(text=f"{mins:03}:{secs:02}:00")

        # 3. Scope
        amp = self.engine.meter_levels[-1]
        pts = []
        t = time.time()
        for i in range(0, 300, 5):
            y = 30 + math.sin(i*0.1 + t*15) * (amp * 25) * math.sin(i*0.05)
            pts.extend([i, y])
        if len(pts) > 2:
            self.cv_scope.coords(self.scope_line, *pts)
            
        # CPU
        cpu_h = random.randint(5, 14)
        self.cpu_cv.coords(self.cpu_line, 0, 15, 60, 15-cpu_h)

        self.root.after(30, self.animate)

    def on_close(self):
        if self.engine.stream:
            self.engine.stream.stop()
            self.engine.stream.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CatStudio26(root)
    root.mainloop()
