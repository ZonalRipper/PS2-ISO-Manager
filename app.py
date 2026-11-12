import os
import re
import sys
import glob
import socket
import subprocess
import urllib.request
import json
import asyncio
import uuid
import threading
import time
import shutil
import base64
import urllib.parse
import tkinter as tk
from tkinter import filedialog
from typing import List, Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

from ps2_utility.core import (
    extract_game_id,
    format_size,
    resource_path,
    get_drive_info,
    split_iso_to_ul,
    read_ul_cfg_ids,
    verify_disc_image,
    read_opl_cfg,
    write_opl_cfg,
    detect_bin_track_mode,
    generate_cue_for_bin,
)

# Redirect stdout/stderr when running as a windowed PyInstaller executable (console=False)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

app = FastAPI(title="PS2 ISO Manager Web")
templates = Jinja2Templates(directory=resource_path("templates"))

# --- Load GameDB in memory ---
game_db = {}
game_meta_db = {}
db_path = resource_path("PS2.data.json")
if os.path.exists(db_path):
    try:
        with open(db_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            for raw_id, game_info in data.items():
                if not isinstance(game_info, dict):
                    continue
                game_title = (game_info.get("title") or "").strip()
                clean_key = raw_id.replace('_', '').replace('-', '').replace('.', '').replace(' ', '').upper()
                if clean_key and game_title:
                    game_db[clean_key] = game_title
                    game_meta_db[clean_key] = game_info
        print(f"[SYSTEM] Loaded {len(game_db)} titles from local database.")
    except Exception as e:
        print(f"[ERROR] Failed to parse database: {e}")


def format_meta_field(value, default: str) -> str:
    """Normalize string or list metadata fields from PS2.data.json."""
    if isinstance(value, list):
        cleaned = [str(v).strip().rstrip('.') for v in value if str(v).strip()]
        return ", ".join(cleaned) if cleaned else default
    if isinstance(value, str) and value.strip():
        return value.strip().rstrip('.')
    return default


# --- Shared File Helpers ---
ILLEGAL_FS_CHARS = re.compile(r'[\\/*?:"<>|]')

# .bin is deliberately excluded: renaming a .bin breaks the FILE reference inside its .cue.
RENAMEABLE_EXTS = ('.iso', '.zso', '.chd')

def lookup_title(clean_id):
    """Database title made safe for a filename, or "" if the ID isn't in the database."""
    if not clean_id:
        return ""
    return ILLEGAL_FS_CHARS.sub("", game_db.get(clean_id, "")).strip()

def build_rename_target(fpath, clean_id, raw_id, include_id):
    """Full path the file should be renamed to, or None if it should be left alone."""
    ext = os.path.splitext(fpath)[1].lower()
    title = lookup_title(clean_id)
    if not raw_id or not title or ext not in RENAMEABLE_EXTS:
        return None
    display_id = raw_id.replace('_', '-')
    new_name = f"{title} [{display_id}]{ext}" if include_id else f"{title}{ext}"
    return os.path.join(os.path.dirname(fpath), new_name)


def evaluate_rename(fpath, clean_id, raw_id, include_id):
    """Evaluate what a rename operation will do for `fpath`.

    Returns (op_status, new_path, message):
      - 'rename': file will be renamed to `new_path`
      - 'already_named': filename already matches the target name exactly
      - 'conflict': another distinct file already exists at `new_path`
      - 'not_in_db': Game ID was extracted, but is not in PS2.data.json
      - 'no_id': no Game ID could be extracted from header or filename
    """
    filename = os.path.basename(fpath)
    new_path = build_rename_target(fpath, clean_id, raw_id, include_id)
    if not new_path:
        if clean_id:
            return "not_in_db", None, "Game ID not found in database"
        return "no_id", None, "No Game ID detected"

    new_name = os.path.basename(new_path)
    if filename == new_name:
        return "already_named", new_path, "No change needed (already matches standard name)"

    if os.path.exists(new_path):
        try:
            is_same = os.path.samefile(fpath, new_path)
        except OSError:
            is_same = (os.path.normcase(os.path.abspath(fpath)) == os.path.normcase(os.path.abspath(new_path)))
        if not is_same:
            return "conflict", new_path, f"Target '{new_name}' already exists"

    return "rename", new_path, new_name

def find_cue(bin_path):
    """The .cue sitting next to a .bin (same base name), or None."""
    base, _ = os.path.splitext(bin_path)
    for ext in ('.cue', '.CUE', '.Cue'):
        if os.path.exists(base + ext):
            return base + ext
    return None

def remove_quietly(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

async def run_tool(cmd, session, tag, stream=True):
    """Run an external tool, logging its output, and terminate it as soon as the user cancels.

    Output is read in chunks rather than with readline(), so the pipe can never fill up and stall
    the tool, and '\\r'-redrawn progress lines collapse to their final state.
    Returns (returncode, cancelled).
    """
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

    async def watch_cancel():
        while proc.returncode is None:
            if session.cancel_requested:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
                return
            await asyncio.sleep(0.2)

    def log_line(raw):
        text = raw.split(b'\r')[-1].decode('utf-8', errors='ignore').strip()
        if text and stream:
            session.logs.append(f"[{tag}] {text}")

    watcher = asyncio.create_task(watch_cancel())
    try:
        buf = b""
        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            *lines, buf = buf.split(b'\n')
            for raw in lines:
                log_line(raw)
        log_line(buf)
        await proc.wait()
    finally:
        watcher.cancel()
    return proc.returncode, session.cancel_requested

async def convert_bin_to_iso(bin_path, session, stream=True):
    """Convert a BIN/CUE pair to '<name>_converted.iso'. Auto-recreates a missing .cue file if needed."""
    name = os.path.basename(bin_path)
    cue_path = find_cue(bin_path)
    if not cue_path:
        try:
            cue_path, track_mode = generate_cue_for_bin(bin_path)
            session.logs.append(f"[CUE] {name}: Missing .cue file detected — automatically recreated '{os.path.basename(cue_path)}' ({track_mode}).")
        except Exception as e:
            session.logs.append(f"[ERROR] {name}: Failed to auto-generate missing .cue file ({e}).")
            return None

    base_path, _ = os.path.splitext(bin_path)
    out_prefix = base_path + "_converted"
    final_iso = out_prefix + ".iso"
    if os.path.exists(final_iso):
        session.logs.append(f"[SKIP] {name}: {os.path.basename(final_iso)} already exists, using it.")
        return final_iso

    # bchunk appends a track number to its output (e.g. game_converted01.iso), so find what it made.
    track_pattern = glob.escape(out_prefix) + "[0-9][0-9].*"
    before = set(glob.glob(track_pattern))
    rc, cancelled = await run_tool([resource_path("bchunk.exe"), bin_path, cue_path, out_prefix], session, "BCHUNK", stream)
    produced = sorted(set(glob.glob(track_pattern)) - before)

    if cancelled or rc != 0:
        for p in produced:
            remove_quietly(p)
        if not cancelled:
            session.logs.append(f"[ERROR] bchunk failed on {name} (exit code {rc}).")
        return None

    data_tracks = [p for p in produced if p.lower().endswith('.iso')]
    if not data_tracks:
        session.logs.append(f"[ERROR] bchunk produced no ISO data track for {name}.")
        return None

    os.replace(data_tracks[0], final_iso)
    extras = [p for p in produced if p != data_tracks[0]]
    if extras:
        session.logs.append(f"[SYSTEM] {name}: kept {len(extras)} extra track file(s) alongside the ISO.")
    return final_iso

async def compress_iso_to_zso(iso_path, session, stream=True):
    """Compress an ISO to ZSO. Returns the ZSO path, or None (any partial output is removed)."""
    name = os.path.basename(iso_path)
    out_zso = os.path.splitext(iso_path)[0] + ".zso"
    if os.path.exists(out_zso):
        session.logs.append(f"[SKIP] {name}: {os.path.basename(out_zso)} already exists.")
        return None

    rc, cancelled = await run_tool([resource_path("ziso.exe"), "-i", iso_path, "-o", out_zso], session, "ZISO", stream)
    if cancelled or rc != 0 or not os.path.exists(out_zso) or os.path.getsize(out_zso) == 0:
        remove_quietly(out_zso)
        if not cancelled:
            session.logs.append(f"[ERROR] ziso failed on {name} (exit code {rc}).")
        return None
    return out_zso


async def decompress_zso_to_iso(zso_path, session, stream=True):
    """Decompress a ZSO back to standard ISO. Returns the ISO path, or None on failure."""
    name = os.path.basename(zso_path)
    out_iso = os.path.splitext(zso_path)[0] + ".iso"
    if os.path.exists(out_iso):
        session.logs.append(f"[SKIP] {name}: {os.path.basename(out_iso)} already exists.")
        return None

    rc, cancelled = await run_tool([resource_path("ziso.exe"), "-i", zso_path, "-o", out_iso], session, "ZISO", stream)
    if cancelled or rc != 0 or not os.path.exists(out_iso) or os.path.getsize(out_iso) == 0:
        remove_quietly(out_iso)
        if not cancelled:
            session.logs.append(f"[ERROR] ziso decompression failed on {name} (exit code {rc}).")
        return None
    return out_iso


async def convert_chd_to_iso(chd_path, session, stream=True):
    """Extract a CHD disc image into '<name>_converted.iso'. Handles both raw/DVD and CD-track CHDs."""
    name = os.path.basename(chd_path)
    base_path, _ = os.path.splitext(chd_path)
    final_iso = base_path + "_converted.iso"
    if os.path.exists(final_iso):
        session.logs.append(f"[SKIP] {name}: {os.path.basename(final_iso)} already exists, using it.")
        return final_iso

    chdman_exe = resource_path("chdman.exe")
    if not os.path.exists(chdman_exe):
        session.logs.append(f"[ERROR] chdman.exe not found; cannot convert {name}.")
        return None

    # Inspect CHD metadata to determine whether it is a CD-track CHD (CHT2/CHTR/CHCD) or a raw/DVD CHD
    is_cd_chd = False
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        proc = await asyncio.create_subprocess_exec(
            chdman_exe, "info", "-i", chd_path,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=creationflags
        )
        out_bytes, _ = await proc.communicate()
        info_txt = out_bytes.decode('utf-8', errors='ignore')
        if any(tag in info_txt for tag in ("Tag='CHT2'", "Tag='CHTR'", "Tag='CHCD'")):
            is_cd_chd = True
    except Exception:
        pass

    if is_cd_chd:
        tmp_cue = base_path + "_chdtmp.cue"
        tmp_bin = base_path + "_chdtmp.bin"
        remove_quietly(tmp_cue)
        remove_quietly(tmp_bin)
        rc, cancelled = await run_tool(
            [chdman_exe, "extractcd", "-f", "-i", chd_path, "-o", tmp_cue, "-ob", tmp_bin],
            session, "CHDMAN", stream
        )
        if cancelled or rc != 0 or not os.path.exists(tmp_bin):
            remove_quietly(tmp_cue)
            remove_quietly(tmp_bin)
            if not cancelled:
                session.logs.append(f"[ERROR] chdman extractcd failed on {name} (exit code {rc}).")
            return None
        converted = await convert_bin_to_iso(tmp_bin, session, stream=stream)
        remove_quietly(tmp_cue)
        remove_quietly(tmp_bin)
        if converted and os.path.exists(converted):
            os.replace(converted, final_iso)
            return final_iso
        return None
    else:
        rc, cancelled = await run_tool(
            [chdman_exe, "extractraw", "-f", "-i", chd_path, "-o", final_iso],
            session, "CHDMAN", stream
        )
        if cancelled or rc != 0 or not os.path.exists(final_iso) or os.path.getsize(final_iso) == 0:
            remove_quietly(final_iso)
            if not cancelled:
                session.logs.append(f"[ERROR] chdman extractraw failed on {name} (exit code {rc}).")
            return None
        return final_iso


def build_default_cfg_for_game(raw_id: str, clean_id: str = "", existing: dict = None) -> dict:
    """Build a dictionary of OPL CFG fields using PS2.data.json metadata merged with any existing CFG."""
    if not clean_id and raw_id:
        clean_id = raw_id.replace('_', '').replace('-', '').replace('.', '').replace(' ', '').upper()
    db_info = game_meta_db.get(clean_id, {})
    base = dict(existing or {})
    base["CfgVersion"] = base.get("CfgVersion", "8")
    base["$ConfigSource"] = base.get("$ConfigSource", "1")
    base["Title"] = base.get("Title") or game_db.get(clean_id) or raw_id.replace('_', '-')
    dev = format_meta_field(db_info.get("developer"), "")
    pub = format_meta_field(db_info.get("publisher"), "")
    genre = format_meta_field(db_info.get("genre"), "")
    rel = format_meta_field(db_info.get("release_date") or db_info.get("date"), "")
    reg = format_meta_field(db_info.get("region"), "")
    if dev and not base.get("Developer"):
        base["Developer"] = dev
    if pub and not base.get("Publisher"):
        base["Publisher"] = pub
    if genre and not base.get("Genre"):
        base["Genre"] = genre
    if rel and not base.get("Release"):
        base["Release"] = rel
    if reg and not base.get("Region"):
        base["Region"] = reg
    return base


def generate_opl_cfg_sync(opl_root: str, raw_id: str, clean_id: str = "", overwrite: bool = False) -> bool:
    """Create or update CFG/{raw_id}.cfg on an OPL root folder. Returns True if written."""
    if not raw_id:
        return False
    cfg_dir = os.path.join(opl_root, "CFG")
    os.makedirs(cfg_dir, exist_ok=True)
    cfg_path = os.path.join(cfg_dir, f"{raw_id}.cfg")
    if os.path.exists(cfg_path) and not overwrite:
        return False
    existing = read_opl_cfg(cfg_path) if os.path.exists(cfg_path) else {}
    # If overwriting metadata, clear auto metadata keys while preserving user compatibility/VMC keys
    if overwrite and existing:
        for k in ("Title", "Developer", "Publisher", "Genre", "Release", "Region"):
            existing.pop(k, None)
    merged = build_default_cfg_for_game(raw_id, clean_id, existing)
    write_opl_cfg(cfg_path, merged)
    return True


# --- Data Models ---
class FolderResponse(BaseModel):
    path: str
    error: str = ""

class ScanRequest(BaseModel):
    source_path: str

class DestRequest(BaseModel):
    dest_path: str

class ParseRequest(BaseModel):
    filepath: str

class GameFile(BaseModel):
    filename: str
    path: str
    ext: str
    size: str
    size_bytes: int = 0
    raw_id: str
    clean_id: str
    clean_title: str
    missing_cue: bool = False

class RunQueueRequest(BaseModel):
    source: str
    target: str
    files: List[GameFile]
    keep_bin: bool
    enable_rename: bool
    rename_id: bool
    comp_choice: str
    auto_art: bool
    auto_cfg: bool = True
    split_fat32: bool = True

class ToolkitRequest(BaseModel):
    target_path: str
    action: str
    rename_id: bool = True
    keep_bin: bool = False
    keep_iso: bool = False
    keep_zso: bool = False
    art_mode: str = "missing_partial"
    cfg_mode: str = "missing"
    clean_mode: str = "all"
    selected_paths: List[str] = []

class ToolkitPreviewRequest(BaseModel):
    target_path: str
    action: str
    rename_id: bool = True
    keep_bin: bool = False
    keep_iso: bool = False
    keep_zso: bool = False
    art_mode: str = "missing_partial"
    cfg_mode: str = "missing"
    clean_mode: str = "all"
    filepaths: List[str] = []

class CustomArtUploadRequest(BaseModel):
    target_path: str
    raw_id: str
    art_type: str
    data_url: str

class GameCfgRequest(BaseModel):
    target_path: str
    raw_id: str

class SaveGameCfgRequest(BaseModel):
    target_path: str
    raw_id: str
    cfg_data: Dict[str, Any]

# --- Native Dialogs via Tkinter (Compatible with PyInstaller & PyWebView) ---
def pick_folder_native(title: str) -> str:
    print(f"\n[SYSTEM] Triggering folder picker: {title}")
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes('-topmost', True)
    except Exception:
        pass
    path = filedialog.askdirectory(title=title)
    root.destroy()
    return path.strip() if path else ""

def pick_file_native(title: str, action: str) -> str:
    print(f"\n[SYSTEM] Triggering file picker for: {action}")
    tk_filters = "*.iso;*.zso;*.bin;*.chd"
    if action == "convert":
        tk_filters = "*.bin;*.chd"
    elif action == "compress":
        tk_filters = "*.iso"
    elif action == "decompress":
        tk_filters = "*.zso"

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes('-topmost', True)
    except Exception:
        pass
    path = filedialog.askopenfilename(
        title=title, 
        filetypes=[('PS2 Images', tk_filters), ('All files', '*.*')]
    )
    root.destroy()
    return path.strip() if path else ""

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
def serve_ui(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    icon_path = resource_path("app_icon.ico")
    if os.path.exists(icon_path):
        return FileResponse(icon_path, media_type="image/x-icon")
    return Response(content=b"", media_type="image/x-icon")

@app.get("/api/select-source", response_model=FolderResponse)
def select_source_folder():
    path = pick_folder_native("Select Source Folder (Games)")
    return FolderResponse(path=path if path else "No Folder Selected")

@app.get("/api/select-destination", response_model=FolderResponse)
def select_dest_folder():
    path = pick_folder_native("Select OPL Target Destination")
    return FolderResponse(path=path if path else "No OPL Destination Selected")

@app.get("/api/select-toolkit-folder", response_model=FolderResponse)
def select_toolkit_folder(action: str = "all"):
    opl_actions = ("art", "cfg", "clean")
    title = "Select Target OPL Root Folder (Must contain CD/DVD/ART)" if action in opl_actions else "Select Target Folder for Toolkit Action"
    path = pick_folder_native(title)
    return FolderResponse(path=path if path else "")

@app.get("/api/select-file", response_model=FolderResponse)
def select_single_file(action: str = "all"):
    path = pick_file_native("Select Target Game File", action)
    return FolderResponse(path=path if path else "")

@app.post("/api/get-source-files")
def get_source_files(req: ScanRequest):
    files = []
    if not os.path.exists(req.source_path):
        return {"files": files}
    for root_dir, _, filenames in os.walk(req.source_path):
        for filename in filenames:
            if filename.lower().endswith(('.iso', '.zso', '.chd', '.bin')):
                files.append(os.path.join(root_dir, filename))
    return {"files": files}

@app.post("/api/get-dest-files")
def get_dest_files(req: DestRequest):
    files = set()
    for sub in ["CD", "DVD"]:
        p = os.path.join(req.dest_path, sub)
        if os.path.exists(p):
            for fn in os.listdir(p):
                files.add(fn.lower())
    drive_info = get_drive_info(req.dest_path)
    ul_ids = list(read_ul_cfg_ids(req.dest_path))
    return {"files": list(files), "drive_info": drive_info, "ul_ids": ul_ids}

@app.post("/api/parse-file", response_model=GameFile)
def parse_file(req: ParseRequest):
    fpath = req.filepath
    filename = os.path.basename(fpath)
    try:
        size_bytes = os.path.getsize(fpath)
        size = format_size(size_bytes)
        clean_id, raw_id = extract_game_id(fpath)
        # Empty when the ID isn't in the database, so the UI won't plan an "Unknown Title" rename.
        clean_title = lookup_title(clean_id)
        ext = os.path.splitext(filename)[1].lower()
        missing_cue = (ext == '.bin' and find_cue(fpath) is None)
        return GameFile(
            filename=filename,
            path=fpath,
            ext=ext,
            size=size,
            size_bytes=size_bytes,
            raw_id=raw_id if raw_id else "Unknown",
            clean_id=clean_id if clean_id else "",
            clean_title=clean_title,
            missing_cue=missing_cue,
        )
    except Exception:
        return GameFile(filename=filename, path=fpath, ext="", size="0 MB", size_bytes=0, raw_id="Unknown", clean_id="", clean_title="")

OPL_ART_CATEGORIES = ("COV", "COV2", "LAB", "ICO", "LGO", "BG", "SCR")
CORE_CASE_CATEGORIES = ("COV", "COV2", "LAB", "ICO")


def inspect_existing_art(raw_id: str, art_files_upper: set):
    """Return (existing_tags, missing_tags, art_status) for a Game ID against an uppercase set of ART filenames."""
    if not raw_id:
        return [], list(OPL_ART_CATEGORIES), "Missing"
    rid = raw_id.upper()
    existing = []
    missing = []
    checks = {
        "COV": (f"{rid}_COV.PNG", f"{rid}_COV.JPG", f"{rid}_COV.JPEG"),
        "COV2": (f"{rid}_COV2.PNG", f"{rid}_COV2.JPG", f"{rid}_COV2.JPEG"),
        "LAB": (f"{rid}_LAB.PNG", f"{rid}_LAB.JPG", f"{rid}_LAB.JPEG"),
        "ICO": (f"{rid}_ICO.PNG", f"{rid}_ICO.JPG", f"{rid}_ICO.JPEG"),
        "LGO": (f"{rid}_LGO.PNG", f"{rid}_LGO.JPG", f"{rid}_LGO.JPEG"),
        "BG": (f"{rid}_BG_00.PNG", f"{rid}_BG_01.PNG", f"{rid}_BG.PNG", f"{rid}_BG_00.JPG", f"{rid}_BG_01.JPG", f"{rid}_BG.JPG"),
        "SCR": (f"{rid}_SCR_00.PNG", f"{rid}_SCR_01.PNG", f"{rid}_SCR.PNG", f"{rid}_SCR_00.JPG", f"{rid}_SCR_01.JPG", f"{rid}_SCR.JPG"),
    }
    for tag in OPL_ART_CATEGORIES:
        if any(candidate in art_files_upper for candidate in checks[tag]):
            existing.append(tag)
        else:
            missing.append(tag)

    if len(existing) == 0:
        art_status = "Missing"
    elif len(existing) == len(OPL_ART_CATEGORIES) and all(c in existing for c in CORE_CASE_CATEGORIES):
        art_status = "Full Set"
    else:
        art_status = "Partial"

    return existing, missing, art_status


def collect_toolkit_files(target_path: str, action: str):
    """Return (target_files, error_msg) for a toolkit target path and action."""
    if action in ('art', 'cfg', 'clean'):
        has_cd = os.path.exists(os.path.join(target_path, "CD"))
        has_dvd = os.path.exists(os.path.join(target_path, "DVD"))
        has_art = os.path.exists(os.path.join(target_path, "ART"))
        has_cfg = os.path.exists(os.path.join(target_path, "CFG"))
        has_ul = os.path.exists(os.path.join(target_path, "ul.cfg"))
        if not (has_cd or has_dvd or has_art or has_cfg or has_ul):
            return [], "Invalid OPL Folder Structure! Selected folder must contain standard OPL subfolders (CD, DVD, ART, or CFG)."

    files = []
    if action in ('art', 'cfg', 'clean'):
        for sub in ["CD", "DVD", "ART"]:
            sub_p = os.path.join(target_path, sub)
            if os.path.exists(sub_p):
                for root, _, fnames in os.walk(sub_p):
                    for fn in fnames:
                        files.append(os.path.join(root, fn))
    else:
        if os.path.isfile(target_path):
            files = [target_path]
        elif os.path.isdir(target_path):
            for root, _, fnames in os.walk(target_path):
                for fn in fnames:
                    files.append(os.path.join(root, fn))

    valid_exts = {
        'convert': ['.bin', '.chd'],
        'compress': ['.iso'],
        'decompress': ['.zso'],
        'rename': list(RENAMEABLE_EXTS),
        'verify': ['.iso', '.zso', '.bin', '.chd'],
        'cfg': ['.iso', '.zso', '.bin', '.chd', '.png', '.jpg', '.jpeg'],
        'art': ['.iso', '.zso', '.bin', '.chd', '.png', '.jpg', '.jpeg'],
        'clean': ['.iso', '.zso', '.bin', '.chd', '.png', '.jpg', '.jpeg', '.part'],
    }
    allowed = valid_exts.get(action, [])
    target_files = [f for f in files if os.path.splitext(f)[1].lower() in allowed]
    return target_files, ""


def inspect_opl_drive_games(target_path: str):
    """Scan CD/, DVD/, and ul.cfg to return (active_raw_ids, primary_path_by_id)."""
    active_ids = set(read_ul_cfg_ids(target_path))
    games_by_id = {}
    ext_priority = {'.zso': 0, '.iso': 1, '.chd': 2, '.bin': 3}
    for sub in ("CD", "DVD"):
        sub_p = os.path.join(target_path, sub)
        if not os.path.exists(sub_p):
            continue
        for root, _, fnames in os.walk(sub_p):
            for fn in fnames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in ext_priority:
                    continue
                fpath = os.path.join(root, fn)
                _, raw_id = extract_game_id(fpath)
                if raw_id:
                    rid = raw_id.upper()
                    active_ids.add(rid)
                    games_by_id.setdefault(rid, []).append(fpath)

    primary_by_id = {}
    for rid, paths in games_by_id.items():
        paths_sorted = sorted(paths, key=lambda p: (ext_priority.get(os.path.splitext(p)[1].lower(), 99), p))
        primary_by_id[rid] = os.path.normcase(os.path.abspath(paths_sorted[0]))
    return active_ids, primary_by_id


@app.post("/api/get-toolkit-files")
def get_toolkit_files(req: ToolkitPreviewRequest):
    target_files, error = collect_toolkit_files(req.target_path, req.action)
    return {"files": target_files, "error": error, "action": req.action, "target_path": req.target_path}


@app.post("/api/toolkit-preview")
async def toolkit_preview(req: ToolkitPreviewRequest):
    target_path = req.target_path
    action = req.action

    if req.filepaths:
        target_files = req.filepaths
    else:
        target_files, error = collect_toolkit_files(target_path, action)
        if error:
            return {"error": error, "items": [], "action": action}

    preview_items = []
    loop = asyncio.get_running_loop()
    seen_ids = set()

    art_dir = os.path.join(target_path, "ART") if action == 'art' else ""
    art_files_upper = set()
    if action == 'art' and os.path.exists(art_dir):
        try:
            art_files_upper = {fn.upper() for fn in os.listdir(art_dir)}
        except OSError:
            art_files_upper = set()

    active_opl_ids = set()
    primary_game_by_id = {}
    if action == 'clean':
        active_opl_ids, primary_game_by_id = await loop.run_in_executor(None, inspect_opl_drive_games, target_path)

    for fpath in target_files:
        if not os.path.exists(fpath):
            continue
        filename = os.path.basename(fpath)
        ext_lower = os.path.splitext(filename)[1].lower()
        size_bytes = os.path.getsize(fpath)
        size = format_size(size_bytes)
        clean_id, raw_id = await loop.run_in_executor(None, extract_game_id, fpath)
        existing_art = []
        missing_art = []
        art_status = ""

        if action == 'art':
            if not raw_id or raw_id in seen_ids:
                continue
            seen_ids.add(raw_id)
            existing_art, missing_art, art_status = inspect_existing_art(raw_id, art_files_upper)
            if ext_lower in ('.png', '.jpg', '.jpeg'):
                db_title = lookup_title(clean_id)
                filename = f"{db_title} [Art Only]" if db_title else f"{raw_id.replace('_', '-')} [Art Only]"
                size = "ART Folder"
            projected = art_status
            op_status = art_status

        elif action == 'cfg':
            if not raw_id or raw_id in seen_ids:
                continue
            seen_ids.add(raw_id)
            cfg_path = os.path.join(target_path, "CFG", f"{raw_id}.cfg")
            cfg_exists = os.path.exists(cfg_path)
            db_title = lookup_title(clean_id) or raw_id.replace('_', '-')
            if ext_lower in ('.png', '.jpg', '.jpeg'):
                filename = f"{db_title} [Art Only]"
                size = "ART Folder"
            if cfg_exists and req.cfg_mode != "overwrite":
                op_status = "already_named"
                projected = f"CFG/{raw_id}.cfg exists ({db_title})"
            else:
                op_status = "ready"
                verb = "Overwrite" if cfg_exists else "Generate"
                projected = f"{verb} CFG/{raw_id}.cfg ({db_title})"

        elif action == 'clean':
            norm_p = os.path.normcase(os.path.abspath(fpath))
            parent_folder = os.path.basename(os.path.dirname(fpath)).upper()
            if ext_lower == '.part':
                op_status = "ready"
                art_status = "temp"
                projected = "Delete leftover .part temporary file"
            elif parent_folder == "ART" and ext_lower in ('.png', '.jpg', '.jpeg'):
                rid_upper = (raw_id or "").upper()
                if not rid_upper or rid_upper not in active_opl_ids:
                    op_status = "ready"
                    art_status = "orphan_art"
                    projected = f"Orphaned Art — Game {raw_id or 'Unknown'} not on drive"
                else:
                    continue
            elif parent_folder in ("CD", "DVD") and raw_id:
                rid_upper = raw_id.upper()
                primary_p = primary_game_by_id.get(rid_upper)
                if primary_p and norm_p != primary_p:
                    op_status = "ready"
                    art_status = "duplicate"
                    keep_name = os.path.basename(primary_p)
                    projected = f"Duplicate of {keep_name} ({raw_id})"
                else:
                    continue
            else:
                continue

        elif action == 'verify':
            v_info = await loop.run_in_executor(None, verify_disc_image, fpath, True)
            op_status = "already_named" if v_info["healthy"] else "skipped"
            projected = v_info["summary"]

        else:
            op_status = "ready"
            base_name = os.path.splitext(filename)[0]
            projected = filename
            if action == 'rename':
                op_status, _, projected = evaluate_rename(fpath, clean_id, raw_id, req.rename_id)
            elif action == 'convert':
                converted_iso = os.path.join(os.path.dirname(fpath), f"{base_name}_converted.iso")
                if os.path.exists(converted_iso):
                    op_status = "already_named"
                    projected = f"'{base_name}_converted.iso' already exists"
                else:
                    op_status = "ready"
                    src_label = "CHD" if ext_lower == '.chd' else "BIN/CUE"
                    keep_note = f"keeps {src_label}" if req.keep_bin else f"removes {src_label}"
                    if ext_lower == '.bin' and not find_cue(fpath):
                        track_mode = await loop.run_in_executor(None, detect_bin_track_mode, fpath)
                        projected = f"{base_name}_converted.iso (⚡ Auto-recreates missing .cue [{track_mode}] • {keep_note})"
                    else:
                        projected = f"{base_name}_converted.iso ({keep_note})"
            elif action == 'compress':
                target_zso = os.path.join(os.path.dirname(fpath), f"{base_name}.zso")
                if os.path.exists(target_zso):
                    op_status = "already_named"
                    projected = f"'{base_name}.zso' already exists"
                else:
                    op_status = "ready"
                    iso_note = "keeps original ISO" if req.keep_iso else "removes original ISO"
                    projected = f"{base_name}.zso ({iso_note})"
            elif action == 'decompress':
                target_iso = os.path.join(os.path.dirname(fpath), f"{base_name}.iso")
                if os.path.exists(target_iso):
                    op_status = "already_named"
                    projected = f"'{base_name}.iso' already exists"
                else:
                    op_status = "ready"
                    zso_note = "keeps original ZSO" if req.keep_zso else "removes original ZSO"
                    projected = f"{base_name}.iso ({zso_note})"

        preview_items.append({
            "path": fpath,
            "filename": filename,
            "size": size,
            "size_bytes": size_bytes,
            "raw_id": raw_id if raw_id else "Unknown",
            "existing_art": existing_art,
            "missing_art": missing_art,
            "art_status": art_status,
            "op_status": op_status,
            "all_art_types": list(OPL_ART_CATEGORIES) if action == 'art' else [],
            "projected": projected
        })
    return {"items": preview_items, "action": action, "target_path": target_path}

@app.post("/api/toolkit-gallery")
def toolkit_gallery(req: ToolkitPreviewRequest):
    target_path = req.target_path
    art_dir = os.path.join(target_path, "ART")
    cfg_dir = os.path.join(target_path, "CFG")
    if not os.path.exists(art_dir):
        return {"games": []}

    games_map = {}
    for fn in os.listdir(art_dir):
        if "_" in fn and fn.lower().endswith(('.png', '.jpg', '.jpeg')):
            parts = fn.split("_")
            raw_id = f"{parts[0]}_{parts[1]}" if len(parts) > 2 else parts[0]
            
            if raw_id not in games_map:
                clean_key = raw_id.replace('_', '').replace('-', '').replace('.', '').replace(' ', '').upper()
                db_info = game_meta_db.get(clean_key, {})
                cfg_file = os.path.join(cfg_dir, f"{raw_id}.cfg")
                
                games_map[raw_id] = {
                    "raw_id": raw_id.replace('_', '-'),
                    "raw_id_internal": raw_id,
                    "title": game_db.get(clean_key, raw_id.replace('_', '-')),
                    "publisher": format_meta_field(db_info.get("publisher"), "Unknown Publisher"),
                    "developer": format_meta_field(db_info.get("developer"), "Unknown Developer"),
                    "release_date": format_meta_field(db_info.get("release_date") or db_info.get("date"), "Unknown Date"),
                    "genre": format_meta_field(db_info.get("genre"), "Unknown Genre"),
                    "has_cfg": os.path.exists(cfg_file),
                    "cov": None,
                    "cov2": None,
                    "lab": None,
                    "ico": None,
                    "lgo": None,
                    "bg": None
                }
            
            full_img_path = os.path.join(art_dir, fn)
            encoded_path = urllib.parse.quote(full_img_path, safe='')
            
            # Prefer _COV for front cover
            if "_COV." in fn and "_COV2." not in fn:
                games_map[raw_id]["cov"] = f"/api/art-image/{encoded_path}"
            elif not games_map[raw_id]["cov"] and "_COV2." in fn:
                games_map[raw_id]["cov"] = f"/api/art-image/{encoded_path}"
            
            if "_COV2." in fn:
                games_map[raw_id]["cov2"] = f"/api/art-image/{encoded_path}"
            if "_LAB." in fn:
                games_map[raw_id]["lab"] = f"/api/art-image/{encoded_path}"
            if "_ICO." in fn:
                games_map[raw_id]["ico"] = f"/api/art-image/{encoded_path}"
            if "_LGO." in fn:
                games_map[raw_id]["lgo"] = f"/api/art-image/{encoded_path}"
            if "_BG_00." in fn or "_BG_01." in fn or "_BG." in fn:
                games_map[raw_id]["bg"] = f"/api/art-image/{encoded_path}"

    return {"games": list(games_map.values())}


@app.post("/api/upload-custom-art")
def upload_custom_art(req: CustomArtUploadRequest):
    """Save a resized custom PNG data URL from the 3D Gallery Viewer into ART/{raw_id}_{art_type}.png."""
    art_dir = os.path.join(req.target_path, "ART")
    os.makedirs(art_dir, exist_ok=True)
    raw_id = req.raw_id.strip()
    art_type = req.art_type.strip().upper()
    valid_slots = {"COV": "COV", "COV2": "COV2", "LAB": "LAB", "ICO": "ICO", "LGO": "LGO", "BG": "BG_00"}
    if not raw_id or art_type not in valid_slots:
        return {"error": "Invalid art slot or Game ID."}

    suffix = valid_slots[art_type]
    try:
        header, b64_data = req.data_url.split(",", 1) if "," in req.data_url else ("", req.data_url)
        img_bytes = base64.b64decode(b64_data)
    except Exception as e:
        return {"error": f"Invalid image data: {e}"}

    # Remove any conflicting .jpg/.jpeg for the same slot so OPL and the gallery load the new .png
    for ext in ("png", "jpg", "jpeg", "PNG", "JPG", "JPEG"):
        remove_quietly(os.path.join(art_dir, f"{raw_id}_{suffix}.{ext}"))

    dest_file = os.path.join(art_dir, f"{raw_id}_{suffix}.png")
    with open(dest_file, "wb") as f:
        f.write(img_bytes)

    encoded_path = urllib.parse.quote(dest_file, safe='')
    return {
        "status": "ok",
        "url": f"/api/art-image/{encoded_path}?t={int(time.time() * 1000)}",
        "slot": art_type.lower(),
    }


@app.post("/api/get-game-cfg")
def get_game_cfg(req: GameCfgRequest):
    """Read CFG/{raw_id}.cfg or build defaults from PS2.data.json for the 3D Gallery CFG Editor."""
    raw_id = req.raw_id.strip()
    clean_id = raw_id.replace('_', '').replace('-', '').replace('.', '').replace(' ', '').upper()
    cfg_path = os.path.join(req.target_path, "CFG", f"{raw_id}.cfg")
    exists = os.path.exists(cfg_path)
    existing = read_opl_cfg(cfg_path) if exists else {}
    merged = build_default_cfg_for_game(raw_id, clean_id, existing)
    return {"exists": exists, "cfg": merged, "raw_id": raw_id}


@app.post("/api/save-game-cfg")
def save_game_cfg(req: SaveGameCfgRequest):
    """Save user-edited OPL configuration fields to CFG/{raw_id}.cfg."""
    raw_id = req.raw_id.strip()
    if not raw_id:
        return {"error": "Missing Game ID"}
    cfg_path = os.path.join(req.target_path, "CFG", f"{raw_id}.cfg")
    existing = read_opl_cfg(cfg_path) if os.path.exists(cfg_path) else {}
    existing.update(req.cfg_data)
    existing["CfgVersion"] = "8"
    existing["$ConfigSource"] = "1"
    write_opl_cfg(cfg_path, existing)
    return {"status": "ok", "path": cfg_path}

ALLOWED_IMAGE_EXTS = ('.png', '.jpg', '.jpeg')

@app.get("/api/art-image/{encoded_path:path}")
def get_art_image(encoded_path: str):
    full_path = os.path.abspath(urllib.parse.unquote(encoded_path))
    parent_dir = os.path.basename(os.path.dirname(full_path)).upper()
    if (
        parent_dir == "ART"
        and full_path.lower().endswith(ALLOWED_IMAGE_EXTS)
        and os.path.isfile(full_path)
    ):
        return FileResponse(full_path)
    return Response(status_code=404)

# --- Core Task Logic ---
active_sessions = {}
is_running = False

class LogSession:
    def __init__(self):
        self.logs = []
        self.is_running = True
        self.cancel_requested = False

ART_FILE_SPECS = (
    ("COV", "COV", "png"),
    ("COV2", "COV2", "png"),
    ("LAB", "LAB", "png"),
    ("ICO", "ICO", "png"),
    ("LGO", "LGO", "png"),
    ("BG_00", "BG", "png"),
    ("BG_01", "BG", "png"),
    ("SCR_00", "SCR", "png"),
    ("SCR_01", "SCR", "png"),
)

def fetch_all_art_sync(raw_id: str, art_p: str, overwrite: bool = False, missing_categories: set = None) -> int:
    base_url = f"https://raw.githubusercontent.com/Luden02/psx-ps2-opl-art-database/main/PS2/{raw_id}"
    downloaded = 0
    for art_type, category, ext in ART_FILE_SPECS:
        if not overwrite and missing_categories is not None and category not in missing_categories:
            continue
        file_name = f"{raw_id}_{art_type}.{ext}"
        file_url = f"{base_url}/{file_name}"
        local_path = os.path.join(art_p, file_name)
        if overwrite or not os.path.exists(local_path):
            # Download to a .part file and only move it into place once complete, so a timeout
            # can't leave a truncated image that would be treated as "already downloaded" forever.
            part_path = local_path + ".part"
            try:
                req = urllib.request.Request(file_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=3) as resp, open(part_path, 'wb') as out:
                    shutil.copyfileobj(resp, out)
                os.replace(part_path, local_path)
                downloaded += 1
            except Exception:
                remove_quietly(part_path)
    return downloaded

@app.post("/api/cancel-queue")
async def cancel_queue(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    if session_id in active_sessions:
        active_sessions[session_id].cancel_requested = True
        return {"status": "cancelling"}
    return {"status": "not_found"}

async def queue_worker(session_id: str, config: RunQueueRequest):
    global is_running
    session = active_sessions[session_id]
    src = config.source
    dst = config.target
    
    session.logs.append("=== QUEUE WIZARD ENGAGED ===")
    session.logs.append(f"Source: {src}")
    session.logs.append(f"Destination: {dst}")
    await asyncio.sleep(0.1)
    
    bchunk_exe = resource_path("bchunk.exe")
    chdman_exe = resource_path("chdman.exe")
    ziso_exe = resource_path("ziso.exe")
    
    raw_input_files = [f.path for f in config.files]
    current_files = list(dict.fromkeys(raw_input_files))
    
    try:
        conv_files = [f for f in current_files if f.lower().endswith(('.bin', '.chd'))]
        processed_files = [f for f in current_files if not f.lower().endswith(('.bin', '.chd'))]
        
        if conv_files:
            session.logs.append(f"--- Step 2: Converting {len(conv_files)} BIN/CHD file(s) to ISO ---")
            for c_path in conv_files:
                if session.cancel_requested:
                    session.logs.append("[SYSTEM] ⚠️ Queue aborted by user.")
                    break
                ext_low = os.path.splitext(c_path)[1].lower()
                session.logs.append(f"Converting: {os.path.basename(c_path)}...")
                await asyncio.sleep(0.1)
                try:
                    if ext_low == '.bin':
                        if not os.path.exists(bchunk_exe):
                            session.logs.append("[SYSTEM] bchunk.exe not found, skipping BIN conversion.")
                            processed_files.append(c_path)
                            continue
                        converted_iso = await convert_bin_to_iso(c_path, session)
                        if converted_iso:
                            processed_files.append(converted_iso)
                            if not config.keep_bin:
                                remove_quietly(c_path)
                                remove_quietly(find_cue(c_path))
                    elif ext_low == '.chd':
                        if not os.path.exists(chdman_exe):
                            session.logs.append("[SYSTEM] chdman.exe not found, skipping CHD conversion.")
                            processed_files.append(c_path)
                            continue
                        converted_iso = await convert_chd_to_iso(c_path, session)
                        if converted_iso:
                            processed_files.append(converted_iso)
                            if not config.keep_bin:
                                remove_quietly(c_path)
                except Exception as e:
                    session.logs.append(f"[ERROR] {e}")

        if not session.cancel_requested:
            session.logs.append("--- Step 3: Renaming & Standardizing Files ---")
            await asyncio.sleep(0.1)
            renamed_files = []
            for fpath in processed_files:
                await asyncio.sleep(0.01)
                if session.cancel_requested: break
                if not os.path.exists(fpath): continue
                
                loop = asyncio.get_running_loop()
                clean_id, raw_id = await loop.run_in_executor(None, extract_game_id, fpath)
                
                if config.enable_rename:
                    op_status, new_path, detail = evaluate_rename(fpath, clean_id, raw_id, config.rename_id)
                    if op_status == "rename":
                        new_name = os.path.basename(new_path)
                        try:
                            os.rename(fpath, new_path)
                            session.logs.append(f"Renamed: {os.path.basename(fpath)} -> {new_name}")
                            await asyncio.sleep(0.1)
                            fpath = new_path
                        except Exception as e:
                            session.logs.append(f"[ERROR] Rename failed: {e}")
                    elif op_status == "already_named":
                        session.logs.append(f"[SKIP] {os.path.basename(fpath)}: Already matches standard name.")
                    elif op_status == "conflict":
                        session.logs.append(f"[SKIP] Not renaming {os.path.basename(fpath)}: {detail}.")
                    else:
                        session.logs.append(f"[SKIP] Not renaming {os.path.basename(fpath)}: {detail}.")
                renamed_files.append(fpath)
        else: renamed_files = processed_files

        final_games = []
        if not session.cancel_requested:
            session.logs.append("--- Step 4: Compressing Files to ZSO ---")
            await asyncio.sleep(0.1)
            unique_renamed_files = list(dict.fromkeys(renamed_files))
            
            if config.comp_choice == 'opl' and os.path.exists(ziso_exe):
                total_orig_bytes = 0
                total_comp_bytes = 0
                comp_count = 0
                for fpath in unique_renamed_files:
                    if session.cancel_requested:
                        session.logs.append("[SYSTEM] ⚠️ Queue aborted by user (Compression stopped).")
                        break
                    if not fpath.lower().endswith('.iso'):
                        final_games.append(fpath)
                        continue
                    session.logs.append(f"Compressing: {os.path.basename(fpath)}...")
                    try:
                        orig_sz = os.path.getsize(fpath) if os.path.exists(fpath) else 0
                        out_zso = await compress_iso_to_zso(fpath, session)
                        if out_zso and os.path.exists(out_zso):
                            zso_sz = os.path.getsize(out_zso)
                            total_orig_bytes += orig_sz
                            total_comp_bytes += zso_sz
                            comp_count += 1
                            saved = max(0, orig_sz - zso_sz)
                            pct = round((saved / orig_sz) * 100, 1) if orig_sz > 0 else 0.0
                            session.logs.append(f"[SUCCESS] Compressed to {os.path.basename(out_zso)} (saved {format_size(saved)}, -{pct}%)")
                            final_games.append(out_zso)
                            remove_quietly(fpath)
                        else:
                            final_games.append(fpath)
                    except Exception as e:
                        session.logs.append(f"[ERROR] {e}"); final_games.append(fpath)
                if comp_count > 0 and total_orig_bytes > 0:
                    total_saved = max(0, total_orig_bytes - total_comp_bytes)
                    total_pct = round((total_saved / total_orig_bytes) * 100, 1)
                    session.logs.append(f"[SUCCESS] 💾 Total Storage Saved: {format_size(total_saved)} ({total_pct}% reduction across {comp_count} game(s))")
            else:
                session.logs.append("--- Compression Skipped ---")
                final_games = unique_renamed_files
        else: final_games = renamed_files

        if not session.cancel_requested:
            session.logs.append("--- Step 5: OPL Push, CFG & Art Scraper ---")
            await asyncio.sleep(0.1)
            dvd_p = os.path.join(dst, "DVD")
            cd_p = os.path.join(dst, "CD")
            art_p = os.path.join(dst, "ART")
            cfg_p = os.path.join(dst, "CFG")
            os.makedirs(dvd_p, exist_ok=True); os.makedirs(cd_p, exist_ok=True); os.makedirs(art_p, exist_ok=True); os.makedirs(cfg_p, exist_ok=True)
            pushed = 0
            seen_game_ids = set()
            unique_final_games = list(dict.fromkeys(final_games))
            dest_drive_info = get_drive_info(dst)
            is_fat32 = (dest_drive_info.get("fs_type") == "FAT32")
            FAT32_MAX_FILE = 4 * 1024 * 1024 * 1024 - 1
            
            for fpath in unique_final_games:
                await asyncio.sleep(0.01)
                if session.cancel_requested:
                    session.logs.append("[SYSTEM] ⚠️ Queue aborted by user (Push stopped).")
                    break
                if not os.path.exists(fpath): continue
                
                loop = asyncio.get_running_loop()
                clean_id, raw_id = await loop.run_in_executor(None, extract_game_id, fpath)
                
                game_identifier = raw_id if raw_id else fpath
                if game_identifier in seen_game_ids: continue
                seen_game_ids.add(game_identifier)

                size_bytes = os.path.getsize(fpath)
                subfolder = "CD" if size_bytes < 700 * 1024 * 1024 else "DVD"
                dest_file = os.path.join(cd_p if subfolder == "CD" else dvd_p, os.path.basename(fpath))
                
                if os.path.abspath(fpath) == os.path.abspath(dest_file):
                    session.logs.append(f"Skipped {os.path.basename(fpath)} (already in destination).")
                    continue
                if os.path.exists(dest_file):
                    session.logs.append(f"[SKIP] {os.path.basename(fpath)} already exists in {subfolder}, not overwriting.")
                    continue
                free_bytes = shutil.disk_usage(os.path.dirname(dest_file)).free
                if free_bytes < size_bytes:
                    session.logs.append(f"[ERROR] Not enough space for {os.path.basename(fpath)}: needs {format_size(size_bytes)}, {format_size(free_bytes)} free.")
                    continue

                try:
                    if is_fat32 and config.split_fat32 and size_bytes > FAT32_MAX_FILE and fpath.lower().endswith('.iso') and raw_id:
                        game_title = lookup_title(clean_id) or os.path.splitext(os.path.basename(fpath))[0]
                        session.logs.append(f"[FAT32] {os.path.basename(fpath)} is {format_size(size_bytes)} (>4GB limit). Splitting into USBUtil (ul.cfg) 1GB chunks...")
                        num_parts = await loop.run_in_executor(None, split_iso_to_ul, fpath, dst, raw_id, game_title, None)
                        pushed += 1
                        session.logs.append(f"[SUCCESS] Split {os.path.basename(fpath)} into {num_parts} ul.cfg part(s) on OPL Root.")
                    else:
                        part_file = dest_file + ".part"
                        try:
                            await loop.run_in_executor(None, shutil.copy2, fpath, part_file)
                            os.replace(part_file, dest_file)
                        except BaseException:
                            remove_quietly(part_file)
                            raise
                        pushed += 1
                        session.logs.append(f"Pushed {os.path.basename(fpath)} to {subfolder} folder.")

                    await asyncio.sleep(0.1)
                    if config.auto_cfg and raw_id and not session.cancel_requested:
                        wrote_cfg = await loop.run_in_executor(None, generate_opl_cfg_sync, dst, raw_id, clean_id, False)
                        if wrote_cfg:
                            session.logs.append(f"  -> Generated OPL config: CFG/{raw_id}.cfg")

                    if config.auto_art and raw_id and not session.cancel_requested:
                        session.logs.append(f"Scraping art for {raw_id}...")
                        downloaded_count = await loop.run_in_executor(None, fetch_all_art_sync, raw_id, art_p)
                        session.logs.append(f"  -> Successfully fetched artwork assets for {raw_id} ({downloaded_count} new files).")
                        await asyncio.sleep(0.1)
                except Exception as e:
                    session.logs.append(f"[ERROR] Failed pushing: {e}")

            session.logs.append(f"=== QUEUE COMPLETE: {pushed} GAMES PUSHED ===")
        else: session.logs.append("=== QUEUE ABORTED ===")
    except Exception as e: session.logs.append(f"[ERROR] Worker crashed: {e}")
    finally: session.is_running = False; is_running = False

async def toolkit_worker(session_id: str, config: ToolkitRequest):
    global is_running
    session = active_sessions[session_id]
    action = config.action
    target_path = config.target_path
    
    session.logs.append(f"=== TOOLKIT ENGINE: {action.upper()} ===")
    session.logs.append(f"Target: {target_path}")
    await asyncio.sleep(0.1)
    
    try:
        if config.selected_paths:
            target_files = [p for p in config.selected_paths if os.path.exists(p)]
        else:
            target_files, error = collect_toolkit_files(target_path, action)
            if error:
                session.logs.append(f"[ERROR] {error}")
                return

        loop = asyncio.get_running_loop()

        if action == 'art':
            unique_raw_ids = []
            seen_raw_ids = set()
            for fpath in target_files:
                _, raw_id = await loop.run_in_executor(None, extract_game_id, fpath)
                if raw_id and raw_id not in seen_raw_ids:
                    seen_raw_ids.add(raw_id)
                    unique_raw_ids.append(raw_id)
            
            art_dir = os.path.join(target_path, "ART")
            os.makedirs(art_dir, exist_ok=True)
            try:
                art_files_upper = {fn.upper() for fn in os.listdir(art_dir)}
            except OSError:
                art_files_upper = set()

            art_mode = config.art_mode or "missing_partial"
            mode_labels = {
                "missing": "Only Missing",
                "missing_partial": "Missing & Partial",
                "full": "Full Rescan (Overwrite All)",
            }
            session.logs.append(f"Art Scan Mode: {mode_labels.get(art_mode, art_mode)}")
            session.logs.append(f"Processing {len(unique_raw_ids)} selected Game ID(s)...")
            
            success_count = 0
            skipped_count = 0
            for raw_id in unique_raw_ids:
                if session.cancel_requested:
                    session.logs.append("[SYSTEM] ⚠️ Art scraping aborted by user.")
                    break

                _, missing_art, art_status = inspect_existing_art(raw_id, art_files_upper)

                if art_mode == "missing" and art_status != "Missing":
                    session.logs.append(f"[SKIP] {raw_id}: Status is '{art_status}' (skipping in Only Missing mode).")
                    skipped_count += 1
                    continue
                if art_mode == "missing_partial" and art_status == "Full Set":
                    session.logs.append(f"[SKIP] {raw_id}: Already has Full Set.")
                    skipped_count += 1
                    continue

                overwrite = (art_mode == "full")
                missing_set = None if overwrite else set(missing_art)
                session.logs.append(f"Scraping art for {raw_id} ({art_status})...")
                downloaded_count = await loop.run_in_executor(
                    None, fetch_all_art_sync, raw_id, art_dir, overwrite, missing_set
                )
                session.logs.append(f"[SUCCESS] Scraped {downloaded_count} asset(s) for {raw_id}")
                success_count += 1
            
            session.logs.append(f"=== TOOLKIT COMPLETE: {success_count} SCRAPED, {skipped_count} SKIPPED ===")
            return

        if action == 'cfg':
            # If the user explicitly checked items in the UI table, write/update all checked items
            overwrite_cfg = (config.cfg_mode == "overwrite") or bool(config.selected_paths)
            seen_raw_ids = set()
            success_count = 0
            skipped_count = 0
            for fpath in target_files:
                if session.cancel_requested:
                    break
                clean_id, raw_id = await loop.run_in_executor(None, extract_game_id, fpath)
                if not raw_id or raw_id in seen_raw_ids:
                    continue
                seen_raw_ids.add(raw_id)
                wrote = await loop.run_in_executor(None, generate_opl_cfg_sync, target_path, raw_id, clean_id, overwrite_cfg)
                if wrote:
                    title = lookup_title(clean_id) or raw_id
                    session.logs.append(f"[SUCCESS] Wrote CFG/{raw_id}.cfg ({title})")
                    success_count += 1
                else:
                    session.logs.append(f"[SKIP] CFG/{raw_id}.cfg already exists.")
                    skipped_count += 1
            session.logs.append(f"=== TOOLKIT COMPLETE: {success_count} CFG FILES WRITTEN, {skipped_count} SKIPPED ===")
            return

        if action == 'clean':
            reclaimed_bytes = 0
            deleted_count = 0
            for fpath in target_files:
                if session.cancel_requested:
                    break
                if not os.path.exists(fpath):
                    continue
                sz = os.path.getsize(fpath)
                fname = os.path.basename(fpath)
                try:
                    os.remove(fpath)
                    reclaimed_bytes += sz
                    deleted_count += 1
                    session.logs.append(f"[SUCCESS] Removed {fname} ({format_size(sz)})")
                except Exception as e:
                    session.logs.append(f"[ERROR] Could not remove {fname}: {e}")
            session.logs.append(f"=== CLEANUP COMPLETE: {deleted_count} FILE(S) REMOVED, {format_size(reclaimed_bytes)} RECLAIMED ===")
            return

        if action == 'verify':
            healthy_count = 0
            issue_count = 0
            for fpath in target_files:
                if session.cancel_requested:
                    break
                fname = os.path.basename(fpath)
                session.logs.append(f"Verifying {fname}...")
                v_info = await loop.run_in_executor(None, verify_disc_image, fpath, True)
                if v_info["healthy"]:
                    healthy_count += 1
                    session.logs.append(f"[SUCCESS] {fname} -> Healthy | CRC32: {v_info['crc32']} | MD5: {v_info['md5']}")
                else:
                    issue_count += 1
                    session.logs.append(f"[ERROR] {fname} -> {v_info['summary']}")
            session.logs.append(f"=== VERIFY COMPLETE: {healthy_count} HEALTHY, {issue_count} WITH ISSUES ===")
            return

        if not target_files:
            session.logs.append(f"[SYSTEM] No valid files found for this operation.")
            return
            
        session.logs.append(f"Found {len(target_files)} valid file(s) for {action}.")
        await asyncio.sleep(0.1)
        
        success_count = 0
        skipped_count = 0
        total_orig_bytes = 0
        total_comp_bytes = 0

        for fpath in target_files:
            await asyncio.sleep(0.05)
            if session.cancel_requested: break
            filename = os.path.basename(fpath)
            ext_low = os.path.splitext(filename)[1].lower()
            
            if action == 'rename':
                clean_id, raw_id = await loop.run_in_executor(None, extract_game_id, fpath)
                op_status, new_path, detail = evaluate_rename(fpath, clean_id, raw_id, config.rename_id)
                if op_status == "already_named":
                    session.logs.append(f"[SKIP] {filename}: Already matches standard name (no change needed).")
                    skipped_count += 1
                    continue
                if op_status != "rename":
                    session.logs.append(f"[SKIP] {filename}: {detail}.")
                    skipped_count += 1
                    continue
                new_name = os.path.basename(new_path)
                try:
                    os.rename(fpath, new_path)
                    session.logs.append(f"[SUCCESS] Renamed: {filename} -> {new_name}")
                    success_count += 1
                except Exception as e:
                    session.logs.append(f"[ERROR] {e}")

            elif action == 'convert':
                try:
                    if ext_low == '.chd':
                        converted_iso = await convert_chd_to_iso(fpath, session, stream=False)
                    else:
                        converted_iso = await convert_bin_to_iso(fpath, session, stream=False)
                    if converted_iso:
                        session.logs.append(f"[SUCCESS] Converted {filename} -> {os.path.basename(converted_iso)}")
                        if not config.keep_bin:
                            remove_quietly(fpath)
                            if ext_low == '.bin':
                                remove_quietly(find_cue(fpath))
                            session.logs.append(f"[SYSTEM] Removed original source for {filename}")
                        success_count += 1
                    else:
                        skipped_count += 1
                except Exception as e: session.logs.append(f"[ERROR] {e}")

            elif action == 'compress':
                try:
                    orig_sz = os.path.getsize(fpath) if os.path.exists(fpath) else 0
                    out_zso = await compress_iso_to_zso(fpath, session, stream=False)
                    if out_zso and os.path.exists(out_zso):
                        zso_sz = os.path.getsize(out_zso)
                        total_orig_bytes += orig_sz
                        total_comp_bytes += zso_sz
                        saved = max(0, orig_sz - zso_sz)
                        pct = round((saved / orig_sz) * 100, 1) if orig_sz > 0 else 0.0
                        session.logs.append(f"[SUCCESS] Compressed {filename} (saved {format_size(saved)}, -{pct}%)")
                        if not config.keep_iso:
                            remove_quietly(fpath)
                            session.logs.append(f"[SYSTEM] Removed original ISO: {filename}")
                        success_count += 1
                    else:
                        skipped_count += 1
                except Exception as e: session.logs.append(f"[ERROR] {e}")

            elif action == 'decompress':
                try:
                    out_iso = await decompress_zso_to_iso(fpath, session, stream=False)
                    if out_iso and os.path.exists(out_iso):
                        session.logs.append(f"[SUCCESS] Decompressed {filename} -> {os.path.basename(out_iso)}")
                        if not config.keep_zso:
                            remove_quietly(fpath)
                            session.logs.append(f"[SYSTEM] Removed original ZSO: {filename}")
                        success_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    session.logs.append(f"[ERROR] {e}")

        if action == 'compress' and success_count > 0 and total_orig_bytes > 0:
            total_saved = max(0, total_orig_bytes - total_comp_bytes)
            total_pct = round((total_saved / total_orig_bytes) * 100, 1)
            session.logs.append(f"[SUCCESS] 💾 Total Storage Saved: {format_size(total_saved)} ({total_pct}% reduction across {success_count} game(s))")

        session.logs.append(f"=== TOOLKIT COMPLETE: {success_count} PROCESSED, {skipped_count} SKIPPED/UNCHANGED ===")
    except Exception as e:
        session.logs.append(f"[ERROR] Toolkit crashed: {e}")
    finally:
        session.is_running = False
        is_running = False


@app.post("/api/process-queue")
async def process_queue(config: RunQueueRequest):
    global is_running
    if is_running:
        return {"session_id": "", "status": "already_running"}
    is_running = True
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = LogSession()
    asyncio.create_task(queue_worker(session_id, config))
    return {"session_id": session_id}

@app.post("/api/process-toolkit")
async def process_toolkit(config: ToolkitRequest):
    global is_running
    if is_running:
        return {"session_id": "", "status": "already_running"}
    is_running = True
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = LogSession()
    asyncio.create_task(toolkit_worker(session_id, config))
    return {"session_id": session_id}

@app.get("/api/poll-logs")
async def poll_logs(session_id: str, last_index: int = 0):
    if session_id not in active_sessions:
        return {"logs": [], "next_index": 0, "is_running": False}
    session = active_sessions[session_id]
    new_logs = session.logs[last_index:]
    return {"logs": new_logs, "next_index": last_index + len(new_logs), "is_running": session.is_running}


def find_available_port(preferred: int = 8000) -> int:
    """Return `preferred` if available on localhost, otherwise pick a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def wait_for_server(host: str, port: int, timeout: float = 5.0) -> None:
    """Block until the TCP port is accepting connections or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)


if __name__ == "__main__":
    host = "127.0.0.1"
    port = find_available_port(8000)
    url = f"http://{host}:{port}"
    print(f"Starting PS2 ISO Manager Web Server at {url}...")
    
    # 1. Start FastAPI in a background daemon thread
    threading.Thread(
        target=lambda: uvicorn.run(app, host=host, port=port, log_level="warning"), 
        daemon=True
    ).start()
    
    # 2. Wait until the server socket is actively listening
    wait_for_server(host, port)
    
    # 3. Create native window with pywebview on the MAIN thread
    import webview
    window = webview.create_window(
        title="PS2 ISO Manager",
        url=url,
        width=1180,
        height=850,
        resizable=True,
        min_size=(900, 650)
    )
    
    # Start the native window event loop
    webview.start()
    
    print("\n[SYSTEM] Native app window closed. Shutting down server...")
    os._exit(0)