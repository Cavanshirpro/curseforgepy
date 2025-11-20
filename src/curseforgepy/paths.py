"""
curseforgepy.paths
------------------

Platform-aware path utilities and an InstallPaths dataclass used by the client/installer.

Responsibilities
- Provide sane defaults for Minecraft instance layout across OSes.
- Normalize and validate instance paths.
- Create required directories on demand (atomic-safe semantics using os.makedirs).
- Resolve "destination folder only" downloads into final file paths using server-provided filenames.
- Provide small helpers to detect default Minecraft directory and whether a folder looks like a valid instance.

Usage
-----
from pathlib import Path
from curseforgepy.paths import InstallPaths

# Create instance paths from a custom base directory:
paths = InstallPaths.from_custom(Path("/games/mc/instances/pack1"))

# Ensure required directories exist:
paths.ensure_dirs()

# Resolve where to save a mod file (server filename provided separately):
final_path = paths.resolve_target_path_for_file(server_filename="example-mod-1.0.jar", dest_folder=paths.mods_dir)
"""

from __future__ import annotations

import os
import platform
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import *

def _slugify(value: str) -> str:
    """
    Minimal slugify implementation for filesystem-safe names.
    Keeps letters, digits, underscores and hyphens. Converts spaces to hyphens.
    """
    if not isinstance(value, str):
        value = str(value)
    value = value.strip().lower()
    # Replace whitespace with hyphen
    value = re.sub(r"\s+", "-", value)
    # Remove anything except alnum, hyphen, underscore, dot
    value = re.sub(r"[^a-z0-9\-_\.]", "", value)
    # Collapse repeated hyphens
    value = re.sub(r"-{2,}", "-", value)
    return value or "instance"

def _ensure_dir(path: Path, mode: int = 0o755) -> Path:
    """
    Ensure directory exists. Creates parents if necessary.
    Uses os.makedirs(..., exist_ok=True) which is atomic enough for our needs.
    Returns the Path for chaining.
    """
    path = Path(path)
    path.mkdir(mode=mode, parents=True, exist_ok=True)
    return path


def _safe_join(folder: Path, filename: str) -> Path:
    """
    Return folder / filename (Path) and ensure filename is a single file (no path separators).
    """
    filename = filename or ""
    # Prevent directory traversal in filename
    filename = filename.replace("\\", "/")
    basename = os.path.basename(filename)
    if not basename:
        raise ValueError("Empty filename cannot be resolved into a path")
    return folder / basename

@dataclass
class InstallPaths:
    """
    Container for standard Minecraft instance directories.

    Attributes
    ----------
    instance_root : pathlib.Path
        The root directory of the Minecraft instance. (e.g. ~/minecraft/instances/pack1)
    mods_dir : pathlib.Path
        Directory to store mods: typically <instance_root>/mods
    resourcepacks_dir : pathlib.Path
        Directory to store resource packs: typically <instance_root>/resourcepacks
    shaderpacks_dir : pathlib.Path
        Directory to store shader packs: typically <instance_root>/shaderpacks
    config_dir : pathlib.Path
        Directory for mod configuration files: typically <instance_root>/config
    overrides_dir : pathlib.Path
        Directory used by modpacks for overrides (copied into the instance): typically <instance_root>/overrides
    saves_dir : pathlib.Path
        World saves directory: typically <instance_root>/saves
    logs_dir : pathlib.Path
        Directory for logs (optional)
    """

    instance_root: Path
    mods_dir: Path
    resourcepacks_dir: Path
    shaderpacks_dir: Path
    config_dir: Path
    overrides_dir: Path
    saves_dir: Path
    logs_dir: Optional[Path] = None

    @classmethod
    def from_minecraft_user(cls, base_game_dir: Optional[Path] = None, instance_name: Optional[str] = None) -> "InstallPaths":
        """
        Detects platform default Minecraft directory (if base_game_dir is None) and
        returns InstallPaths rooted at base_game_dir/instances/<instance_name> if instance_name provided,
        otherwise at base_game_dir (the default "vanilla" instance).

        Platform defaults:
        - Windows: %APPDATA%\.minecraft
        - macOS: ~/Library/Application Support/minecraft
        - Linux: ~/.minecraft

        Parameters
        ----------
        base_game_dir : Optional[Path]
            If provided, use this as the root of the instance(s).
        instance_name : Optional[str]
            If provided, will create an instance subfolder inside base_game_dir with a safe slug name.

        Returns
        -------
        InstallPaths
        """
        root = Path(base_game_dir) if base_game_dir else Path(_detect_default_minecraft_dir())
        if instance_name:
            safe_name = _slugify(instance_name)
            instance_root = root / "instances" / safe_name
        else:
            instance_root = root

        return cls.from_custom(instance_root)

    @classmethod
    def from_custom(cls, instance_root: Path) -> "InstallPaths":
        """
        Build InstallPaths from a custom instance root directory.

        Parameters
        ----------
        instance_root : Path
            The root directory for the instance.

        Returns
        -------
        InstallPaths
        """
        instance_root = Path(instance_root).expanduser().resolve()
        mods_dir = instance_root / "mods"
        resourcepacks_dir = instance_root / "resourcepacks"
        shaderpacks_dir = instance_root / "shaderpacks"
        config_dir = instance_root / "config"
        overrides_dir = instance_root / "overrides"
        saves_dir = instance_root / "saves"
        logs_dir = instance_root / "logs"

        return cls(
            instance_root=instance_root,
            mods_dir=mods_dir,
            resourcepacks_dir=resourcepacks_dir,
            shaderpacks_dir=shaderpacks_dir,
            config_dir=config_dir,
            overrides_dir=overrides_dir,
            saves_dir=saves_dir,
            logs_dir=logs_dir,
        )

    def ensure_dirs(self, *, mode: int = 0o755, exist_ok: bool = True) -> None:
        """
        Ensure all standard directories exist. Creates them if missing.

        Parameters
        ----------
        mode : int
            File mode for created directories (umask applies).
        exist_ok : bool
            If False, raises if directory already exists? (kept for future expansion) — current implementation always creates.
        """
        # Create instance root first
        _ensure_dir(self.instance_root, mode=mode)
        # Ensure children
        _ensure_dir(self.mods_dir, mode=mode)
        _ensure_dir(self.resourcepacks_dir, mode=mode)
        _ensure_dir(self.shaderpacks_dir, mode=mode)
        _ensure_dir(self.config_dir, mode=mode)
        _ensure_dir(self.overrides_dir, mode=mode)
        _ensure_dir(self.saves_dir, mode=mode)
        if self.logs_dir:
            _ensure_dir(self.logs_dir, mode=mode)

    def resolve_target_path_for_file(self, server_filename: Optional[str], *, dest_folder: Optional[Path] = None) -> Path:
        """
        Given a server-provided filename (or URL basename), return the final Path
        inside dest_folder where the file should be saved.

        Parameters
        ----------
        server_filename : Optional[str]
            Filename from server metadata or URL. If None, a ValueError is raised.
        dest_folder : Optional[Path]
            If provided, use this folder (must exist or will be created). If not provided,
            defaults to `self.mods_dir`.

        Returns
        -------
        Path
            Full path to the resolved destination file (folder + basename).

        Raises
        ------
        ValueError
            If server_filename is empty/invalid.
        """
        folder = Path(dest_folder) if dest_folder else self.mods_dir
        _ensure_dir(folder)
        return _safe_join(folder, server_filename)

    def is_valid_instance(self) -> bool:
        """
        Heuristic: Determine whether instance_root looks like a Minecraft instance
        by checking for at least one of the common subdirectories (mods, config, saves).

        Returns
        -------
        bool
        """
        return any((self.mods_dir.exists(), self.config_dir.exists(), self.saves_dir.exists()))

    def backup_instance(self, backup_root: Optional[Path] = None, *, timestamp: Optional[str] = None) -> Path:
        """
        Create a timestamped backup copy of the entire instance_root under backup_root.
        Returns the path to the created backup folder.

        Notes:
        - Uses shutil.copytree; large instances may take time and disk space.
        - Caller must ensure sufficient free space.
        """
        source = self.instance_root
        if backup_root is None:
            backup_root = source.parent / (source.name + "-backups")
        _ensure_dir(backup_root)
        if timestamp is None:
            import datetime
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        backup_dest = backup_root / f"{source.name}-{timestamp}"
        # copytree will raise if backup_dest exists; that's fine
        shutil.copytree(source, backup_dest)
        return backup_dest

    def remove_instance(self) -> None:
        """
        Remove the entire instance folder. Use with care.
        """
        if self.instance_root.exists():
            shutil.rmtree(self.instance_root)

    @property
    def name(self) -> str:
        """Safe name (last path component) for the instance."""
        return self.instance_root.name

    def __repr__(self) -> str:
        return f"<InstallPaths root={str(self.instance_root)!r} mods={str(self.mods_dir)!r}>"


def _detect_default_minecraft_dir() -> Path:
    """
    Return the platform-default Minecraft game directory.

    Windows: %APPDATA%\.minecraft
    macOS: ~/Library/Application Support/minecraft
    Linux: ~/.minecraft

    If the usual environment variables are not set, falls back to user home + '.minecraft'.
    """
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / ".minecraft"
        # fallback to home/.minecraft
        return home / ".minecraft"
    elif system == "Darwin":
        return home / "Library" / "Application Support" / "minecraft"
    else:
        # Linux, BSD, etc.
        return home / ".minecraft"


def find_minecraft_instances(parent_dir: Optional[Path] = None) -> List[InstallPaths]:
    """
    Search for typical instance folders under parent_dir. If parent_dir is None,
    uses default Minecraft directory's 'instances' subfolder.

    Returns a list of InstallPaths, one per found instance directory.
    """
    if parent_dir is None:
        parent_dir = _detect_default_minecraft_dir() / "instances"
    parent_dir = Path(parent_dir).expanduser()
    results: List[InstallPaths] = []
    if not parent_dir.exists():
        return results
    for entry in parent_dir.iterdir():
        if entry.is_dir():
            results.append(InstallPaths.from_custom(entry))
    return results


def path_for_asset(asset_type: str, instance_root: Path, *, instance_name: Optional[str] = None) -> Path:
    """
    Convenience helper: get a path for a top-level asset type under an instance root.

    asset_type must be one of: "mods", "resourcepacks", "shaderpacks", "config", "overrides", "saves", "logs"

    Example:
        path_for_asset("mods", Path("/games/mc/instances/pack1"))
    """
    ip = InstallPaths.from_custom(instance_root)
    mapping = {
        "mods": ip.mods_dir,
        "resourcepacks": ip.resourcepacks_dir,
        "shaderpacks": ip.shaderpacks_dir,
        "config": ip.config_dir,
        "overrides": ip.overrides_dir,
        "saves": ip.saves_dir,
        "logs": ip.logs_dir or (ip.instance_root / "logs")
    }
    if asset_type not in mapping:
        raise ValueError(f"Unknown asset_type {asset_type!r}")
    return mapping[asset_type]

def ensure_instance_dirs(instance_root: Path) -> InstallPaths:
    """
    Quick helper: build InstallPaths from instance_root and ensure its directories exist.
    Returns the InstallPaths object.
    """
    ip = InstallPaths.from_custom(instance_root)
    ip.ensure_dirs()
    return ip


def resolve_download_target(instance_root: Path, server_filename: str, folder: Optional[str] = None) -> Path:
    """
    Convenience: resolve where to save a server_filename into the instance.
    folder accepts one of the asset short names ("mods", "resourcepacks", ..) or an explicit path.
    """
    ip = InstallPaths.from_custom(instance_root)
    if folder is None or folder == "mods":
        dest = ip.mods_dir
    elif folder in ("resourcepacks", "shaderpacks", "config", "overrides", "saves", "logs"):
        dest = path_for_asset(folder, instance_root)
    else:
        # treat folder as path
        dest = Path(folder)
    _ensure_dir(dest)
    return ip.resolve_target_path_for_file(server_filename, dest_folder=dest)
