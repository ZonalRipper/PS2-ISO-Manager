import os
import sys
import re
import zlib
import hashlib
import shutil
import struct
import ctypes

BYTE_GAME_ID_PATTERN = re.compile(
    rb'[SBPM][LCEPAKOWV][USEIADM]S?_\d{3}\.\d{2}',
    re.IGNORECASE,
)
FILENAME_GAME_ID_PATTERN = re.compile(
    r'[SBPM][LCEPAKOWV][USEIADM]S?[-_]\d{3}\.?\d{2}',
    re.IGNORECASE,
)

MAX_SCAN_BYTES = 15 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
OVERLAP_SIZE = 32


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller _MEIPASS"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def extract_game_id(file_path):
    """Extract (clean_id, raw_id) from a PS2 disc image header or filename fallback."""
    try:
        with open(file_path, 'rb') as f:
            bytes_read = 0
            tail = b""
            while bytes_read < MAX_SCAN_BYTES:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                bytes_read += len(chunk)
                buffer = tail + chunk
                match = BYTE_GAME_ID_PATTERN.search(buffer)
                if match:
                    raw_id = match.group(0).decode('ascii', errors='ignore').upper()
                    clean_id = raw_id.replace('_', '').replace('.', '').replace('-', '').upper()
                    return clean_id, raw_id
                tail = buffer[-OVERLAP_SIZE:]
    except Exception as e:
        print(f"Error scanning file headers: {e}")

    filename = os.path.basename(file_path)
    match = FILENAME_GAME_ID_PATTERN.search(filename)
    if match:
        raw_id = match.group(0).upper()
        clean_id = raw_id.replace('_', '').replace('.', '').replace('-', '').upper()
        std_raw_id = f"{clean_id[:4]}_{clean_id[4:7]}.{clean_id[7:]}"
        return clean_id, std_raw_id

    return None, None


def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_drive_info(path: str) -> dict:
    """Return filesystem type and disk space info for a given path."""
    target = os.path.abspath(path) if path else ""
    while target and not os.path.exists(target):
        parent = os.path.dirname(target)
        if parent == target:
            break
        target = parent
    if not target or not os.path.exists(target):
        return {
            "fs_type": "Unknown",
            "total_bytes": 0,
            "used_bytes": 0,
            "free_bytes": 0,
            "total_fmt": "0 B",
            "used_fmt": "0 B",
            "free_fmt": "0 B",
            "used_pct": 0.0,
        }

    usage = shutil.disk_usage(target)
    fs_type = "Unknown"
    if os.name == "nt":
        try:
            drive_root = os.path.splitdrive(target)[0] + "\\"
            fs_buf = ctypes.create_unicode_buffer(64)
            vol_buf = ctypes.create_unicode_buffer(261)
            res = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive_root),
                vol_buf,
                ctypes.sizeof(vol_buf),
                None,
                None,
                None,
                fs_buf,
                ctypes.sizeof(fs_buf),
            )
            if res and fs_buf.value:
                fs_type = fs_buf.value.upper()
        except Exception:
            pass

    used_pct = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0
    return {
        "fs_type": fs_type,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "total_fmt": format_size(usage.total),
        "used_fmt": format_size(usage.used),
        "free_fmt": format_size(usage.free),
        "used_pct": used_pct,
    }


def opl_ul_crc32(game_name: str) -> int:
    """Compute OPL USBUtil 32-bit CRC hash for a game title (up to 32 bytes)."""
    raw_bytes = game_name.encode('ascii', errors='replace')[:32]
    crctab = [0] * 256
    for table_idx in range(256):
        crc = table_idx << 24
        for _ in range(8):
            if crc < 0:
                crc = (crc << 1) ^ 0x04C11DB7
            else:
                crc = crc << 1
            crc &= 0xFFFFFFFF
            if crc & 0x80000000:
                crc -= 0x100000000
        crctab[table_idx] = crc & 0xFFFFFFFF

    crc = 0
    for b in raw_bytes + b'\x00':
        index = ((crc >> 24) ^ b) & 0xFF
        crc = ((crc << 8) ^ crctab[index]) & 0xFFFFFFFF
    return (~crc) & 0xFFFFFFFF


def split_iso_to_ul(iso_path: str, opl_root: str, raw_id: str, game_title: str, progress_cb=None) -> int:
    """Split a >4GB ISO into 1GB USBUtil chunks (ul.<CRC>.<ID>.00..) and update ul.cfg."""
    CHUNK_LIMIT = 1024 * 1024 * 1024  # 1 GB per USBUtil part
    COPY_BUF = 4 * 1024 * 1024
    clean_name = (game_title or raw_id)[:32]
    crc_val = opl_ul_crc32(clean_name)
    crc_hex = f"{crc_val:08X}"

    total_size = os.path.getsize(iso_path)
    num_parts = max(1, (total_size + CHUNK_LIMIT - 1) // CHUNK_LIMIT)

    created_parts = []
    try:
        with open(iso_path, 'rb') as src:
            for part_idx in range(num_parts):
                part_name = f"ul.{crc_hex}.{raw_id}.{part_idx:02d}"
                part_path = os.path.join(opl_root, part_name)
                bytes_left = min(CHUNK_LIMIT, total_size - (part_idx * CHUNK_LIMIT))
                with open(part_path, 'wb') as dst:
                    while bytes_left > 0:
                        chunk = src.read(min(COPY_BUF, bytes_left))
                        if not chunk:
                            break
                        dst.write(chunk)
                        bytes_left -= len(chunk)
                created_parts.append(part_path)
                if progress_cb:
                    progress_cb(part_idx + 1, num_parts, part_name)

        # Build 64-byte ul.cfg entry
        name_field = clean_name.encode('ascii', errors='replace')[:32].ljust(32, b'\x00')
        id_str = f"ul.{raw_id}".encode('ascii', errors='replace')[:14].ljust(15, b'\x00')
        media_byte = 0x14 if total_size >= 700 * 1024 * 1024 else 0x12
        pad_tail = bytearray(15)
        pad_tail[4] = 0x08  # USBUtil compatibility flag
        entry = name_field + id_str + struct.pack("BB", num_parts, media_byte) + bytes(pad_tail)

        ul_cfg_path = os.path.join(opl_root, "ul.cfg")
        existing_entries = []
        if os.path.exists(ul_cfg_path):
            with open(ul_cfg_path, 'rb') as f:
                data = f.read()
            for offset in range(0, len(data), 64):
                rec = data[offset:offset + 64]
                if len(rec) == 64 and rec[32:32 + len(f"ul.{raw_id}")] != f"ul.{raw_id}".encode('ascii'):
                    existing_entries.append(rec)
        existing_entries.append(entry)
        with open(ul_cfg_path, 'wb') as f:
            for rec in existing_entries:
                f.write(rec)

        return num_parts
    except Exception:
        for p in created_parts:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        raise


def read_ul_cfg_ids(opl_root: str) -> set:
    """Return a set of raw Game IDs registered in ul.cfg on an OPL root."""
    ids = set()
    ul_cfg_path = os.path.join(opl_root, "ul.cfg")
    if not os.path.exists(ul_cfg_path):
        return ids
    try:
        with open(ul_cfg_path, 'rb') as f:
            data = f.read()
        for offset in range(0, len(data), 64):
            rec = data[offset:offset + 64]
            if len(rec) == 64:
                raw_field = rec[32:47].split(b'\x00', 1)[0].decode('ascii', errors='ignore')
                if raw_field.upper().startswith("UL."):
                    ids.add(raw_field[3:].upper())
    except Exception:
        pass
    return ids


def verify_disc_image(file_path: str, compute_hashes: bool = True) -> dict:
    """Verify structural integrity of a PS2 image (.iso, .zso, .bin, .chd) and optionally compute CRC32/MD5."""
    ext = os.path.splitext(file_path)[1].lower()
    size_bytes = os.path.getsize(file_path)
    issues = []

    if size_bytes < 64 * 1024:
        issues.append("File is abnormally small (<64 KB)")

    try:
        with open(file_path, 'rb') as f:
            header = f.read(65536)
            if ext == '.iso':
                if size_bytes % 2048 != 0:
                    issues.append(f"Non-standard sector alignment ({size_bytes % 2048} trailing bytes)")
                # Check ISO9660 primary volume descriptor at sector 16 (0x8000)
                if len(header) >= 0x8006 and header[0x8001:0x8006] != b'CD001':
                    issues.append("Missing ISO9660 'CD001' signature at sector 16")
            elif ext == '.zso':
                if header[:4] != b'ZISO':
                    issues.append("Invalid ZSO magic header (expected 'ZISO')")
                elif len(header) >= 24:
                    header_size, total_bytes, block_size, ver, align = struct.unpack("<IIQBBxx", header[4:24])
                    if total_bytes == 0 or block_size not in (512, 1024, 2048, 4096):
                        issues.append(f"Suspicious ZSO header values (block={block_size})")
            elif ext == '.chd':
                if header[:8] != b'MComprHD':
                    issues.append("Invalid CHD magic header (expected 'MComprHD')")
            elif ext == '.bin':
                if size_bytes % 2352 != 0 and size_bytes % 2048 != 0:
                    issues.append("File size is not a multiple of 2352 (raw CD) or 2048 bytes")
    except Exception as e:
        issues.append(f"Read error: {e}")

    crc_val = 0
    md5_hasher = hashlib.md5()
    if compute_hashes and not issues:
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    crc_val = zlib.crc32(chunk, crc_val)
                    md5_hasher.update(chunk)
        except Exception as e:
            issues.append(f"Hash read error: {e}")

    crc_hex = f"{crc_val & 0xFFFFFFFF:08X}" if compute_hashes and not issues else "N/A"
    md5_hex = md5_hasher.hexdigest().upper() if compute_hashes and not issues else "N/A"
    healthy = len(issues) == 0
    return {
        "healthy": healthy,
        "crc32": crc_hex,
        "md5": md5_hex,
        "issues": issues,
        "summary": f"Healthy • CRC32: {crc_hex} • MD5: {md5_hex[:12]}..." if healthy else f"⚠️ {'; '.join(issues)}",
    }


def read_opl_cfg(cfg_path: str) -> dict:
    """Parse an OPL CFG/{raw_id}.cfg file into a dictionary."""
    result = {}
    if not os.path.exists(cfg_path):
        return result
    try:
        with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                result[k.strip()] = v.strip()
    except Exception:
        pass
    return result


def write_opl_cfg(cfg_path: str, data: dict) -> None:
    """Write an OPL CFG/{raw_id}.cfg file preserving any custom keys."""
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    ordered_keys = [
        "CfgVersion",
        "$ConfigSource",
        "Title",
        "Developer",
        "Publisher",
        "Genre",
        "Release",
        "Region",
        "Players",
        "PlayersText",
        "Description",
        "Modes",
        "$Compatibility",
        "$VMC_0",
        "$VMC_1",
        "$EnableGSM",
        "$GSMVMode",
    ]
    written = set()
    lines = []
    for k in ordered_keys:
        if k in data and str(data[k]).strip() != "":
            lines.append(f"{k}={data[k]}")
            written.add(k)
    for k, v in data.items():
        if k not in written and str(v).strip() != "":
            lines.append(f"{k}={v}")
    with open(cfg_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")


def detect_bin_track_mode(bin_path: str) -> str:
    """Inspect a .bin disc image to detect its sector track mode (MODE2/2352, MODE1/2352, or MODE1/2048)."""
    try:
        size_bytes = os.path.getsize(bin_path)
        with open(bin_path, 'rb') as f:
            header = f.read(65536)

        # Check ISO9660 'CD001' Primary Volume Descriptor at Sector 16
        # 1. Raw 2352-byte sector Mode 2 XA (24-byte header before 2048-byte user data)
        s16_raw = 16 * 2352
        if len(header) >= s16_raw + 30 and header[s16_raw + 25:s16_raw + 30] == b'CD001':
            return "MODE2/2352"
        # 2. Raw 2352-byte sector Mode 1 (16-byte header before 2048-byte user data)
        if len(header) >= s16_raw + 22 and header[s16_raw + 17:s16_raw + 22] == b'CD001':
            return "MODE1/2352"
        # 3. Cooked 2048-byte sector Mode 1
        s16_iso = 16 * 2048
        if len(header) >= s16_iso + 6 and header[s16_iso + 1:s16_iso + 6] == b'CD001':
            return "MODE1/2048"

        # Check Sector 0 CD-ROM 12-byte sync pattern (00 FF x 10 00) + mode byte at offset 15
        if len(header) >= 16 and header[:12] == b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00':
            if header[15] == 1:
                return "MODE1/2352"
            return "MODE2/2352"

        if size_bytes > 0 and size_bytes % 2048 == 0 and size_bytes % 2352 != 0:
            return "MODE1/2048"
    except Exception:
        pass
    return "MODE2/2352"


def generate_cue_for_bin(bin_path: str) -> tuple:
    """Create a matching .cue file next to `bin_path` using the auto-detected sector mode.

    Returns (cue_path, track_mode).
    """
    track_mode = detect_bin_track_mode(bin_path)
    base, _ = os.path.splitext(bin_path)
    cue_path = base + ".cue"
    bin_filename = os.path.basename(bin_path)
    cue_contents = (
        f'FILE "{bin_filename}" BINARY\n'
        f'  TRACK 01 {track_mode}\n'
        f'    INDEX 01 00:00:00\n'
    )
    with open(cue_path, 'w', encoding='utf-8') as f:
        f.write(cue_contents)
    return cue_path, track_mode


