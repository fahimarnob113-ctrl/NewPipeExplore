# NewPipe Playlist Browser & Exporter

[![Release](https://img.shields.io/github/v/release/fahimarnob113-ctrl/NewPipeExplore?label=Download%20v1.0.0)](https://github.com/fahimarnob113-ctrl/NewPipeExplore/releases/latest)
[![Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue)](https://github.com/fahimarnob113-ctrl/NewPipeExplore/releases/latest)

A lightweight, dependency-free Windows desktop application for browsing, searching, and exporting playlists from NewPipe database backups (.zip or .db).

---

## 📥 Download Standalone App

No Python or installation required:
👉 **[Download NewPipePlaylists.exe (v1.0.0)](https://github.com/fahimarnob113-ctrl/NewPipeExplore/releases/download/v1.0.0/NewPipePlaylists.exe)**

Or visit the **[Releases Page](https://github.com/fahimarnob113-ctrl/NewPipeExplore/releases/latest)** for release notes.

---

## Features

- **Zero External Dependencies**: Pure Python standard library (	kinter, sqlite3, zipfile, json, csv).
- **Backup Loader**: Automatically reads and extracts NewPipe SQLite databases (
ewpipe.db) from .zip exports or raw .db files.
- **Two-Pane Explorer**:
  - Left pane: Local and bookmarked playlists treeview with real-time search filter.
  - Right pane: Video stream table with live search and sortable columns (Title, Uploader, Duration, Playlist, URL).
- **Global Cross-Playlist Search**: Toggle between searching within the current playlist or across all local playlists.
- **Duplicate Video Detection**: Instantly detect and inspect videos appearing across multiple playlists.
- **Export Options**:
  - Export single or multi-selected playlists to .txt, .csv, .m3u, or .json.
  - Batch export multiple playlists to dedicated folders.
- **Themes**: Native Windows ista theme and custom dark mode (persisted across sessions).
- **Quick Actions**: Double-click to open any video directly in your default browser, or right-click context menu to copy link.

---

## Running from Source

`ash
python newpipe_playlist_browser.py
`

## Packaging as Standalone Executable (.exe)

You can build the single-file executable locally using PyInstaller:

`ash
pip install pyinstaller
pyinstaller --noconfirm NewPipePlaylists.spec
`

The output executable will be placed in dist/NewPipePlaylists.exe.
