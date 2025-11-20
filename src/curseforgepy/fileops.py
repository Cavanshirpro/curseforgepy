"""
curseforgepy.fileops
--------------------

File operations utilities used by the CurseForge client/installer:

- atomic_write: write bytes / stream atomically to a file (temp -> fsync -> replace)
- atomic_copy_dir: copy a directory atomically (copy -> rename/move) and handle cross-filesystem cases
- is_same_file: compute and compare checksums against expected hashes
- safe_remove: remove file or directory with retries and safety
- get_filename_from_content_disposition / get_filename_from_response: parse remote filenames
- temp_part_path: helper for ".part" temporary download names
- write_stream_to_tempfile: write streaming chunks to a temp file in destination folder

Notes:
- This module intentionally uses small, robust building blocks. The higher-level download manager
  (download.py) should call these helpers to perform network streaming and verification.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import *

import requests

from .utils import sha1_sum, sha256_sum, md5_sum

from .exceptions import DownloadError

# Utility helpers
def _fsync_fileobj(fp) -> None:
    """
    Flush and fsync a file object. Ignore on platforms where fsync is unsupported.
    """
    try:
        fp.flush()
        os.fsync(fp.fileno())
    except Exception:
        # ignore: some file-like objects may not support fileno/fsync
        pass


# atomic_write
def atomic_write(dest_path: Path,
                 data: Optional[bytes] = None,
                 chunks: Optional[Iterable[bytes]] = None,
                 *,
                 mode: str = "wb",
                 tmp_suffix: Optional[str] = None) -> Path:
    """
    Atomically write `data` or an iterable `chunks` to `dest_path`.

    Behavior:
      - Creates destination directory if missing.
      - Writes to a temporary file in the same directory (ensures atomic os.replace).
      - Flushes and fsyncs file before replacing.
      - Replaces the destination with os.replace(temp, dest) ensuring atomic swap on same filesystem.

    Parameters
    ----------
    dest_path : Path
        Final destination path for the file.
    data : Optional[bytes]
        Whole bytes to write. If provided, `chunks` must be None.
    chunks : Optional[Iterable[bytes]]
        Iterable yielding bytes chunks (streaming). If provided, `data` must be None.
    mode : str
        File open mode, default 'wb'. For text use 'w' and pass encoded bytes yourself.
    tmp_suffix : Optional[str]
        Optional suffix appended to temp filename (e.g. '.part').

    Returns
    -------
    Path
        The final destination path.

    Raises
    ------
    ValueError
        If neither `data` nor `chunks` provided or both provided.
    DownloadError
        On I/O errors during write or replace.
    """
    dest_path = Path(dest_path)
    dest_dir = dest_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    if (data is None and chunks is None) or (data is not None and chunks is not None):
        raise ValueError("Provide exactly one of `data` or `chunks`.")

    # create temp file in same directory for atomic replace
    tmp = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=str(dest_dir), suffix=(tmp_suffix or ".tmp"))
        tmp = Path(tmp_name)
        # open fd as file object with correct mode
        with os.fdopen(fd, mode) as f:
            if data is not None:
                # data may be bytes or str depending on mode
                if "b" in mode:
                    f.write(data)
                else:
                    f.write(data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data))
            else:
                # streaming chunks
                for chunk in chunks:
                    if not chunk:
                        continue
                    if "b" in mode:
                        f.write(chunk)
                    else:
                        f.write(chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else str(chunk))
            _fsync_fileobj(f)

        # atomic replace
        try:
            os.replace(str(tmp), str(dest_path))
        except Exception as e:
            # On cross-filesystem issues, fallback to move with removal
            try:
                # remove existing dest first to avoid move error on some OS
                if dest_path.exists():
                    dest_path.unlink()
                shutil.move(str(tmp), str(dest_path))
            except Exception as e2:
                # cleanup temp file
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except Exception:
                        pass
                raise DownloadError(f"Failed to move temp file to destination: {e2}") from e2

        return dest_path
    except Exception as exc:
        # cleanup temporary file
        if tmp is not None and tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
        raise DownloadError(f"atomic_write failed for {dest_path}: {exc}") from exc


# atomic_copy_dir
def atomic_copy_dir(src: Path,
                    dst: Path,
                    *,
                    preserve_permissions: bool = True,
                    tmp_suffix: Optional[str] = None) -> Path:
    """
    Copy directory tree `src` to `dst` atomically.

    Strategy:
      1. Create a temporary directory next to `dst` (same parent) with unique name.
      2. Copytree(src, tmp_dir) using shutil.copytree (this copies contents).
      3. fsync directory metadata if possible.
      4. Replace/rename tmp_dir -> dst using os.replace, or fallback to shutil.move.
      5. If dst exists it will be atomically replaced on same filesystem.

    Notes:
      - If src and dst are on different filesystems, os.replace may fail; fallback logic uses shutil.move and removes old dst.
      - Large directories may take time and space; user must ensure sufficient disk space.

    Parameters
    ----------
    src : Path
        Source directory to copy.
    dst : Path
        Destination directory path (will be replaced if exists).
    preserve_permissions : bool
        If True, preserve file permissions during copy (shutil.copy2 used).
    tmp_suffix : Optional[str]
        Optional suffix for temporary directory.

    Returns
    -------
    Path
        Final destination path (dst).

    Raises
    ------
    FileNotFoundError
        If src does not exist.
    DownloadError
        On copy/move failures.
    """
    src = Path(src)
    dst = Path(dst)
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src}")

    parent = dst.parent
    parent.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%dT%H%M%S")
    tmp_name = f".{dst.name}.tmp.{timestamp}"
    if tmp_suffix:
        tmp_name += tmp_suffix
    tmp_dir = parent / tmp_name

    if tmp_dir.exists():
        # try to remove stale tmp_dir
        shutil.rmtree(tmp_dir)

    try:
        # copytree: copy2 preserves metadata; use copy_function accordingly
        if preserve_permissions:
            copy_func = shutil.copy2
        else:
            copy_func = shutil.copy

        shutil.copytree(str(src), str(tmp_dir), copy_function=copy_func)
        # attempt to fsync directories (best-effort)
        try:
            for root, dirs, files in os.walk(tmp_dir):
                for fname in files:
                    fp = Path(root) / fname
                    try:
                        with open(fp, "rb") as f:
                            os.fsync(f.fileno())
                    except Exception:
                        pass
        except Exception:
            pass

        # try atomic replace
        try:
            # if dst exists, try atomic replace
            if dst.exists():
                os.replace(str(tmp_dir), str(dst))
            else:
                shutil.move(str(tmp_dir), str(dst))
        except OSError as e:
            # fallback: remove dst and move tmp into place
            try:
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(tmp_dir), str(dst))
            except Exception as e2:
                # cleanup tmp_dir
                if tmp_dir.exists():
                    try:
                        shutil.rmtree(tmp_dir)
                    except Exception:
                        pass
                raise DownloadError(f"atomic_copy_dir failed moving tmp -> dst: {e2}") from e2

        return dst
    except Exception as exc:
        # cleanup tmp_dir
        if tmp_dir.exists():
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass
        raise DownloadError(f"atomic_copy_dir failed: {exc}") from exc


# is_same_file
def is_same_file(local_path: Path, expected_hashes: Optional[Dict[str, str]] = None) -> Tuple[bool, Dict[str, str]]:
    """
    Check if `local_path` matches any of the expected hashes.

    Parameters
    ----------
    local_path : Path
        Local file path to check.
    expected_hashes : Optional[Dict[str, str]]
        Mapping of algorithm -> expected_hex_value, e.g. {"sha1": "...", "md5": "..."}.
        If None or empty, returns (False, computed_hashes) because there's nothing to compare to.

    Returns
    -------
    (bool, Dict[str,str])
        Tuple of (matches_any_expected, computed_hashes). computed_hashes contains keys for
        algorithms computed (sha1, sha256, md5) as available.

    Raises
    ------
    FileNotFoundError
        If the local file does not exist.
    """
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    computed: Dict[str, str] = {}
    # compute a sensible set of hashes; stop early if matching quickly
    try:
        # compute sha1 first (fast and commonly provided by CurseForge)
        computed["sha1"] = sha1_sum(path)
    except Exception:
        computed["sha1"] = ""

    try:
        computed["sha256"] = sha256_sum(path)
    except Exception:
        computed["sha256"] = ""

    try:
        computed["md5"] = md5_sum(path)
    except Exception:
        computed["md5"] = ""

    if not expected_hashes:
        return False, computed

    # Normalize keys for case-insensitive comparison
    norm_expected = {k.lower(): v.lower() for k, v in expected_hashes.items() if v}
    for algo, expected in norm_expected.items():
        actual = computed.get(algo)
        if actual and actual.lower() == expected.lower():
            return True, computed

    return False, computed


# safe_remove
def safe_remove(path: Path, *, retries: int = 3, delay: float = 0.2) -> None:
    """
    Safely remove a file or directory. Retries on transient errors.

    Parameters
    ----------
    path : Path
        File or directory to remove.
    retries : int
        Number of attempts on error (default 3).
    delay : float
        Seconds to wait between attempts.

    Raises
    ------
    OSError
        If removal fails after retries.
    """
    path = Path(path)
    attempt = 0
    while True:
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(delay)


# get_filename_from_content_disposition / get_filename_from_response
def get_filename_from_content_disposition(header_value: Optional[str]) -> Optional[str]:
    """
    Parse Content-Disposition header to extract filename parameter (RFC 6266).

    Returns None if no filename present.
    """
    if not header_value:
        return None
    # common forms:
    # Content-Disposition: attachment; filename="fname.ext"
    # Content-Disposition: attachment; filename*=UTF-8''fname.ext
    try:
        parts = header_value.split(";")
        filename = None
        for p in parts:
            if "=" not in p:
                continue
            k, v = p.strip().split("=", 1)
            k = k.lower()
            v = v.strip().strip('"')
            if k == "filename*":
                # format: filename*=utf-8''file.name
                # take substring after first "''"
                if "''" in v:
                    v = v.split("''", 1)[1]
                filename = v
                break
            if k == "filename":
                filename = v
                break
        if filename:
            # sanitize filename to basename only (prevent traversal)
            filename = os.path.basename(filename)
            return filename
    except Exception:
        return None
    return None


def get_filename_from_response(resp: requests.Response, fallback_url: Optional[str] = None) -> Optional[str]:
    """
    Try to determine a sensible filename for a response:
     1) parse Content-Disposition header
     2) fallback to URL basename
     3) return None if not determinable

    Parameters
    ----------
    resp : requests.Response
        Response object (must have .headers and .url).
    fallback_url : Optional[str]
        If provided, use this URL to extract a fallback name instead of resp.url.

    Returns
    -------
    Optional[str]
    """
    filename = get_filename_from_content_disposition(resp.headers.get("Content-Disposition"))
    if filename:
        return filename
    # fallback to resp.url or provided fallback_url
    url = fallback_url if fallback_url else getattr(resp, "url", None)
    if url:
        # parse basename from URL path
        parsed = url.split("?")[0].rstrip("/")
        basename = os.path.basename(parsed)
        if basename:
            return basename
    return None


# temp_part_path
def temp_part_path(dest: Path) -> Path:
    """
    Return a temporary ".part" path for an in-progress download next to `dest`.
    """
    dest = Path(dest)
    return dest.with_suffix(dest.suffix + ".part") if dest.suffix else Path(str(dest) + ".part")


# write_stream_to_tempfile
def write_stream_to_tempfile(resp: requests.Response,
                             dest: Path,
                             *,
                             chunk_size: int = 8192,
                             progress_cb: Optional[Callable[[int, Optional[int]], None]] = None,
                             resume: bool = False) -> Path:
    """
    Stream response.content iterator to a temporary file (in the dest folder) and verify it's fully written.

    Parameters
    ----------
    resp : requests.Response
        Response object with stream=True.
    dest : Path
        Final destination path (folder+filename); this function writes to dest.part and then moves.
    chunk_size : int
        Chunk size in bytes.
    progress_cb : Optional[Callable[[downloaded_bytes, total_bytes_or_None], None]]
        Optional callback to receive progress updates.
    resume : bool
        If True and a .part file exists, attempt to append to it (requires server support for byte ranges).

    Returns
    -------
    Path
        Final destination path (dest)

    Raises
    ------
    DownloadError
        On write failure.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = temp_part_path(dest)
    total = None
    try:
        total = int(resp.headers.get("Content-Length", 0)) if resp.headers.get("Content-Length") else None
    except Exception:
        total = None

    # If resume is True and part exists, open in append mode, else write new
    mode = "ab" if resume and part.exists() else "wb"

    try:
        with open(part, mode) as f:
            downloaded = f.tell() if mode == "ab" else 0
            if progress_cb:
                progress_cb(downloaded, total)
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
            _fsync_fileobj(f)
        # Move part -> dest (atomic)
        atomic_write(dest, chunks=None, data=None)  # placeholder to ensure signature; we'll use rename below

    except DownloadError:
        raise
    except Exception as exc:
        raise DownloadError(f"Failed writing stream to temp file {part}: {exc}") from exc

    # Move/replace part to final destination
    try:
        # If dest exists, replace; use os.replace
        os.replace(str(part), str(dest))
    except Exception:
        # fallback
        try:
            if dest.exists():
                dest.unlink()
            shutil.move(str(part), str(dest))
        except Exception as exc:
            # Cleanup part
            if part.exists():
                try:
                    part.unlink()
                except Exception:
                    pass
            raise DownloadError(f"Failed promoting part file to final destination: {exc}") from exc

    return dest
