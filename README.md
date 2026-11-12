# 🎮 PS2 ISO Manager — Open PS2 Loader (OPL) Suite

![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0051cc?style=for-the-badge&logo=windows)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Three.js](https://img.shields.io/badge/3D%20Gallery-Three.js%20WebGL-000000?style=for-the-badge&logo=threedotjs&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-10b981?style=for-the-badge)

A desktop utility built with **FastAPI**, **PyWebView**, **Tailwind CSS**, and **Three.js** to convert, rename, compress, verify, and manage PlayStation 2 game libraries for **Open PS2 Loader (OPL)** on USB, exFAT/FAT32 drives, internal HDDs, and SMB shares.

Designed with an authentic **PlayStation 2 BIOS ("Seven Towers" & Monolith)** visual theme, DualShock 2 button prompts (`△ ○ × □`), a toggleable **CRT Scanline** filter, and an interactive **3D WebGL Amaray DVD Case & Config Studio**.

---

## ✨ Key Highlights

- **⚡ 1-Click Auto Pilot Pipeline**: Turn a folder of raw downloads or disc rips (`.iso`, `.zso`, `.bin/.cue`, `.chd`) into a clean, named, compressed, artwork-populated OPL drive.
- **🩹 Auto-Recreates Missing `.CUE` Files**: Detects `.bin` dumps with missing `.cue` sheets, inspects binary sector headers (`MODE2/2352`, `MODE1/2352`, `MODE1/2048`), and automatically regenerates the `.cue` file before converting to `.iso`.
- **💿 Full `.CHD` & `.ZSO` Support**: Extract single-track DVD or multi-track CD `.chd` archives to `.iso`, compress `.iso` to `.zso` (saving 25–40% space), or decompress `.zso` back to `.iso`.
- **💾 Automatic `FAT32 >4GB` Splitting (`ul.cfg`)**: Detects `FAT32` destination drives and automatically splits ISOs larger than 4 GB into `1 GB` USBUtil chunks (`ul.<CRC>.<ID>.00`) with a valid 64-byte `ul.cfg` index.
- **🖼️ 3D WebGL Cover Art Gallery & Custom Art Dropper**: Inspect your library in a rotatable 3D PlayStation 2 cobalt-blue DVD case with a spinning optical disc, or upload/drag-and-drop custom images that automatically resize to OPL's exact pixel dimensions.
- **⚙️ Per-Game OPL `CFG` Studio with Mode & VMC Guides**: Generate and edit `CFG/<GameID>.cfg` files with interactive hover guides explaining **OPL Compatibility Modes 1–6** (symptoms + example games) and **Virtual Memory Card (`$VMC_0`)** presets.

---

## 🚀 Auto Pilot Queue (5-Stage Automated Pipeline)

Auto Pilot processes an entire folder of games end-to-end in five automated stages:

| Stage | Operation | Details |
| :--- | :--- | :--- |
| **Stage 1** | **Disc Format Conversion** | Converts `.BIN/.CUE` (`bchunk.exe`) and `.CHD` (`chdman.exe`) dumps into standard PS2 `.ISO` images. Automatically recreates missing `.CUE` sheets by inspecting sector 16 `CD001` & sync headers. |
| **Stage 2** | **Game ID Scan & Naming** | Reads `SYSTEM.CNF` directly from disc sectors to extract the Sony serial (`SLUS_xxx.xx`, `SLES_xxx.xx`, `SCUS_xxx.xx`, etc.) and renames files against the bundled 11,000+ PS2 title database (`Title [SLUS-20062].iso`). |
| **Stage 3** | **ZSO Compression / FAT32 Split** | Compresses ISOs into OPL-compatible `.ZSO` files via `ziso.exe` (with live storage-saved reporting), or splits `>4GB` ISOs into `ul.cfg` chunks when targeting a `FAT32` USB drive. |
| **Stage 4** | **Smart OPL Routing** | Creates standard OPL directories (`DVD/`, `CD/`, `ART/`, `CFG/`) on the destination drive, routes `< 700 MB` games to `CD/` and `≥ 700 MB` games to `DVD/`, checks free drive space, and uses atomic `.part` transfers. |
| **Stage 5** | **Artwork & CFG Metadata** | Downloads 6-piece OPL artwork (`COV`, `COV2`, `LAB`, `ICO`, `LGO`, `BG`, `SCR`) into `ART/` and generates per-game `CFG/<GameID>.cfg` files (`Title`, `Publisher`, `Developer`, `Genre`, `Release Date`). |

---

## 🛠️ Manual Toolkit (8 Dedicated Tools)

Switch to the **Manual Toolkit** tab to run targeted single-file or batch-folder operations. Every tool features an interactive **Operation Preview Table** with live search, status filtering (`All`, `Actionable Only`, `Skipped Only`), and per-row selection checkboxes:

| Tool | Scope | Description |
| :--- | :--- | :--- |
| **🏷️ Standardize Name** | File / Folder | Scans internal disc headers for the Sony Game ID and renames `.iso`, `.zso`, and `.chd` files to their official title (with optional `[Game ID]` suffix). |
| **💿 Convert BIN / CHD** | File / Folder | Converts `.bin`/`.cue` and `.chd` images into standard `.iso` files. Automatically recreates missing `.cue` files when only a `.bin` is present. |
| **🗜️ Compress to ZSO** | File / Folder | Compresses `.iso` images into LZ4 `.zso` format for OPL and reports exact MB/GB and percentage saved. |
| **📦 Decompress ZSO** | File / Folder | Restores `.zso` compressed games back into uncompressed `.iso` images. |
| **🖼️ OPL Art Scraper** | OPL Root | Audits your OPL `ART/` directory (`Full Set`, `Partial`, `Missing`) and scrapes missing or complete artwork sets (`Only Missing`, `Missing & Partial`, or `Full Rescan`). |
| **📝 OPL CFG Generator** | OPL Root | Batch-generates `CFG/<GameID>.cfg` metadata files for every game on your OPL drive (including `ul.cfg` split games) while preserving existing Compatibility Mode & VMC settings. |
| **🛡️ Verify & Hash Check** | File / Folder | Validates ISO9660 `CD001` volume descriptors, sector alignment, `.ZSO` headers (`ZISO`), and `.CHD` headers (`MComprHD`), and computes `CRC32` & `MD5` checksums. |
| **🧹 OPL Drive Cleaner** | OPL Root | Scans an OPL drive to find and remove orphaned artwork in `ART/`, duplicate games across `CD/` & `DVD/`, and leftover `.part` temporary files. |

---

## 🎨 3D WebGL Art Gallery & OPL Config Studio

Accessible directly from the **OPL Art Scraper** preview in the Manual Toolkit:

- **Interactive 3D PS2 Case & Optical Disc**: Rotate and zoom an authentic PlayStation 2 cobalt-blue Amaray DVD case textured with your drive's front cover (`COV`), back cover (`COV2`), spine label (`LAB`), and spinning disc icon (`ICO`).
- **Custom Art Upload & Auto-Resizer**: Click any art slot (`+ COV`, `+ COV2`, `+ LAB`, `+ ICO`, `+ LGO`, `+ BG`) or drag-and-drop any PNG/JPG/WebP image onto the 3D viewport. The app automatically scales and converts it to OPL's exact dimensions (`140×200`, `242×344`, `18×240`, `64×64`, `300×125`, `640×480`) and saves it to `ART/`.
- **Per-Game OPL CFG Editor & Hover Assistant**:
  - Edit `Title`, `Developer`, `Publisher`, `Release Date`, `Genre`, and `Description`.
  - Toggle **OPL Compatibility Modes 1–6** (`Accurate Reads`, `Sync DMA`, `Unhook Syscalls`, `Skip Videos (PSS)`, `Emulate DVD-DL`, `Disable IGR`) with an interactive hover guide that explains the exact symptoms each mode fixes and lists example games.
  - Configure **Virtual Memory Card Slot 1 (`$VMC_0`)** with one-click presets for **Shared Card (`generic_0`)**, **Per-Game Card (`<GameID>_0`)**, or **Physical MC (Blank)**.

---

## 📂 Target OPL Folder Structure

PS2 ISO Manager reads and maintains the standard Open PS2 Loader directory hierarchy:

```text
OPL-Drive-Root/
├── DVD/                    # DVD-5 / DVD-9 games (≥ 700 MB) [.iso / .zso]
├── CD/                     # CD-ROM games (< 700 MB) [.iso / .zso]
├── ART/                    # Per-game artwork (<GameID>_COV.png, _COV2, _LAB, _ICO, _LGO, _BG_00, _SCR_00)
├── CFG/                    # Per-game metadata & compatibility configs (<GameID>.cfg)
├── VMC/                    # Virtual Memory Card images (e.g. generic_0.bin)
├── ul.cfg                  # Index file for FAT32 >4GB split games (auto-managed when FAT32 is detected)
└── ul.<CRC>.<ID>.00..04    # 1 GB USBUtil split chunks on FAT32 drives
```

---

## 🏗️ Project Architecture

```text
PS2-ISO-Manager/
├── ps2_utility/
│   ├── __init__.py         # Package exports
│   └── core.py             # Game ID sector scanner, missing .CUE generator, FAT32 ul.cfg splitter,
│                           # disc verifier (CRC32/MD5), drive filesystem detector, and CFG parser/writer
├── templates/
│   └── index.html          # PS2-themed Tailwind CSS + Three.js WebGL single-page application UI
├── app.py                  # FastAPI backend server, async worker queues, and PyWebView native window launcher
├── app.spec                # PyInstaller build specification for standalone Windows executable
├── PS2.data.json           # Bundled offline PS2 serial, title, publisher, developer, genre & release database
├── bchunk.exe              # External CLI utility for BIN/CUE to ISO track extraction
├── ziso.exe                # External CLI utility for ISO <-> ZSO LZ4 compression/decompression
├── chdman.exe              # External CLI utility for MAME CHD to ISO/BIN extraction
├── app_icon.ico            # Application icon
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.10+** (for running from source or building the executable)
2. **Bundled CLI Binaries** in the project root directory:
   - `bchunk.exe` — Converts `.bin`/`.cue` tracks to `.iso`
   - `ziso.exe` — Compresses `.iso` to `.zso` and decompresses `.zso` to `.iso`
   - `chdman.exe` — Extracts `.chd` images to `.iso` / `.bin`

### Running from Source (Development)

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the desktop application
python app.py
```

### Building the Standalone Windows Executable (`.exe`)

Package the entire application—including the FastAPI backend, PyWebView window, offline `PS2.data.json` database, and CLI binaries (`bchunk.exe`, `ziso.exe`, `chdman.exe`)—into a single portable executable:

```powershell
.\.venv\Scripts\pyinstaller.exe app.spec --noconfirm
```

The standalone executable will be output to:
```text
dist/PS2-ISO-Manager.exe
```

---

## 🙏 Credits & Attributions

- **[Open PS2 Loader (OPL)](https://github.com/ps2homebrew/Open-PS2-Loader)** — The open-source PlayStation 2 game loader platform.
- **[Luden02 OPL Art Database](https://github.com/Luden02/psx-ps2-opl-art-database)** & **[xlenore ps2-covers](https://github.com/xlenore/ps2-covers)** — Community PlayStation 2 cover, disc, logo, and backdrop repositories.
- **ZSO Compression (`ziso`)** — LZ4-based compressed ISO format developed for OPL.
- **`bchunk` & MAME `chdman`** — Optical disc track conversion and Compressed Hunks of Data extraction tools.
- **[Three.js](https://threejs.org/)** — Powers the interactive 3D WebGL PS2 game case and rotating disc preview.

---

## 📄 License

Distributed under the **MIT License**. Contributions, issues, and feature requests are welcome!
