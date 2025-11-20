"""
types.py

Typed dataclasses that mirror/augment the dynamic objects defined in dataTypes.py.

Purpose
-------
- Provide typed, documented, and easy-to-use data containers for CurseForge API objects.
- Supply `from_dict()` factories to convert raw API JSON/dict into typed objects.
- Keep original raw payload available in `.data` for debugging/forward-compatibility.

Notes
-----
- These dataclasses are intentionally lightweight (no validation beyond presence/type coercion).
- Use these types across client/installer/download modules to avoid ad-hoc dict handling.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import IntEnum
from datetime import datetime
import dateutil.parser as _dateutil_parser


# Enums
class MODLOADER(IntEnum):
    """
    Known mod loader identifiers used internally in some APIs.
    The numeric values follow conventions used in your dataTypes (keeps parity).
    """
    any = 0
    forge = 1
    cauldron = 2
    liteloader = 3
    fabric = 4
    quilt = 5
    neoforge = 6


class CURSEFORGECLASS(IntEnum):
    """
    Example class ids commonly used to denote resource types on CurseForge.
    Kept for readability and mapping when classId field appears in API objects.
    """
    MOD = 6
    RESOURCE_PACK = 12
    SHADER = 6552
    MODPACKS = 4471
    WORLDS = 17
    DATAPACKS = 6871
    COSMETIC = 4994
    PLUGINS = 5


# Simple value containers
@dataclass
class MODSS:
    """
    Screenshot / small media object for a mod (used in mod summary lists).

    Attributes
    ----------
    id : Optional[int]
        Internal id of the screenshot object.
    modId : Optional[int]
        Associated mod/project id.
    title : Optional[str]
        Short title for the screenshot.
    description : Optional[str]
        Description or caption of this screenshot.
    thumbnailUrl : Optional[str]
        URL to the thumbnail image.
    url : Optional[str]
        Full size image URL or page URL.
    data : Dict[str,Any]
        Original raw JSON payload for debugging or forward compatibility.
    """
    id: Optional[int] = None
    modId: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    url: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODSS":
        d = d or {}
        return cls(
            id=d.get("id"),
            modId=d.get("modId"),
            title=d.get("title"),
            description=d.get("description"),
            thumbnailUrl=d.get("thumbnailUrl"),
            url=d.get("url"),
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MODLINKS:
    """
    Container for external links related to a mod/project.

    Attributes
    ----------
    websiteUrl : Optional[str]
        Official project website URL (if provided).
    wikiUrl : Optional[str]
        Link to project's wiki or docs.
    issuesUrl : Optional[str]
        Bug tracker / issue reporting URL.
    sourceUrl : Optional[str]
        Source repository URL (GitHub/GitLab/etc).
    data : Dict[str,Any]
        Raw JSON payload.
    """
    websiteUrl: Optional[str] = None
    wikiUrl: Optional[str] = None
    issuesUrl: Optional[str] = None
    sourceUrl: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODLINKS":
        d = d or {}
        return cls(
            websiteUrl=d.get("websiteUrl"),
            wikiUrl=d.get("wikiUrl"),
            issuesUrl=d.get("issuesUrl"),
            sourceUrl=d.get("sourceUrl"),
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CATEGORY:
    """
    Represents a category entry returned by the CurseForge API.

    Attributes
    ----------
    id : Optional[int]
        Category id.
    gameId : Optional[int]
        Which game this category belongs to (game id).
    name : Optional[str]
        Human readable category name.
    slug : Optional[str]
        URL slug for the category.
    url : Optional[str]
        Full web URL for category on CurseForge.
    iconUrl : Optional[str]
        Icon image URL for category.
    dateModified : Optional[str]
        ISO date string when category last modified.
    classId : Optional[int]
        Class id (grouping) for special classification.
    isClass : Optional[bool]
        Whether this entry is actually a "class" (category group).
    parentCategoryId : Optional[int]
        Optional parent id to represent nested categories.
    data : Dict[str,Any]
        Raw JSON.
    """
    id: Optional[int] = None
    gameId: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    url: Optional[str] = None
    iconUrl: Optional[str] = None
    dateModified: Optional[str] = None
    classId: Optional[int] = None
    isClass: Optional[bool] = None
    parentCategoryId: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CATEGORY":
        d = d or {}
        return cls(
            id=d.get("id"),
            gameId=d.get("gameId"),
            name=d.get("name"),
            slug=d.get("slug"),
            url=d.get("url"),
            iconUrl=d.get("iconUrl"),
            dateModified=d.get("dateModified"),
            classId=d.get("classId"),
            isClass=d.get("isClass"),
            parentCategoryId=d.get("parentCategoryId"),
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MODAUTHOR:
    """
    Author (contributor) summary object.

    Attributes
    ----------
    id : Optional[int]
        Author id on CurseForge.
    name : Optional[str]
        Display name.
    url : Optional[str]
        Author's public page URL.
    avatarUrl : Optional[str]
        Avatar image URL.
    data : Dict[str, Any]
        Raw JSON.
    """
    id: Optional[int] = None
    name: Optional[str] = None
    url: Optional[str] = None
    avatarUrl: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODAUTHOR":
        d = d or {}
        return cls(
            id=d.get("id"),
            name=d.get("name"),
            url=d.get("url"),
            avatarUrl=d.get("avatarUrl"),
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MODLOGO:
    """
    Logo/image object for a mod/project.

    Attributes
    ----------
    id, modId, title, description, thumbnailUrl, url : various metadata fields
    data : Dict[str,Any] : raw payload
    """
    id: Optional[int] = None
    modId: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    url: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODLOGO":
        d = d or {}
        return cls(
            id=d.get("id"),
            modId=d.get("modId"),
            title=d.get("title"),
            description=d.get("description"),
            thumbnailUrl=d.get("thumbnailUrl"),
            url=d.get("url"),
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# File / hash related small types
@dataclass
class MODFILEHASH:
    """
    Represents a single file hash object (algorithm + hex digest).

    Common API shapes:
      - {"algorithm":"sha1","value":"..."}
      - {"algo":1,"value":"..."} depending on API version.

    Attributes
    ----------
    value : Optional[str]  -- hex digest
    algo : Optional[int|str] -- algorithm indicator (API variant)
    data : Dict[str,Any] -- raw
    """
    value: Optional[str] = None
    algo: Optional[Any] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODFILEHASH":
        d = d or {}
        return cls(value=d.get("value") or d.get("hash"), algo=d.get("algorithm") or d.get("algo"), data=d)


@dataclass
class MODFILEMODULE:
    """
    Some files expose 'modules' (for modular jars). Minimal typed container.

    Attributes
    ----------
    name : Optional[str]
        Module name.
    fingerprint : Optional[int]
        Fingerprint integer used by CurseForge matching.
    data : Dict[str,Any]
        Raw.
    """
    name: Optional[str] = None
    fingerprint: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODFILEMODULE":
        d = d or {}
        return cls(name=d.get("name"), fingerprint=d.get("fingerprint"), data=d)


@dataclass
class MODFILEsortableGameVersions:
    """
    Auxiliary structure representing sortable game version information for a file.
    Useful when API returns both 'gameVersion' and padding metadata.
    """
    gameVersionName: Optional[str] = None
    gameVersionPadded: Optional[str] = None
    gameVersion: Optional[str] = None
    gameVersionReleaseDate: Optional[str] = None
    gameVersionTypeId: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODFILEsortableGameVersions":
        d = d or {}
        return cls(
            gameVersionName=d.get("gameVersionName"),
            gameVersionPadded=d.get("gameVersionPadded"),
            gameVersion=d.get("gameVersion"),
            gameVersionReleaseDate=d.get("gameVersionReleaseDate"),
            gameVersionTypeId=d.get("gameVersionTypeId"),
            data=d,
        )


@dataclass
class MODFILEsIndexes:
    """
    Index-like metadata for 'latestFilesIndexes' structures from API.
    Contains mapping per file for quick compatibility checks etc.
    """
    gameVersion: Optional[str] = None
    fileId: Optional[int] = None
    filename: Optional[str] = None
    releaseType: Optional[int] = None
    gameVersionTypeId: Optional[int] = None
    modLoader: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODFILEsIndexes":
        d = d or {}
        return cls(
            gameVersion=d.get("gameVersion"),
            fileId=d.get("fileId"),
            filename=d.get("filename"),
            releaseType=d.get("releaseType"),
            gameVersionTypeId=d.get("gameVersionTypeId"),
            modLoader=d.get("modLoader"),
            data=d,
        )


# Core complex objects: MODFILE and MODINFO (Mod metadata)
@dataclass
class MODFILE:
    """
    Typed representation of a mod's file record (a single uploaded file/version).

    Fields mirror common CurseForge API fields. Keep the raw `data` for any missing fields.

    Important fields:
      - id: file id
      - modId: project id this file belongs to
      - fileName: server filename (used for saving)
      - fileLength: file size in bytes
      - downloadUrl: may or may not be present; client can request it separately
      - hashes: list of MODFILEHASH objects (or empty)
    """
    id: Optional[int] = None
    gameId: Optional[int] = None
    modId: Optional[int] = None
    isAvailable: Optional[bool] = None

    displayName: Optional[str] = None
    fileName: Optional[str] = None
    releaseType: Optional[int] = None
    fileStatus: Optional[int] = None

    hashes: List[MODFILEHASH] = field(default_factory=list)
    fileDate: Optional[str] = None
    fileLength: Optional[int] = None
    downloadCount: Optional[int] = None
    downloadUrl: Optional[str] = None

    gameVersions: List[str] = field(default_factory=list)
    sortableGameVersions: List[MODFILEsortableGameVersions] = field(default_factory=list)

    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    alternateFileId: Optional[int] = None
    isServerPack: Optional[bool] = None
    fileFingerprint: Optional[int] = None

    modules: List[MODFILEMODULE] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODFILE":
        d = d or {}
        hashes = [MODFILEHASH.from_dict(h) for h in (d.get("hashes") or [])]
        modules = [MODFILEMODULE.from_dict(m) for m in (d.get("modules") or [])]
        sortable = [MODFILEsortableGameVersions.from_dict(s) for s in (d.get("sortableGameVersions") or [])]
        return cls(
            id=d.get("id"),
            gameId=d.get("gameId"),
            modId=d.get("modId"),
            isAvailable=d.get("isAvailable"),
            displayName=d.get("displayName"),
            fileName=d.get("fileName"),
            releaseType=d.get("releaseType"),
            fileStatus=d.get("fileStatus"),
            hashes=hashes,
            fileDate=d.get("fileDate"),
            fileLength=d.get("fileLength"),
            downloadCount=d.get("downloadCount"),
            downloadUrl=d.get("downloadUrl"),
            gameVersions=d.get("gameVersions") or [],
            sortableGameVersions=sortable,
            dependencies=d.get("dependencies") or [],
            alternateFileId=d.get("alternateFileId"),
            isServerPack=d.get("isServerPack"),
            fileFingerprint=d.get("fileFingerprint"),
            modules=modules,
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return f"<MODFILE id={self.id} fileName={self.fileName!r} size={self.fileLength}>"


@dataclass
class MODINFO:
    """
    Typed representation of a project's (mod's) metadata.

    Contains:
      - core fields like id, name, slug
      - author info, categories, links and logo
      - file lists such as latestFiles (as MODFILE instances)
      - a `data` dict with raw payload for future-proof access
    """
    id: Optional[int] = None
    gameId: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    link: Optional[MODLINKS] = None
    summary: Optional[str] = None
    status: Optional[int] = None
    downloadCount: Optional[int] = None
    isFeatured: Optional[bool] = None
    primaryCategoryId: Optional[int] = None

    categories: List[CATEGORY] = field(default_factory=list)
    classId: Optional[int] = None
    authors: List[MODAUTHOR] = field(default_factory=list)
    logo: Optional[MODLOGO] = None

    mainFileId: Optional[int] = None
    latestFiles: List[MODFILE] = field(default_factory=list)
    latestFilesIndexes: List[MODFILEsIndexes] = field(default_factory=list)
    latestEarlyAccessFilesIndexes: Optional[List[Dict[str, Any]]] = None

    screenshots: List[MODSS] = field(default_factory=list)
    selected_file: Optional[MODFILE] = None

    dateCreated: Optional[str] = None
    dateModified: Optional[str] = None
    dateReleased: Optional[str] = None

    allowModDistribution: Optional[bool] = None
    gamePopularityRank: Optional[int] = None
    isAvailable: Optional[bool] = None
    thumbsUpCount: Optional[int] = None
    featuredProjectTag: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODINFO":
        """
        Convert raw API dict into MODINFO dataclass, converting nested lists into typed lists.
        """
        d = d or {}
        screenshots = [MODSS.from_dict(s) for s in (d.get("screenshots") or [])]
        link = MODLINKS.from_dict(d.get("links") or {}) if d.get("links") else None
        categories = [CATEGORY.from_dict(c) for c in (d.get("categories") or [])]
        authors = [MODAUTHOR.from_dict(a) for a in (d.get("authors") or [])]
        logo = MODLOGO.from_dict(d.get("logo") or {}) if d.get("logo") else None
        latest_files = [MODFILE.from_dict(f) for f in (d.get("latestFiles") or [])]
        latest_indexes = [MODFILEsIndexes.from_dict(i) for i in (d.get("latestFilesIndexes") or [])]

        selected_file = MODFILE.from_dict(d["selected_file"]) if d.get("selected_file") else None

        return cls(
            id=d.get("id"),
            gameId=d.get("gameId"),
            name=d.get("name"),
            slug=d.get("slug"),
            link=link,
            summary=d.get("summary"),
            status=d.get("status"),
            downloadCount=d.get("downloadCount"),
            isFeatured=d.get("isFeatured"),
            primaryCategoryId=d.get("primaryCategoryId"),
            categories=categories,
            classId=d.get("classId"),
            authors=authors,
            logo=logo,
            mainFileId=d.get("mainFileId"),
            latestFiles=latest_files,
            latestFilesIndexes=latest_indexes,
            latestEarlyAccessFilesIndexes=d.get("latestEarlyAccessFilesIndexes"),
            screenshots=screenshots,
            selected_file=selected_file,
            dateCreated=d.get("dateCreated"),
            dateModified=d.get("dateModified"),
            dateReleased=d.get("dateReleased"),
            allowModDistribution=d.get("allowModDistribution"),
            gamePopularityRank=d.get("gamePopularityRank"),
            isAvailable=d.get("isAvailable"),
            thumbsUpCount=d.get("thumbsUpCount"),
            featuredProjectTag=d.get("featuredProjectTag"),
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return f"<MODINFO id={self.id} name={self.name!r}>"


# Game & Assets
@dataclass
class ASSETS:
    """
    Image assets associated with a game entry:
      - iconUrl: small square icon
      - titleUrl: banner/title image
      - coverUrl: large promotional cover
      - data: original JSON payload
    """
    iconUrl: Optional[str] = None
    titleUrl: Optional[str] = None
    coverUrl: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASSETS":
        d = d or {}
        return cls(iconUrl=d.get("iconUrl"), titleUrl=d.get("titleUrl"), coverUrl=d.get("coverUrl"), data=d)


@dataclass
class GAME:
    """
    Represents a game supported by CurseForge (e.g., Minecraft).

    Fields:
      - id/name/slug: identity
      - assets: various images
      - status/apiStatus: internal flags
      - data: raw JSON
    """
    id: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    assets: ASSETS = field(default_factory=ASSETS)
    status: Optional[int] = None
    apiStatus: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GAME":
        d = d or {}
        assets = ASSETS.from_dict(d.get("assets") or {})
        return cls(
            id=d.get("id"),
            name=d.get("name"),
            slug=d.get("slug"),
            assets=assets,
            status=d.get("status"),
            apiStatus=d.get("apiStatus"),
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Modpack manifest structures
@dataclass
class MODPACKMANIFESTALT:
    """
    Helper container grouping for nested manifest parts (keeps naming parity with previous dynamic model).
    Contains nested dataclasses for MINECRAFT section and File entries.
    """

    @dataclass
    class MINECRAFT:
        """
        Represents the 'minecraft' section in a modpack manifest.

        Attributes
        ----------
        version: Optional[str]
            Minecraft version string (e.g., "1.20.1").
        modLoaders: List[ModLoader]
            List of mod loader choices (forge/fabric etc).
        data: raw JSON
        """
        @dataclass
        class ModLoader:
            id: Optional[str] = None
            primary: Optional[bool] = None
            data: Dict[str, Any] = field(default_factory=dict)

            @classmethod
            def from_dict(cls, d: Dict[str, Any]) -> "MODPACKMANIFESTALT.MINECRAFT.ModLoader":
                d = d or {}
                return cls(id=d.get("id"), primary=d.get("primary"), data=d)

        version: Optional[str] = None
        modLoaders: List["MODPACKMANIFESTALT.MINECRAFT.ModLoader"] = field(default_factory=list)
        data: Dict[str, Any] = field(default_factory=dict)

        @classmethod
        def from_dict(cls, d: Dict[str, Any]) -> "MODPACKMANIFESTALT.MINECRAFT":
            d = d or {}
            loaders = [MODPACKMANIFESTALT.MINECRAFT.ModLoader.from_dict(m) for m in (d.get("modLoaders") or [])]
            return cls(version=d.get("version"), modLoaders=loaders, data=d)

    @dataclass
    class File:
        """
        One entry in the manifest's 'files' list.

        Fields:
          - projectID: CurseForge project id
          - fileID: chosen file id for that project (specific upload)
          - required: whether the mod is required
          - data: raw JSON
        """
        projectID: Optional[int] = None
        fileID: Optional[int] = None
        required: Optional[bool] = None
        data: Dict[str, Any] = field(default_factory=dict)

        @classmethod
        def from_dict(cls, d: Dict[str, Any]) -> "MODPACKMANIFESTALT.File":
            d = d or {}
            return cls(projectID=d.get("projectID"), fileID=d.get("fileID"), required=d.get("required"), data=d)


@dataclass
class MODPACKMANIFEST:
    """
    Represents a full modpack manifest (manifest.json) used by many CurseForge modpacks.

    Typical fields:
      - minecraft: nested info (version/modLoaders)
      - manifestType/manifestVersion: manifest schema info
      - name/version/author: metadata
      - files: list of MODPACKMANIFESTALT.File items
      - data: raw JSON payload kept for debug/forward-compat
    """
    minecraft: MODPACKMANIFESTALT.MINECRAFT = field(default_factory=MODPACKMANIFESTALT.MINECRAFT)
    manifestType: Optional[str] = None
    manifestVersion: Optional[int] = None
    name: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    files: List[MODPACKMANIFESTALT.File] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MODPACKMANIFEST":
        d = d or {}
        mc = MODPACKMANIFESTALT.MINECRAFT.from_dict(d.get("minecraft") or {})
        files = [MODPACKMANIFESTALT.File.from_dict(f) for f in (d.get("files") or [])]
        return cls(
            minecraft=mc,
            manifestType=d.get("manifestType"),
            manifestVersion=d.get("manifestVersion"),
            name=d.get("name"),
            version=d.get("version"),
            author=d.get("author"),
            files=files,
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Fingerprint matching result types
@dataclass
class FingerprintAlt:
    """
    Helper nested classes for fingerprint matches returned by fingerprint endpoints.
    This version avoids using default_factory with class objects that are not yet defined.
    """

    @dataclass
    class File:
        id: Optional[int] = None
        fileName: Optional[str] = None
        downloadUrl: Optional[str] = None
        data: Dict[str, Any] = field(default_factory=dict)

        @classmethod
        def from_dict(cls, d: Dict[str, Any]) -> "FingerprintAlt.File":
            d = d or {}
            return cls(
                id=d.get("id"),
                fileName=d.get("fileName"),
                downloadUrl=d.get("downloadUrl"),
                data=d,
            )

    @dataclass
    class exactMatche:
        id: Optional[int] = None
        # use Optional and default None; set proper instance in from_dict
        file: Optional["FingerprintAlt.File"] = None
        data: Dict[str, Any] = field(default_factory=dict)

        @classmethod
        def from_dict(cls, d: Dict[str, Any]) -> "FingerprintAlt.exactMatche":
            d = d or {}
            file_obj = None
            if d.get("file") is not None:
                file_obj = FingerprintAlt.File.from_dict(d.get("file"))
            return cls(id=d.get("id"), file=file_obj, data=d)

    @dataclass
    class partialMatche:
        id: Optional[int] = None
        file: Optional["FingerprintAlt.File"] = None
        data: Dict[str, Any] = field(default_factory=dict)

        @classmethod
        def from_dict(cls, d: Dict[str, Any]) -> "FingerprintAlt.partialMatche":
            d = d or {}
            file_obj = None
            if d.get("file") is not None:
                file_obj = FingerprintAlt.File.from_dict(d.get("file"))
            return cls(id=d.get("id"), file=file_obj, data=d)


@dataclass
class Fingerprint:
    """
    Top-level fingerprint response container.

    Common fields:
      - isCacheBuilt: whether the fingerprint database/cache is ready
      - exactMatches: list of exact match objects (FingerprintAlt.exactMatche)
      - exactFingerprints: list of fingerprint integers that matched exactly
      - partialMatches: similar but not exact
      - partialMatchFingerprints: mapping (string fingerprint -> list modIDs or similar)
      - installedFingerprints: list of fingerprints provided by client (echo)
      - unmatchedFingerprints: fingerprints that could not be matched
      - data: raw JSON
    """
    isCacheBuilt: Optional[bool] = None
    exactMatches: List[FingerprintAlt.exactMatche] = field(default_factory=list)
    exactFingerprints: List[int] = field(default_factory=list)
    partialMatches: List[FingerprintAlt.partialMatche] = field(default_factory=list)
    partialMatchFingerprints: Dict[str, Any] = field(default_factory=dict)
    installedFingerprints: List[int] = field(default_factory=list)
    unmatchedFingerprints: List[int] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Fingerprint":
        d = d or {}
        exact = [FingerprintAlt.exactMatche.from_dict(x) for x in (d.get("exactMatches") or [])]
        partial = [FingerprintAlt.partialMatche.from_dict(x) for x in (d.get("partialMatches") or [])]
        return cls(
            isCacheBuilt=d.get("isCacheBuilt"),
            exactMatches=exact,
            exactFingerprints=d.get("exactFingerprints") or [],
            partialMatches=partial,
            partialMatchFingerprints=d.get("partialMatchFingerprints") or {},
            installedFingerprints=d.get("installedFingerprints") or [],
            unmatchedFingerprints=d.get("unmatchedFingerprints") or [],
            data=d,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Game version grouping (for /games/{id}/versions response)
@dataclass
class GAMEVERSION:
    """
    Represents a grouping of game versions (often returned as arrays of versions grouped by type).
    Each GAMEVERSION contains a `type` (release/beta) and a list of VERSION entries.
    """
    @dataclass
    class VERSION:
        id: Optional[int] = None
        slug: Optional[str] = None
        name: Optional[str] = None
        data: Dict[str, Any] = field(default_factory=dict)

        @classmethod
        def from_dict(cls, d: Dict[str, Any]) -> "GAMEVERSION.VERSION":
            d = d or {}
            return cls(id=d.get("id"), slug=d.get("slug"), name=d.get("name"), data=d)

    type: Optional[int] = None
    versions: List[VERSION] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GAMEVERSION":
        d = d or {}
        versions = [GAMEVERSION.VERSION.from_dict(v) for v in (d.get("versions") or [])]
        return cls(type=d.get("type"), versions=versions, data=d)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MODLOADERDATA_DT:
    """
    Typed dataclass for a modloader entry.

    Fields mirror the API response. This is intended to be used in the
    library's typed layers (client return types, internal processing).

    Attributes
    ----------
    name : Optional[str]
        e.g. "forge-9.11.1.965"
    gameVersion : Optional[str]
        e.g. "1.6.4"
    latest : bool
        Whether this entry is the latest release.
    recommended : bool
        Whether this entry is recommended.
    dateModified : Optional[str]
        ISO8601 timestamp string as returned by the API.
    data : Dict[str, Any]
        Original raw mapping (kept for debugging/round-trip).
    """

    name: Optional[str] = None
    gameVersion: Optional[str] = None
    latest: bool = False
    recommended: bool = False
    dateModified: Optional[str] = None

    # original raw data for debugging or serialization
    data: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    # Factory
    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "MODLOADERDATA_DT":
        """
        Construct a MODLOADERDATA_DT from a raw dictionary.

        This method is defensive: it tolerates None and missing keys.
        """
        if not d:
            return cls()
        return cls(
            name=d.get("name"),
            gameVersion=d.get("gameVersion"),
            latest=bool(d.get("latest", False)),
            recommended=bool(d.get("recommended", False)),
            dateModified=d.get("dateModified"),
            data=d,
        )

    # Serialization
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert back to the canonical API-like dictionary.
        """
        return {
            "name": self.name,
            "gameVersion": self.gameVersion,
            "latest": self.latest,
            "recommended": self.recommended,
            "dateModified": self.dateModified,
        }

    # Convenience: parsed datetime
    def date_modified_dt(self) -> Optional[datetime]:
        """
        Parse dateModified into a datetime if possible.

        Returns None when parsing fails or dateModified is empty.
        """
        if not self.dateModified:
            return None
        # Prefer python-dateutil if available (handles many ISO variants).
        if _dateutil_parser is not None:
            try:
                return _dateutil_parser.parse(self.dateModified)
            except Exception:
                pass
        # Fallback to fromisoformat (handle 'Z' suffix)
        try:
            return datetime.fromisoformat(self.dateModified.replace("Z", "+00:00"))
        except Exception:
            return None

    # Representation
    def __repr__(self) -> str:
        return (
            f"<MODLOADERDATA_DT name={self.name!r} gameVersion={self.gameVersion!r} "
            f"latest={self.latest} recommended={self.recommended}>"
        )

# Module exports
__all__ = [
    "MODLOADER", "CURSEFORGECLASS","MODLOADERDATA_DT",
    "MODSS", "MODLINKS", "CATEGORY", "MODAUTHOR", "MODLOGO",
    "MODFILEHASH", "MODFILEMODULE", "MODFILEsortableGameVersions", "MODFILEsIndexes",
    "MODFILE", "MODINFO",
    "ASSETS", "GAME",
    "MODPACKMANIFESTALT", "MODPACKMANIFEST", "FingerprintAlt", "Fingerprint",
    "GAMEVERSION",
]
