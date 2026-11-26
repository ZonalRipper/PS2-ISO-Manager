import ctypes
import os
import re
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

from ps2_utility.core import format_size

HDD_DEVICE_RE = re.compile(r'^hdd(\d+):$', re.IGNORECASE)
QUERY_LINE_RE = re.compile(r'^\s*(hdd\d+:)\s+(\d+)\s*MB(.*)$', re.IGNORECASE)
TOTAL_SUMMARY_RE = re.compile(
    r'total(?:\s+slice\s+size)?:\s*(\d+)\s*MB,\s*used:\s*(\d+)\s*MB,\s*available:\s*(\d+)\s*MB',
    re.IGNORECASE,
)
TOTAL_SUMMARY_ALT_RE = re.compile(
    r'total\s+(\d+)\s*MB,\s*used\s+(\d+)\s*MB,\s*available\s+(\d+)\s*MB',
    re.IGNORECASE,
)
# pfsshell unmounted ls: "0x0100   256MB +OPL"
PFSSHELL_PART_RE = re.compile(r'^\s*0x([0-9a-fA-F]{4})\s+(\d+)\s*MB\s+(.+?)\s*$')
# pfsshell mounted ls: "drwxrwxrwx          0 2026-11-26 ART/" or "-rw-rw-rw-  24512 2026-11-26 file.png"
PFSSHELL_ENTRY_RE = re.compile(r'^\s*([d\-lcbps][rwxstST\-]{9})\s+(\d+)\s+(\S+(?:\s+\d{2}:\d{2}(?::\d{2})?)?)\s+(.+?)\s*$')

PROTECTED_PARTITIONS = {
    "__mbr",
    "__net",
    "__system",
    "__sysconf",
    "__common",
    "__boot",
    "__extend",
    "__empty",
    "+opl",
}

PFSSHELL_FATAL_ERRORS = (
    "mount of",
    "dopen:",
    "init_apa: failed",
    "init_pfs: failed",
    "no device selected",
    "no partition mounted",
    "write failed with",
    "create failed with",
    "could not open device",
    "permission denied",
    "invalid partition size",
    "invalid partition table",
    "ata initialization failed",
)


def is_admin() -> bool:
    """Return True if the current process has Windows Administrator privileges."""
    if os.name != "nt":
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_pfs_target(target: str) -> bool:
    """Return True if target is a valid hdl_dump local HDD identifier like 'hdd1:'."""
    return bool(target and HDD_DEVICE_RE.match(target.strip()))


def hdd_to_physical_drive(hdd_device: str) -> str:
    """Strictly convert 'hddN:' to '\\\\.\\PhysicalDriveN'. Raises ValueError if invalid."""
    match = HDD_DEVICE_RE.match((hdd_device or "").strip())
    if not match:
        raise ValueError(f"Invalid PS2 HDD device identifier: {hdd_device!r}")
    idx = int(match.group(1))
    return f"\\\\.\\PhysicalDrive{idx}"


def sanitize_hdl_title(title: str, fallback: str = "PS2 Game") -> str:
    """Sanitize a game title for HDL APA partition headers (max 160 chars, no quotes/newlines)."""
    cleaned = re.sub(r'[\r\n\t"\x00-\x1f]', ' ', title or '')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if not cleaned:
        cleaned = fallback
    return cleaned[:160]


def sanitize_pfs_token(name: str) -> str:
    """Validate and sanitize a single PFS filename or folder name (no slashes, control chars, or '..')."""
    cleaned = (name or "").strip().strip("/")
    if not cleaned or cleaned in (".", ".."):
        raise ValueError(f"Invalid PFS name: {name!r}")
    if any(ch in cleaned for ch in ('/', '\\', '\n', '\r', '\x00', '"', "'")):
        raise ValueError(f"PFS name contains illegal characters: {name!r}")
    return cleaned


def normalize_pfs_dir(remote_dir: str) -> List[str]:
    """Normalize a PFS directory path like '/ART/sub' into safe path segments ['ART', 'sub']."""
    raw = (remote_dir or "/").replace("\\", "/").strip()
    parts: List[str] = []
    for seg in raw.split("/"):
        seg = seg.strip()
        if not seg or seg == ".":
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(sanitize_pfs_token(seg))
    return parts


def _hdl_env() -> Dict[str, str]:
    """Return process env with RunAsInvoker so Windows UAC Installer Detection never blocks hdl_dump."""
    env = os.environ.copy()
    env["__COMPAT_LAYER"] = "RunAsInvoker"
    return env


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def run_pfsshell_script(
    pfsshell_exe: str,
    commands: List[str],
    cwd: Optional[str] = None,
    timeout: int = 180,
) -> Tuple[bool, str]:
    """Execute a scripted pfsshell.exe session and return (ok, combined_output)."""
    if not pfsshell_exe or not os.path.exists(pfsshell_exe):
        return False, "pfsshell.exe not found."
    script = "\n".join(commands) + "\n"
    try:
        proc = subprocess.run(
            [pfsshell_exe],
            input=script,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_creationflags(),
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        lower_out = output.lower()
        has_error = any(err in lower_out for err in PFSSHELL_FATAL_ERRORS)
        ok = (proc.returncode == 0) and not has_error
        return ok, output.strip()
    except Exception as e:
        return False, str(e)


def parse_hdl_query_output(output: str) -> Tuple[List[Dict], List[Dict]]:
    """Parse `hdl_dump.exe query` stdout into (ps2_drives, all_drives)."""
    ps2_drives: List[Dict] = []
    all_drives: List[Dict] = []
    for line in (output or "").splitlines():
        m = QUERY_LINE_RE.match(line)
        if not m:
            continue
        dev = m.group(1).lower()
        size_mb = int(m.group(2))
        rest = (m.group(3) or "").strip()
        is_ps2 = "formatted playstation 2 hdd" in rest.lower()
        size_bytes = size_mb * 1024 * 1024
        entry = {
            "device": dev,
            "physical_drive": hdd_to_physical_drive(dev),
            "size_mb": size_mb,
            "size_bytes": size_bytes,
            "size_fmt": format_size(size_bytes),
            "status_text": rest.lstrip(", ").strip() or "Non-PS2 Drive",
            "is_ps2": is_ps2,
        }
        all_drives.append(entry)
        if is_ps2:
            ps2_drives.append(entry)
    return ps2_drives, all_drives


def parse_hdl_toc_output(output: str) -> Dict:
    """Parse `hdl_dump.exe hdl_toc <device> --csv` output into games, installed_ids, and drive_info."""
    games: List[Dict] = []
    installed_ids = set()
    installed_titles = set()
    total_mb = 0
    used_mb = 0
    free_mb = 0

    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m_tot = TOTAL_SUMMARY_RE.search(line) or TOTAL_SUMMARY_ALT_RE.search(line)
        if m_tot:
            total_mb += int(m_tot.group(1))
            used_mb += int(m_tot.group(2))
            free_mb += int(m_tot.group(3))
            continue

        # CSV line format: DVD;4194304KB;0x00;*u4;SCUS_973.99 ;God of War
        if ";" in line:
            parts = line.split(";", 5)
            if len(parts) == 6 and parts[0].strip().upper() in ("CD", "DVD"):
                media = parts[0].strip().upper()
                size_str = parts[1].strip().upper().replace("KB", "").strip()
                try:
                    size_kb = int(size_str)
                except ValueError:
                    size_kb = 0
                flags = parts[2].strip()
                dma = parts[3].strip()
                raw_id = parts[4].strip().upper()
                title = parts[5].strip()
                clean_id = re.sub(r'[_\-\.\s]', '', raw_id).upper()
                if clean_id:
                    installed_ids.add(clean_id)
                if raw_id:
                    installed_ids.add(raw_id)
                if title:
                    installed_titles.add(title.lower())
                games.append({
                    "media": media,
                    "size_kb": size_kb,
                    "size_bytes": size_kb * 1024,
                    "size_fmt": format_size(size_kb * 1024),
                    "flags": flags,
                    "dma": dma,
                    "raw_id": raw_id,
                    "clean_id": clean_id,
                    "title": title,
                    "partition_name": "",
                })

    total_bytes = total_mb * 1024 * 1024
    used_bytes = used_mb * 1024 * 1024
    free_bytes = free_mb * 1024 * 1024
    used_pct = round((used_bytes / total_bytes) * 100, 1) if total_bytes > 0 else 0.0

    drive_info = {
        "fs_type": "APA / PFS",
        "filesystem": "APA / PFS",
        "total_bytes": total_bytes,
        "used_bytes": used_bytes,
        "free_bytes": free_bytes,
        "total_fmt": format_size(total_bytes),
        "used_fmt": format_size(used_bytes),
        "free_fmt": format_size(free_bytes),
        "used_pct": used_pct,
    }

    return {
        "games": games,
        "installed_ids": sorted(installed_ids),
        "installed_titles": sorted(installed_titles),
        "drive_info": drive_info,
    }


def parse_pfsshell_partitions(output: str) -> List[Dict]:
    """Parse unmounted `pfsshell` `ls` output into structured APA partition dicts."""
    partitions: List[Dict] = []
    seen = set()
    for line in (output or "").splitlines():
        m = PFSSHELL_PART_RE.match(line)
        if not m:
            continue
        type_hex = f"0x{m.group(1).lower()}"
        size_mb = int(m.group(2))
        name = m.group(3).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        name_low = name.lower()
        is_pfs = (type_hex == "0x0100")
        is_hdl = (type_hex == "0x1337")
        is_mbr = (type_hex == "0x0001")
        is_system = is_mbr or name_low in PROTECTED_PARTITIONS or name.startswith("__")
        if is_mbr:
            type_label = "MBR"
        elif is_pfs:
            type_label = "PFS"
        elif is_hdl:
            type_label = "HDL Game"
        else:
            type_label = f"APA ({type_hex})"
        partitions.append({
            "name": name,
            "type_hex": type_hex,
            "type_label": type_label,
            "size_mb": size_mb,
            "size_bytes": size_mb * 1024 * 1024,
            "size_fmt": format_size(size_mb * 1024 * 1024),
            "is_pfs": is_pfs,
            "is_hdl": is_hdl,
            "is_system": is_system,
        })
    return partitions


def parse_pfsshell_ls(output: str) -> List[Dict]:
    """Parse mounted `pfsshell` `ls` output into sorted file/directory entry dicts."""
    entries: List[Dict] = []
    for line in (output or "").splitlines():
        m = PFSSHELL_ENTRY_RE.match(line)
        if not m:
            continue
        perms = m.group(1)
        size_bytes = int(m.group(2))
        modified = m.group(3).strip()
        raw_name = m.group(4).strip()
        is_dir = perms.startswith("d") or raw_name.endswith("/")
        name = raw_name.rstrip("/")
        if not name or name in (".", ".."):
            continue
        ext = "" if is_dir else os.path.splitext(name)[1].lower()
        entries.append({
            "name": name,
            "is_dir": is_dir,
            "size_bytes": size_bytes,
            "size_fmt": "Folder" if is_dir else format_size(size_bytes),
            "perms": perms,
            "modified": modified,
            "ext": ext,
            "is_image": (not is_dir) and ext in (".png", ".jpg", ".jpeg"),
        })
    entries.sort(key=lambda e: (0 if e["is_dir"] else 1, e["name"].lower()))
    return entries


def query_ps2_hdd_drives(hdl_dump_exe: str, pfsshell_exe: str) -> Dict:
    """Query connected PS2 APA hard drives via `hdl_dump.exe query`."""
    admin = is_admin()
    has_hdl = bool(hdl_dump_exe and os.path.exists(hdl_dump_exe))
    has_pfs = bool(pfsshell_exe and os.path.exists(pfsshell_exe))

    if not has_hdl:
        return {
            "is_admin": admin,
            "hdl_dump_available": False,
            "pfsshell_available": has_pfs,
            "drives": [],
            "total_scanned_drives": 0,
            "error": "hdl_dump.exe not found in application directory.",
        }

    try:
        proc = subprocess.run(
            [hdl_dump_exe, "query"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_hdl_env(),
            creationflags=_creationflags(),
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        ps2_drives, all_drives = parse_hdl_query_output(combined)
        error = ""
        if not admin and len(all_drives) == 0:
            error = "Administrator privileges are required to detect raw physical PS2 hard drives on Windows."
        return {
            "is_admin": admin,
            "hdl_dump_available": True,
            "pfsshell_available": has_pfs,
            "drives": ps2_drives,
            "total_scanned_drives": len(all_drives),
            "error": error,
        }
    except Exception as e:
        return {
            "is_admin": admin,
            "hdl_dump_available": True,
            "pfsshell_available": has_pfs,
            "drives": [],
            "total_scanned_drives": 0,
            "error": str(e),
        }


def list_pfs_partitions(pfsshell_exe: str, hdd_device: str) -> Tuple[bool, List[str], List[Dict], str]:
    """Run `pfsshell.exe` to list APA partitions and check if `+OPL` exists."""
    if not pfsshell_exe or not os.path.exists(pfsshell_exe):
        return False, [], [], "pfsshell.exe not found"

    phys = hdd_to_physical_drive(hdd_device)
    _, output = run_pfsshell_script(pfsshell_exe, [f"device {phys}", "ls", "exit"], timeout=20)
    detailed = parse_pfsshell_partitions(output)
    names = [p["name"] for p in detailed]
    has_opl = any(p["name"].upper() == "+OPL" for p in detailed) or ("+OPL" in output)
    return has_opl, names, detailed, output


def _match_game_partition_name(game: Dict, hdl_partitions: List[Dict]) -> str:
    """Best-effort match an HDL game entry to its APA partition name (e.g. PP.SLUS-20062.. or PP.HDL...)."""
    raw_id = (game.get("raw_id") or "").upper()
    dash_id = raw_id.replace("_", "-")
    dotless_id = raw_id.replace(".", "")
    dash_dotless = dash_id.replace(".", "")
    title_low = (game.get("title") or "").lower()

    for p in hdl_partitions:
        pname = p["name"]
        p_up = pname.upper()
        if raw_id and (raw_id in p_up or dash_id in p_up or dotless_id in p_up or dash_dotless in p_up):
            return pname

    # Fallback: match sanitized title prefix in partition name
    if title_low:
        title_slug = re.sub(r'[^a-z0-9]+', '', title_low)
        for p in hdl_partitions:
            pslug = re.sub(r'[^a-z0-9]+', '', p["name"].lower())
            if title_slug and len(title_slug) >= 4 and title_slug[:12] in pslug:
                return p["name"]
    return ""


def inspect_ps2_hdd(hdl_dump_exe: str, pfsshell_exe: str, hdd_device: str) -> Dict:
    """Inspect a selected PS2 APA HDD (`hddN:`): installed games, space, and APA partitions."""
    dev = (hdd_device or "").strip().lower()
    phys = hdd_to_physical_drive(dev)

    if not hdl_dump_exe or not os.path.exists(hdl_dump_exe):
        raise FileNotFoundError("hdl_dump.exe not found.")

    proc = subprocess.run(
        [hdl_dump_exe, "hdl_toc", dev, "--csv"],
        capture_output=True,
        text=True,
        timeout=25,
        env=_hdl_env(),
        creationflags=_creationflags(),
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0 and "total" not in combined.lower():
        err_msg = combined.strip() or f"hdl_dump hdl_toc failed (exit code {proc.returncode})"
        raise RuntimeError(err_msg)

    toc_data = parse_hdl_toc_output(combined)
    has_opl, part_names, part_details, _ = list_pfs_partitions(pfsshell_exe, dev)

    hdl_parts = [p for p in part_details if p["is_hdl"]]
    for g in toc_data["games"]:
        g["partition_name"] = _match_game_partition_name(g, hdl_parts)

    return {
        "device": dev,
        "physical_drive": phys,
        "games": toc_data["games"],
        "installed_ids": toc_data["installed_ids"],
        "installed_titles": toc_data["installed_titles"],
        "drive_info": toc_data["drive_info"],
        "has_opl_partition": has_opl,
        "partitions": part_names,
        "partitions_detail": part_details,
    }


def pfs_list_dir(
    pfsshell_exe: str,
    hdd_device: str,
    partition: str = "+OPL",
    remote_dir: str = "/",
) -> Dict:
    """Browse a directory inside a PFS partition (default `+OPL`) via `pfsshell.exe`."""
    phys = hdd_to_physical_drive(hdd_device)
    part = sanitize_pfs_token(partition)
    segments = normalize_pfs_dir(remote_dir)
    norm_path = "/" + "/".join(segments) if segments else "/"

    commands = [f"device {phys}", f"mount {part}"]
    for seg in segments:
        commands.append(f"cd {seg}")
    commands.extend(["ls", "umount", "exit"])

    ok, output = run_pfsshell_script(pfsshell_exe, commands, timeout=25)
    entries = parse_pfsshell_ls(output)
    error = ""
    if not ok and not entries:
        error = output.splitlines()[-1] if output else f"Failed to browse {part}:{norm_path}"
    return {
        "device": hdd_device.strip().lower(),
        "partition": part,
        "path": norm_path,
        "segments": segments,
        "entries": entries,
        "error": error,
    }


def pfs_download_files(
    pfsshell_exe: str,
    hdd_device: str,
    partition: str,
    remote_dir: str,
    filenames: List[str],
    dest_dir: str,
) -> Tuple[bool, str]:
    """Download one or more files from a PFS partition directory into `dest_dir` in one session."""
    safe_files = [sanitize_pfs_token(fn) for fn in filenames if fn]
    if not safe_files:
        return True, "No files requested."
    os.makedirs(dest_dir, exist_ok=True)
    phys = hdd_to_physical_drive(hdd_device)
    part = sanitize_pfs_token(partition)
    segments = normalize_pfs_dir(remote_dir)

    commands = [f"device {phys}", f"mount {part}"]
    for seg in segments:
        commands.append(f"cd {seg}")
    for fn in safe_files:
        commands.append(f"get {fn}")
    commands.extend(["umount", "exit"])

    return run_pfsshell_script(pfsshell_exe, commands, cwd=dest_dir, timeout=180)


def pfs_upload_files(
    pfsshell_exe: str,
    hdd_device: str,
    partition: str,
    remote_dir: str,
    local_dir: str,
    filenames: List[str],
    ensure_dir: bool = True,
) -> Tuple[bool, str]:
    """Upload one or more files from `local_dir` into `partition:remote_dir` in one session."""
    safe_files = [sanitize_pfs_token(os.path.basename(fn)) for fn in filenames if fn]
    if not safe_files:
        return True, "No files to upload."
    phys = hdd_to_physical_drive(hdd_device)
    part = sanitize_pfs_token(partition)
    segments = normalize_pfs_dir(remote_dir)

    commands = [f"device {phys}", f"mount {part}"]
    for seg in segments:
        if ensure_dir:
            commands.append(f"mkdir {seg}")
        commands.append(f"cd {seg}")
    for fn in safe_files:
        commands.append(f"put {fn}")
    commands.extend(["umount", "exit"])

    return run_pfsshell_script(pfsshell_exe, commands, cwd=local_dir, timeout=180)


def pfs_delete_entries(
    pfsshell_exe: str,
    hdd_device: str,
    partition: str,
    remote_dir: str,
    entries: List[Tuple[str, bool]],
) -> Tuple[bool, str]:
    """Delete files or empty folders inside `partition:remote_dir`. Each item is (name, is_dir)."""
    if not entries:
        return True, "Nothing to delete."
    phys = hdd_to_physical_drive(hdd_device)
    part = sanitize_pfs_token(partition)
    segments = normalize_pfs_dir(remote_dir)

    commands = [f"device {phys}", f"mount {part}"]
    for seg in segments:
        commands.append(f"cd {seg}")
    for name, is_dir in entries:
        safe = sanitize_pfs_token(name)
        commands.append(f"rmdir {safe}" if is_dir else f"rm {safe}")
    commands.extend(["umount", "exit"])

    return run_pfsshell_script(pfsshell_exe, commands, timeout=60)


def pfs_mkdir(
    pfsshell_exe: str,
    hdd_device: str,
    partition: str,
    remote_dir: str,
    folder_name: str,
) -> Tuple[bool, str]:
    """Create a folder inside `partition:remote_dir`."""
    phys = hdd_to_physical_drive(hdd_device)
    part = sanitize_pfs_token(partition)
    segments = normalize_pfs_dir(remote_dir)
    new_dir = sanitize_pfs_token(folder_name)

    commands = [f"device {phys}", f"mount {part}"]
    for seg in segments:
        commands.append(f"cd {seg}")
    commands.extend([f"mkdir {new_dir}", "umount", "exit"])

    return run_pfsshell_script(pfsshell_exe, commands, timeout=30)


def pfs_create_opl_partition(
    pfsshell_exe: str,
    hdd_device: str,
    size_mb: int = 256,
) -> Tuple[bool, str]:
    """Create and format the `+OPL` PFS partition (power of 2 in MB: 128..2048)."""
    if size_mb not in (128, 256, 512, 1024, 2048):
        raise ValueError("Partition size must be 128, 256, 512, 1024, or 2048 MB.")
    phys = hdd_to_physical_drive(hdd_device)
    commands = [
        f"device {phys}",
        f"mkpart +OPL {size_mb}M",
        "mkfs +OPL",
        "mount +OPL",
        "mkdir ART",
        "mkdir CFG",
        "mkdir VMC",
        "umount",
        "exit",
    ]
    return run_pfsshell_script(pfsshell_exe, commands, timeout=60)


def hdl_rename_game(
    hdl_dump_exe: str,
    hdd_device: str,
    current_title: str,
    new_title: str,
) -> Tuple[bool, str]:
    """Rename an installed HDL game via `hdl_dump.exe modify`."""
    dev = (hdd_device or "").strip().lower()
    hdd_to_physical_drive(dev)
    if not hdl_dump_exe or not os.path.exists(hdl_dump_exe):
        return False, "hdl_dump.exe not found."
    safe_new = sanitize_hdl_title(new_title)
    if not current_title or not safe_new:
        return False, "Both current title and new title are required."
    try:
        proc = subprocess.run(
            [hdl_dump_exe, "modify", dev, current_title, safe_new],
            capture_output=True,
            text=True,
            timeout=25,
            cwd=tempfile.gettempdir(),
            env=_hdl_env(),
            creationflags=_creationflags(),
        )
        out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return proc.returncode == 0, out
    except Exception as e:
        return False, str(e)


def pfs_remove_hdl_partition(
    pfsshell_exe: str,
    hdd_device: str,
    partition_name: str,
) -> Tuple[bool, str]:
    """Safely delete an HDL game partition via `pfsshell rmpart` (blocks system/+OPL partitions)."""
    phys = hdd_to_physical_drive(hdd_device)
    part = (partition_name or "").strip()
    if not part or any(ch in part for ch in ("\n", "\r", "\x00")):
        return False, "Invalid partition name."
    if part.lower() in PROTECTED_PARTITIONS or part.startswith("__"):
        return False, f"Refused to remove protected system partition '{part}'."
    commands = [f"device {phys}", f"rmpart {part}", "exit"]
    return run_pfsshell_script(pfsshell_exe, commands, timeout=60)


def upload_opl_assets_to_pfs(
    pfsshell_exe: str,
    hdd_device: str,
    stage_root: str,
    art_files: Optional[List[str]] = None,
    cfg_files: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Batch-upload staged ART/ and CFG/ files into the `+OPL` PFS partition in one pfsshell session.

    Uses `cwd=stage_root` and relative `lcd ART` / `lcd CFG` so paths never contain spaces.
    """
    art_files = [os.path.basename(f) for f in (art_files or []) if f]
    cfg_files = [os.path.basename(f) for f in (cfg_files or []) if f]
    if not art_files and not cfg_files:
        return True, "No ART or CFG files to upload."

    if not pfsshell_exe or not os.path.exists(pfsshell_exe):
        return False, "pfsshell.exe not found."

    phys = hdd_to_physical_drive(hdd_device)
    commands = [
        f"device {phys}",
        "mount +OPL",
    ]

    if art_files:
        commands.append("mkdir ART")
        commands.append("cd ART")
        commands.append("lcd ART")
        for fn in art_files:
            commands.append(f"put {fn}")
        commands.append("cd /")
        commands.append("lcd ..")

    if cfg_files:
        commands.append("mkdir CFG")
        commands.append("cd CFG")
        commands.append("lcd CFG")
        for fn in cfg_files:
            commands.append(f"put {fn}")
        commands.append("cd /")
        commands.append("lcd ..")

    commands.append("umount")
    commands.append("exit")

    return run_pfsshell_script(pfsshell_exe, commands, cwd=stage_root, timeout=180)
