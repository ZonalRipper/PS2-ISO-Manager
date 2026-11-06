# Copilot instructions for PS2 ISO Manager

## Running the application

This is a Windows desktop application built with Tkinter. From the repository root:

```powershell
python -m pip install -r requirements.txt
python main.py
```

There is no configured build system, test runner, or linter in this repository. For a focused syntax check of one module, use:

```powershell
python -m py_compile ps2_utility\ui.py
```

To check all Python modules without launching the GUI:

```powershell
python -m py_compile main.py ps2_utility\core.py ps2_utility\ui.py ps2_utility\viewer.py
```

The GUI requires a working desktop session. Functional testing should use disposable copies of ISO/ZSO/CHD files and an OPL test directory because conversion and cleanup options can rename, create, or delete files.

## Architecture

- [`main.py`](../main.py) is only the application entry point. It creates `tk.Tk`, instantiates `PSToolkitApp`, and starts `mainloop()`.
- [`ps2_utility/ui.py`](../ps2_utility/ui.py) contains the `PSToolkitApp` and almost all application behavior:
  - six tabs expose BIN/CUE to ISO, rename, ZSO compression, CHD compression, ZSO extraction, and OPL drive/art workflows;
  - `queued_files`, `opl_files`, and `file_cache` are the in-memory state shared by the tabs;
  - long-running scans, downloads, and conversions run in daemon worker threads;
  - worker threads must update Tk widgets through `root.after(...)`, not directly;
  - conversions invoke external Windows executables with `subprocess.Popen` and store the active process in `self.active_process` for cancellation/close handling.
- [`ps2_utility/core.py`](../ps2_utility/core.py) contains shared filesystem/resource helpers, PS2 game-ID extraction, and human-readable size formatting. The ID extractor first scans the first 15 MiB of a file and then falls back to the filename.
- [`ps2_utility/viewer.py`](../ps2_utility/viewer.py) builds a temporary HTML file containing a Three.js WebGL viewer and opens it in the default browser. It reads OPL art from the selected target's `ART` directory and embeds images as base64 data.

## Runtime files and external tools

These files are resolved relative to the application root via `resource_path(...)` or the current working directory:

- `PS2.data.json` is optional local title metadata. Its keys are normalized game IDs and each record should provide a `title`; missing/invalid data leaves titles as `Unknown Title`.
- `bchunk.exe` is required for BIN/CUE conversion.
- `ziso.exe` is required for ISO/ZSO compression and ZSO extraction.
- `chdman.exe` is required for CHD compression. The code selects `createcd` for CD-sized or `/CD/` paths and `createdvd` otherwise.

The OPL workflow expects a selected target containing (or able to receive) `DVD`, `CD`, `ART`, `CFG`, and `VMC` directories. Art is downloaded from the `Luden02/psx-ps2-opl-art-database` GitHub repository using the detected raw game ID. The 3D viewer also depends on browser access to the pinned Three.js CDN scripts.

## Important conventions

- Keep the Tkinter event loop responsive: put filesystem walks, file-header scans, subprocess execution, and network downloads in worker threads, then marshal progress/status/tree changes back with `root.after`.
- Preserve the cancellation protocol: workers check `self.cancel_requested`, subprocess helpers assign/clear `self.active_process`, and UI actions are enabled/disabled by `start_progress` and `stop_progress`.
- Use the existing ID representation consistently. `clean_id` is the normalized lookup key; `raw_id` preserves the `XXYY_###.##`-style form used in filenames, OPL art names, and display text. Use the existing helpers instead of adding another parser.
- New queue entries should be reflected through `cache_file_info(...)` and the relevant `populate_*_tree` method so all tabs see consistent IDs, sizes, and status values.
- File operations are intentionally user-selectable: rename can be in-place or copy-only, and compression/extraction can delete originals. Preserve these flags and existing collision checks when changing batch workflows.
- UI callbacks may be invoked from background work only through `root.after`; keep modal dialogs and all direct widget access on the Tk main thread.
- Use `resource_path(...)` for bundled/runtime assets so PyInstaller-style `_MEIPASS` execution remains supported.
- Keep the browser viewer's generated HTML self-contained except for its existing Three.js CDN dependencies, and continue writing it to the system temporary directory rather than the repository.
