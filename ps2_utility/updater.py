import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from typing import Callable, Dict, Optional, Tuple

from ps2_utility.core import format_size

APP_VERSION = "2.1.1"
GITHUB_OWNER = "ZonalRipper"
GITHUB_REPO = "PS2-ISO-Manager"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_WEB = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
EXPECTED_EXE_NAME = "PS2-ISO-Manager.exe"

ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
}

VERSION_RE = re.compile(r'v?(\d+(?:\.\d+){1,3})', re.IGNORECASE)


def parse_version_tuple(raw: str) -> Optional[Tuple[int, ...]]:
    """Extract a numeric version tuple from strings like 'v2.1', '2.0.1', or 'Release v2.1.3'."""
    if not raw:
        return None
    m = VERSION_RE.search(str(raw).strip())
    if not m:
        return None
    try:
        return tuple(int(part) for part in m.group(1).split("."))
    except ValueError:
        return None


def is_newer_version(latest_str: str, current_str: str = APP_VERSION) -> bool:
    """Return True strictly if latest_str parses to a higher numeric version than current_str."""
    latest = parse_version_tuple(latest_str)
    current = parse_version_tuple(current_str)
    if not latest or not current:
        return False
    max_len = max(len(latest), len(current))
    latest_pad = latest + (0,) * (max_len - len(latest))
    current_pad = current + (0,) * (max_len - len(current))
    return latest_pad > current_pad


def is_allowed_github_url(url: str) -> bool:
    """Ensure URL is HTTPS and hosted on an official GitHub domain."""
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https":
            return False
        return host in ALLOWED_DOWNLOAD_HOSTS or host.endswith(".githubusercontent.com")
    except Exception:
        return False


def can_self_update() -> bool:
    """Return True when running as a frozen standalone Windows executable."""
    return bool(getattr(sys, "frozen", False) and os.name == "nt")


def parse_github_release(payload: Dict, current_version: str = APP_VERSION) -> Dict:
    """Normalize a GitHub Releases API JSON payload into a clean update status dictionary."""
    tag_name = str(payload.get("tag_name") or "").strip()
    release_name = str(payload.get("name") or tag_name or "").strip()
    body = str(payload.get("body") or "").strip()
    published_at = str(payload.get("published_at") or "").strip()
    release_url = str(payload.get("html_url") or GITHUB_RELEASES_WEB).strip()
    if not is_allowed_github_url(release_url):
        release_url = GITHUB_RELEASES_WEB

    # Prefer numeric version in tag_name, fallback to release title
    parsed_ver = parse_version_tuple(tag_name) or parse_version_tuple(release_name)
    latest_version = ".".join(str(x) for x in parsed_ver) if parsed_ver else (tag_name or current_version)
    update_available = bool(parsed_ver and is_newer_version(latest_version, current_version))

    # Locate the Windows executable asset and optional SHA-256 asset
    assets = payload.get("assets") or []
    exe_asset = None
    sha_asset = None
    for a in assets:
        name = str(a.get("name") or "")
        low = name.lower()
        if low == EXPECTED_EXE_NAME.lower():
            exe_asset = a
            break
    if not exe_asset:
        for a in assets:
            name = str(a.get("name") or "")
            if name.lower().endswith(".exe"):
                exe_asset = a
                break
    for a in assets:
        low = str(a.get("name") or "").lower()
        if low.endswith(".sha256") or low in ("sha256sums.txt", "checksums.txt"):
            sha_asset = a
            break

    download_url = str(exe_asset.get("browser_download_url") or "") if exe_asset else ""
    if download_url and not is_allowed_github_url(download_url):
        download_url = ""
    asset_name = str(exe_asset.get("name") or EXPECTED_EXE_NAME) if exe_asset else EXPECTED_EXE_NAME
    asset_size = int(exe_asset.get("size") or 0) if exe_asset else 0

    sha_url = str(sha_asset.get("browser_download_url") or "") if sha_asset else ""
    if sha_url and not is_allowed_github_url(sha_url):
        sha_url = ""

    return {
        "status": "ok",
        "current_version": current_version,
        "latest_version": latest_version,
        "tag_name": tag_name,
        "release_name": release_name,
        "release_notes": body,
        "published_at": published_at[:10] if published_at else "",
        "release_url": release_url,
        "update_available": update_available,
        "download_url": download_url,
        "asset_name": asset_name,
        "asset_size": asset_size,
        "asset_size_fmt": format_size(asset_size) if asset_size > 0 else "Unknown",
        "sha256_url": sha_url,
        "can_self_update": can_self_update(),
        "error": "",
    }


def check_for_updates(current_version: str = APP_VERSION, timeout: int = 8) -> Dict:
    """Query GitHub Releases API for the latest PS2 ISO Manager release."""
    req = urllib.request.Request(
        GITHUB_RELEASES_API,
        headers={
            "User-Agent": f"PS2-ISO-Manager/{current_version}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
        return parse_github_release(payload, current_version=current_version)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {
                "status": "ok",
                "current_version": current_version,
                "latest_version": current_version,
                "update_available": False,
                "release_url": GITHUB_RELEASES_WEB,
                "can_self_update": can_self_update(),
                "error": "",
            }
        return {
            "status": "error",
            "current_version": current_version,
            "latest_version": current_version,
            "update_available": False,
            "release_url": GITHUB_RELEASES_WEB,
            "can_self_update": can_self_update(),
            "error": f"GitHub API returned HTTP {e.code}.",
        }
    except Exception as e:
        return {
            "status": "error",
            "current_version": current_version,
            "latest_version": current_version,
            "update_available": False,
            "release_url": GITHUB_RELEASES_WEB,
            "can_self_update": can_self_update(),
            "error": f"Could not reach GitHub: {e}",
        }


def _extract_expected_sha256(text: str, asset_name: str) -> Optional[str]:
    """Parse a 64-hex-char SHA-256 digest from a checksum file."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    for line in lines:
        if asset_name.lower() in line.lower():
            m = re.search(r'\b([0-9a-fA-F]{64})\b', line)
            if m:
                return m.group(1).lower()
    if len(lines) == 1:
        m = re.search(r'\b([0-9a-fA-F]{64})\b', lines[0])
        if m:
            return m.group(1).lower()
    return None


def download_and_verify_update(
    download_url: str,
    expected_size: int = 0,
    sha256_url: str = "",
    asset_name: str = EXPECTED_EXE_NAME,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    timeout: int = 120,
) -> Tuple[bool, str, str]:
    """Download the updated executable to a temp staging path and verify PE header, size, and optional SHA-256.

    Returns (ok, staged_path, error_msg).
    """
    if not is_allowed_github_url(download_url):
        return False, "", "Refused download: URL is not a trusted GitHub HTTPS release link."

    stage_dir = tempfile.mkdtemp(prefix="ps2_iso_mgr_update_")
    staged_path = os.path.join(stage_dir, EXPECTED_EXE_NAME)

    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": f"PS2-ISO-Manager/{APP_VERSION}"},
    )

    try:
        hasher = hashlib.sha256()
        downloaded = 0
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Verify final redirected URL is still on an allowed GitHub host
            final_url = resp.geturl()
            if final_url and not is_allowed_github_url(final_url):
                return False, "", "Refused download: redirect left trusted GitHub domains."

            cl_hdr = resp.headers.get("Content-Length")
            total = int(cl_hdr) if (cl_hdr and cl_hdr.isdigit()) else expected_size

            with open(staged_path, "wb") as out_f:
                while True:
                    chunk = resp.read(128 * 1024)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total, "Downloading update...")

        if progress_cb:
            progress_cb(downloaded, downloaded, "Verifying executable integrity...")

        # 1. Size check
        if downloaded < 1024 * 1024:
            return False, "", f"Downloaded file is too small ({format_size(downloaded)}) — aborting update."
        if expected_size > 0 and downloaded != expected_size:
            return False, "", f"Download size mismatch (got {downloaded:,} bytes, expected {expected_size:,})."

        # 2. Windows PE executable header ("MZ") check
        with open(staged_path, "rb") as f:
            magic = f.read(2)
        if magic != b"MZ":
            return False, "", "Downloaded file is not a valid Windows executable (missing MZ header)."

        # 3. Optional SHA-256 verification if a checksum file was attached to the GitHub Release
        if sha256_url and is_allowed_github_url(sha256_url):
            try:
                sreq = urllib.request.Request(sha256_url, headers={"User-Agent": f"PS2-ISO-Manager/{APP_VERSION}"})
                with urllib.request.urlopen(sreq, timeout=15) as sresp:
                    sha_text = sresp.read().decode("utf-8", errors="ignore")
                expected_hash = _extract_expected_sha256(sha_text, asset_name)
                if expected_hash:
                    actual_hash = hasher.hexdigest().lower()
                    if actual_hash != expected_hash:
                        return False, "", f"SHA-256 checksum mismatch! Expected {expected_hash[:12]}..., got {actual_hash[:12]}..."
            except Exception:
                # Don't silently fail if checksum asset couldn't be fetched — report cleanly
                return False, "", "Failed to verify SHA-256 checksum file from GitHub."

        return True, staged_path, ""
    except Exception as e:
        try:
            if os.path.exists(staged_path):
                os.remove(staged_path)
        except OSError:
            pass
        return False, "", f"Update download failed: {e}"


def _clean_relaunch_env() -> Dict[str, str]:
    """Return an environment dictionary stripped of PyInstaller onefile internal variables."""
    env = os.environ.copy()
    for key in list(env.keys()):
        up = key.upper()
        if up.startswith("_PYI_") or up.startswith("_MEIPASS") or up in ("TCL_LIBRARY", "TK_LIBRARY"):
            env.pop(key, None)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _ps_quote(value: str) -> str:
    """Safely single-quote a string literal for PowerShell."""
    return "'" + str(value).replace("'", "''") + "'"


def launch_self_replace_updater(
    staged_exe_path: str,
    target_exe_override: Optional[str] = None,
    wait_pid_override: Optional[int] = None,
    relaunch: bool = True,
) -> Tuple[bool, str]:
    """Spawn a detached PowerShell helper that waits for this app & PyInstaller bootloader to exit,
    safely swaps the EXE with retry + rollback protection, and relaunches the updated EXE.
    """
    if not target_exe_override and not can_self_update():
        return False, "Self-update is only available when running the standalone PS2-ISO-Manager.exe."

    if not staged_exe_path or not os.path.isfile(staged_exe_path):
        return False, "Staged update executable not found."

    current_exe = os.path.abspath(target_exe_override or sys.executable)
    target_dir = os.path.dirname(current_exe)
    target_stem = os.path.splitext(os.path.basename(current_exe))[0]
    pid = int(wait_pid_override if wait_pid_override is not None else os.getpid())
    ppid = int(os.getppid()) if wait_pid_override is None else 0

    # Ensure target directory is writable before committing to exit
    probe = os.path.join(target_dir, f".ps2_update_write_test_{pid}")
    try:
        with open(probe, "wb") as f:
            f.write(b"ok")
        os.remove(probe)
    except OSError:
        return False, f"Cannot write to '{target_dir}'. Run PS2-ISO-Manager.exe as Administrator or move it to a writable folder."

    backup_exe = current_exe + ".bak"
    stage_dir = os.path.dirname(os.path.abspath(staged_exe_path))
    temp_dir = tempfile.gettempdir()
    script_path = os.path.join(temp_dir, f"ps2_iso_mgr_apply_{pid}.ps1")
    log_path = os.path.join(temp_dir, "ps2_iso_mgr_update.log")

    ps_script = f"""$ErrorActionPreference = 'Stop'
$ChildPid = {pid}
$ParentPid = {ppid}
$Target = {_ps_quote(current_exe)}
$TargetDir = {_ps_quote(target_dir)}
$TargetStem = {_ps_quote(target_stem)}
$Staged = {_ps_quote(os.path.abspath(staged_exe_path))}
$Backup = {_ps_quote(backup_exe)}
$StageDir = {_ps_quote(stage_dir)}
$LogPath = {_ps_quote(log_path)}
$DoRelaunch = {'$true' if relaunch else '$false'}

function Write-Log([string]$Msg) {{
    try {{
        $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss.fff')
        Add-Content -LiteralPath $LogPath -Value "[$ts] $Msg" -Encoding UTF8
    }} catch {{}}
}}

Write-Log "Updater started (ChildPid=$ChildPid, ParentPid=$ParentPid, Target=$Target)"

# Clear any inherited PyInstaller environment variables so relaunched EXE extracts cleanly
foreach ($v in @('_MEIPASS2', '_PYI_APPLICATION_HOME_DIR', '_PYI_ARCHIVE_FILE', '_PYI_PARENT_PROCESS_LEVEL', 'TCL_LIBRARY', 'TK_LIBRARY')) {{
    Remove-Item -Path ("Env:" + $v) -ErrorAction SilentlyContinue
}}
$env:PYINSTALLER_RESET_ENVIRONMENT = '1'

# 1. Wait for Python child PID to exit (up to 30s)
for ($i = 0; $i -lt 60; $i++) {{
    if (-not (Get-Process -Id $ChildPid -ErrorAction SilentlyContinue)) {{
        Write-Log "Child PID $ChildPid exited after $($i * 500)ms"
        break
    }}
    Start-Sleep -Milliseconds 500
}}

# 2. Wait for PyInstaller parent bootloader PID to exit if it is the same executable (up to 15s)
if ($ParentPid -gt 0 -and $ParentPid -ne $ChildPid) {{
    for ($i = 0; $i -lt 30; $i++) {{
        $pp = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
        if (-not $pp -or $pp.ProcessName -ne $TargetStem) {{
            Write-Log "Parent bootloader PID $ParentPid finished after $($i * 500)ms"
            break
        }}
        Start-Sleep -Milliseconds 500
    }}
}}

# Brief settle pause for Windows file handle release
Start-Sleep -Milliseconds 500

$expectedLen = (Get-Item -LiteralPath $Staged).Length
$swapped = $false

# 3. Move old EXE to .bak and copy staged EXE into place (up to 30 retries / 15s)
for ($try = 1; $try -le 30; $try++) {{
    try {{
        if (Test-Path -LiteralPath $Backup) {{
            Remove-Item -LiteralPath $Backup -Force -ErrorAction SilentlyContinue
        }}
        if (Test-Path -LiteralPath $Target) {{
            Move-Item -LiteralPath $Target -Destination $Backup -Force
        }}
        Copy-Item -LiteralPath $Staged -Destination $Target -Force
        $actualLen = (Get-Item -LiteralPath $Target).Length
        if ($actualLen -eq $expectedLen) {{
            $swapped = $true
            Write-Log "Swap succeeded on attempt $try ($actualLen bytes)"
            break
        }} else {{
            throw "Byte size mismatch after copy ($actualLen != $expectedLen)"
        }}
    }} catch {{
        Write-Log "Attempt $try failed: $($_.Exception.Message)"
        if ((-not (Test-Path -LiteralPath $Target)) -and (Test-Path -LiteralPath $Backup)) {{
            try {{ Move-Item -LiteralPath $Backup -Destination $Target -Force }} catch {{}}
        }}
        Start-Sleep -Milliseconds 500
    }}
}}

if ($swapped) {{
    Remove-Item -LiteralPath $Backup -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Staged -Force -ErrorAction SilentlyContinue
    if ((Test-Path -LiteralPath $StageDir) -and ($StageDir -like '*ps2_iso_mgr_update_*')) {{
        Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
    }}
}} else {{
    Write-Log "ERROR: All swap attempts failed; keeping original executable."
    if ((-not (Test-Path -LiteralPath $Target)) -and (Test-Path -LiteralPath $Backup)) {{
        try {{ Move-Item -LiteralPath $Backup -Destination $Target -Force }} catch {{}}
    }}
}}

if ($DoRelaunch -and (Test-Path -LiteralPath $Target)) {{
    Write-Log "Relaunching $Target"
    try {{
        Start-Process -FilePath $Target -WorkingDirectory $TargetDir
    }} catch {{
        Write-Log "Relaunch failed: $($_.Exception.Message)"
    }}
}}

try {{ Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue }} catch {{}}
"""

    try:
        # Write UTF-8 with BOM so Windows PowerShell 5.1 handles Unicode paths cleanly
        with open(script_path, "w", encoding="utf-8-sig") as f:
            f.write(ps_script)

        # Note: Never combine DETACHED_PROCESS with CREATE_NO_WINDOW on Windows (mutually exclusive in CreateProcess).
        flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            env=_clean_relaunch_env(),
            creationflags=flags,
        )
        return True, ""
    except Exception as e:
        return False, f"Failed to launch updater script: {e}"
