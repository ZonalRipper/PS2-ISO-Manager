# 🫧 PS2 ISO Manager — Release v2.0 (New GUI Layout)

Welcome to **PS2 ISO Manager v2.0**! This landmark release introduces a ground-up **Liquid Glass GUI Layout**, a categorized sidebar organized by **drive format**, a brand-new **USB / exFAT / FAT32 / SMB Drive Browser**, smooth GPU-accelerated animations throughout, and full **Internal PS2 HDD (APA / PFS)** management—all bundled inside a single standalone Windows executable (`PS2-ISO-Manager.exe`).

---

## ✨ What's New in v2.0

### 🫧 New Liquid Glass GUI Layout (Now Default)
- **Modern Translucent Glass Aesthetic:** Multi-layered frosted glass surfaces with specular rim highlights, drifting ambient light orbs, and a one-click **Dark Glass / Light Frost** theme switcher in the sidebar footer.
- **Categorized Left Sidebar by Workflow & Drive Format:** Clearly separated frosted glass category cards with color-coded header bars and format badges so you always know which tool targets which drive type:
  - **Guided Setup (`WIZARD`):** 7-Step Auto Pilot Wizard for all drive formats.
  - **USB / exFAT / SMB (`FOLDER`):** USB / SMB Browser, OPL Art Scraper, OPL CFG Generator, OPL Drive Cleaner, and 3D Cover Gallery.
  - **Internal PS2 HDD (`APA / PFS`):** PFS Drive Browser, PFS Art Scraper, PFS CFG Generator, PFS Drive Cleaner, and PFS 3D Gallery.
  - **Local Disc Tools (`PC FILES`):** Standardize Names, Convert BIN / CHD, Compress to `.ZSO`, Decompress `.ZSO`, and Verify & Hash Check.
- **Smooth, Fluid Animations:** Tactile sidebar hover & active glow indicators, glossy sheen button highlights, smooth view & tool transitions, directional forward/backward wizard step slides, browser tab reveals, and spring-animated modals & Lightbox previews (respecting `prefers-reduced-motion`).
- **Dynamic Window-Responsive Design:** Scales seamlessly from compact split-screen windows (`700×540` minimum) up to maximized 1080p/1440p/4K displays, with a collapsible mobile/narrow sidebar drawer and `ResizeObserver`-backed 3D WebGL viewport.

---

### 💾 New USB / exFAT / FAT32 / SMB Drive Browser
Full interactive drive & file management for folder-based OPL setups, mirroring the Internal PS2 HDD browser:
- **Auto-Detected Drives & Direct SMB UNC Support:** Scans connected removable USB drives, mapped network shares, and local drives with filesystem type (`exFAT`, `FAT32`, `NTFS`, `SMB`), free space HUD, and `★ OPL` indicators—plus a folder picker and direct path bar for UNC network shares (e.g. `\\192.168.1.50\PS2SMB`).
- **🎮 Games on Drive Tab:** Lists all games across `DVD/`, `CD/`, and FAT32 `ul.cfg` split games with Game ID, media/format badges, `✓ ART` & `✓ CFG` status pills, plus one-click **`⚙️ CFG`** editing, **`✏️ Rename`**, and **`🗑️ Delete`**.
- **📂 File Explorer Tab:** Full directory navigation with clickable breadcrumbs, OPL quick-jump pills (`Root`, `DVD`, `CD`, `ART`, `CFG`, `VMC`, `CHT`, `THM`, `APPS`), folder creation, file upload/download, image Lightbox preview, direct `.cfg` editing, rename, and delete.
- **🗂️ OPL Folders Tab & One-Click Setup:** Inspect item counts and sizes for every standard OPL directory and create any missing OPL folders in one click.
- **Quick Tool Integration:** Jump directly into **Scrape Art**, **Generate CFGs**, **Clean Orphans**, or the **3D Cover Gallery** pre-loaded with the active USB/SMB drive.

---

### 💽 Internal PS2 HDD (APA / PFS) Support & PFS Drive Browser
Manage classic APA/PFS-formatted PlayStation 2 internal hard drives directly over SATA or a USB-to-SATA adapter:
- **Built-in UAC Admin Elevation:** Live sidebar privilege status pill with one-click **Restart as Administrator**.
- **Auto Pilot APA / PFS Injection Pipeline:** Automatically skips `.ZSO` compression / FAT32 splitting, decompresses `.ZSO` sources as needed, skips already-installed Game IDs, injects CD/DVD games via `hdl_dump` (without leaving `info.sys` files behind), and batch-uploads `ART/` & `CFG/` into `+OPL` via `pfsshell`.
- **Inline PFS Drive Browser:** Search, rename, delete, and edit CFGs for installed HDL games; browse/upload/download/preview files inside `+OPL` and other PFS partitions; inspect APA partitions; and create a 256 MB `+OPL` partition in one click.
- **Full Toolkit & 3D Gallery Parity:** Dedicated PFS Art Scraper, PFS CFG Generator, PFS Drive Cleaner, and PFS 3D Cover Gallery with live `+OPL/ART` sync and custom art upload.

---

### ⚙️ Polished OPL Config Studio & Guided Wizard
- **Silky-Smooth Compatibility Mode & VMC Hover Guides:** Eliminated layout-shift jitter when hovering Compatibility Modes 1–6 or Virtual Memory Card (`$VMC_0`) options with a fixed-height guide panel, debounced hover transitions, and keyboard focus support.
- **7-Step Guided Auto Pilot Wizard:** Clear step-by-step configuration with saved preferences, live filename previews, clickable review summary tiles, and a **`⚡ Skip to Review`** shortcut.
- **Codebase Cleanup:** Promoted Liquid Glass as the single unified UI (`templates/index.html`) and removed legacy template code, temporary preview routes/flags, and unused imports.

---

## 📦 Installation & Usage (Standalone Windows `.exe`)
1. Download **`PS2-ISO-Manager.exe`** from the Assets section below.
2. Double-click `PS2-ISO-Manager.exe` to launch—no Python installation or external dependencies required.
3. *(For APA / PFS internal PS2 hard drives)* Run as Administrator—or click the **Standard User → Elevate** pill in the sidebar footer.

---

## 🙏 Credits & Attributions
- **Open PS2 Loader (OPL)** — Open-source PlayStation 2 game loader.
- **hdl_dump (`ps2homebrew/hdl-dump` — The W1zard 0f 0z & AKuHAK)** — APA/HDL internal PS2 HDD installer & TOC utility.
- **pfsshell (`ps2homebrew/pfsshell` — uyjulian, Wizard of Oz & `ps2sdk`)** — PFS partition shell and APA/PFS/iomanX libraries.
- **Luden02 OPL Art Database** & **xlenore ps2-covers** — Community PlayStation 2 artwork repositories.
- **`ziso`, `bchunk`, MAME `chdman`, & Three.js** — Disc compression, conversion, extraction, and 3D case rendering.
