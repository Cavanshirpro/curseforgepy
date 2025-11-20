"""
curseforgepy.installer
----------------------

High-level modpack installer for CurseForge modpacks.

Main class: ModPackInstaller

Features:
 - Load manifest (manifest.json path, dict, or zip containing manifest + overrides)
 - Build InstallPlan (choose files, target folders, expected hashes)
 - Download files in parallel with retries, progress callbacks and verification
 - Apply overrides directory into instance (with optional backup)
 - Dry-run and detailed InstallReport dataclasses as result

Dependencies:
 - a client object that provides at least `get_file_download_url(mod_id, file_id)`
   and optionally `get_mod_file(mod_id,file_id)` or `get_mods_bulk`.
 - paths.InstallPaths for resolving folders
 - fileops.write_stream_to_tempfile, fileops.is_same_file, fileops.atomic_copy_dir, fileops.safe_remove
 - download manager helpers (requests streaming) — included via write_stream_to_tempfile usage

If some helper names differ in your project, update the import aliases accordingly.
"""

from __future__ import annotations

import json
import os
import zipfile
import shutil
import time
import tempfile
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import *

import requests


from .paths import InstallPaths, ensure_instance_dirs, resolve_download_target
from .fileops import (
    write_stream_to_tempfile,
    is_same_file,
    atomic_copy_dir,
    safe_remove,
    get_filename_from_response,
    temp_part_path,
)
from .utils import exponential_backoff, parse_retry_after
from .exceptions import DownloadError, ManifestError


# Data classes for results
@dataclass
class InstallItem:
    """Represents a single manifest entry mapped to a concrete download/install target."""
    project_id: int
    file_id: int
    required: bool = True
    remote_file_name: Optional[str] = None
    download_url: Optional[str] = None
    expected_hashes: Dict[str, str] = field(default_factory=dict)  # e.g., {"sha1": "..."}
    target_folder: Optional[Path] = None
    target_path: Optional[Path] = None  # final path (folder + filename)
    size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # raw API file object etc.


@dataclass
class InstallResult:
    """Result for one InstallItem."""
    item: InstallItem
    success: bool
    path: Optional[Path] = None
    downloaded_bytes: int = 0
    attempts: int = 0
    error: Optional[str] = None
    checksum_ok: Optional[bool] = None


@dataclass
class ModPackInstallReport:
    """Summary report for a modpack install run."""
    manifest_name: Optional[str] = None
    manifest_version: Optional[str] = None
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    results: List[InstallResult] = field(default_factory=list)
    backups: List[Path] = field(default_factory=list)
    time_elapsed: float = 0.0
    success: bool = False


# Helper internal functions
def _safe_load_json(path_or_dict: Any) -> Dict:
    """Load manifest data from dict or file path (json)"""
    if isinstance(path_or_dict, dict):
        return path_or_dict
    p = Path(path_or_dict)
    if not p.exists():
        raise ManifestError(f"Manifest path not found: {p}")
    # check zip
    if p.suffix.lower() == ".zip":
        # find manifest.json inside zip root or top-level folder
        with zipfile.ZipFile(p, "r") as z:
            candidates = [n for n in z.namelist() if n.endswith("manifest.json")]
            if not candidates:
                raise ManifestError("No manifest.json found inside the zip.")
            # prefer top-level manifest.json
            candidate = min(candidates, key=lambda n: (n.count("/"), n))
            with z.open(candidate) as f:
                data = json.load(f)
            # also extract overrides to temp dir and return path info in data
            temp_dir = Path(tempfile.mkdtemp(prefix="cfpack-"))
            # extract overrides folder if present in zip entries
            # many modpack zips include a directory named "overrides"
            overrides_names = [n for n in z.namelist() if n.startswith("overrides/") or "/overrides/" in n]
            if overrides_names:
                for name in overrides_names:
                    dest = temp_dir / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if name.endswith("/"):
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        with z.open(name) as srcf, open(dest, "wb") as outf:
                            shutil.copyfileobj(srcf, outf)
                # record temp overrides dir for later application
                data["_overrides_extracted_path"] = str(temp_dir / "overrides")
            return data
    else:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)


# The installer
class ModPackInstaller:
    """
    Orchestrates modpack installation from a CurseForge manifest.
    """

    def __init__(self,
                 client: Any,
                 *,
                 concurrency: int = 4,
                 max_retries: int = 3,
                 backoff_base: float = 0.6,
                 backup_on_failure: bool = True):
        """
        Parameters
        ----------
        client : object
            A CurseForge client instance that must implement:
              - get_file_download_url(mod_id, file_id) -> str
              - optionally get_mod_file(mod_id, file_id) -> dict (metadata) or similar
        concurrency : int
            Number of parallel downloads.
        max_retries : int
            Max attempts per file (including initial attempt).
        backoff_base : float
            Base backoff seconds used (exponential).
        backup_on_failure : bool
            If True, create a backup before modifying instance that can be restored on fatal failure.
        """
        self.client = client
        self.concurrency = max(1, int(concurrency))
        self.max_retries = max(1, int(max_retries))
        self.backoff_base = float(backoff_base)
        self.backup_on_failure = bool(backup_on_failure)

    # -------------
    # Plan builder
    # -------------
    def build_plan_from_manifest(self, manifest: Dict, install_paths: InstallPaths) -> List[InstallItem]:
        """
        Build a concrete InstallItem list from a parsed manifest dict and target InstallPaths.

        For each manifest entry:
          - find the projectID and fileID
          - try to get file metadata via client.get_mod_file or client.get_file
          - determine download_url via client.get_file_download_url or client.get_file_download_url
          - resolve target folder (mods, resourcepacks, shaders) — default to mods
          - set expected_hashes if present in metadata

        Returns list of InstallItem
        """
        items: List[InstallItem] = []
        files = manifest.get("files") or []
        for entry in files:
            projectID = entry.get("projectID") or entry.get("projectId") or entry.get("project")
            fileID = entry.get("fileID") or entry.get("fileId") or entry.get("file")
            required = bool(entry.get("required", True))
            if projectID is None or fileID is None:
                # skip malformed
                continue
            item = InstallItem(project_id=int(projectID), file_id=int(fileID), required=required)
            # try to get metadata
            metadata = None
            try:
                # try several method names the client may provide
                fn = None
                if hasattr(self.client, "get_mod_file"):
                    fn = getattr(self.client, "get_mod_file")
                elif hasattr(self.client, "get_file"):
                    fn = getattr(self.client, "get_file")
                elif hasattr(self.client, "get_modfile") :
                    fn = getattr(self.client, "get_modfile")
                if fn:
                    metadata = fn(int(projectID), int(fileID))
            except Exception:
                metadata = None

            # If metadata is dict-like and has hashes / fileName
            if isinstance(metadata, dict):
                item.metadata = metadata
                item.remote_file_name = metadata.get("fileName") or metadata.get("displayName") or None
                # attempt to extract hashes
                hashes = {}
                if metadata.get("hashes"):
                    # API sometimes returns list of hash objects
                    if isinstance(metadata["hashes"], dict):
                        hashes.update({k: v for k, v in metadata["hashes"].items()})
                    elif isinstance(metadata["hashes"], list):
                        for h in metadata["hashes"]:
                            algo = h.get("algorithm") or h.get("algo")
                            value = h.get("value") or h.get("hash")
                            if algo and value:
                                hashes[algo.lower()] = value
                # sometimes there's a 'fileFingerprint' field (single int) — not usable as hash; we keep for reference
                if metadata.get("fileSize"):
                    try:
                        item.size_bytes = int(metadata.get("fileSize"))
                    except Exception:
                        pass
                item.expected_hashes = hashes

            # Resolve download_url if client can provide
            download_url = None
            try:
                if hasattr(self.client, "get_file_download_url"):
                    download_url = self.client.get_file_download_url(int(projectID), int(fileID))
                elif hasattr(self.client, "get_file_download_link"):
                    download_url = self.client.get_file_download_link(int(projectID), int(fileID))
            except Exception:
                download_url = None

            item.download_url = download_url
            # default folder: mods_dir
            item.target_folder = install_paths.mods_dir
            # determine filename
            if not item.remote_file_name and item.download_url:
                # fallback to URL basename
                basename = item.download_url.split("?")[0].rstrip("/").split("/")[-1]
                if basename:
                    item.remote_file_name = basename
            # compute target path
            if item.remote_file_name:
                item.target_path = item.target_folder / os.path.basename(item.remote_file_name)
            else:
                # placeholder name using project-file ids
                item.remote_file_name = f"{item.project_id}-{item.file_id}.jar"
                item.target_path = item.target_folder / item.remote_file_name

            items.append(item)
        return items

    # -----------------------
    # Manifest loader helper
    # -----------------------
    def _load_manifest(self, manifest_source: Any) -> Tuple[Dict, Optional[Path]]:
        """
        Load manifest dict from input which may be:
          - dict already
          - local json path
          - zip file path containing manifest.json and possibly overrides

        Returns (manifest_dict, overrides_source_path_or_None)
        """
        if isinstance(manifest_source, dict):
            return manifest_source, None
        p = Path(manifest_source)
        if not p.exists():
            raise ManifestError(f"Manifest source not found: {manifest_source}")
        # JSON file?
        if p.suffix.lower() == ".json":
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            overrides = None
            # if overrides path is relative inside manifest, respect it relative to the manifest location
            overrides_rel = data.get("overrides")
            if overrides_rel:
                overrides_candidate = (p.parent / overrides_rel)
                if overrides_candidate.exists():
                    overrides = overrides_candidate
            return data, overrides
        # Zip file
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p, "r") as z:
                names = z.namelist()
                # find manifest.json
                manifests = [n for n in names if n.endswith("manifest.json")]
                if not manifests:
                    raise ManifestError("No manifest.json found inside zip file.")
                manifest_name = min(manifests, key=lambda n: (n.count("/"), n))
                with z.open(manifest_name) as mf:
                    data = json.load(mf)
                # extract overrides folder (if present) to temporary dir
                tmp_dir = Path(tempfile.mkdtemp(prefix="cf-overrides-"))
                overrides_entries = [n for n in names if n.startswith("overrides/") or "/overrides/" in n]
                if overrides_entries:
                    for name in overrides_entries:
                        # write each entry
                        dest = tmp_dir / name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if name.endswith("/"):
                            dest.mkdir(parents=True, exist_ok=True)
                        else:
                            with z.open(name) as rf, open(dest, "wb") as wf:
                                shutil.copyfileobj(rf, wf)
                    overrides_path = tmp_dir / "overrides"
                else:
                    overrides_path = None
                return data, overrides_path
        # fallback: try to load as json
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f), None

    # -----------------------
    # Core: install_from_manifest
    # -----------------------
    def install_from_manifest(self,
                              manifest_source: Any,
                              instance_root: Path,
                              *,
                              create_instance_dirs: bool = True,
                              overwrite: bool = True,
                              progress_callback: Optional[Callable[[InstallResult], None]] = None,
                              dry_run: bool = False,
                              max_workers: Optional[int] = None,
                              preserve_backups: bool = True) -> ModPackInstallReport:
        """
        Main entry point. Install modpack described by manifest_source into instance_root.

        Parameters
        ----------
        manifest_source : dict | Path | str
            Manifest dict, path to manifest.json, or path to a zip modpack.
        instance_root : Path
            Target instance root directory.
        create_instance_dirs : bool
            If True, create instance directories if missing.
        overwrite : bool
            Overwrite existing files in instance when copying overrides or installing mods.
        progress_callback : Optional[callable(InstallResult)]
            Called after each file download completes (or fails).
        dry_run : bool
            If True, only build plan and return it in report.results (no downloads/writes).
        max_workers : Optional[int]
            Parallel download workers (defaults to self.concurrency).
        preserve_backups : bool
            If True keep backup(s) created on failure; otherwise delete backup after success.

        Returns
        -------
        ModPackInstallReport
        """
        start = time.time()
        report = ModPackInstallReport()
        max_workers = max_workers or self.concurrency
        instance_root = Path(instance_root).expanduser().resolve()
        install_paths = InstallPaths.from_custom(instance_root)

        # create dirs
        if create_instance_dirs:
            install_paths.ensure_dirs()

        # load manifest and optional extracted overrides path
        manifest, extracted_overrides = self._load_manifest(manifest_source)

        report.manifest_name = manifest.get("name")
        report.manifest_version = manifest.get("version")

        # backup instance if requested and if backup_on_failure True
        backup_path = None
        if self.backup_on_failure:
            try:
                backup_root = instance_root.parent / f"{instance_root.name}-backups"
                backup_root.mkdir(parents=True, exist_ok=True)
                ts = time.strftime("%Y%m%dT%H%M%SZ")
                backup_dest = backup_root / f"{instance_root.name}-{ts}"
                # do a shallow copy (copytree) for safety
                shutil.copytree(str(instance_root), str(backup_dest))
                report.backups.append(backup_dest)
                backup_path = backup_dest
            except Exception:
                # if backup fails, we still continue but record nothing
                backup_path = None

        # build install plan
        items = self.build_plan_from_manifest(manifest, install_paths)
        report.total_files = len(items)

        if dry_run:
            # create InstallResult placeholders but don't download
            for it in items:
                res = InstallResult(item=it, success=False, path=it.target_path, attempts=0, error="dry-run")
                report.results.append(res)
            report.time_elapsed = time.time() - start
            report.success = False
            return report

        # Ensure target folders exist
        for it in items:
            if it.target_folder:
                it.target_folder.mkdir(parents=True, exist_ok=True)

        # -------------------------
        # Download workers
        # -------------------------
        results: List[InstallResult] = []

        def _download_task(it: InstallItem) -> InstallResult:
            """Download single item with retry/backoff and verification."""
            attempts = 0
            last_err = None
            downloaded_bytes = 0
            success = False
            checksum_ok = None
            final_path = it.target_path
            # If file already exists and matches expected hash, skip
            try:
                if final_path and final_path.exists() and it.expected_hashes:
                    same, computed = is_same_file(final_path, it.expected_hashes)
                    if same:
                        return InstallResult(item=it, success=True, path=final_path, downloaded_bytes=computed.get("size", 0) or 0,
                                             attempts=0, checksum_ok=True)
            except Exception:
                # ignore and continue to download
                pass

            # If client didn't give download_url, attempt to obtain it during each attempt
            for attempt in range(1, self.max_retries + 1):
                attempts = attempt
                try:
                    # ensure we have a download_url
                    if not it.download_url:
                        if hasattr(self.client, "get_file_download_url"):
                            it.download_url = self.client.get_file_download_url(it.project_id, it.file_id)
                        else:
                            # maybe client exposes get_file or get_mod_file with url inside metadata
                            meta = it.metadata
                            it.download_url = meta.get("downloadUrl") if isinstance(meta, dict) else None

                    if not it.download_url:
                        raise DownloadError(f"No download URL for {it.project_id}/{it.file_id}")

                    # perform HTTP GET with stream
                    with requests.get(it.download_url, stream=True, timeout=30) as resp:
                        # handle HTTP errors explicitly
                        if resp.status_code >= 400:
                            # if rate-limited, honor Retry-After header
                            if resp.status_code == 429:
                                ra = parse_retry_after(resp.headers.get("Retry-After"))
                                wait = ra if ra and ra > 0 else exponential_backoff(attempt, base=self.backoff_base)
                                time.sleep(wait)
                                raise DownloadError(f"429 Rate limited; waited {wait}s then retrying")
                            else:
                                raise DownloadError(f"HTTP {resp.status_code}: {resp.reason} for URL {it.download_url}")

                        # decide filename if not set
                        if not it.remote_file_name:
                            fn = get_filename_from_response(resp, fallback_url=it.download_url)
                            if fn:
                                it.remote_file_name = fn
                                it.target_path = it.target_folder / fn

                        # Write stream to tempfile next to final dest and promote atomically
                        # Using write_stream_to_tempfile helper
                        dest_path = it.target_path or (it.target_folder / (it.remote_file_name or f"{it.project_id}-{it.file_id}"))
                        part = temp_part_path(dest_path)
                        # ensure parent
                        dest_path.parent.mkdir(parents=True, exist_ok=True)

                        # streaming write
                        written_path = write_stream_to_tempfile(resp, dest_path, progress_cb=None, resume=True)
                        downloaded_bytes = written_path.stat().st_size if written_path.exists() else 0

                        # verify checksum if expected_hashes present
                        checksum_ok = None
                        try:
                            if it.expected_hashes:
                                same, computed = is_same_file(written_path, it.expected_hashes)
                                checksum_ok = bool(same)
                                if not same:
                                    # delete corrupted file and raise to retry
                                    safe_remove(written_path)
                                    raise DownloadError("Checksum mismatch after download")
                            else:
                                checksum_ok = None  # unknown
                        except Exception as ex:
                            # if verification routine failed, treat as failure and retry
                            safe_remove(written_path)
                            raise DownloadError(f"Checksum verification error: {ex}") from ex

                        # mark success
                        success = True
                        final_path = written_path
                        last_err = None
                        break  # exit retry loop
                except Exception as exc:
                    last_err = str(exc)
                    # exponential backoff before retrying unless last attempt
                    if attempt < self.max_retries:
                        wait = exponential_backoff(attempt, base=self.backoff_base)
                        time.sleep(wait)
                        continue
                    else:
                        # exhausted retries
                        break

            return InstallResult(item=it,
                                 success=success,
                                 path=final_path if success else it.target_path,
                                 downloaded_bytes=downloaded_bytes,
                                 attempts=attempts,
                                 error=last_err,
                                 checksum_ok=checksum_ok)

        # run downloads in ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as exe:
            future_to_item = {exe.submit(_download_task, it): it for it in items}
            for fut in as_completed(future_to_item):
                it = future_to_item[fut]
                try:
                    res: InstallResult = fut.result()
                except Exception as e:
                    res = InstallResult(item=it, success=False, error=str(e), attempts=self.max_retries)
                results.append(res)
                if progress_callback:
                    try:
                        progress_callback(res)
                    except Exception:
                        pass

        # populate report
        report.results = results
        report.successful = sum(1 for r in results if r.success)
        report.failed = sum(1 for r in results if not r.success and r.item.required)
        report.time_elapsed = time.time() - start
        report.success = (report.failed == 0)

        # Apply overrides if present (priority: extracted overrides from zip -> manifest.overrides -> no overrides)
        applied_overrides = False
        try:
            overrides_source = None
            # check extracted_overrides path if we used _load_manifest earlier
            if extracted_overrides:
                overrides_source = Path(extracted_overrides)
            elif manifest.get("overrides"):
                ov = manifest.get("overrides")
                # ov may be path relative to manifest; try it
                manifest_base = Path(manifest_source) if isinstance(manifest_source, (str, Path)) else None
                if manifest_base and manifest_base.exists():
                    candidate = (manifest_base.parent / ov)
                    if candidate.exists():
                        overrides_source = candidate
                # else treat overrides as provided path
                if overrides_source is None and Path(ov).exists():
                    overrides_source = Path(ov)

            if overrides_source and overrides_source.exists():
                # copy overrides into instance_root
                # copy with overwrite option
                if overwrite:
                    # apply overrides by copying files into instance root, replacing existing files
                    # we'll use atomic_copy_dir for safety: copy overrides to a temp location inside instance root then move
                    target_overrides_dest = install_paths.instance_root
                    # performing a direct copy (merge) because atomic_copy_dir replaces a full folder
                    for root, dirs, files in os.walk(overrides_source):
                        rel = Path(root).relative_to(overrides_source)
                        dest_dir = install_paths.instance_root / rel
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        for f in files:
                            srcf = Path(root) / f
                            dstf = dest_dir / f
                            # if overwrite allowed, remove dest first
                            if dstf.exists() and overwrite:
                                try:
                                    dstf.unlink()
                                except Exception:
                                    pass
                            shutil.copy2(srcf, dstf)
                    applied_overrides = True
        except Exception:
            # do not fail entire install because overrides failed; just record
            applied_overrides = False

        # If there were required failures, attempt rollback (restore backup) or cleanup
        if report.failed > 0 and backup_path:
            try:
                # remove current instance and restore backup
                safe_remove(instance_root)
                shutil.move(str(backup_path), str(instance_root))
                # keep backup recorded
            except Exception:
                # if restore fails, leave as-is but report failure
                pass

        # Cleanup: if backup created and success & not preserve_backups, remove backup
        if backup_path and report.success and not preserve_backups:
            try:
                safe_remove(backup_path)
            except Exception:
                pass

        report.success = (report.failed == 0)
        report.time_elapsed = time.time() - start
        return report
