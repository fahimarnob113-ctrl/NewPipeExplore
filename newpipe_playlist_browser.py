#!/usr/bin/env python3
"""
NewPipe Playlist Browser & Exporter
------------------------------------
A tiny, dependency-free desktop app (Python standard library only) for browsing
the playlists inside a NewPipe backup (the .zip you get from
NewPipe > Settings > Backup and Restore > Export Database) and exporting
video links / whole playlists to TXT, CSV, M3U or JSON.

HOW TO RUN
    python newpipe_playlist_browser.py

HOW TO TURN THIS INTO A STANDALONE .exe (optional, do this on Windows):
    pip install pyinstaller
    pyinstaller --onefile --windowed --name "NewPipePlaylists" newpipe_playlist_browser.py
    -> the .exe will appear in the generated "dist" folder.

No external Python packages are required to just run the .py file.
"""

import csv
import json
import os
import sqlite3
import sys
import tempfile
import webbrowser
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "NewPipe Playlist Browser"
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".newpipe_playlist_browser.json")


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

class Video:
    __slots__ = ("title", "uploader", "url", "duration", "stream_type")

    def __init__(self, title, uploader, url, duration, stream_type):
        self.title = title or ""
        self.uploader = uploader or ""
        self.url = url or ""
        self.duration = duration or 0
        self.stream_type = stream_type or ""


class Playlist:
    def __init__(self, name, kind, uid, url=None):
        self.name = name or "(unnamed)"
        self.kind = kind  # "local" or "bookmarked"
        self.uid = uid
        self.url = url  # only set for bookmarked/remote playlists
        self.videos = []  # list[Video]


def fmt_duration(seconds):
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        return ""
    if seconds <= 0:
        return ""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def table_exists(conn, name):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def load_backup(path):
    """
    Accepts either a NewPipe backup .zip (containing newpipe.db) or a raw
    newpipe.db sqlite file directly. Returns a list of Playlist objects.
    """
    tmp_dir = None
    db_path = path

    if path.lower().endswith(".zip"):
        tmp_dir = tempfile.mkdtemp(prefix="newpipe_")
        with zipfile.ZipFile(path, "r") as z:
            db_member = None
            for name in z.namelist():
                if name.lower().endswith(".db"):
                    db_member = name
                    break
            if db_member is None:
                raise ValueError(
                    "No .db file found inside the zip. Is this a real "
                    "NewPipe 'Export Database' backup?"
                )
            z.extract(db_member, tmp_dir)
            db_path = os.path.join(tmp_dir, db_member)

    conn = sqlite3.connect(db_path)
    playlists = []

    try:
        # --- Local playlists (created on-device, videos stored locally) ---
        if table_exists(conn, "playlists") and table_exists(conn, "playlist_stream_join") \
                and table_exists(conn, "streams"):
            rows = conn.execute("SELECT uid, name FROM playlists ORDER BY name COLLATE NOCASE").fetchall()
            for uid, name in rows:
                pl = Playlist(name, "local", uid)
                vid_rows = conn.execute(
                    """
                    SELECT s.title, s.uploader, s.url, s.duration, s.stream_type
                    FROM playlist_stream_join AS j
                    JOIN streams AS s ON s.uid = j.stream_id
                    WHERE j.playlist_id = ?
                    ORDER BY j.join_index
                    """,
                    (uid,),
                ).fetchall()
                pl.videos = [Video(*row) for row in vid_rows]
                playlists.append(pl)

        # --- Bookmarked / remote playlists (e.g. bookmarked YouTube playlists) ---
        if table_exists(conn, "remote_playlists"):
            cols = [c[1] for c in conn.execute("PRAGMA table_info(remote_playlists)").fetchall()]
            sel_cols = [c for c in ("uid", "name", "url") if c in cols]
            rows = conn.execute(
                f"SELECT {', '.join(sel_cols)} FROM remote_playlists ORDER BY name COLLATE NOCASE"
            ).fetchall()
            for row in rows:
                data = dict(zip(sel_cols, row))
                pl = Playlist(data.get("name"), "bookmarked", data.get("uid"), data.get("url"))
                # Bookmarked/remote playlists don't store their video list locally;
                # NewPipe fetches it live from the source when opened.
                playlists.append(pl)
    finally:
        conn.close()
        if tmp_dir:
            try:
                os.remove(db_path)
                os.rmdir(tmp_dir)
            except OSError:
                pass

    return playlists


# --------------------------------------------------------------------------
# Export helpers
# --------------------------------------------------------------------------

def export_videos(videos, filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["title", "uploader", "url", "duration_seconds"])
            for v in videos:
                w.writerow([v.title, v.uploader, v.url, v.duration])
    elif ext == ".json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                [{"title": v.title, "uploader": v.uploader, "url": v.url, "duration": v.duration}
                 for v in videos],
                f, indent=2, ensure_ascii=False,
            )
    elif ext == ".m3u" or ext == ".m3u8":
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for v in videos:
                dur = v.duration if v.duration else -1
                f.write(f"#EXTINF:{dur},{v.uploader} - {v.title}\n")
                f.write(v.url + "\n")
    else:  # plain .txt -> one link per line
        with open(filepath, "w", encoding="utf-8") as f:
            for v in videos:
                f.write(v.url + "\n")


def export_playlists_to_folder(playlists_to_export, folder):
    manifest = []
    for pl in playlists_to_export:
        safe_name = "".join(c for c in pl.name if c not in '\\/:*?"<>|').strip() or f"playlist_{pl.uid}"
        if pl.kind == "local":
            path = os.path.join(folder, safe_name + ".txt")
            export_videos(pl.videos, path)
            manifest.append({"name": pl.name, "type": "local", "video_count": len(pl.videos), "file": os.path.basename(path)})
        else:
            manifest.append({"name": pl.name, "type": "bookmarked", "url": pl.url})
    with open(os.path.join(folder, "_playlists_index.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def export_all_playlists(playlists, folder):
    export_playlists_to_folder(playlists, folder)


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1020x580")
        self.minsize(760, 420)

        self.playlists = []          # all loaded Playlist objects
        self.pl_by_iid = {}          # treeview iid -> Playlist
        self.current_videos = []     # full videos list of currently selected playlist
        self.displayed_videos = []   # videos currently displayed (after filtering/sorting)
        self.sort_column = None      # current sort column name
        self.sort_ascending = True   # current sort order

        # Tier 2 indexes
        self.global_video_index = [] # list of dict: {video, playlist_name, playlist_kind}
        self.duplicate_urls = set()  # set of video URLs appearing in >1 playlist
        self.view_mode = "playlist"  # "playlist", "global", or "duplicates"

        # Theme handling
        self.settings = load_settings()
        self.current_theme = self.settings.get("theme", "vista")
        self.style = ttk.Style(self)
        self._init_dark_theme()
        self.apply_theme(self.current_theme, save=False)

        self._build_menu()
        self._build_widgets()

    def _init_dark_theme(self):
        """Builds a dense dark theme palette based on 'clam'."""
        try:
            # Create dark style elements on clam without affecting vista
            bg = "#252526"
            fg = "#d4d4d4"
            field_bg = "#1e1e1e"
            select_bg = "#094771"
            select_fg = "#ffffff"
            header_bg = "#333333"

            self.style.theme_settings("clam", {
                "TFrame": {"configure": {"background": bg}},
                "TLabel": {"configure": {"background": bg, "foreground": fg}},
                "TButton": {
                    "configure": {"background": "#3a3d41", "foreground": fg, "padding": (6, 2)},
                    "map": {"background": [("active", "#45494e"), ("pressed", "#2d2d30")]}
                },
                "TEntry": {
                    "configure": {"fieldbackground": field_bg, "foreground": fg, "insertcolor": fg}
                },
                "Treeview": {
                    "configure": {
                        "background": field_bg,
                        "foreground": fg,
                        "fieldbackground": field_bg,
                        "rowheight": 20
                    },
                    "map": {
                        "background": [("selected", select_bg)],
                        "foreground": [("selected", select_fg)]
                    }
                },
                "Treeview.Heading": {
                    "configure": {"background": header_bg, "foreground": fg, "padding": (4, 2)},
                    "map": {"background": [("active", "#3e3e42")]}
                },
                "TPanedwindow": {"configure": {"background": bg}}
            })
        except Exception:
            pass

    def apply_theme(self, theme_name, save=True):
        if theme_name == "dark":
            try:
                self.style.theme_use("clam")
                self.configure(bg="#252526")
            except Exception:
                pass
            self.current_theme = "dark"
        else:
            try:
                self.style.theme_use("vista")
                self.configure(bg="#f0f0f0")
            except Exception:
                pass
            self.current_theme = "vista"

        if save:
            self.settings["theme"] = self.current_theme
            save_settings(self.settings)

    # ---- UI construction -------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)

        # File Menu
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open NewPipe backup (.zip or .db)...", command=self.open_backup)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=filemenu)

        # View Menu (Theme & Display modes)
        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Light Theme (Windows Vista)", command=lambda: self.apply_theme("vista"))
        viewmenu.add_command(label="Dark Theme", command=lambda: self.apply_theme("dark"))
        viewmenu.add_separator()
        viewmenu.add_command(label="Show Duplicate Videos Across Playlists", command=self.show_duplicates)
        menubar.add_cascade(label="View", menu=viewmenu)

        self.config(menu=menubar)

    def _build_widgets(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Open Backup...", command=self.open_backup).pack(side="left")
        self.path_label = ttk.Label(top, text="No backup loaded yet.", foreground="#555")
        self.path_label.pack(side="left", padx=10)

        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Left: playlist pane with search filter
        left = ttk.Frame(main)
        main.add(left, weight=1)

        pl_header = ttk.Frame(left)
        pl_header.pack(fill="x", pady=(0, 4))
        ttk.Label(pl_header, text="Playlists").pack(side="left")

        # Compact playlist filter box
        pl_filter_frame = ttk.Frame(left)
        pl_filter_frame.pack(fill="x", pady=(0, 4))
        self.pl_search_var = tk.StringVar()
        self.pl_search_var.trace_add("write", self._on_playlist_filter_change)
        self.pl_search_entry = ttk.Entry(pl_filter_frame, textvariable=self.pl_search_var)
        self.pl_search_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(pl_filter_frame, text="✕", width=3, command=lambda: self.pl_search_var.set("")).pack(side="right", padx=(2, 0))

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, show="tree", selectmode="extended")
        self.tree.pack(fill="both", expand=True, side="left")
        vsb1 = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb1.pack(fill="y", side="right")
        self.tree.configure(yscrollcommand=vsb1.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_select_playlist)

        # Right: videos pane with search filter and sortable treeview
        right = ttk.Frame(main)
        main.add(right, weight=3)

        vid_header = ttk.Frame(right)
        vid_header.pack(fill="x", pady=(0, 4))
        self.vid_header_label = ttk.Label(vid_header, text="Videos in selected playlist")
        self.vid_header_label.pack(side="left")

        # Global search toggle
        self.search_mode_var = tk.StringVar(value="selected") # "selected" or "all"
        mode_frame = ttk.Frame(vid_header)
        mode_frame.pack(side="right")
        ttk.Radiobutton(mode_frame, text="This Playlist", variable=self.search_mode_var, value="selected", command=self._on_search_mode_change).pack(side="left", padx=4)
        ttk.Radiobutton(mode_frame, text="Search All Playlists", variable=self.search_mode_var, value="all", command=self._on_search_mode_change).pack(side="left")

        # Compact video filter box
        vid_filter_frame = ttk.Frame(right)
        vid_filter_frame.pack(fill="x", pady=(0, 4))
        self.vid_search_var = tk.StringVar()
        self.vid_search_var.trace_add("write", self._on_video_filter_change)
        self.vid_search_entry = ttk.Entry(vid_filter_frame, textvariable=self.vid_search_var)
        self.vid_search_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(vid_filter_frame, text="✕", width=3, command=lambda: self.vid_search_var.set("")).pack(side="right", padx=(2, 0))

        vid_tree_frame = ttk.Frame(right)
        vid_tree_frame.pack(fill="both", expand=True)
        self.cols = ("title", "uploader", "duration", "playlist", "url")
        self.col_labels = {
            "title": "Title",
            "uploader": "Uploader",
            "duration": "Duration",
            "playlist": "Playlist",
            "url": "URL",
        }
        self.videos_tree = ttk.Treeview(vid_tree_frame, columns=self.cols, show="headings", selectmode="extended")
        col_widths = {"title": 280, "uploader": 140, "duration": 70, "playlist": 140, "url": 300}
        for c in self.cols:
            self.videos_tree.column(c, width=col_widths.get(c, 100), anchor="w")
            self.videos_tree.heading(c, text=self.col_labels[c], command=lambda col=c: self.sort_videos_by(col))
        self.videos_tree.pack(fill="both", expand=True, side="left")
        vsb2 = ttk.Scrollbar(vid_tree_frame, orient="vertical", command=self.videos_tree.yview)
        vsb2.pack(fill="y", side="right")
        self.videos_tree.configure(yscrollcommand=vsb2.set)

        # Interactions on video rows: Double-click and Right-click context menu
        self.videos_tree.bind("<Double-1>", self.on_video_double_click)
        self.videos_tree.bind("<Button-3>", self.on_video_right_click)

        self.video_context_menu = tk.Menu(self, tearoff=0)
        self.video_context_menu.add_command(label="Open in Browser", command=self.open_selected_in_browser)
        self.video_context_menu.add_command(label="Copy Link", command=self.copy_selected_links)

        bottom = ttk.Frame(self, padding=(8, 0, 8, 8))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Copy Selected Link(s)", command=self.copy_selected_links).pack(side="left")
        ttk.Button(bottom, text="Export Selected Playlist(s)...", command=self.export_selected_playlists).pack(side="left", padx=6)
        ttk.Button(bottom, text="Export ALL Playlists...", command=self.export_all).pack(side="left")

        self.status = ttk.Label(self, text="Ready.", relief="sunken", anchor="w")
        self.status.pack(fill="x", side="bottom")

    # ---- Actions & Filtering -----------------------------------------
    def set_status(self, text):
        self.status.config(text=text)
        self.update_idletasks()

    def open_backup(self):
        path = filedialog.askopenfilename(
            title="Select NewPipe backup",
            filetypes=[("NewPipe backup or database", "*.zip *.db"), ("All files", "*.*")],
        )
        if not path:
            return
        self.set_status("Loading backup...")
        try:
            self.playlists = load_backup(path)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not read backup:\n{e}")
            self.set_status("Failed to load backup.")
            return

        self.path_label.config(text=os.path.basename(path))
        self.pl_search_var.set("")
        self.vid_search_var.set("")
        self.search_mode_var.set("selected")
        self.view_mode = "playlist"

        # Build Tier 2 flat in-memory index across all local playlists
        self._build_global_index()

        self._populate_playlist_tree()

        n_local = sum(1 for pl in self.playlists if pl.kind == "local")
        n_bm = sum(1 for pl in self.playlists if pl.kind != "local")
        dup_msg = f" | {len(self.duplicate_urls)} cross-playlist duplicate URL(s) detected." if self.duplicate_urls else ""
        self.set_status(f"Loaded {n_local} local playlist(s) and {n_bm} bookmarked playlist(s).{dup_msg}")
        if n_local == 0 and n_bm == 0:
            messagebox.showinfo(
                APP_TITLE,
                "No playlists were found in this backup.\n"
                "Make sure you exported via NewPipe > Settings > Backup and Restore "
                "> Export Database, and that 'Playlists' was included."
            )

    def _build_global_index(self):
        """Builds a flat index of all videos and finds duplicates across playlists."""
        self.global_video_index = []
        url_to_playlists = {}
        for pl in self.playlists:
            if pl.kind == "local":
                for v in pl.videos:
                    self.global_video_index.append({
                        "video": v,
                        "playlist_name": pl.name,
                        "playlist_kind": pl.kind,
                    })
                    if v.url:
                        url_to_playlists.setdefault(v.url, set()).add(pl.name)

        self.duplicate_urls = {url for url, names in url_to_playlists.items() if len(names) > 1}

    def _populate_playlist_tree(self):
        query = self.pl_search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        self.pl_by_iid.clear()
        self.videos_tree.delete(*self.videos_tree.get_children())

        local_node = self.tree.insert("", "end", text="Local playlists", open=True)
        bm_node = self.tree.insert("", "end", text="Bookmarked playlists", open=True)

        n_local = n_bm = 0
        for pl in self.playlists:
            if query and query not in pl.name.lower():
                continue
            if pl.kind == "local":
                label = f"{pl.name}  ({len(pl.videos)})"
                iid = self.tree.insert(local_node, "end", text=label)
                n_local += 1
            else:
                label = f"{pl.name}  [bookmarked]"
                iid = self.tree.insert(bm_node, "end", text=label)
                n_bm += 1
            self.pl_by_iid[iid] = pl

        # Auto-collapse groups with zero matches if filtering
        if n_local == 0:
            self.tree.item(local_node, open=False)
        if n_bm == 0:
            self.tree.item(bm_node, open=False)

    def _on_playlist_filter_change(self, *args):
        self._populate_playlist_tree()

    def _on_search_mode_change(self):
        mode = self.search_mode_var.get()
        if mode == "all":
            self.view_mode = "global"
            self.vid_header_label.config(text="Global Search: All Playlists")
        else:
            self.view_mode = "playlist"
            pl = self.get_selected_playlist()
            pl_name = pl.name if pl else "None"
            self.vid_header_label.config(text=f"Videos in: {pl_name}")
        self._render_videos()

    def show_duplicates(self):
        """View duplicates across all playlists."""
        if not self.playlists:
            messagebox.showinfo(APP_TITLE, "Load a backup first.")
            return
        if not self.duplicate_urls:
            messagebox.showinfo(APP_TITLE, "No duplicate video URLs found across playlists.")
            return
        self.view_mode = "duplicates"
        self.search_mode_var.set("all")
        self.vid_header_label.config(text="Duplicate Videos Across Playlists")
        self._render_videos()

    def get_selected_playlists(self):
        """Returns list of all currently selected Playlist objects in treeview."""
        sel = self.tree.selection()
        if not sel:
            return []
        res = []
        for s in sel:
            pl = self.pl_by_iid.get(s)
            if pl and pl not in res:
                res.append(pl)
        return res

    def get_selected_playlist(self):
        pls = self.get_selected_playlists()
        return pls[0] if pls else None

    def on_select_playlist(self, _event=None):
        if self.view_mode != "playlist":
            self.view_mode = "playlist"
            self.search_mode_var.set("selected")

        pls = self.get_selected_playlists()
        self.videos_tree.delete(*self.videos_tree.get_children())
        self.current_videos = []
        self.displayed_videos = []

        if not pls:
            return

        if len(pls) > 1:
            # Multi-selection info
            local_count = sum(len(p.videos) for p in pls if p.kind == "local")
            self.vid_header_label.config(text=f"Multiple Selected ({len(pls)} playlists)")
            self.set_status(f"Selected {len(pls)} playlists ({local_count} total videos). Click 'Export Selected Playlist(s)...' to export.")
            return

        pl = pls[0]
        self.vid_header_label.config(text=f"Videos in: {pl.name}")
        if pl.kind == "bookmarked":
            self.set_status(
                f"'{pl.name}' is a bookmarked playlist — NewPipe streams its "
                f"contents live rather than storing them locally. Link: {pl.url}"
            )
            return

        self.current_videos = list(pl.videos)
        self._render_videos()

    def _render_videos(self):
        """Filters, sorts, and renders videos based on current view_mode."""
        self.videos_tree.delete(*self.videos_tree.get_children())
        query = self.vid_search_var.get().strip().lower()

        items_to_display = [] # list of (Video, playlist_name)

        if self.view_mode == "duplicates":
            for item in self.global_video_index:
                v = item["video"]
                if v.url in self.duplicate_urls:
                    if not query or query in v.title.lower() or query in v.uploader.lower() or query in item["playlist_name"].lower():
                        items_to_display.append((v, item["playlist_name"]))
        elif self.view_mode == "global":
            for item in self.global_video_index:
                v = item["video"]
                if not query or query in v.title.lower() or query in v.uploader.lower() or query in item["playlist_name"].lower():
                    items_to_display.append((v, item["playlist_name"]))
        else: # "playlist"
            pl = self.get_selected_playlist()
            pl_name = pl.name if pl else ""
            for v in self.current_videos:
                if not query or query in v.title.lower() or query in v.uploader.lower():
                    items_to_display.append((v, pl_name))

        # In-memory sorting
        if self.sort_column:
            def sort_key(entry):
                v, p_name = entry
                if self.sort_column == "playlist":
                    val = p_name
                else:
                    val = getattr(v, self.sort_column, "")
                if self.sort_column == "duration":
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return 0
                return str(val).lower()

            items_to_display.sort(key=sort_key, reverse=not self.sort_ascending)

        self.displayed_videos = [v for v, _ in items_to_display]
        for v, p_name in items_to_display:
            self.videos_tree.insert(
                "", "end", values=(v.title, v.uploader, fmt_duration(v.duration), p_name, v.url)
            )

        # Update sort indicators on headers
        for col in self.cols:
            base_label = self.col_labels[col]
            if col == self.sort_column:
                indicator = " ▲" if self.sort_ascending else " ▼"
                self.videos_tree.heading(col, text=base_label + indicator)
            else:
                self.videos_tree.heading(col, text=base_label)

        # Update Stats Footer
        total_dur = sum(v.duration for v in self.displayed_videos if v.duration)
        dur_str = f" | Total duration: {fmt_duration(total_dur)}" if total_dur > 0 else ""

        if self.view_mode == "duplicates":
            self.set_status(f"Duplicate videos across playlists — {len(self.displayed_videos)} match(es){dur_str}")
        elif self.view_mode == "global":
            self.set_status(f"Global index — {len(self.displayed_videos)} video(s) found across all playlists{dur_str}")
        else:
            pl = self.get_selected_playlist()
            pl_name = pl.name if pl else "None"
            filter_str = f" (filtered from {len(self.current_videos)})" if len(self.displayed_videos) != len(self.current_videos) else ""
            self.set_status(f"'{pl_name}' — {len(self.displayed_videos)} video(s){filter_str}{dur_str}")

    def _on_video_filter_change(self, *args):
        self._render_videos()

    def sort_videos_by(self, column):
        if self.sort_column == column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = column
            self.sort_ascending = True
        self._render_videos()

    def on_video_double_click(self, event):
        item = self.videos_tree.identify_row(event.y)
        if not item:
            return
        vals = self.videos_tree.item(item, "values")
        if vals and len(vals) >= 5:
            url = vals[4] # URL is at index 4 with playlist column added
            if url:
                webbrowser.open(url)

    def on_video_right_click(self, event):
        item = self.videos_tree.identify_row(event.y)
        if item:
            if item not in self.videos_tree.selection():
                self.videos_tree.selection_set(item)
            self.video_context_menu.post(event.x_root, event.y_root)

    def open_selected_in_browser(self):
        sel = self.videos_tree.selection()
        if not sel:
            return
        for item in sel:
            vals = self.videos_tree.item(item, "values")
            if vals and len(vals) >= 5:
                url = vals[4]
                if url:
                    webbrowser.open(url)

    def copy_selected_links(self):
        sel = self.videos_tree.selection()
        if not sel:
            messagebox.showinfo(APP_TITLE, "Select one or more videos first.")
            return
        links = [self.videos_tree.item(i, "values")[4] for i in sel]
        self.clipboard_clear()
        self.clipboard_append("\n".join(links))
        self.set_status(f"Copied {len(links)} link(s) to clipboard.")

    def export_selected_playlists(self):
        """Exports either single selected playlist to a chosen file, or multi-selected playlists to a chosen folder."""
        pls = self.get_selected_playlists()
        if not pls:
            messagebox.showinfo(APP_TITLE, "Select one or more playlists first.")
            return

        if len(pls) == 1:
            # Single playlist export
            pl = pls[0]
            if pl.kind == "bookmarked":
                messagebox.showinfo(
                    APP_TITLE,
                    "Bookmarked playlists only store a link, not individual videos.\n"
                    f"Link: {pl.url}"
                )
                return
            if not pl.videos:
                messagebox.showinfo(APP_TITLE, "This playlist has no videos.")
                return

            default_name = "".join(c for c in pl.name if c not in '\\/:*?"<>|').strip() or "playlist"
            path = filedialog.asksaveasfilename(
                title=f"Export '{pl.name}'",
                initialfile=default_name + ".txt",
                defaultextension=".txt",
                filetypes=[
                    ("Text - one link per line", "*.txt"),
                    ("CSV", "*.csv"),
                    ("M3U playlist", "*.m3u"),
                    ("JSON", "*.json"),
                ],
            )
            if not path:
                return
            try:
                export_videos(pl.videos, path)
            except Exception as e:
                messagebox.showerror(APP_TITLE, f"Export failed:\n{e}")
                return
            self.set_status(f"Exported '{pl.name}' ({len(pl.videos)} videos) to {path}")
            messagebox.showinfo(APP_TITLE, f"Exported to:\n{path}")
        else:
            # Multiple playlists selected -> export to folder
            folder = filedialog.askdirectory(title=f"Choose folder to export {len(pls)} selected playlists into")
            if not folder:
                return
            try:
                export_playlists_to_folder(pls, folder)
            except Exception as e:
                messagebox.showerror(APP_TITLE, f"Export failed:\n{e}")
                return
            self.set_status(f"Exported {len(pls)} selected playlist(s) to {folder}")
            messagebox.showinfo(
                APP_TITLE,
                f"Exported {len(pls)} playlist(s) to:\n{folder}\n\n"
                "Local playlists -> one .txt file per playlist.\n"
                "Bookmarked playlists -> listed with links in _playlists_index.json."
            )

    def export_all(self):
        if not self.playlists:
            messagebox.showinfo(APP_TITLE, "Load a backup first.")
            return
        folder = filedialog.askdirectory(title="Choose a folder to export all playlists into")
        if not folder:
            return
        try:
            export_all_playlists(self.playlists, folder)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Export failed:\n{e}")
            return
        self.set_status(f"Exported all playlists to {folder}")
        messagebox.showinfo(
            APP_TITLE,
            f"Exported {len(self.playlists)} playlist(s) to:\n{folder}\n\n"
            "Local playlists -> one .txt file per playlist (one link per line).\n"
            "Bookmarked playlists -> listed with their link in _playlists_index.json."
        )


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
