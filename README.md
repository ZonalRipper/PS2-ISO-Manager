# 🎮 PS2 ISO Manager v2.1 — Open PS2 Loader (OPL) Suite

![Version](https://img.shields.io/badge/Version-2.1-0ea5e9?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0051cc?style=for-the-badge&logo=windows)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Three.js](https://img.shields.io/badge/3D%20Gallery-Three.js%20WebGL-000000?style=for-the-badge&logo=threedotjs&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-10b981?style=for-the-badge)

A modern desktop utility built with **FastAPI**, **PyWebView**, **Tailwind CSS**, and **Three.js** to convert, rename, compress, verify, browse, and organize PlayStation 2 game libraries for **Open PS2 Loader (OPL)** across **USB, exFAT/FAT32 drives, SMB network shares, and Internal PS2 HDDs (APA / PFS)**.

Featuring the **Liquid Glass GUI** with Dark Glass & Light Frost themes, a drive-format categorized sidebar, interactive USB/SMB & APA/PFS drive browsers, a 7-step Auto Pilot Wizard, safe APA/PFS drive formatting, built-in **GitHub Auto-Updater**, and an interactive **3D WebGL Amaray DVD Case & OPL Config Studio**.

---

## ✨ Key Highlights

- **🫧 Liquid Glass GUI Layout**: Frosted translucent surfaces, Dark Glass / Light Frost theme switcher, smooth fluid transitions, and a categorized left sidebar organized by workflow & drive format (**Guided Setup**, **USB / exFAT / SMB**, **Internal PS2 HDD (APA / PFS)**, and **Local Disc Tools**).
- **⚡ 7-Step Guided Auto Pilot Wizard**: Turn a folder of raw downloads or disc rips (`.iso`, `.zso`, `.bin/.cue`, `.chd`) into a clean, named, compressed, artwork-populated OPL USB/SMB drive or APA/PFS internal PS2 HDD.
- **💾 USB / exFAT / FAT32 / SMB Drive Browser**: Auto-detects mounted USB & mapped network drives, supports direct UNC SMB paths (`\\SERVER\PS2SMB`), lists `DVD/`, `CD/`, and FAT32 `ul.cfg` games, manages OPL folders, previews artwork, and edits per-game `CFG` files directly.
- **💽 Internal PS2 HDD (APA / PFS) Support & PFS Drive Browser**: Built-in `hdl_dump` and `pfsshell` integration with 1-click UAC elevation to install/rename/delete HDL games, browse `+OPL` files, create `+OPL` partitions, scrape art, generate CFGs, and clean orphaned artwork directly on APA-formatted PS2 hard drives.
- **🩹 Auto-Recreates Missing `.CUE` Files & Full `.CHD` / `.ZSO` Support**: Automatically regenerates missing `.cue` sheets from `.bin` sector headers, extracts `.chd` dumps, compresses `.iso` to `.zso` (saving 25–40% space), and automatically splits `>4 GB` ISOs into `1 GB` USBUtil (`ul.cfg`) chunks on `FAT32` drives.
- **🎨 3D WebGL Cover Art Gallery & OPL Config Studio**: Inspect your USB/SMB or Internal HDD library in a rotatable 3D PlayStation 2 DVD case with spinning disc, drag-and-drop custom art auto-resizing, and edit **Compatibility Modes 1–6** & **Virtual Memory Card (`$VMC_0`)** presets with smooth hover guides.
- **🔄 Built-in GitHub Auto-Updater**: Quietly checks GitHub Releases on startup (or manually from **Info → Check for Updates**), displays release notes, downloads and verifies the new `PS2-ISO-Manager.exe` (PE header, byte size, and optional `.sha256` checksum), safely swaps the executable with rollback protection, and relaunches automatically.

---

## 🧭 Navigation & Workflows

### 1. Guided Setup — Auto Pilot Wizard
Walks through your batch library setup step by step with clickable progress tracking, saved preferences, and a **`⚡ Skip to Review`** shortcut:
1. **Source Folder** — Scans `.iso`, `.zso`, `.bin`, and `.chd` files with format & size breakdown.
2. **Destination Drive** — Target **USB / exFAT / FAT32 / SMB** folders or **Internal PS2 HDD (APA / PFS)** drives.
3. **BIN / CHD Cleanup** — Choose whether to keep or clean up original `.bin/.cue`/`.chd` files after verified `.iso` conversion.
4. **Standardize Names & Game ID** — Match against the bundled 13,000+ offline PS2 database (`PS2.data.json`) with live filename preview.
5. **Storage & FAT32 Handling** — Compress to `.ZSO` or keep `.ISO`, with automatic `FAT32 >4GB` (`ul.cfg`) splitting (or raw HDL `.ISO` partitions on APA/PFS).
6. **OPL Artwork & Metadata** — Automatically scrape 6-piece OPL artwork (`ART/`) and generate per-game `CFG/<GameID>.cfg` files.
7. **Review Queue & Launch** — Inspect per-file execution plans, select/deselect items, and monitor live progress.

### 2. USB / exFAT / SMB Tools
- **💾 USB / SMB Browser:** Browse installed games (`DVD/`, `CD/`, `ul.cfg`), explore/upload/download/rename/delete files, inspect OPL folders, preview artwork, and jump straight into per-game CFG editing or 3D Gallery.
- **🖼️ OPL Art Scraper / 📝 OPL CFG Generator / 🧹 OPL Drive Cleaner / 🎨 3D Cover Gallery**

### 3. Internal PS2 HDD (APA / PFS) Tools
- **💽 PFS Drive Browser:** View installed HDL games (rename, delete, edit CFG), browse `+OPL` and other PFS partitions (upload/download/mkdir/preview/delete), inspect APA partitions, and create a 256 MB `+OPL` partition in one click.
- **🔥 Format Drive to PFS:** Safely initialize a non-OS physical drive (up to 2 TB) to PlayStation 2 APA with automatic OS/Boot disk protection, typed `FORMAT hddN:` confirmation, optional `diskpart clean`, and automated `+OPL` partition (`128 MB`–`2 GB`) + `ART/CFG/VMC/CHT/THM/APPS` folder setup.
- **🖼️ PFS Art Scraper / 📝 PFS CFG Generator / 🧹 PFS Drive Cleaner / 🎨 PFS 3D Gallery**

### 4. Local Disc Tools (PC Files)
- **🏷️ Standardize Names** • **💿 Convert BIN / CHD** • **🗜️ Compress to .ZSO** • **📦 Decompress .ZSO** • **🛡️ Verify & Hash Check (`CRC32` & `MD5`)**

---

## 📂 Target OPL Folder Structure

```text
OPL-Drive-Root/
├── DVD/                    # DVD-5 / DVD-9 games (≥ 700 MB) [.iso / .zso]
├── CD/                     # CD-ROM games (< 700 MB) [.iso / .zso]
├── ART/                    # Per-game artwork (<GameID>_COV.png, _COV2, _LAB, _ICO, _LGO, _BG_00, _SCR_00)
├── CFG/                    # Per-game metadata & compatibility configs (<GameID>.cfg)
├── VMC/                    # Virtual Memory Card images (e.g. generic_0.bin)
├── ul.cfg                  # Index file for FAT32 >4GB split games (auto-managed on FAT32)
└── ul.<CRC>.<ID>.00..04    # 1 GB USBUtil split chunks on FAT32 drives
```

---

## 🏗️ Project Architecture

```text
PS2-ISO-Manager/
├── ps2_utility/
│   ├── __init__.py         # Package exports
│   ├── core.py             # Game ID sector scanner, missing .CUE generator, FAT32 ul.cfg splitter,
│   │                       # disc verifier (CRC32/MD5), drive filesystem detector, and CFG parser/writer
│   ├── pfs.py              # APA/PFS drive detection, safe formatter, HDL TOC manager, and pfsshell bridge
│   └── updater.py          # GitHub Releases version checker, verified EXE downloader, and self-updater
├── templates/
│   └── index.html          # Liquid Glass Tailwind CSS + Three.js WebGL single-page application UI
├── app.py                  # FastAPI backend server, USB/SMB & PFS APIs, async workers, PyWebView launcher
├── app.spec                # PyInstaller build specification for standalone Windows executable
├── PS2.data.json           # Bundled offline 13,000+ PS2 title & metadata database
├── bchunk.exe              # External CLI utility for BIN/CUE to ISO track extraction
├── ziso.exe                # External CLI utility for ISO <-> ZSO LZ4 compression/decompression
├── chdman.exe              # External CLI utility for MAME CHD to ISO/BIN extraction
├── hdl_dump.exe            # External CLI utility for PS2 APA/HDL internal HDD installation & TOC
├── pfsshell.exe            # External CLI utility for PS2 PFS (+OPL) partition file operations
├── app_icon.ico            # Application icon
├── requirements.txt        # Python dependencies
├── RELEASE_NOTES.md        # Release changelog
└── README.md               # Project documentation
```

---

## 🚀 Getting Started

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

Precompiled Windows executables are available in GitHub Releases. To build locally with all tools and databases bundled:

```powershell
.\.venv\Scripts\pyinstaller.exe app.spec --noconfirm
```

Output: `dist/PS2-ISO-Manager.exe`

---

## 🙏 Credits & Attributions

- **[Open PS2 Loader (OPL)](https://github.com/ps2homebrew/Open-PS2-Loader)** — The open-source PlayStation 2 game loader platform.
- **[hdl_dump (`ps2homebrew/hdl-dump`)](https://github.com/ps2homebrew/hdl-dump)** — Created by The W1zard 0f 0z & revisited by AKuHAK; powers APA/HDL internal PS2 HDD game installation and management.
- **[pfsshell (`ps2homebrew/pfsshell`)](https://github.com/ps2homebrew/pfsshell)** — Maintained by uyjulian (originally by Wizard of Oz, powered by `ps2sdk`); enables browsing and managing `+OPL` PFS partitions on Windows.
- **[Luden02 OPL Art Database](https://github.com/Luden02/psx-ps2-opl-art-database)** & **[xlenore ps2-covers](https://github.com/xlenore/ps2-covers)** — Community PlayStation 2 cover, disc, logo, and backdrop repositories.
- **ZSO Compression (`ziso`)** — LZ4-based compressed ISO format developed for OPL.
- **`bchunk` & MAME `chdman`** — Optical disc track conversion and Compressed Hunks of Data extraction tools.
- **[Three.js](https://threejs.org/)** — Powers the interactive 3D WebGL PS2 game case and rotating disc preview.

---

## 📄 License

Distributed under the **MIT License**. Contributions, issues, and feature requests are welcome!
