# 🎮 PS2 ISO Manager — Official Release v1.00

Welcome to **PS2 ISO Manager v1.00**, an all-in-one desktop suite for preparing, converting, compressing, naming, verifying, and customizing PlayStation 2 game libraries for **Open PS2 Loader (OPL)**.

This release packages the entire application—including the offline 11,000+ PS2 title & metadata database (`PS2.data.json`), 3D WebGL Cover Art & Config Studio, and conversion binaries (`bchunk`, `ziso`, `chdman`)—into a single standalone Windows executable (`PS2-ISO-Manager.exe`).

---

## ✨ Highlights in v1.00

### ⚡ 1-Click Auto Pilot Queue (5-Stage Automated Pipeline)
Drop a folder of raw downloads or disc rips into **Step 1 (Source)** and select your OPL USB, exFAT/FAT32 drive, HDD, or SMB folder in **Step 2 (Destination)**:
1. **Format Conversion (`BIN/CUE` & `CHD` → `ISO`)**: Automatically converts multi-track `.bin/.cue` and `.chd` disc images into standard PS2 `.iso` files.
2. **Automatic Missing `.CUE` Recreation**: If a `.bin` file is missing its `.cue` sheet, the engine inspects the binary sector headers (`MODE2/2352`, `MODE1/2352`, `MODE1/2048`), recreates the `.cue` file automatically, and proceeds with conversion.
3. **Internal Disc Sector Game ID Scan & Naming**: Reads `SYSTEM.CNF` directly from the disc image to detect the official Sony serial (`SLUS`, `SLES`, `SCUS`, `SCES`, `SLPS`, etc.) and renames messy files to their clean official title (`God of War [SCUS-97399].iso`).
4. **ZSO Compression & Automatic `FAT32 >4GB` Splitting (`ul.cfg`)**:
   - Compresses `.iso` files into OPL-compatible `.zso` format (saving **25%–40%** drive space) with live storage-saved statistics.
   - Automatically detects `FAT32` destination drives and splits uncompressed ISOs over 4 GB into `1 GB` USBUtil chunks (`ul.<CRC>.<ID>.00`) with a valid 64-byte `ul.cfg` index.
5. **Smart OPL Routing, 6-Piece Artwork & `CFG` Generation**:
   - Builds the standard OPL directory structure (`DVD/`, `CD/`, `ART/`, `CFG/`) and routes `< 700 MB` games to `CD/` and `≥ 700 MB` games to `DVD/` using safe `.part` atomic transfers.
   - Scrapes missing OPL artwork (`COV`, `COV2`, `LAB`, `ICO`, `LGO`, `BG`, `SCR`) into `ART/`.
   - Generates per-game `CFG/<GameID>.cfg` metadata files (`Title`, `Publisher`, `Developer`, `Genre`, `Release Date`) for OPL's Game Info page.

---

### 🛠️ 8-Tool Manual Toolkit
Need granular control over a single file or an existing OPL drive? Switch to the **Manual Toolkit** tab for 8 dedicated utilities with per-tool state memory, live search, status filtering, and row checkboxes:
- **🏷️ Standardize Name**: Batch-rename `.iso`, `.zso`, and `.chd` files using internal disc Game IDs.
- **💿 Convert BIN / CHD**: Convert `.bin`/`.cue` (with automatic missing `.cue` regeneration) and `.chd` dumps into `.iso`.
- **🗜️ Compress to ZSO**: Compress `.iso` games into `.zso` with exact storage savings summaries.
- **📦 Decompress ZSO**: Restore `.zso` archives back into uncompressed `.iso` images.
- **🖼️ OPL Art Scraper**: Audit existing drive artwork (`Full Set`, `Partial`, `Missing`) and scrape missing assets.
- **📝 OPL CFG Generator**: Batch-create or update `CFG/*.cfg` metadata files across your entire OPL drive while preserving custom compatibility modes.
- **🛡️ Verify & Hash Check**: Validate ISO9660 `CD001` volume descriptors, sector alignment, `.ZSO` headers, and `.CHD` headers, and compute `CRC32` & `MD5` checksums.
- **🧹 OPL Drive Cleaner**: Find and clean up orphaned artwork in `ART/`, duplicate games across `CD/` & `DVD/`, and leftover `.part` temp files.

---

### 🎨 Interactive 3D WebGL Art Gallery & OPL Config Studio
- **360° 3D PS2 Amaray Cobalt-Blue Case & Spinning Disc**: Preview your OPL library's front cover (`COV`), back cover (`COV2`), spine label (`LAB`), spinning disc icon (`ICO`), logo (`LGO`), and backdrop (`BG`) in real time.
- **Drag-and-Drop Custom Art Uploader (Auto-Resizes)**: Drop any PNG/JPG/WebP image onto the 3D viewport or click any art slot button—images are automatically scaled to OPL's exact pixel specifications (`140×200`, `242×344`, `18×240`, `64×64`, `300×125`, `640×480`) and saved to `ART/`.
- **Per-Game OPL `CFG` Editor with Interactive Mode & VMC Guides**:
  - Edit game metadata (`Title`, `Developer`, `Publisher`, `Release Date`, `Genre`, `Description`).
  - Toggle **OPL Compatibility Modes 1–6** (`Accurate Reads`, `Sync DMA`, `Unhook Syscalls`, `Skip Videos (PSS)`, `Emulate DVD-DL`, `Disable IGR`) with built-in hover helpers explaining what symptoms each mode fixes and which games need them.
  - Configure **Virtual Memory Card Slot 1 (`$VMC_0`)** with one-click presets for **Shared (`generic_0`)**, **Per-Game (`<GameID>_0`)**, or **Physical Memory Card**.

---

### 🕹️ Authentic PlayStation 2 / Retro OPL Interface
- **PS2 BIOS "Seven Towers & Ocean Nebula" Theme**: Inspired by the original PlayStation 2 System Configuration screen and fat PS2 hardware shell grooves.
- **DualShock 2 Button Prompts (`△ ○ × □`) & Toggleable CRT Scanlines**: Includes a header toggle (`📺 CRT: ON/OFF`) and automatic persistence of your recent folders and checkbox preferences.

---

## 📦 Installation & Usage (Standalone Windows `.exe`)
1. Download **`PS2-ISO-Manager.exe`** from the Assets section below.
2. Double-click `PS2-ISO-Manager.exe` to launch—no Python installation or external dependencies required.
