# PS2 ISO Batch Management Suite Pro

A feature-rich, high-performance desktop utility built with Python and Tkinter designed to manage, convert, compress, rename, and organize PlayStation 2 assets for Open PS2 Loader (OPL). Features a hardware-accelerated 3D WebGL game case and optical disc viewer powered by Three.js.

---

## Features

- **BIN/CUE to ISO Compilation**: Automatically parses track metadata and compiles multi-track rips into standard ISO images.
- **Batch Renaming**: Matches ISO, ZSO, and CHD files against an offline database (`PS2.data.json`) to clean up filenames and inject official Game IDs.
- **Lossless Compression**: 
  - Compress ISOs to `.zso` via `ziso.exe`.
  - Compress ISOs to lossless `.chd` via MAME's `chdman.exe` (with automatic `createcd`/`createdvd` sector detection).
- **Extraction**: Restore `.zso` images back to standard `.iso` format.
- **OPL Drive Manager & Scraper**: Automatically builds required OPL folder structures (`DVD`, `CD`, `ART`, `CFG`, `VMC`), tracks missing artwork status, and scrapes full art layouts from community databases.
- **Interactive 3D WebGL Gallery**: View your game cases in a 360-degree rotatable 3D environment complete with spinning optical disc renders (`ICO`) and a side drawer for flat 2D assets (`BG`, `LGO`, `SCR`).

---

## Project Architecture

The project is modularized into a clean package structure for easy maintenance and expansion:

```text
PS2-ISO-Manager/
│
├── ps2_utility/
│   ├── __init__.py     # Package initialization
│   ├── core.py         # Low-level utilities, path resolution, and header parsing
│   ├── ui.py           # Tkinter application GUI, tabs, theme engine, and queue logic
│   └── viewer.py       # Three.js 3D WebGL HTML generator & browser launcher
│
├── main.py             # Application entry point
├── requirements.txt    # Python dependencies (Pillow)
├── .gitignore          # Git exclusion rules
└── README.md           # Documentation & Attributions
