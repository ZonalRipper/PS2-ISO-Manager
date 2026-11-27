# 🫧 PS2 ISO Manager — Release v2.1

Welcome to **PS2 ISO Manager v2.1**! Building on the v2.0 **Liquid Glass GUI Layout**, this release adds a **Built-in GitHub Auto-Updater** with one-click verified executable replacement and a **Safe Format Drive to PS2 APA / PFS** tool—all bundled inside a single standalone Windows executable (`PS2-ISO-Manager.exe`).

---

## ✨ What's New in v2.1

### 🔄 Built-in GitHub Auto-Updater
Stay up to date automatically without manually hunting for new builds:
- **Quiet Startup Update Check:** Checks `ZonalRipper/PS2-ISO-Manager` GitHub Releases cleanly in the background on launch (fails silently if offline) and reveals a glowing **`⬆️ Update vX.X`** badge in the sidebar footer when a newer version is available.
- **Manual Check Anytime:** Click **`ℹ️ Info → 🔄 Check for Updates`** to check on demand.
- **Liquid Glass Update Modal:** Shows your current vs. latest version, release date, file size, and full GitHub release notes right inside the app.
- **Verified Download & Safe Self-Replace:** Streams `PS2-ISO-Manager.exe` with a live progress bar, verifies the Windows PE (`MZ`) header, exact byte size, and optional `.sha256` checksum (strictly over trusted GitHub HTTPS domains), safely swaps the executable with automatic `.bak` rollback protection, and relaunches automatically.

---

### 🔥 Format Drive to PS2 APA / PFS Tool
Initialize new or repurposed hard drives for internal PlayStation 2 use right from **Internal PS2 HDD → 🔥 Format Drive to PFS**:
- **Hardware-Aware Disk Scanner:** Enumerates physical drives with hardware model, bus type (`USB`, `SATA`, `NVMe`), capacity, mounted Windows drive letters, and current partition layout (`RAW`, `MBR`, `GPT`, or `PS2 APA`).
- **Multi-Layer Safety Guardrails:** Automatically locks and blocks **Windows OS / System / Boot disks**, **Read-Only disks**, empty media, and drives exceeding the **2 TB PS2 APA limit** (advising `exFAT` instead). Requires Windows Administrator privileges plus an exact typed confirmation (`FORMAT hddN:`).
- **One-Shot Setup Pipeline:** Optionally clears existing Windows partitions (`diskpart clean`) to release volume locks, initializes the PlayStation 2 APA partition table (`pfsshell initialize yes`), creates & formats a **`+OPL`** PFS partition (`128 MB`–`2 GB`) pre-populated with `ART/`, `CFG/`, `VMC/`, `CHT/`, `THM/`, and `APPS/`, verifies the result, and lets you jump straight into the **PFS Drive Browser**.

---

## 🫧 Also Included (v2.0 Liquid Glass Suite)
- **Liquid Glass GUI Layout:** Dark Glass & Light Frost themes, clearly separated frosted glass sidebar sections (**Guided Setup**, **USB / exFAT / SMB**, **Internal PS2 HDD**, **Local Disc Tools**), smooth GPU-accelerated transitions, and jitter-free OPL Config Compatibility Mode & VMC hover guides.
- **USB / exFAT / FAT32 / SMB Drive Browser:** Auto-detected USB & network drives, direct SMB UNC path support (`\\SERVER\PS2SMB`), game list (`DVD/`, `CD/`, `ul.cfg`), full file explorer, OPL folder setup, and quick tool launchers.
- **Internal PS2 HDD (APA / PFS) Support & PFS Drive Browser:** Full `hdl_dump` & `pfsshell` integration with UAC elevation, HDL game management, `+OPL` explorer, and full Art/CFG/Cleaner/3D Gallery parity.
- **7-Step Guided Auto Pilot Wizard & 3D WebGL Cover Art Studio:** Automated `.BIN/.CUE` (auto-CUE recovery), `.CHD`, `.ZSO`, `FAT32 >4GB` (`ul.cfg`) splitting, 6-piece OPL art scraping, and interactive 3D case inspection.

---

## 📦 Installation & Usage (Standalone Windows `.exe`)
1. Download **`PS2-ISO-Manager.exe`** from the Assets section below *(and optionally verify against `PS2-ISO-Manager.exe.sha256`)*.
2. Double-click `PS2-ISO-Manager.exe` to launch—no Python installation or external dependencies required.
3. *(For APA / PFS internal PS2 hard drives)* Run as Administrator—or click the **Standard User → Elevate** pill in the sidebar footer.

---

## 🙏 Credits & Attributions
- **Open PS2 Loader (OPL)** — Open-source PlayStation 2 game loader.
- **hdl_dump (`ps2homebrew/hdl-dump` — The W1zard 0f 0z & AKuHAK)** — APA/HDL internal PS2 HDD installer & TOC utility.
- **pfsshell (`ps2homebrew/pfsshell` — uyjulian, Wizard of Oz & `ps2sdk`)** — PFS partition shell and APA/PFS/iomanX libraries.
- **Luden02 OPL Art Database** & **xlenore ps2-covers** — Community PlayStation 2 artwork repositories.
- **`ziso`, `bchunk`, MAME `chdman`, & Three.js** — Disc compression, conversion, extraction, and 3D case rendering.
