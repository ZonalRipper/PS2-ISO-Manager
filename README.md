# PS2 ISO Manager

A high-performance desktop utility built with **FastAPI**, **PyWebView**, **Tailwind CSS**, and **Three.js** to manage, convert, compress, rename, and organize PlayStation 2 game libraries for **Open PS2 Loader (OPL)**.

---

## Features

- **Auto Pilot Queue Wizard**:
  - Scans a source directory for `.iso`, `.zso`, `.bin`, and `.chd` game images and extracts PS2 Game IDs directly from disc headers or filenames.
  - Converts multi-track `BIN/CUE` rips into standard `.iso` images via `bchunk.exe`.
  - Standardizes filenames against the bundled offline database (`PS2.data.json`) with optional `[Game ID]` tags.
  - Compresses `.iso` images into OPL-compatible `.zso` format via `ziso.exe`.
  - Automatically routes games into OPL `CD` (< 700 MB) and `DVD` (≥ 700 MB) folders with pre-flight disk space checks and safe `.part` atomic transfers.
  - Scrapes missing OPL artwork (`COV`, `COV2`, `ICO`, `LAB`, `LGO`, `BG`, `SCR`) from community repositories.
- **Manual Toolkit**:
  - Run single-file or batch folder operations with an interactive **Operation Preview** before applying changes (Standardize Name, Convert BIN to ISO, Compress ISO to ZSO, or OPL Art Scraper).
- **Interactive 3D WebGL Art Gallery**:
  - Inspect your OPL library in a 360-degree rotatable 3D PS2 game case & spinning optical disc viewer powered by Three.js, complete with game metadata (`Publisher`, `Developer`, `Release Date`, `Genre`) and a 2D asset lightbox.

---

## Project Architecture

```text
PS2-ISO-Manager/
│
├── ps2_utility/
│   ├── __init__.py     # Package initialization
│   └── core.py         # Resource path resolution, header Game ID extraction, and size formatting
│
├── templates/
│   └── index.html      # Tailwind CSS + Three.js WebGL single-page application UI
│
├── app.py              # FastAPI backend server, async worker queues, and PyWebView native window launcher
├── app.spec            # PyInstaller build specification for standalone Windows executable
├── PS2.data.json       # Offline PS2 serial/title/metadata database
├── app_icon.ico        # Application icon
├── requirements.txt    # Python dependencies
├── .gitignore          # Git exclusion rules
└── README.md           # Project documentation
```

---

## Getting Started

### Prerequisites

1. Python 3.10+
2. External CLI tools placed in the project root directory:
   - `bchunk.exe` (for BIN/CUE to ISO conversion)
   - `ziso.exe` (for ISO to ZSO compression)

### Running in Development

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Building Standalone Executable

```powershell
pyinstaller app.spec
```

The packaged standalone executable will be output to `dist/PS2-ISO-Manager.exe`.
