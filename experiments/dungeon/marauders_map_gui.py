#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karte des Rumtreibers - Live GUI v2
====================================
Echtzeit-Visualisierung der Bot-Bewegungen im BACH-System.

Liest bot_*.json Dateien aus data/swarm/map/ und zeigt
die Bots auf einer Karte des BACH-Verzeichnisbaums.

Verwendung:
  cd system/
  python data/swarm/marauders_map_gui.py [DUNGEON_ROOT] [MAP_DIR]

  Ohne Argumente: BACH system/ als Root, data/swarm/map/ als Bot-Daten.
  Mit DUNGEON_ROOT: Beliebiger Ordner als Dungeon-Root.
  Mit MAP_DIR: Beliebiger Ordner fuer Bot-JSON-Dateien.

Features v2:
  - Stockwerk-Navigation (Floor Tabs): Filtern nach Tiefe
  - Findings Chat-Panel: Scrollbares Log rechts vom Canvas
  - Konfigurierbarer Dungeon-Root via CLI-Argument
  - Frame-basiertes Layout mit PanedWindow

Nur tkinter (Python-Standardbibliothek), keine externen Abhaengigkeiten.
"""

import os
import sys
import json
import math
import time
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Pfade ermitteln (Defaults, werden ggf. durch CLI-Argumente ueberschrieben)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # system/data/swarm/
SYSTEM_DIR = SCRIPT_DIR.parent.parent.parent          # system/
MAP_DIR = SCRIPT_DIR / "map"

# Fallback falls Struktur anders ist
if not (SYSTEM_DIR / "hub").exists():
    cwd = Path.cwd()
    if (cwd / "hub").exists():
        SYSTEM_DIR = cwd
    elif (cwd / "system" / "hub").exists():
        SYSTEM_DIR = cwd / "system"

# ---------------------------------------------------------------------------
# CLI-Argumente: optionaler Dungeon-Root und Map-Dir
# ---------------------------------------------------------------------------
if len(sys.argv) >= 2:
    _arg_root = Path(sys.argv[1]).resolve()
    if _arg_root.is_dir():
        SYSTEM_DIR = _arg_root
    else:
        print(f"WARNUNG: Angegebener Dungeon-Root existiert nicht: {sys.argv[1]}")

if len(sys.argv) >= 3:
    _arg_map = Path(sys.argv[2]).resolve()
    if _arg_map.is_dir():
        MAP_DIR = _arg_map
    else:
        print(f"WARNUNG: Angegebenes Map-Dir existiert nicht: {sys.argv[2]}")


# ---------------------------------------------------------------------------
# Farben und Konstanten
# ---------------------------------------------------------------------------
BG_COLOR        = "#0a0a0f"
BG_PARCHMENT    = "#0d0d14"
BORDER_COLOR    = "#2a2a40"
BORDER_BRIGHT   = "#5a5a8a"
BORDER_ROOT     = "#8878a0"
TEXT_COLOR       = "#c8c8dc"
TEXT_DIM         = "#5a5a70"
TEXT_TITLE       = "#d4c090"
TEXT_HEADER      = "#a0a0c0"

COLOR_EXPLORING  = "#22cc44"
COLOR_COMPLETED  = "#4488ee"
COLOR_DEAD_STARVE= "#aa2222"   # Tote = rot (verhungert: dunkler)
COLOR_DEAD_TRAP  = "#ff3333"   # Tote = rot (Falle: heller/greller)
COLOR_TREASURE   = "#ffd700"

# Chat-Panel Farben
CHAT_BG          = "#0d0d14"
CHAT_TEXT        = "#c8c8dc"
CHAT_TIME        = "#5a5a70"
CHAT_BOT_NAME    = "#d4c090"

# Floor-Button Farben
FLOOR_BTN_BG     = "#2a2a40"
FLOOR_BTN_ACTIVE = TEXT_TITLE   # "#d4c090"
FLOOR_BTN_FG     = "#c8c8dc"
FLOOR_BTN_FG_ACT = "#0a0a0f"

# Tiefenabhaengige Farben: tiefer = hoeher im Gebaeude (nach oben!)
DEPTH_BG = [
    "#16162a",  # Tiefe 0 - Erdgeschoss (Dungeon-Root)
    "#121228",  # Tiefe 1 - 1. OG
    "#0e0e22",  # Tiefe 2 - 2. OG
    "#0a0a1c",  # Tiefe 3 - 3. OG
]
DEPTH_BORDER = [
    "#4a4a70",  # Tiefe 0
    "#3a3a58",  # Tiefe 1
    "#2a2a44",  # Tiefe 2
    "#222238",  # Tiefe 3
]

# Gedimmte Farben fuer nicht-aktive Stockwerke
DEPTH_BG_DIM = [
    "#0c0c18",  # Tiefe 0 dimmed
    "#0a0a14",  # Tiefe 1 dimmed
    "#080812",  # Tiefe 2 dimmed
    "#06060e",  # Tiefe 3 dimmed
]
DEPTH_BORDER_DIM = [
    "#1e1e30",  # Tiefe 0 dimmed
    "#181828",  # Tiefe 1 dimmed
    "#141420",  # Tiefe 2 dimmed
    "#10101a",  # Tiefe 3 dimmed
]

REFRESH_MS = 2000
WIN_W = 1400
WIN_H = 900
CHAT_WIDTH = 350

IGNORE_DIRS = {
    ".git", ".pytest_cache", "__pycache__", "node_modules",
    ".claude", ".venv", "venv", ".idea", ".vscode",
}

MAX_DEPTH = 3  # Erhoet auf 3 fuer 3.OG Support


# ---------------------------------------------------------------------------
# Verzeichnisstruktur einlesen
# ---------------------------------------------------------------------------
class RoomInfo:
    """Ein 'Raum' = ein Verzeichnis im BACH-System."""
    __slots__ = ("path", "name", "depth", "file_count", "children",
                 "x", "y", "w", "h", "parent_path", "total_files")

    def __init__(self, path, name, depth, file_count, parent_path=""):
        self.path = path
        self.name = name
        self.depth = depth
        self.file_count = file_count
        self.children = []
        self.parent_path = parent_path
        self.total_files = file_count  # wird spaeter berechnet
        self.x = self.y = self.w = self.h = 0


def scan_system_directory(system_dir):
    """Scannt das BACH-System und gibt ein Dict {rel_path: RoomInfo} zurueck."""
    rooms = {}
    system_path = Path(system_dir).resolve()

    if not system_path.exists():
        return rooms

    for dirpath, dirnames, filenames in os.walk(system_path, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)

        try:
            rel = str(Path(dirpath).resolve().relative_to(system_path))
            rel = rel.replace("\\", "/")
        except ValueError:
            dirnames.clear()
            continue

        if rel == ".":
            rel = ""

        depth = rel.count("/") if rel else 0
        if depth > MAX_DEPTH:
            dirnames.clear()
            continue

        if rel in rooms:
            dirnames.clear()
            continue

        file_count = len(filenames)
        name = Path(dirpath).name if rel else system_path.name
        parent = str(Path(rel).parent).replace("\\", "/") if rel else ""
        if parent == ".":
            parent = ""

        room = RoomInfo(rel, name, depth, file_count, parent)
        rooms[rel] = room

        if parent in rooms and rel != parent:
            rooms[parent].children.append(rel)

    # total_files Bottom-Up berechnen (iterativ, sicher)
    _compute_total_files(rooms)

    return rooms


def _compute_total_files(rooms):
    """Berechnet total_files Bottom-Up (Blatt -> Wurzel)."""
    # Sortiere nach Tiefe absteigend -> Blaetter zuerst
    by_depth = sorted(rooms.values(), key=lambda r: -r.depth)
    for room in by_depth:
        room.total_files = room.file_count
        for child_path in room.children:
            child = rooms.get(child_path)
            if child:
                room.total_files += child.total_files


# ---------------------------------------------------------------------------
# Bot-Daten lesen
# ---------------------------------------------------------------------------
class BotInfo:
    """Zustand eines einzelnen Bots."""
    __slots__ = ("agent_id", "position", "doing", "status", "cause",
                 "findings", "searched", "treasure_here", "updated")

    def __init__(self, data):
        self.agent_id = data.get("agent_id", "???")
        self.position = self._normalize_position(data.get("position", ""))
        self.doing = data.get("doing", "")
        self.status = data.get("status", "exploring")
        self.cause = data.get("cause", "")
        self.findings = data.get("findings", [])
        self.searched = data.get("searched", [])
        self.treasure_here = data.get("treasure_here", False)
        self.updated = data.get("updated", "")

    @staticmethod
    def _normalize_position(pos):
        if not pos:
            return ""
        pos = pos.strip().replace("\\", "/").strip("/")
        if pos.lower() in ("start", "system root", "system/root", "root"):
            return ""
        if pos.startswith("system/"):
            pos = pos[7:]
        return pos


def read_bot_files(map_dir):
    """Liest alle bot_*.json Dateien und gibt Liste von BotInfo zurueck."""
    bots = []
    map_path = Path(map_dir)
    if not map_path.exists():
        return bots
    for f in sorted(map_path.glob("bot_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            bots.append(BotInfo(data))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
    return bots


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def compute_layout(rooms, canvas_w, canvas_h):
    """Treemap-Layout: Ordner werden als verschachtelte Rechtecke dargestellt."""
    if not rooms:
        return

    margin_top = 10
    margin_bottom = 10
    margin_side = 10

    usable_w = canvas_w - 2 * margin_side
    usable_h = canvas_h - margin_top - margin_bottom

    if usable_w < 50 or usable_h < 50:
        return

    root = rooms.get("")
    if not root:
        return

    root.x = margin_side
    root.y = margin_top
    root.w = usable_w
    root.h = usable_h

    _layout_children(rooms, "", margin_side, margin_top, usable_w, usable_h, set())


def _layout_children(rooms, parent_path, px, py, pw, ph, visited):
    """Layoutet die Kinder eines Raumes mittels Slice-and-Dice."""
    if parent_path in visited:
        return
    visited.add(parent_path)

    parent = rooms.get(parent_path)
    if not parent or not parent.children:
        return

    children = [rooms[c] for c in parent.children if c in rooms]
    if not children:
        return

    pad = 2
    label_h = 14
    inner_x = px + pad
    inner_y = py + label_h
    inner_w = pw - 2 * pad
    inner_h = ph - label_h - pad

    if inner_w < 8 or inner_h < 8:
        return

    # Gewichte basierend auf Dateianzahl
    weights = [max(c.total_files, 1) for c in children]
    total_w = sum(weights)

    # Achse waehlen: breitere Dimension teilen
    horizontal = inner_w >= inner_h
    total_dim = inner_w if horizontal else inner_h

    # Dimensionen berechnen mit proportionaler Verteilung
    # Mindestbreite: jeder Raum bekommt mindestens min_px Pixel
    n = len(children)
    min_px = 12 if parent.depth == 0 else 4  # Top-Level sichtbarer halten
    min_total = min_px * n

    dims = []
    if total_dim <= min_total:
        # Zu wenig Platz: gleichmaessig aufteilen
        dims = [total_dim / n] * n
    else:
        # Proportional verteilen, aber mit Mindestgroesse
        avail = total_dim - min_total  # Platz ueber Minimum hinaus
        for w in weights:
            dims.append(min_px + avail * w / total_w)

    # Normalisierung: Summe muss genau total_dim ergeben
    dim_sum = sum(dims)
    if dim_sum > 0 and abs(dim_sum - total_dim) > 0.5:
        scale = total_dim / dim_sum
        dims = [d * scale for d in dims]

    offset = 0.0
    for i, child in enumerate(children):
        dim = dims[i]

        if horizontal:
            child.x = inner_x + offset
            child.y = inner_y
            child.w = dim
            child.h = inner_h
        else:
            child.x = inner_x
            child.y = inner_y + offset
            child.w = inner_w
            child.h = dim

        offset += dim

        # Rekursiv, nur wenn genug Platz
        if child.children and child.w > 30 and child.h > 30:
            _layout_children(rooms, child.path,
                             child.x, child.y, child.w, child.h, visited)


# ---------------------------------------------------------------------------
# Bot -> Raum Zuordnung
# ---------------------------------------------------------------------------
def find_room_for_bot(rooms, position):
    """Findet den passenden Raum fuer eine Bot-Position."""
    if not position:
        return rooms.get("")

    if position in rooms:
        return rooms[position]

    # Laengster Prefix-Match
    best = ""
    for rp in rooms:
        if not rp:
            continue
        if position.startswith(rp + "/") or position == rp:
            if len(rp) > len(best):
                best = rp
        elif rp.endswith("/" + position) or rp == position:
            if len(rp) > len(best):
                best = rp
    if best:
        return rooms[best]

    # Name-Match (letzter Pfadteil)
    pos_name = position.split("/")[-1].lower()
    for rp, room in rooms.items():
        if room.name.lower() == pos_name:
            return room

    return rooms.get("")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
def build_gui(rooms, map_dir, dungeon_root_path):
    """Erstellt und startet die tkinter GUI."""
    import tkinter as tk
    from tkinter import font as tkfont

    win = tk.Tk()

    # Fenstertitel mit Dungeon-Root-Pfad
    root_label = Path(dungeon_root_path).name or str(dungeon_root_path)
    win.title(f"Karte des Rumtreibers  -  Dungeon: {root_label}/")
    win.geometry(f"{WIN_W}x{WIN_H}")
    win.configure(bg=BG_COLOR)
    win.resizable(True, True)

    # Fonts
    try:
        f_title   = tkfont.Font(family="Consolas", size=15, weight="bold")
        f_sub     = tkfont.Font(family="Consolas", size=8)
        f_room_l  = tkfont.Font(family="Consolas", size=9, weight="bold")
        f_room_s  = tkfont.Font(family="Consolas", size=7)
        f_bot     = tkfont.Font(family="Consolas", size=7, weight="bold")
        f_bot_s   = tkfont.Font(family="Consolas", size=6)
        f_legend  = tkfont.Font(family="Consolas", size=8)
        f_small   = tkfont.Font(family="Consolas", size=7)
        f_chat    = tkfont.Font(family="Consolas", size=8)
        f_chat_b  = tkfont.Font(family="Consolas", size=8, weight="bold")
        f_floor   = tkfont.Font(family="Consolas", size=9, weight="bold")
    except Exception:
        f_title  = ("Courier", 15, "bold")
        f_sub    = ("Courier", 8)
        f_room_l = ("Courier", 9, "bold")
        f_room_s = ("Courier", 7)
        f_bot    = ("Courier", 7, "bold")
        f_bot_s  = ("Courier", 6)
        f_legend = ("Courier", 8)
        f_small  = ("Courier", 7)
        f_chat   = ("Courier", 8)
        f_chat_b = ("Courier", 8, "bold")
        f_floor  = ("Courier", 9, "bold")

    # ==================================================================
    # Layout-Frames aufbauen
    # ==================================================================

    # --- Top Frame: Titel + Floor-Buttons ---
    top_frame = tk.Frame(win, bg=BG_COLOR)
    top_frame.pack(side=tk.TOP, fill=tk.X)

    # Titelzeile
    title_frame = tk.Frame(top_frame, bg=BG_COLOR)
    title_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(8, 0))

    tk.Label(
        title_frame, text="~ Karte des Rumtreibers ~",
        bg=BG_COLOR, fg=TEXT_TITLE, font=f_title,
    ).pack(side=tk.LEFT, padx=(5, 15))

    tk.Label(
        title_frame, text=f"[Dungeon: {root_label}/]",
        bg=BG_COLOR, fg=TEXT_DIM, font=f_sub,
    ).pack(side=tk.LEFT, padx=(0, 15))

    tk.Label(
        title_frame,
        text="Ich schwoere feierlich, dass ich ein Tunichtgut bin.",
        bg=BG_COLOR, fg=TEXT_DIM, font=f_sub,
    ).pack(side=tk.RIGHT, padx=5)

    # Floor-Buttons-Leiste
    floor_frame = tk.Frame(top_frame, bg=BG_COLOR)
    floor_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(4, 4))

    # State
    state = {
        "bots": [],
        "last_update": "",
        "tooltip_id": None,
        "prev_size": (0, 0),
        "active_floor": -1,      # -1 = Alle, 0=EG, 1=1.OG, 2=2.OG, 3=3.OG
        "floor_buttons": [],
        "chat_findings": [],     # Liste von (timestamp, bot_id, position, lines)
        "chat_findings_hash": "",  # Zum Erkennen von Aenderungen
    }

    # Floor-Button-Erstellung
    floor_labels = ["Alle", "EG", "1.OG", "2.OG", "3.OG"]
    floor_values = [-1, 0, 1, 2, 3]

    def set_active_floor(floor_val):
        state["active_floor"] = floor_val
        _update_floor_buttons()
        draw()

    def _update_floor_buttons():
        active = state["active_floor"]
        for btn, val in state["floor_buttons"]:
            if val == active:
                btn.configure(bg=FLOOR_BTN_ACTIVE, fg=FLOOR_BTN_FG_ACT)
            else:
                btn.configure(bg=FLOOR_BTN_BG, fg=FLOOR_BTN_FG)

    for i, (label, val) in enumerate(zip(floor_labels, floor_values)):
        btn = tk.Button(
            floor_frame, text=f" {label} ",
            bg=FLOOR_BTN_ACTIVE if val == -1 else FLOOR_BTN_BG,
            fg=FLOOR_BTN_FG_ACT if val == -1 else FLOOR_BTN_FG,
            font=f_floor,
            relief=tk.FLAT,
            activebackground=FLOOR_BTN_ACTIVE,
            activeforeground=FLOOR_BTN_FG_ACT,
            cursor="hand2",
            bd=0,
            padx=8, pady=2,
            command=lambda v=val: set_active_floor(v),
        )
        btn.pack(side=tk.LEFT, padx=(0, 4))
        state["floor_buttons"].append((btn, val))

    # --- Mittlerer Bereich: PanedWindow mit Canvas + Chat ---
    middle_pane = tk.PanedWindow(
        win, orient=tk.HORIZONTAL,
        bg=BG_COLOR, sashwidth=4, sashrelief=tk.FLAT,
        borderwidth=0,
    )
    middle_pane.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=0)

    # Canvas (links)
    canvas = tk.Canvas(middle_pane, bg=BG_COLOR, highlightthickness=0)
    middle_pane.add(canvas, stretch="always")

    # Chat-Panel (rechts)
    chat_frame = tk.Frame(middle_pane, bg=CHAT_BG, width=CHAT_WIDTH)
    middle_pane.add(chat_frame, stretch="never", width=CHAT_WIDTH)

    # Chat-Header
    chat_header = tk.Label(
        chat_frame, text="  Findings Chat-Log  ",
        bg="#14142a", fg=TEXT_TITLE, font=f_chat_b,
        anchor="w", padx=8, pady=4,
    )
    chat_header.pack(side=tk.TOP, fill=tk.X)

    # Chat-Text-Widget mit Scrollbar
    chat_scroll_frame = tk.Frame(chat_frame, bg=CHAT_BG)
    chat_scroll_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    chat_scrollbar = tk.Scrollbar(chat_scroll_frame, orient=tk.VERTICAL)
    chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    chat_text = tk.Text(
        chat_scroll_frame,
        bg=CHAT_BG,
        fg=CHAT_TEXT,
        font=f_chat,
        wrap=tk.WORD,
        state=tk.DISABLED,
        relief=tk.FLAT,
        borderwidth=0,
        padx=8, pady=4,
        yscrollcommand=chat_scrollbar.set,
        cursor="arrow",
        selectbackground="#2a2a50",
        selectforeground=CHAT_TEXT,
    )
    chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    chat_scrollbar.config(command=chat_text.yview)

    # Text-Tags fuer Chat-Formatierung
    chat_text.tag_configure("timestamp", foreground=CHAT_TIME, font=f_chat)
    chat_text.tag_configure("botname", foreground=CHAT_BOT_NAME, font=f_chat_b)
    chat_text.tag_configure("finding", foreground=CHAT_TEXT, font=f_chat)
    chat_text.tag_configure("finding_good", foreground=COLOR_EXPLORING, font=f_chat)
    chat_text.tag_configure("finding_warn", foreground=COLOR_TREASURE, font=f_chat)
    chat_text.tag_configure("separator", foreground="#1e1e30", font=f_chat)

    # --- Bottom Frame: Legende + Stats ---
    bottom_frame = tk.Frame(win, bg=BG_COLOR)
    bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(2, 6))

    # Trennlinie
    sep = tk.Frame(bottom_frame, bg=BORDER_COLOR, height=1)
    sep.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))

    # Legende (obere Zeile des bottom_frame)
    legend_frame = tk.Frame(bottom_frame, bg=BG_COLOR)
    legend_frame.pack(side=tk.TOP, fill=tk.X)

    legend_items = [
        (COLOR_EXPLORING,   "Aktiv"),
        (COLOR_COMPLETED,   "Fertig"),
        (COLOR_DEAD_STARVE, "Tot (verhungert)"),
        (COLOR_DEAD_TRAP,   "Tot (Falle)"),
        (COLOR_TREASURE,    "Schatz!"),
    ]

    for col, label in legend_items:
        item_frame = tk.Frame(legend_frame, bg=BG_COLOR)
        item_frame.pack(side=tk.LEFT, padx=(0, 16))

        # Farbiger Punkt als Canvas
        dot = tk.Canvas(item_frame, width=12, height=12, bg=BG_COLOR,
                        highlightthickness=0)
        dot.pack(side=tk.LEFT, padx=(0, 4))
        dot.create_oval(1, 1, 11, 11, fill=col, outline=col)

        tk.Label(
            item_frame, text=label,
            bg=BG_COLOR, fg=TEXT_COLOR, font=f_legend,
        ).pack(side=tk.LEFT)

    # Stats-Label (rechts in der Legende)
    stats_label = tk.Label(
        legend_frame, text="Bots: 0",
        bg=BG_COLOR, fg=TEXT_COLOR, font=f_legend,
        anchor="e",
    )
    stats_label.pack(side=tk.RIGHT, padx=(10, 0))

    # Footer-Zeile
    footer_frame = tk.Frame(bottom_frame, bg=BG_COLOR)
    footer_frame.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))

    footer_left = tk.Label(
        footer_frame, text="Unheil angerichtet!",
        bg=BG_COLOR, fg=TEXT_DIM, font=f_small,
        anchor="w",
    )
    footer_left.pack(side=tk.LEFT)

    footer_right = tk.Label(
        footer_frame, text="Warte auf Daten...",
        bg=BG_COLOR, fg=TEXT_DIM, font=f_small,
        anchor="e",
    )
    footer_right.pack(side=tk.RIGHT)

    # ==================================================================
    # Zeichenfunktionen
    # ==================================================================

    def draw():
        """Zeichnet die gesamte Karte auf dem Canvas."""
        canvas.delete("all")
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 100 or ch < 100:
            return

        compute_layout(rooms, cw, ch)

        bots = state["bots"]
        active_floor = state["active_floor"]

        # --- Durchsuchte Raeume & Schatz-Raeume ermitteln ---
        searched_set = set()
        treasure_set = set()
        for bot in bots:
            for s in bot.searched:
                searched_set.add(s.lower())
            if bot.treasure_here:
                rm = find_room_for_bot(rooms, bot.position)
                if rm:
                    treasure_set.add(rm.path)

        # --- Raeume zeichnen (Eltern vor Kindern) ---
        for room in sorted(rooms.values(), key=lambda r: r.depth):
            is_dimmed = (active_floor != -1 and room.depth != active_floor)
            _draw_room(canvas, room, searched_set, treasure_set, is_dimmed)

        # --- Bots sammeln und zeichnen ---
        room_bots = {}
        for bot in bots:
            rm = find_room_for_bot(rooms, bot.position)
            if rm:
                room_bots.setdefault(rm.path, []).append(bot)

        for rp, bot_list in room_bots.items():
            rm = rooms.get(rp)
            if not rm:
                continue
            # Bots auf gedimmten Stockwerken kleiner/transparenter
            is_dimmed = (active_floor != -1 and rm.depth != active_floor)
            for idx, bot in enumerate(bot_list):
                _draw_bot(canvas, rm, bot, idx, len(bot_list), is_dimmed)

        # --- Stats-Label aktualisieren ---
        n_total = len(bots)
        n_exp = sum(1 for b in bots if b.status == "exploring")
        n_done = sum(1 for b in bots if b.status == "completed")
        n_dead = sum(1 for b in bots if b.status == "dead")
        n_find = sum(len(b.findings) for b in bots)

        stats_text = (f"Bots: {n_total}   Aktiv: {n_exp}   "
                      f"Fertig: {n_done}   Tot: {n_dead}   "
                      f"Findings: {n_find}")
        stats_label.configure(text=stats_text)

        # --- Footer-Timestamp aktualisieren ---
        ts = state["last_update"]
        footer_right.configure(
            text=f"Update: {ts}" if ts else "Warte auf Daten..."
        )

    # ------------------------------------------------------------------
    def _draw_room(cv, room, searched, treasures, dimmed=False):
        x, y, w, h = room.x, room.y, room.w, room.h
        if w < 3 or h < 3:
            return

        # Farbe
        di = min(room.depth, len(DEPTH_BG) - 1)

        if dimmed:
            bg = DEPTH_BG_DIM[di]
            border = DEPTH_BORDER_DIM[di]
        else:
            bg = DEPTH_BG[di]
            border = DEPTH_BORDER[di]

        if not dimmed:
            if room.path in treasures:
                bg = "#2a2510"
                border = COLOR_TREASURE
            elif room.name.lower() in searched or room.path.lower() in searched:
                bg = "#0f1f0f"
                border = "#2a5a2a"

        bw = 2 if room.depth == 0 else 1

        cv.create_rectangle(x, y, x + w, y + h,
                            fill=bg, outline=border, width=bw)

        # Label
        if w < 20 or h < 12:
            return

        label = room.name
        fnt = f_room_l if room.depth <= 1 and w > 40 else f_room_s

        if dimmed:
            color = "#2a2a38"
        else:
            color = TEXT_COLOR if room.depth == 0 else TEXT_HEADER if room.depth == 1 else TEXT_DIM

        if not dimmed and room.path in treasures:
            color = COLOR_TREASURE

        # Kuerzen falls noetig
        max_chars = max(3, int(w / 7))
        if len(label) > max_chars:
            label = label[:max_chars - 1] + "."

        # Dateianzahl anhaengen wenn Platz
        suffix = ""
        if room.total_files > 0 and w > 60:
            suffix = f" ({room.total_files})"

        cv.create_text(x + 3, y + 2, anchor="nw",
                       text=label + suffix, fill=color, font=fnt)

    # ------------------------------------------------------------------
    def _draw_bot(cv, room, bot, idx, total, dimmed=False):
        rx, ry, rw, rh = room.x, room.y, room.w, room.h

        # Bot-Position im Raum berechnen
        if total == 1:
            bx = rx + rw * 0.5
            by = ry + rh * 0.55
        else:
            cols = max(1, int(math.ceil(math.sqrt(total))))
            row_i = idx // cols
            col_i = idx % cols
            rows = max(1, (total + cols - 1) // cols)
            bx = rx + (col_i + 0.5) * rw / cols
            by = ry + 14 + (row_i + 0.5) * (rh - 14) / rows

        # Innerhalb des Raums halten
        bx = max(rx + 12, min(bx, rx + rw - 12))
        by = max(ry + 16, min(by, ry + rh - 12))

        r = 4 if dimmed else 7
        status = bot.status.lower()
        cause = (bot.cause or "").lower()

        if dimmed:
            # Gedimmte Bots: kleiner, dunkler
            dim_col = "#1a1a2a"
            cv.create_oval(bx - r, by - r, bx + r, by + r,
                           fill=dim_col, outline="#2a2a3a", width=1)
            return

        if status == "exploring":
            # Aeusserer Puls-Ring
            cv.create_oval(bx - r - 4, by - r - 4, bx + r + 4, by + r + 4,
                           outline=COLOR_EXPLORING, width=1, dash=(2, 3))
            cv.create_oval(bx - r, by - r, bx + r, by + r,
                           fill=COLOR_EXPLORING, outline="#33ff55", width=2)
            cv.create_text(bx, by, text=bot.agent_id[-3:],
                           fill="#000000", font=f_bot)
            label_color = COLOR_EXPLORING

        elif status == "completed":
            cv.create_oval(bx - r, by - r, bx + r, by + r,
                           fill=COLOR_COMPLETED, outline="#66aaff", width=2)
            cv.create_text(bx, by, text="OK", fill="#ffffff", font=f_bot)
            label_color = COLOR_COMPLETED

        elif status == "dead":
            col = COLOR_DEAD_TRAP if cause == "falle" else COLOR_DEAD_STARVE
            cv.create_oval(bx - r, by - r, bx + r, by + r,
                           fill=col, outline="#aaaaaa", width=1)
            cv.create_text(bx, by, text="X", fill="#ffffff", font=f_bot)
            label_color = col
        else:
            cv.create_oval(bx - r, by - r, bx + r, by + r,
                           fill="#444444", outline="#666666", width=1)
            cv.create_text(bx, by, text="?", fill="#ffffff", font=f_bot)
            label_color = TEXT_DIM

        # Bot-ID unter dem Punkt
        cv.create_text(bx, by + r + 7, text=bot.agent_id,
                       fill=label_color, font=f_bot_s)

        # "doing" Text (wenn Platz)
        if rw > 90 and rh > 45 and bot.doing:
            txt = bot.doing
            mc = max(8, int(rw / 6))
            if len(txt) > mc:
                txt = txt[:mc - 2] + ".."
            cv.create_text(bx, by + r + 16, text=txt,
                           fill=TEXT_DIM, font=f_bot_s)

    # ------------------------------------------------------------------
    # Chat-Panel aktualisieren
    # ------------------------------------------------------------------
    def update_chat(bots):
        """Aktualisiert das Chat-Panel mit Findings der Bots."""
        # Alle Findings sammeln
        new_findings = []
        for bot in bots:
            if bot.findings:
                # Position kuerzen
                pos = bot.position or "system root"
                ts = bot.updated or ""
                # Timestamp aus bot-Daten extrahieren oder aktuell
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        time_str = dt.strftime("%H:%M")
                    except (ValueError, TypeError):
                        time_str = ts[:5] if len(ts) >= 5 else "??:??"
                else:
                    time_str = datetime.now().strftime("%H:%M")

                new_findings.append((time_str, bot.agent_id, pos, bot.findings))

        # Hash bilden um unnoetige Updates zu vermeiden
        findings_hash = str([(t, b, p, f) for t, b, p, f in new_findings])
        if findings_hash == state["chat_findings_hash"]:
            return
        state["chat_findings_hash"] = findings_hash

        # Text-Widget updaten
        chat_text.configure(state=tk.NORMAL)
        chat_text.delete("1.0", tk.END)

        if not new_findings:
            chat_text.insert(tk.END, "\n  Noch keine Findings...\n", "finding")
            chat_text.insert(tk.END, "\n  Die Bots erkunden\n", "finding")
            chat_text.insert(tk.END, "  das Dungeon...\n", "finding")
        else:
            for time_str, agent_id, position, findings in new_findings:
                # Zeitstempel + Bot-Name
                chat_text.insert(tk.END, f"[{time_str}] ", "timestamp")
                chat_text.insert(tk.END, f"{agent_id}", "botname")
                chat_text.insert(tk.END, f" @ {position}:\n", "timestamp")

                # Findings-Zeilen
                for finding in findings:
                    # Farbwahl: gruene Saetze fuer "sauber"/"keine", goldene fuer Funde
                    tag = "finding"
                    fl = finding.lower()
                    if ("sauber" in fl or "keine" in fl or "clean" in fl
                            or "ok" in fl):
                        tag = "finding_good"
                    elif any(w in fl for w in [
                        "gefunden", "found", "warnung", "warning",
                        "fehler", "error", "problem", "verdaechtig",
                    ]):
                        tag = "finding_warn"

                    chat_text.insert(tk.END, f"  {finding}\n", tag)

                # Separator
                chat_text.insert(tk.END, "\n", "separator")

        chat_text.configure(state=tk.DISABLED)

        # Auto-Scroll nach unten
        chat_text.see(tk.END)

    # ------------------------------------------------------------------
    # Tooltip bei Maus-Hover
    # ------------------------------------------------------------------
    def on_motion(event):
        mx, my = event.x, event.y

        # Alten Tooltip entfernen
        if state["tooltip_id"]:
            canvas.delete(state["tooltip_id"])
            state["tooltip_id"] = None

        # Bot unter Mauszeiger finden
        for bot in state["bots"]:
            rm = find_room_for_bot(rooms, bot.position)
            if not rm:
                continue
            # Grobe Pruefung: ist Maus im Raum?
            if not (rm.x <= mx <= rm.x + rm.w and rm.y <= my <= rm.y + rm.h):
                continue

            # Tooltip-Text erstellen
            lines = [
                f"  {bot.agent_id}  [{bot.status}]",
                f"  Position: {bot.position or 'root'}",
                f"  Doing: {bot.doing}",
            ]
            if bot.findings:
                lines.append(f"  Findings: {len(bot.findings)}")
                lines.append(f"    {bot.findings[-1][:60]}")
            if bot.searched:
                lines.append(f"  Searched: {', '.join(bot.searched[:5])}")
            if bot.cause:
                lines.append(f"  Cause: {bot.cause}")

            text = "\n".join(lines)

            # Tooltip zeichnen
            tx = mx + 15
            ty = my - 10
            # Hintergrund-Rechteck
            tag = "tooltip"
            canvas.delete(tag)

            tid = canvas.create_text(
                tx, ty, anchor="nw", text=text,
                fill=TEXT_COLOR, font=f_small, tags=(tag,),
            )
            bbox = canvas.bbox(tid)
            if bbox:
                pad = 4
                bg_id = canvas.create_rectangle(
                    bbox[0] - pad, bbox[1] - pad,
                    bbox[2] + pad, bbox[3] + pad,
                    fill="#1a1a2e", outline=BORDER_BRIGHT,
                    tags=(tag,),
                )
                canvas.tag_raise(tid, bg_id)
            state["tooltip_id"] = tag
            return

    canvas.bind("<Motion>", on_motion)
    canvas.bind("<Leave>", lambda e: canvas.delete("tooltip"))

    # ------------------------------------------------------------------
    # Update-Schleife
    # ------------------------------------------------------------------
    def tick():
        try:
            state["bots"] = read_bot_files(map_dir)
            state["last_update"] = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            print(f"[Fehler beim Lesen] {e}")

        draw()
        update_chat(state["bots"])
        win.after(REFRESH_MS, tick)

    # Resize: nur neu zeichnen wenn Groesse sich aendert
    def on_configure(event):
        if event.widget is canvas:
            new_size = (event.width, event.height)
            if new_size != state["prev_size"]:
                state["prev_size"] = new_size
                draw()

    canvas.bind("<Configure>", on_configure)

    # Erster Tick nach kurzem Delay
    win.after(150, tick)
    win.mainloop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Karte des Rumtreibers - BACH System GUI v2")
    print(f"System-Verzeichnis: {SYSTEM_DIR}")
    print(f"Bot-Daten:          {MAP_DIR}")
    print()

    print("Scanne Verzeichnisstruktur...")
    rooms = scan_system_directory(SYSTEM_DIR)
    print(f"  {len(rooms)} Raeume gefunden")

    if not rooms:
        print("WARNUNG: Keine Verzeichnisse gefunden!")
        print(f"  Gepruefter Pfad: {SYSTEM_DIR}")
        print("  Erstelle Platzhalter...")
        rooms = {"": RoomInfo("", "system", 0, 0, "")}

    # Stockwerk-Statistiken
    depths = {}
    for r in rooms.values():
        depths.setdefault(r.depth, []).append(r.name)
    for d in sorted(depths):
        names = depths[d]
        label = "Erdgeschoss" if d == 0 else f"{d}. OG"
        shown = ", ".join(sorted(names)[:12])
        more = f"... (+{len(names) - 12})" if len(names) > 12 else ""
        print(f"  {label}: {len(names)} Raeume  [{shown}{more}]")
    print()

    bots = read_bot_files(MAP_DIR)
    print(f"{len(bots)} Bots geladen")
    for b in bots:
        marker = {"exploring": "+", "completed": "=", "dead": "X"}.get(b.status, "?")
        print(f"  [{marker}] {b.agent_id}: {b.position or 'root'} - {b.doing}")
    print()

    if not MAP_DIR.exists():
        print(f"HINWEIS: {MAP_DIR} existiert nicht.")
        print("  Die GUI startet trotzdem und prueft alle 2s auf neue Daten.")
        print()

    print("Starte GUI... (Schliesse das Fenster um zu beenden)")
    build_gui(rooms, MAP_DIR, SYSTEM_DIR)


if __name__ == "__main__":
    main()
