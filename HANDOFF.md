# Handoff: NewPipe Playlist Browser (Windows app)

## What this is
A small Windows desktop app for browsing playlists inside a **NewPipe backup**
(the `.zip` from NewPipe > Settings > Backup and Restore > Export Database)
and exporting video links / whole playlists. Single user, personal use only,
no distribution — function over polish.

## Current state: working prototype, not yet packaged as an exe
- `newpipe_playlist_browser.py` — the entire app. Pure Python standard library
  (tkinter, sqlite3, zipfile, csv, json). Runs today with `python newpipe_playlist_browser.py`
  on any machine with Python 3 installed. **Not yet tested against a real NewPipe backup** —
  built from documented/observed schema, not verified end-to-end by the user.
- `NewPipePlaylists.spec` — PyInstaller spec to turn the script into a single
  portable `.exe` (`pyinstaller NewPipePlaylists.spec` on Windows). Also untested
  (I don't have a Windows machine in this session to actually run PyInstaller).

## Key decisions already made (don't relitigate unless asked)
- **Stack:** Python + Tkinter, packaged via PyInstaller. Chosen for speed of
  delivery, not for UI polish. User explicitly said "function over form" and
  "no preference, whatever's fastest" — do not suggest rewriting in
  Electron/Qt/.NET/etc. unless the user asks.
- **Distribution:** none. Single portable `.exe` for one person's own PC. No
  installer, no code signing, no auto-update.
- **Icon:** wired to auto-load `app.ico` from the same folder if present;
  no icon has been supplied yet, app works fine without one.

## Data model / schema notes (NewPipe backup internals)
The backup zip contains `newpipe.db` (SQLite) + `newpipe.settings`. Relevant tables,
per NewPipe's Room schema and community tooling (see `load_backup()` in the script
for the exact queries):

- `playlists` (uid, name, ...) — **local** playlists created on-device.
- `playlist_stream_join` (playlist_id, stream_id, join_index) — join table, ordered.
- `streams` (uid, url, title, uploader, duration, stream_type, thumbnail_url) —
  the actual video/audio entries, shared across playlists.
- `remote_playlists` (uid, name, url, ...) — **bookmarked** playlists (e.g. a
  YouTube playlist the user bookmarked). These do **not** store per-video data
  locally — NewPipe fetches them live — so the app only shows their link, not
  a video list. This is intentional, not a bug.

The loader (`load_backup`) checks `sqlite_master` before querying each table
and uses `PRAGMA table_info` for `remote_playlists` columns, so it should degrade
gracefully across NewPipe versions rather than crashing outright — but this
has **not been validated against a real backup file**. That's the top risk area.

## What's NOT done yet / suggested next steps for the agent
1. **Validate against a real backup.** Ask the user for (or have them test with)
   an actual NewPipe export `.zip`. Confirm table/column names match what
   `load_backup()` expects; adjust the SQL if NewPipe's schema has drifted
   (it has changed over the app's history — e.g. the local-playlist feature
   was added later, see TeamNewPipe/NewPipe PR #1004 for schema history context).
2. **Package the exe.** Run `pyinstaller NewPipePlaylists.spec` on a real Windows
   machine, confirm the built `.exe` launches, opens a backup, browses, and
   exports correctly. Watch for PyInstaller + Tkinter quirks (missing `tcl`/`tk`
   DLLs is the classic failure mode — if it happens, add
   `--collect-all tkinter` or check the PyInstaller Tkinter docs).
3. **Icon (optional):** if the user wants one, source or generate an `app.ico`
   and drop it next to the script/spec before building. No code changes needed.
4. **Do steps 1–3 before any of the expansion work below** — everything in the
   backlog assumes the loader and packaging already work against a real backup.

## Expansion backlog (approved scope: Tier 1 + Tier 2 only — user explicitly
## declined Tier 3 thumbnails/new-dependency work for now; don't add it unasked)

User wants: same app, same platform (Windows-only, confirmed — no cross-platform
ask), more features. Still function-over-polish, still no new dependencies unless
a feature genuinely requires one (none below do). Build in the order listed;
each tier is designed to be shippable/testable on its own.

### Tier 1 — bolt onto the current layout, no structural change
Do these first, in any order — fully independent of each other and of Tier 2.

1. **Search/filter box.**
   - One `ttk.Entry` above the playlist tree, one above the video list.
   - Filter **in memory** against already-loaded `self.playlists` / `self.current_videos`
     — do not re-query SQLite per keystroke.
   - Playlist filter: substring match on `pl.name`; re-render tree, keep the
     "Local playlists" / "Bookmarked playlists" parent nodes but hide/collapse
     groups with zero matches.
   - Video filter: substring match on `v.title` or `v.uploader`; re-render
     `self.videos_tree` from a filtered copy of `self.current_videos`, don't
     mutate `self.current_videos` itself (sorting/export need the full list).

2. **Sortable video columns.**
   - Bind each `videos_tree` heading to a sort toggle: clicking "Duration"
     sorts `self.current_videos` by `.duration` (int), flips direction on
     repeat clicks; same pattern for title/uploader (string, case-insensitive)
     and url. Track `(sort_col, ascending)` as instance state.
   - Re-render through the same filtered-list path as the search box above,
     so search + sort compose correctly rather than fighting each other.

3. **Right-click context menu on a video row.**
   - `tk.Menu(tearoff=0)` bound to `<Button-3>` on `videos_tree`.
   - Items: "Open in browser" (`webbrowser.open(url)`), "Copy link".
   - Read-only actions only. Do not add anything that writes back to the
     backup/db — this app is a viewer/exporter, not an editor, and that's a
     deliberate scope boundary, not an oversight.

4. **Double-click to open.**
   - Bind `<Double-1>` on a video row to the same `webbrowser.open(url)` used
     in the context menu — share one helper, don't duplicate the call.

5. **Playlist stats footer.**
   - On playlist selection, compute `len(videos)` and `sum(v.duration for v in videos)`,
     format with the existing `fmt_duration()` helper, show in `self.status`
     (or add a small dedicated label if the status bar gets crowded once
     other features also want it — worth checking before this one lands).

### Tier 2 — moderate, still fits current window except item 5
Do these after Tier 1 lands and is confirmed working.

1. **Multi-select export.**
   - Change the playlist `Treeview`'s `selectmode` to allow multi-select
     (it currently implicitly single-selects via `<<TreeviewSelect>>`).
   - Add an "Export Selected Playlists..." action that iterates the selection
     and reuses `export_all_playlists()`'s per-playlist logic, just scoped to
     the selected subset instead of `self.playlists` in full.

2. **Dark/light theme toggle.**
   - **Light/default = explicitly set `vista`.** The current UI's look (the one
     the user specifically likes and wants kept) is Tkinter's native-Windows
     `vista` ttk theme — it's currently just the unstated OS default, not set
     in code. Make it explicit: `ttk.Style().theme_use('vista')` at startup,
     so it's guaranteed rather than incidental. `vista` only exists on Windows,
     which is fine — this app is Windows-only by design (confirmed earlier).
   - **Dark = separate theme, don't try to recolor `vista`.** `vista` renders
     via the Windows Visual Styles engine, so it can't be recolored like a
     normal ttk theme — trying to reuse it for dark mode won't work. Build
     dark mode on the `clam` base theme instead (ships with Tkinter, fully
     recolorable) with a custom dark color map applied on top.
   - **Consequence to flag to the user, not silently decide:** this means
     light and dark mode won't be the same theme with swapped colors — they'll
     be two visually distinct ttk themes (`vista` vs. recolored `clam`). That's
     an intentional tradeoff to preserve the exact native look in light mode,
     not an oversight, but it means dark mode will look and feel a bit
     different in more than just color (native OS widget rendering vs. a
     drawn/themed one). Fine as agreed, just don't let it read as a bug later.
   - Persist the choice in `SETTINGS_PATH` as `"theme": "vista" | "dark"`, using
     the existing `load_settings`/`save_settings` helpers. Toggle from a new
     View menu (or add to File).

3. **Global search across all playlists.**
   - When a backup loads, also build one flat index: `list[(video, playlist_name)]`
     covering every local playlist's videos. This is cheap — it's just a
     different view over data already in memory, not a new query.
   - New search entry (could live in a new Notebook tab — see item 5 below —
     or as a toggle mode on the existing search box) filters this index and
     shows results with an extra "Playlist" column so the user can see where
     a hit came from.

4. **Duplicate detection.**
   - Reuse the same flat index from item 3: group by `video.url`, surface any
     URL that appears under 2+ playlist names. Build this alongside item 3,
     not separately — they share the index, no reason to compute it twice.

5. **History / Subscriptions browsing — the one structural decision point.**
   - These live in different tables (`stream_history` for watch history,
     `subscriptions` — schema already confirmed earlier in this project: uid,
     service_id, url, name, avatar_url, subscriber_count, description) than
     anything playlists-related.
   - Unlike everything else in this backlog, this doesn't bolt onto the
     current two-pane layout — it needs actual tabs, e.g. `ttk.Notebook`
     with pages: Playlists (today's view) / Search / Duplicates / History /
     Subscriptions.
   - **Confirm with the user before starting this one specifically** — it's
     a real layout change, not an addition, and they may want to scope it
     out even though they approved "Tier 2" broadly, the same way thumbnails
     got flagged and declined for Tier 3. Everything else in Tier 1 and 2 is
     safe to build without re-confirming.

### Suggested build order
Tier 1, all five items, in any order (independent, low-risk) → Tier 2 items
1–2 (multi-select export, theme toggle — easy, no shared state with anything
else) → Tier 2 items 3–4 together (they share the same index) → Tier 2 item 5
last, and only after checking in with the user given the layout change.

## Files in this handoff
- `newpipe_playlist_browser.py` — the app
- `NewPipePlaylists.spec` — PyInstaller build config
- `HANDOFF.md` — this file
- `CLAUDE.md` — standing agent instructions (collaboration style, scope
  boundaries, decision rules). Read this too, not just this file.

## UI Style Guide — hard constraints, not suggestions
The current look (Tkinter's native-Windows `vista` ttk theme, currently just
the unstated OS default) is specifically what the user likes and wants
preserved. Treat the following as binding unless the user explicitly says
otherwise in a given conversation:

- **Native ttk widgets only** — Treeview, native buttons/menus/scrollbars.
  No custom-drawn widgets, no card layouts, no rounded corners, no custom
  color palettes beyond an explicit, separate dark mode (see Tier 2 theme
  item above — dark mode is `clam`-based, not a recolor of `vista`).
- **Set the theme explicitly:** `ttk.Style().theme_use('vista')` at startup.
  Never leave it as an unstated default, and never change the *default* away
  from `vista` without being asked.
- **Density over whitespace.** Minimal padding, tight row height, small
  margins. If a change would add visual "breathing room" at the cost of
  visible rows on screen, don't make it without asking first — this is a
  deliberate, repeatedly-stated preference, not an oversight to "fix."
- **No decorative icons.** Icons only where they encode real information
  (e.g. distinguishing local vs. bookmarked playlists), never next to menu
  items or buttons purely for style.
- **Sortable column headers are the primary interaction model** for any
  tabular data — prefer that over adding toolbar buttons where both would work.
- **Status bar at the bottom** for contextual info (row counts, current
  selection, load status) instead of popups/toasts for routine feedback.
- **Reference points if in doubt:** Sysinternals Process Explorer, Wireshark,
  Total Commander, Everything (voidtools). This app belongs to that dense,
  native-widget utility-software lineage — not modern flat/Fluent design.

## How to pick this up
Read `newpipe_playlist_browser.py` top to bottom (it's one file, ~350 lines,
organized as: data loading → export helpers → GUI). No hidden state, no other
project files, no build system beyond PyInstaller. Start with step 1 above
(schema validation) before making UI changes — everything downstream depends
on the loader actually matching a real backup's structure.
