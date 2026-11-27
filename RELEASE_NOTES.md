# 🫧 PS2 ISO Manager — Release v2.1.1

**PS2 ISO Manager v2.1.1** is a maintenance & reliability patch fixing the Windows standalone self-updater so automatic GitHub updates cleanly replace the executable and relaunch the app.

---

## 🛠️ What's Fixed in v2.1.1
- **Fixed Windows Auto-Updater Self-Replace & Relaunch:**
  - Replaced the legacy hidden `cmd.exe` swap helper (where `DETACHED_PROCESS | CREATE_NO_WINDOW` and `timeout` caused the updater script to exit before replacing the `.exe`) with a hidden **PowerShell** updater using clean Win32 process flags (`CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`) and `Start-Sleep`.
  - Now waits cleanly for both the Python app process and the PyInstaller parent bootloader to exit, retries file replacement with exact byte-size verification and automatic `.bak` rollback, clears inherited PyInstaller environment variables (`_MEIPASS2` / `_PYI_*`) before relaunching, and writes diagnostics to `%TEMP%\ps2_iso_mgr_update.log`.
- **Single-Source Version Wiring:** Unified the version display across the window title, Liquid Glass sidebar, Info modal, and updater from `APP_VERSION`.

---

## 📦 Installation & Usage (Standalone Windows `.exe`)
1. Download **`PS2-ISO-Manager.exe`** from the Assets section below *(and optionally verify against `PS2-ISO-Manager.exe.sha256` using `Get-FileHash .\PS2-ISO-Manager.exe -Algorithm SHA256`)*.
2. Double-click `PS2-ISO-Manager.exe` to launch—no Python installation or external dependencies required.
3. **Windows SmartScreen Note:** Until open-source code signing via SignPath Foundation is active, Windows may show *"Windows protected your PC"* on first run. Click **More info → Run anyway** (or verify the SHA-256 checksum / build from source).
4. *(If updating from an older build before v2.1's fixed updater, replace `PS2-ISO-Manager.exe` manually once—all future updates will apply and restart automatically!)*

---

## ✨ Highlights from v2.0 / v2.1
- **🫧 Liquid Glass GUI Layout:** Dark Glass & Light Frost themes, separated frosted glass sidebar categories, and smooth animations.
- **🔄 Built-in GitHub Auto-Updater:** Quiet startup checks, release notes preview, PE + size + SHA-256 verification, and automatic self-replace & relaunch.
- **🔥 Format Drive to PS2 APA / PFS:** Safe physical disk formatting with OS/Boot/Read-Only/`>2 TB` protection, typed `FORMAT hddN:` confirmation, `diskpart clean`, and automated `+OPL` setup.
- **💾 USB / exFAT / FAT32 / SMB Drive Browser & 💽 PFS Drive Browser:** Full game management, file explorer, OPL CFG editor with smooth hover guides, and 3D WebGL Cover Art Studio.
