"""
curseforgepy.download
---------------------

Robust download helper used by the installer and client.

Features
- Resume-able downloads via "Range" header and .part temporary files
- Atomic promotion of completed downloads
- Checksum verification (sha1/sha256/md5)
- Retries with exponential backoff and honoring Retry-After
- Optional per-chunk progress callbacks and tqdm integration
- Bulk / parallel download helper
"""

from __future__ import annotations

import os
import time
import shutil
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import *
import requests

# Local helpers (adjust import path if your package layout differs)

from .fileops import (
    temp_part_path,
    is_same_file,
    get_filename_from_response,
    safe_remove,
)
from .utils import exponential_backoff, parse_retry_after
from .exceptions import DownloadError

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """
    Result object returned by download functions.

    Attributes
    ----------
    url : str
        The URL that was downloaded.
    path : Optional[Path]
        Final path of the downloaded file (None on failure).
    success : bool
        True if download completed and checksum (if provided) matched.
    attempts : int
        Number of attempts performed.
    bytes : int
        Number of bytes written.
    error : Optional[str]
        Error message on failure.
    """
    url: str
    path: Optional[Path]
    success: bool
    attempts: int
    bytes: int
    error: Optional[str] = None


ProgressCallback = Callable[[int, Optional[int], Dict[str, Any]], None]
# callback(downloaded_bytes, total_bytes_or_None, meta) -> None


class DownloadManager:
    """
    Manages downloads with resume, verification and retries.

    Parameters
    ----------
    session : Optional[requests.Session]
        Optional session to use. If not provided, a new session is created.
    max_retries : int
        Default maximum number of attempts per download.
    backoff_base : float
        Base interval for exponential backoff (seconds).
    timeout : float
        Per-request timeout (seconds) for socket operations.
    user_agent : Optional[str]
        If provided, set User-Agent header on the session.
    """

    def __init__(self,
                 session: Optional[requests.Session] = None,
                 *,
                 max_retries: int = 4,
                 backoff_base: float = 0.6,
                 timeout: float = 30.0,
                 user_agent: Optional[str] = None):
        self.session = session or requests.Session()
        self.max_retries = max(1, int(max_retries))
        self.backoff_base = float(backoff_base)
        self.timeout = float(timeout)
        if user_agent:
            self.session.headers.update({"User-Agent": user_agent})
        # Accept JSON by default for metadata calls if any
        self.session.headers.setdefault("Accept", "application/json")

    def _request_stream(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> requests.Response:
        """
        Perform a streaming GET request using the manager's session.
        This method does not retry; higher-level logic controls retries.
        """
        # pass through kwargs (timeout etc.)
        return self.session.get(url, stream=True, headers=headers or {}, timeout=self.timeout, **kwargs)

    def _attempt_download(self,
                          url: str,
                          dest_path: Path,
                          expected_hashes: Optional[Dict[str, str]] = None,
                          progress_cb: Optional[ProgressCallback] = None,
                          resume: bool = True) -> DownloadResult:
        """
        Single attempt to download url into dest_path, supporting resume if possible.
        Returns DownloadResult with success True/False.
        This does a *single* try (no retries) and raises nothing; caller decides to retry.
        """
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        part = temp_part_path(dest_path)

        headers = {}
        existing_size = 0
        if resume and part.exists():
            existing_size = part.stat().st_size
            headers["Range"] = f"bytes={existing_size}-"

        resp = None
        try:
            resp = self._request_stream(url, headers=headers)
        except Exception as e:
            return DownloadResult(url=url, path=None, success=False, attempts=1, bytes=0, error=str(e))

        # Handle HTTP status
        if resp.status_code in (404, 410):
            return DownloadResult(url=url, path=None, success=False, attempts=1, bytes=0,
                                  error=f"HTTP {resp.status_code}: {resp.reason}")

        if resp.status_code == 416:
            # Requested range not satisfiable: possible mismatch between remote file and local .part
            # Remove .part and try fresh download on caller's retry logic
            try:
                safe_remove(part)
            except Exception:
                pass
            return DownloadResult(url=url, path=None, success=False, attempts=1, bytes=0,
                                  error="416 Range Not Satisfiable: removed local .part; retrying fresh recommended")

        if resp.status_code == 429:
            # let caller handle retry-after; return error with info
            ra = parse_retry_after(resp.headers.get("Retry-After"))
            return DownloadResult(url=url, path=None, success=False, attempts=1, bytes=0,
                                  error=f"429 Rate limited; retry-after={ra}")

        if resp.status_code >= 400:
            return DownloadResult(url=url, path=None, success=False, attempts=1, bytes=0,
                                  error=f"HTTP {resp.status_code}: {resp.reason}")

        # Determine total bytes if provided
        content_length = None
        try:
            if resp.headers.get("Content-Length"):
                content_length = int(resp.headers.get("Content-Length"))
                # If we resumed, the total bytes of the final file is existing_size + content_length
                if existing_size:
                    content_length = existing_size + content_length
        except Exception:
            content_length = None

        # If filename unknown, get from headers/url
        filename = get_filename_from_response(resp, fallback_url=url)
        if filename and not dest_path.name:
            dest_path = dest_path.parent / filename

        # Choose chunk size
        chunk_size = 8192

        # Open part in append or write mode depending on resume
        mode = "ab" if existing_size and resume else "wb"
        written = existing_size

        try:
            # stream write to part file
            with open(part, mode) as f:
                # call progress callback initially with existing
                if progress_cb:
                    try:
                        meta = {"url": url, "path": str(dest_path)}
                        progress_cb(written, content_length, meta)
                    except Exception:
                        pass
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    written += len(chunk)
                    if progress_cb:
                        try:
                            meta = {"url": url, "path": str(dest_path)}
                            progress_cb(written, content_length, meta)
                        except Exception:
                            pass
                # flush+fsync
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except Exception:
                    pass
            # At this point the .part file contains the full content (or appended part)
            # Promote to final destination atomically
            try:
                # If same filesystem, os.replace will be atomic
                os.replace(str(part), str(dest_path))
            except Exception:
                # fallback: move then cleanup
                if dest_path.exists():
                    try:
                        dest_path.unlink()
                    except Exception:
                        pass
                shutil.move(str(part), str(dest_path))
        except Exception as exc:
            # keep part for resume if possible
            return DownloadResult(url=url, path=None, success=False, attempts=1, bytes=written, error=str(exc))
        finally:
            try:
                resp.close()
            except Exception:
                pass

        # Verify checksums if provided
        checksum_ok = True
        try:
            if expected_hashes:
                same, computed = is_same_file(dest_path, expected_hashes)
                checksum_ok = bool(same)
                if not checksum_ok:
                    # if mismatch, remove file to avoid leaving corrupted file
                    try:
                        safe_remove(dest_path)
                    except Exception:
                        pass
                    return DownloadResult(url=url, path=dest_path, success=False, attempts=1, bytes=written,
                                          error="Checksum mismatch after download")
        except Exception as exc:
            return DownloadResult(url=url, path=dest_path, success=False, attempts=1, bytes=written,
                                  error=f"Checksum verification error: {exc}")

        return DownloadResult(url=url, path=dest_path, success=checksum_ok, attempts=1, bytes=written, error=None)

    def download_url_to_folder(self,
                               url: str,
                               folder: Path,
                               *,
                               filename: Optional[str] = None,
                               expected_hashes: Optional[Dict[str, str]] = None,
                               progress_cb: Optional[ProgressCallback] = None,
                               max_retries: Optional[int] = None,
                               resume: bool = True) -> DownloadResult:
        """
        Download a URL into the given folder. Folder must be a directory (will be created).

        Parameters
        ----------
        url : str
        folder : Path
            Target folder (only folder; final filename is derived automatically if not provided).
        filename : Optional[str]
            If provided, use this filename (sanitized). Otherwise a filename is chosen from headers or URL.
        expected_hashes : Optional[Dict[str,str]]
            Map of algorithm -> hex string for verification (e.g. {"sha1": "abc..."}).
        progress_cb : Optional[callable(downloaded, total, meta)]
            Per-chunk progress callback.
        max_retries : Optional[int]
            Override manager default retries for this download.
        resume : bool
            Whether to attempt resuming an existing .part file.

        Returns
        -------
        DownloadResult
        """
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        max_attempts = max_retries or self.max_retries
        attempts = 0
        last_err = None

        # Build tentative dest path; if filename None, pass placeholder and function will derive name from response
        if filename:
            dest_path = folder / filename
        else:
            # use a temporary placeholder name (real name resolved from response). We'll fill with basename from url if needed.
            # Use url basename as fallback
            fallback_basename = os.path.basename(url.split("?")[0]) or f"download-{int(time.time())}"
            dest_path = folder / fallback_basename

        while attempts < max_attempts:
            attempts += 1
            result = self._attempt_download(url, dest_path, expected_hashes=expected_hashes,
                                            progress_cb=progress_cb, resume=resume)
            if result.success:
                # success; update attempts count and return
                result.attempts = attempts
                return result
            # If error indicates retry-after
            if result.error and "429" in (result.error or ""):
                # try parse number
                ra_val = parse_retry_after(result.error)
                wait = ra_val if ra_val and ra_val > 0 else exponential_backoff(attempts, base=self.backoff_base)
                logger.warning("Rate limited while downloading %s; sleeping %.2fs", url, wait)
                time.sleep(wait)
                continue
            # If Range not satisfiable or checksum mismatch, try next attempt after backoff clearing .part if necessary
            if result.error and ("416" in (result.error or "") or "Checksum mismatch" in (result.error or "")):
                # try clearing .part and retry
                part = temp_part_path(dest_path)
                try:
                    if part.exists():
                        safe_remove(part)
                except Exception:
                    pass
                wait = exponential_backoff(attempts, base=self.backoff_base)
                time.sleep(wait)
                continue

            # For other transient errors, backoff and retry
            wait = exponential_backoff(attempts, base=self.backoff_base)
            time.sleep(wait)
            last_err = result.error
            continue

        # exhausted attempts
        result.attempts = attempts
        if not result.success:
            result.error = result.error or last_err or "Unknown download failure"
        return result

    def download_modfile(self,
                         modfile: Any,
                         folder: Path,
                         *,
                         client: Optional[Any] = None,
                         expected_hashes: Optional[Dict[str, str]] = None,
                         progress_cb: Optional[ProgressCallback] = None,
                         max_retries: Optional[int] = None,
                         resume: bool = True) -> DownloadResult:
        """
        Download a ModFile-like object (either our types.ModFile dataclass or a raw metadata dict).

        It attempts to use available download_url in modfile.download_url or (if absent) asks the client
        to resolve the download URL via `client.get_file_download_url(project_id, file_id)`.

        Parameters
        ----------
        modfile : Any
            An object with attributes: `mod_id`/`project_id`, `file_id`, `download_url` or raw dict fields.
        folder : Path
            Destination folder (only).
        client : Optional[Any]
            Client used to resolve download URL if not present on modfile.
        expected_hashes : Optional[dict]
            Overrides expected_hashes from modfile metadata.
        progress_cb : Optional[callable]
        max_retries : Optional[int]
        resume : bool

        Returns
        -------
        DownloadResult
        """
        # Normalize
        project_id = None
        file_id = None
        url = None
        filename = None
        meta_hashes = {}

        if isinstance(modfile, dict):
            project_id = modfile.get("modId") or modfile.get("projectId") or modfile.get("projectID")
            file_id = modfile.get("id") or modfile.get("fileId") or modfile.get("fileID")
            url = modfile.get("downloadUrl") or modfile.get("download_url")
            filename = modfile.get("fileName") or modfile.get("displayName")
            # collect hashes if present
            if modfile.get("hashes"):
                if isinstance(modfile["hashes"], dict):
                    meta_hashes.update({k.lower(): v for k, v in modfile["hashes"].items()})
                elif isinstance(modfile["hashes"], list):
                    for h in modfile["hashes"]:
                        algo = (h.get("algorithm") or h.get("algo") or "").lower()
                        val = h.get("value") or h.get("hash") or h.get("digest")
                        if algo and val:
                            meta_hashes[algo] = val
        else:
            # object: try attribute access
            project_id = getattr(modfile, "mod_id", None) or getattr(modfile, "project_id", None)
            file_id = getattr(modfile, "file_id", None) or getattr(modfile, "id", None)
            url = getattr(modfile, "download_url", None) or getattr(modfile, "downloadUrl", None)
            filename = getattr(modfile, "file_name", None) or getattr(modfile, "fileName", None)
            if hasattr(modfile, "hashes"):
                hashes_val = getattr(modfile, "hashes")
                if isinstance(hashes_val, dict):
                    meta_hashes.update({k.lower(): v for k, v in hashes_val.items()})
                elif isinstance(hashes_val, list):
                    for h in hashes_val:
                        algo = (h.get("algorithm") or h.get("algo") or "").lower()
                        val = h.get("value") or h.get("hash") or h.get("digest")
                        if algo and val:
                            meta_hashes[algo] = val

        # Resolve download URL if missing
        if not url and client and project_id and file_id:
            try:
                if hasattr(client, "get_file_download_url"):
                    url = client.get_file_download_url(int(project_id), int(file_id))
                elif hasattr(client, "get_file_download_link"):
                    url = client.get_file_download_link(int(project_id), int(file_id))
            except Exception as exc:
                logger.debug("Could not resolve download URL from client: %s", exc)

        if not url:
            raise DownloadError("Download URL not available for modfile")

        # Final expected hashes resolution: explicit param overrides metadata
        final_hashes = {}
        if meta_hashes:
            final_hashes.update(meta_hashes)
        if expected_hashes:
            final_hashes.update({k.lower(): v for k, v in expected_hashes.items()})

        # If filename not provided, use URL basename
        if not filename:
            filename = os.path.basename(url.split("?")[0]) or f"{project_id}-{file_id}"

        return self.download_url_to_folder(url, folder, filename=filename, expected_hashes=final_hashes,
                                           progress_cb=progress_cb, max_retries=max_retries, resume=resume)

    def download_bulk(self,
                      tasks: Iterable[Dict[str, Any]],
                      *,
                      concurrency: int = 4,
                      progress_cb: Optional[Callable[[DownloadResult], None]] = None) -> List[DownloadResult]:
        """
        Download many tasks in parallel.

        tasks: iterable of dicts with keys:
          - url (required) OR modfile (object/dict) + client
          - folder (Path) required
          - filename (optional)
          - expected_hashes (optional)
          - client (optional) - used when modfile given

        Returns list of DownloadResult in completion order.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: List[DownloadResult] = []
        def _worker(task: Dict[str, Any]) -> DownloadResult:
            try:
                if "url" in task and task.get("url"):
                    return self.download_url_to_folder(task["url"], Path(task["folder"]),
                                                       filename=task.get("filename"),
                                                       expected_hashes=task.get("expected_hashes"),
                                                       progress_cb=task.get("progress_cb") or (lambda a,b,c: None),
                                                       max_retries=task.get("max_retries"),
                                                       resume=task.get("resume", True))
                elif "modfile" in task:
                    return self.download_modfile(task["modfile"], Path(task["folder"]),
                                                 client=task.get("client"),
                                                 expected_hashes=task.get("expected_hashes"),
                                                 progress_cb=task.get("progress_cb"),
                                                 max_retries=task.get("max_retries"),
                                                 resume=task.get("resume", True))
                else:
                    return DownloadResult(url="", path=None, success=False, attempts=0, bytes=0, error="Invalid task")
            except Exception as exc:
                return DownloadResult(url=task.get("url",""), path=None, success=False, attempts=0, bytes=0, error=str(exc))

        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {ex.submit(_worker, t): t for t in tasks}
            for fut in as_completed(futures):
                res = fut.result()
                results.append(res)
                if progress_cb:
                    try:
                        progress_cb(res)
                    except Exception:
                        pass

        return results
