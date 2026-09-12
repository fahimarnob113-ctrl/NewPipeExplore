# NewPipe Playlist Browser & Exporter

A lightweight, dependency-free Windows desktop application for browsing, searching, and exporting playlists from NewPipe database backups (.zip or .db).

## Features

- **Zero External Dependencies**: Pure Python standard library (	kinter, sqlite3, zipfile, json, csv).
- **Backup Loader**: Automatically reads and extracts NewPipe SQLite databases (
ewpipe.db) from .zip exports or raw .db files.
- **Two-Pane Explorer**:
  - Left pane: Local and bookmarked playlists treeview with search filter.
  - Right pane: Video stream table with live search and sortable columns (Title, Uploader, Duration, Playlist, URL).
- **Global Cross-Playlist Search**: Toggle between searching within the current playlist or across all local playlists.
- **Duplicate Video Detection**: Instantly detect and list videos appearing in multiple playlists.
- **Export Options**:
  - Export single or multi-selected playlists to .txt, .csv, .m3u, or .json.
  - Batch export multiple playlists to dedicated folders.
- **Themes**: Native Windows ista theme and custom dark mode (persisted to settings).
- **Quick Actions**: Double-click to open video in default browser, right-click context menu to copy link or open.

## Requirements

- Python 3.8+ (for running from source)
- Windows 10/11

## Running from Source

`ash
python newpipe_playlist_browser.py
`

## Packaging as Standalone Executable (.exe)

You can package the app as a single-file portable Windows executable using PyInstaller:

`ash
pip install pyinstaller
pyinstaller --noconfirm NewPipePlaylists.spec
`

The resulting standalone executable will be located in dist/NewPipePlaylists.exe.
