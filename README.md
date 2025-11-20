# CurseForgePy

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)

**CurseForgePy** is a production-grade, type-safe Python client library designed to interact with the CurseForge API. It goes beyond simple API wrapping by providing a full-featured **Modpack Installer**, a **Resumable Download Manager**, and an **Intelligent Caching System**.

This library is built for developers creating Minecraft launchers, mod management tools, and server automation scripts. It abstracts away the complexities of authentication, rate-limiting, file hashing, and dependency management.

-----

## 🌟 Key Features

CurseForgePy is packed with advanced utilities found in the uploaded source code:

### 🔌 Core API Client

  * **Full Endpoint Coverage:** Access Games, Categories, Mods, Files, Descriptions, Changelogs, and Fingerprints.
  * **Type-Safe Models:** Uses Python `dataclasses` (`ModInfo`, `ModFile`, `Category`) for all API responses, ensuring full IDE autocompletion.
  * **Resilient Networking:** Automatic handling of **HTTP 429 (Rate Limit)** with `Retry-After` headers, and exponential backoff for **5xx** server errors.

### 📦 Modpack Installer Engine

  * **Manifest Parsing:** Natively reads `manifest.json` or standard `.zip` modpacks.
  * **Instance Automation:** Automatically creates the directory structure (mods, config, resourcepacks).
  * **Overrides Handling:** Extracts and merges `overrides` folders (configs/scripts) into the instance.
  * **Backup System:** Optional automatic backup of the instance folder before installation.

### ⬇️ Advanced Download Manager

  * **Resumable Downloads:** Supports `Range` headers to resume interrupted downloads automatically.
  * **Atomic Operations:** Downloads to `.part` files and performs an atomic rename only upon success, preventing corrupted files.
  * **Checksum Verification:** automatically verifies **SHA1** and **MD5** hashes against the API metadata.
  * **Concurrency:** Multi-threaded downloading for high-speed modpack installation.

### 🛠️ Utilities & Optimization

  * **Smart Caching:** Disk-based JSON caching (TTL supported) to reduce API latency and save quota.
  * **Fingerprinting:** Implements the **MurmurHash2** algorithm to identify unknown `.jar` files against the CurseForge database.
  * **OS-Aware Paths:** Automatically detects default Minecraft installation paths on Windows, macOS, and Linux.

-----

## 📥 Installation

Requires **Python 3.10** or higher.

```bash
pip install curseforgepy
```

Or install directly from the source:

```bash
git clone https://github.com/Cavanshirpro/curseforgepy.git
cd curseforgepy
pip install .
```

-----

## 🔑 Authentication

To use the CurseForge API, you must have an API Key (Eternal Key).

1.  Visit the [CurseForge for Studios Console](https://console.curseforge.com/).
2.  Create a project and generate an API Key.
3.  Pass this key to the `CurseForge` client.

-----

## 🚀 Quick Start Examples

### 1\. Searching and Browsing Mods

```python
from curseforgepy import CurseForge

# Initialize with your API Key
cf = CurseForge(api_key="$2a$10$YOUR_API_KEY_HERE")

# Search for "JEI" in Minecraft (Game ID: 432)
mods = cf.search_mods(
    game_id=432,
    search_filter="Just Enough Items",
    page_size=5
)

for mod in mods:
    print(f"Name: {mod.name} | ID: {mod.id}")
    print(f"Summary: {mod.summary}")
    print(f"Downloads: {mod.downloadCount}")
    print("-" * 40)
```

### 2\. Downloading a File (With Validation)

The client handles the download URL resolution, file writing, and hash verification.

```python
from pathlib import Path

# Fetch metadata for a specific file
mod_file = cf.get_mod_file(mod_id=238222, file_id=4668467)

# Download the file
# The library automatically sets the filename and verifies the checksum
saved_path = cf.download_file(
    mod_id=mod_file.modId,
    file_id=mod_file.id,
    dest_folder=Path("./downloads"),
    progress_cb=lambda current, total, meta: print(f"Downloading: {current}/{total} bytes")
)

print(f"File saved to: {saved_path}")
```

### 3\. Installing a Full Modpack

This uses the internal `ModPackInstaller` to turn a manifest into a playable instance.

```python
from pathlib import Path

instance_dir = Path("./my_modpack_instance")

# Install from a manifest file or zip
report = cf.install_modpack(
    manifest_source="BetterMinecraft.zip",
    instance_root=instance_dir,
    concurrency=8,          # Download 8 mods in parallel
    overwrite=True,         # Overwrite existing config files
    backup_on_failure=True  # Safety rollback
)

if report.success:
    print(f"Success! Installed {report.successful} mods in {report.time_elapsed:.2f}s")
else:
    print(f"Installation failed. {report.failed} files failed.")
```

### 4\. Fingerprinting (Identify Local Files)

If you have a folder of JAR files and want to know what mods they are:

```python
from curseforgepy.utils import fingerprint_from_file

# 1. Calculate the MurmurHash2 fingerprint of a local file
jar_fingerprint = fingerprint_from_file("unknown_mod.jar")

# 2. Ask the API to identify it
matches = cf.match_fingerprints([jar_fingerprint])

if matches.exactMatches:
    match = matches.exactMatches[0]
    print(f"Identified Mod ID: {match.id}")
    print(f"File Version: {match.file.fileName}")
```

-----

## ⚙️ Advanced Configuration

You can tune the client behavior during initialization.

```python
cf = CurseForge(
    api_key="YOUR_KEY",
    timeout=20.0,         # Increase socket timeout for slow connections
    max_retries=5,        # Retry failed requests up to 5 times
    backoff_base=1.0,     # Wait longer between retries
    cache_dir=".cf_cache",# Enable disk caching
    cache_ttl=3600        # Cache responses for 1 hour
)
```

-----

## 📂 Project Structure

The library is organized into modular components:

  * **`client.py`**: The main entry point. Handles session management and API requests.
  * **`installer.py`**: Logic for parsing `manifest.json` and orchestrating modpack installation.
  * **`download.py`**: A robust `DownloadManager` supporting resume and threaded downloads.
  * **`types_models.py`**: Dataclasses (`MODINFO`, `MODFILE`, `GAME`) for structured data.
  * **`fileops.py`**: Low-level file operations (Atomic write, Hashing).
  * **`paths.py`**: Utilities to detect Minecraft installation paths on Windows/Linux/macOS.

-----

## 🤝 Contributing

Contributions are welcome\! Please visit the [GitHub Repository](https://github.com/Cavanshirpro/curseforgepy) to report issues or submit pull requests.

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

-----

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](https://choosealicense.com/licenses/mit/) file for details.

-----

**Developed by [Cavanşir Qurbanzadə](https://github.com/Cavanshirpro)**