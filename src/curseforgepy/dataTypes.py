from __future__ import annotations
import requests,time
from typing import *
from enum import IntEnum
from .exceptions import (
    CurseForgeError,
    AuthError,
    NotFoundError,
    BadRequestError,
    RateLimitError,
    ServerError,
    NetworkError,
    map_http_status
)

class MODSS:
    """
    Represents a lightweight mod/project structure (used in file lists or summaries).
    
    Attributes:
        id (int):Internal ID of the mod or file entry.
        modId (int):Parent mod/project ID.
        title (str):Display title of the mod or file.
        description (str):Short or preview description (not the full README).
        thumbnailUrl (str):Thumbnail or logo URL.
        url (str):Full CurseForge web URL of this mod/file.
        data (Dict):Original raw JSON data for debugging or future parsing.
    """
    def __init__(self, data:Dict[str, Union[str, int]]):
        self.id:Optional[int]=data.get('id')
        self.modId:Optional[int]=data.get('modId')
        self.title:Optional[str]=data.get('title')
        self.description:Optional[str]=data.get('description')
        self.thumbnailUrl:Optional[str]=data.get('thumbnailUrl')
        self.url:Optional[str]=data.get('url')
        self.data=data


class MODLINKS:
    """
    Represents external links related to a mod/project.
    
    Attributes:
        websiteUrl (str):Main page of the mod on CurseForge.
        wikiUrl (str):Link to documentation or wiki (if provided).
        issuesUrl (str):Bug tracker or issue reporting page.
        sourceUrl (str):Source code repository (e.g., GitHub).
        data (Dict):Original JSON data.
    """
    def __init__(self, data:Dict):
        self.websiteUrl:Optional[str]=data.get('websiteUrl')
        self.wikiUrl:Optional[str]=data.get('wikiUrl')
        self.issuesUrl:Optional[str]=data.get('issuesUrl')
        self.sourceUrl:Optional[str]=data.get('sourceUrl')
        self.data=data


class CATEGORY:
    """
    Represents a CurseForge category (like "Adventure", "Technology", etc.).
    
    Attributes:
        id (int):Category ID.
        gameId (int):The game this category belongs to.
        name (str):Display name of the category.
        slug (str):URL slug for the category.
        url (str):Full category page URL.
        iconUrl (str):Category icon image URL.
        dateModified (str):ISO date when this category was last updated.
        classId (int):Class grouping ID (e.g., modpack, resourcepack, world).
        isClass (bool):Whether this is a class rather than a category.
        parentCategoryId (int):ID of the parent category, if any.
        data (Dict):Original raw JSON.
    """
    def __init__(self, data:Dict):
        self.id:Optional[int]=data.get('id')
        self.gameId:Optional[int]=data.get('gameId')
        self.name:Optional[str]=data.get('name')
        self.slug:Optional[str]=data.get('slug')
        self.url:Optional[str]=data.get('url')
        self.iconUrl:Optional[str]=data.get('iconUrl')
        self.dateModified:Optional[str]=data.get('dateModified')
        self.classId:Optional[int]=data.get('classId')
        self.isClass:Optional[bool]=data.get('isClass')
        self.parentCategoryId:Optional[int]=data.get('parentCategoryId')
        self.data=data


class MODAUTHOR:
    """
    Represents an author or contributor of a mod/project.
    
    Attributes:
        id (int):Author's CurseForge ID.
        name (str):Display name of the author.
        url (str):Link to the author's profile.
        avatarUrl (str):Author's profile picture.
        data (Dict):Original JSON.
    """
    def __init__(self, data:Dict):
        self.id:Optional[int]=data.get('id')
        self.name:Optional[str]=data.get('name')
        self.url:Optional[str]=data.get('url')
        self.avatarUrl:Optional[str]=data.get('avatarUrl')
        self.data=data


class MODLOGO:
    """
    Represents a mod’s logo or thumbnail image object.
    
    Attributes:
        id (int):Image ID.
        modId (int):Related mod/project ID.
        title (str):Optional title/alt text for the image.
        description (str):Optional image description.
        thumbnailUrl (str):Small-sized image URL.
        url (str):Full-sized image URL.
        data (Dict):Original JSON.
    """
    def __init__(self, data:Dict):
        self.id:Optional[int]=data.get('id')
        self.modId:Optional[int]=data.get('modId')
        self.title:Optional[str]=data.get('title')
        self.description:Optional[str]=data.get('description')
        self.thumbnailUrl:Optional[str]=data.get('thumbnailUrl')
        self.url:Optional[str]=data.get('url')
        self.data=data


class MODFILEHASH:
    """
    Represents a hash value for a specific mod file.
    
    Attributes:
        value (str):Hash string (e.g., MD5/SHA1/CRC).
        algo (int):Algorithm type (see CurseForge API docs, usually 1=SHA1, 2=MD5).
        data (Dict):Original JSON.
    """
    def __init__(self, data:Dict):
        self.value:Optional[str]=data.get('value')
        self.algo:Optional[int]=data.get('algo')
        self.data=data


class MODFILESORTABLEGAMEVERSIONS:
    """
    Represents game version metadata associated with a file.
    
    Attributes:
        gameVersionName (str):Version name (e.g., "1.20.1").
        gameVersionPadded (str):Padded numeric format used for sorting.
        gameVersion (str):Original string version.
        gameVersionReleaseDate (str):ISO date of version release.
        gameVersionTypeId (int):Version type ID (release/beta/alpha).
        data (Dict):Original JSON.
    """
    def __init__(self, data:Dict):
        self.gameVersionName:Optional[str]=data.get('gameVersionName')
        self.gameVersionPadded:Optional[str]=data.get('gameVersionPadded')
        self.gameVersion:Optional[str]=data.get('gameVersion')
        self.gameVersionReleaseDate:Optional[str]=data.get('gameVersionReleaseDate')
        self.gameVersionTypeId:Optional[int]=data.get('gameVersionTypeId')
        self.data=data


class MODFILEMODULE:
    """
    Represents a single module inside a mod file.
    
    Modules usually correspond to internal parts of a modpack (e.g., submods or libraries).
    
    Attributes:
        name (str):Name of the module or internal file.
        fingerprint (int):File fingerprint identifier.
        data (Dict):Original JSON.
    """
    def __init__(self, data:Dict):
        self.name:Optional[str]=data.get('name')
        self.fingerprint:Optional[int]=data.get('fingerprint')
        self.data=data

class MODFILEsortableGameVersions:
    """
    Represents game version metadata associated with a file.
    
    This object contains detailed metadata about the supported or targeted
    game versions for a specific mod file. It allows sorting, filtering, and
    display of compatible versions across different loaders and releases.

    Attributes:
        gameVersionName (str):Human-readable version name (e.g., "1.20.1").
        gameVersionPadded (str):Padded numeric format used internally for version sorting.
        gameVersion (str):Original version identifier string.
        gameVersionReleaseDate (str):ISO-formatted release date string for the version.
        gameVersionTypeId (int):Internal numeric ID representing version type (e.g., Release, Beta, Alpha).
        data (Dict):The raw JSON Dictionary from the CurseForge API response.
    """
    def __init__(self, data:Dict):
        self.gameVersionName:Optional[str]=data.get('gameVersionName')
        self.gameVersionPadded:Optional[str]=data.get('gameVersionPadded')
        self.gameVersion:Optional[str]=data.get('gameVersion')
        self.gameVersionReleaseDate:Optional[str]=data.get('gameVersionReleaseDate')
        self.gameVersionTypeId:Optional[int]=data.get('gameVersionTypeId')
        self.data=data


class MODFILE:
    """
    Represents a single mod file entry in the CurseForge API response.

    A mod file is a specific uploaded version of a mod or modpack. It contains
    information about the file's metadata, compatibility, hashes, dependencies,
    and downloadable modules. This class helps parse and structure that data
    into manageable Python objects.

    Attributes:
        id (int):Unique file ID assigned by CurseForge.
        gameId (int):ID of the game this file belongs to (e.g., 432 for Minecraft).
        modId (int):ID of the parent mod this file belongs to.
        isAvailable (bool):Whether the file is available for download.
        displayName (str):Display title of the file (usually includes version or release tag).
        fileName (str):Actual filename of the uploaded mod file (e.g., `.jar`, `.zip`).
        releaseType (int):Numeric release type (1=Release, 2=Beta, 3=Alpha).
        fileStatus (int):Internal CurseForge file status code.
        hashes (List[MODFILEHASH]):List of file hashes for integrity verification.
        fileDate (str):Upload date in ISO-8601 format.
        fileLength (int):File size in bytes.
        downloadCount (int):Total number of downloads for this specific file.
        downloadUrl (str):Direct download URL for the file.
        gameVersions (List[str]):List of game versions this file supports (e.g., ["1.20.1", "1.20.2"]).
        sortableGameVersions (List[MODFILEsortableGameVersions]):Detailed version objects for sorting/filtering.
        dependencies (List[Dict]):Dependencies declared for this file (mods required or optional).
        alternateFileId (int):If this file is an alternate release, links to the main file’s ID.
        isServerPack (bool):Whether the file is flagged as a server pack (for modpacks).
        fileFingerprint (int):Unique fingerprint hash for matching file versions.
        modules (List[MODFILEMODULE]):Internal components or submodules included within this file.
        data (Dict):Original JSON data from the CurseForge API response.
    """
    def __init__(self, data:Dict):
        # Basic identifying info
        self.id:Optional[int]=data.get('id')
        self.gameId:Optional[int]=data.get('gameId')
        self.modId:Optional[int]=data.get('modId')
        self.isAvailable:Optional[bool]=data.get('isAvailable')

        # Descriptive info
        self.displayName:Optional[str]=data.get('displayName')
        self.fileName:Optional[str]=data.get('fileName')
        self.releaseType:Optional[int]=data.get('releaseType')
        self.fileStatus:Optional[int]=data.get('fileStatus')

        # File hashes (list of MODFILEHASH objects)
        self.hashes:List['MODFILEHASH']=[]
        if data.get('hashes'):
            for hashe in data['hashes']:
                self.hashes.append(MODFILEHASH(hashe))

        # File metadata
        self.fileDate:Optional[str]=data.get('fileDate')
        self.fileLength:Optional[int]=data.get('fileLength')
        self.downloadCount:Optional[int]=data.get('downloadCount')
        self.downloadUrl:Optional[str]=data.get('downloadUrl')

        # Supported game versions (simple + detailed)
        self.gameVersions:Optional[List[str]]=data.get('gameVersions')
        self.sortableGameVersions:List['MODFILEsortableGameVersions']=[]
        if data.get('sortableGameVersions'):
            for sgv in data['sortableGameVersions']:
                self.sortableGameVersions.append(MODFILEsortableGameVersions(sgv))

        # Dependency & linking info
        self.dependencies:Optional[List[Dict]]=data.get('dependencies')
        self.alternateFileId:Optional[int]=data.get('alternateFileId')
        self.isServerPack:Optional[bool]=data.get('isServerPack')
        self.fileFingerprint:Optional[int]=data.get('fileFingerprint')

        # Internal modules (list of MODFILEMODULE)
        self.modules:List['MODFILEMODULE']=[]
        if data.get('modules'):
            for module in data['modules']:
                self.modules.append(MODFILEMODULE(module))

        # Keep raw data for reference
        self.data:Dict=data

class MODFILEsIndexes:
    """
    Represents a lightweight mapping between game versions and file identifiers for a mod.

    This object is typically used to quickly determine which file corresponds to which
    game version, without needing to fetch all file details.

    Attributes:
        gameVersion (str):The game version string (e.g., "1.20.1").
        fileId (int):The ID of the corresponding file for that version.
        filename (str):The name of the uploaded file.
        releaseType (int):Numeric release type (1=Release, 2=Beta, 3=Alpha).
        gameVersionTypeId (int):The internal game version type ID (used in filtering).
        modLoader (int):Identifier for the mod loader type (e.g., Forge=1, Fabric=4).
        data (Dict):Original JSON response data.
    """
    def __init__(self, data:Dict):
        self.gameVersion:Optional[str]=data.get('gameVersion')
        self.fileId:Optional[int]=data.get('fileId')
        self.filename:Optional[str]=data.get('filename')
        self.releaseType:Optional[int]=data.get('releaseType')
        self.gameVersionTypeId:Optional[int]=data.get('gameVersionTypeId')
        self.modLoader:Optional[int]=data.get('modLoader')
        self.data:Dict=data


class MODINFO:
    """
    Represents the full metadata of a mod (project) retrieved from the CurseForge API.

    This class provides structured access to mod attributes, authors, categories,
    files, screenshots, and statistics. It acts as a unified data container for
    all primary mod-related information returned by the `/v1/mods/{mod_id}` endpoint.

    Attributes:
        id (int):Unique mod ID.
        gameId (int):The game ID this mod belongs to.
        name (str):Human-readable mod name.
        slug (str):URL-friendly identifier used in CurseForge links.
        link (MODLINKS):Object containing URLs like website, wiki, issues, and source.
        summary (str):Short description of the mod.
        status (int):Internal project status (active, rejected, etc.).
        downloadCount (int):Total downloads across all versions.
        isFeatured (bool):Whether the mod is currently featured.
        primaryCategoryId (int):The main category ID for this project.
        categories (List[CATEGORY]):List of categories assigned to the mod.
        classId (int):Class type ID (e.g., mods, modpacks, texture packs, etc.).
        authors (List[MODAUTHOR]):List of authors associated with the project.
        logo (MODLOGO):Primary logo object of the mod.
        mainFileId (int):ID of the mod’s main (primary) file.
        latestFiles (List[MODFILE]):List of recently uploaded files for this mod.
        latestFilesIndexes (List[MODFILEsIndexes]):Simplified version-to-file mappings.
        latestEarlyAccessFilesIndexes (List[Dict]):Same as above but for early access versions.
        screenshots (List[MODSS]):List of screenshot metadata objects.
        selected_file (Optional[MODFILE]):Reference to the currently selected or preferred file.
        dateCreated (str):ISO timestamp of project creation.
        dateModified (str):ISO timestamp of last modification.
        dateReleased (str):ISO timestamp of the first release.
        allowModDistribution (bool):Whether redistribution is allowed.
        gamePopularityRank (int):Popularity rank within the game’s mod ecosystem.
        isAvailable (bool):Whether the project is publicly available.
        thumbsUpCount (int):Number of likes / positive votes.
        featuredProjectTag (str):Tag used when mod is featured.
        data (Dict):Original raw JSON data.
    """
    def __init__(self, data:Dict):
        # Initialize screenshots
        self.screenshots:List['MODSS']=[]
        self.selected_file:Optional['MODFILE']=None
        if data.get('screenshots'):
            for ss in data['screenshots']:
                self.screenshots.append(MODSS(ss))

        # Core attributes
        self.id:Optional[int]=data.get('id')
        self.gameId:Optional[int]=data.get('gameId')
        self.name:Optional[str]=data.get('name')
        self.slug:Optional[str]=data.get('slug')
        self.link:Optional['MODLINKS']=MODLINKS(data['links']) if data.get('links') else None
        self.summary:Optional[str]=data.get('summary')
        self.status:Optional[int]=data.get('status')
        self.downloadCount:Optional[int]=data.get('downloadCount')
        self.isFeatured:Optional[bool]=data.get('isFeatured')
        self.primaryCategoryId:Optional[int]=data.get('primaryCategoryId')

        # Category objects
        self.categories:List['CATEGORY']=[]
        if data.get('categories'):
            for category in data['categories']:
                self.categories.append(CATEGORY(category))

        # Class type
        self.classId:Optional[int]=data.get('classId')

        # Author list
        self.authors:List['MODAUTHOR']=[]
        if data.get('authors'):
            for author in data['authors']:
                self.authors.append(MODAUTHOR(author))

        # Logo
        self.logo:Optional['MODLOGO']=MODLOGO(data['logo']) if data.get('logo') else None
        self.mainFileId:Optional[int]=data.get('mainFileId')

        # Latest files (detailed list)
        self.latestFiles:List['MODFILE']=[]
        if data.get('latestFiles'):
            for lf in data['latestFiles']:
                self.latestFiles.append(MODFILE(lf))

        # Latest file indexes (lightweight version map)
        self.latestFilesIndexes:List['MODFILEsIndexes']=[]
        if data.get('latestFilesIndexes'):
            for lfi in data['latestFilesIndexes']:
                self.latestFilesIndexes.append(MODFILEsIndexes(lfi))

        # Optional early access version mapping
        self.latestEarlyAccessFilesIndexes:Optional[List[Dict]]=data.get('latestEarlyAccessFilesIndexes')

        # Metadata and timestamps
        self.dateCreated:Optional[str]=data.get('dateCreated')
        self.dateModified:Optional[str]=data.get('dateModified')
        self.dateReleased:Optional[str]=data.get('dateReleased')
        self.allowModDistribution:Optional[bool]=data.get('allowModDistribution')
        self.gamePopularityRank:Optional[int]=data.get('gamePopularityRank')
        self.isAvailable:Optional[bool]=data.get('isAvailable')
        self.thumbsUpCount:Optional[int]=data.get('thumbsUpCount')
        self.featuredProjectTag:Optional[str]=data.get('featuredProjectTag')

        # Store original JSON for debugging/reference
        self.data:Dict=data

class ASSETS:
    """
    Represents image and media assets associated with a CurseForge game.

    Attributes
    ----------
    iconUrl : Optional[str]
        URL of the game’s square icon (commonly used in lists).
    titleUrl : Optional[str]
        URL of the title/banner image used in headers.
    coverUrl : Optional[str]
        URL of the cover image for marketing or store pages.
    data : Dict
        Original raw JSON data returned by the API.
    """
    def __init__(self, data: Optional[Dict]):
        data = data or {}
        self.data: Dict = data
        self.iconUrl: Optional[str] = data.get("iconUrl")
        self.titleUrl: Optional[str] = data.get("titleUrl")
        self.coverUrl: Optional[str] = data.get("coverUrl")

    def __repr__(self) -> str:
        return f"<ASSETS icon={self.iconUrl!r} title={self.titleUrl!r}>"


class GAME:
    """
    Represents a game entry on CurseForge (e.g., Minecraft, Terraria, etc.).

    Attributes
    ----------
    id : Optional[int]
        Numeric ID of the game on CurseForge.
    name : Optional[str]
        Display name of the game.
    slug : Optional[str]
        URL-friendly slug (used in web addresses).
    assets : ASSETS
        Associated images (icon, title, cover).
    status : Optional[int]
        Internal status code of the game (0 = inactive, 1 = active, etc.).
    apiStatus : Optional[int]
        API availability status (0 = offline, 1 = available).
    data : Dict
        Raw JSON data returned from the API.
    """
    def __init__(self, data: Dict):
        self.data: Dict = data
        self.id: Optional[int] = data.get("id")
        self.name: Optional[str] = data.get("name")
        self.slug: Optional[str] = data.get("slug")
        self.assets: ASSETS = ASSETS(data.get("assets") or {})
        self.status: Optional[int] = data.get("status")
        self.apiStatus: Optional[int] = data.get("apiStatus")

    def __repr__(self) -> str:
        return f"<GAME id={self.id} name={self.name!r} status={self.status}>"
        
class MODPACKMANIFESTALT:
    """
    Internal container classes for CurseForge Modpack manifest sections.
    Used by MODPACKMANIFEST to represent nested structures like Minecraft info or file entries.
    """

    class MINECRAFT:
        """
        Represents the 'minecraft' section of a modpack manifest file.
        
        Attributes
        ----------
        version : Optional[str]
            The Minecraft version string, e.g. "1.20.1".
        modLoaders : List[MODPACKMANIFESTALT.MINECRAFT.ModLoader]
            List of modloaders (Forge, Fabric, Quilt, etc.) used by this modpack.
        data : Dict
            Raw JSON data for debugging or direct access.
        """

        class ModLoader:
            """
            Represents a modloader entry inside the manifest's minecraft.modLoaders list.

            Attributes
            ----------
            id : Optional[str]
                The modloader ID, e.g. "forge-47.2.0".
            primary : Optional[bool]
                Whether this is the primary modloader used by the modpack.
            data : Dict
                Raw JSON data.
            """
            def __init__(self, data: Dict):
                self.data: Dict = data
                self.id: Optional[str] = data.get("id")
                self.primary: Optional[bool] = data.get("primary")

            def __repr__(self):
                return f"<ModLoader id={self.id!r} primary={self.primary}>"

        def __init__(self, data: Dict):
            data = data or {}
            self.data: Dict = data
            self.version: Optional[str] = data.get("version")
            self.modLoaders: List["MODPACKMANIFESTALT.MINECRAFT.ModLoader"] = [
                MODPACKMANIFESTALT.MINECRAFT.ModLoader(d) for d in (data.get("modLoaders") or [])
            ]

        def __repr__(self):
            return f"<MINECRAFT version={self.version!r} modLoaders={len(self.modLoaders)}>"

    class File:
        """
        Represents an individual file (mod entry) in a modpack manifest.
        
        Attributes
        ----------
        projectID : Optional[int]
            CurseForge project ID of the mod.
        fileID : Optional[int]
            Specific file ID from the project used in this modpack.
        required : Optional[bool]
            Whether this mod is required for the modpack to function.
        data : Dict
            Raw JSON data.
        """
        def __init__(self, data: Dict):
            self.data: Dict = data
            self.projectID: Optional[int] = data.get("projectID")
            self.fileID: Optional[int] = data.get("fileID")
            self.required: Optional[bool] = data.get("required")

        def __repr__(self):
            return f"<ManifestFile projectID={self.projectID} fileID={self.fileID} required={self.required}>"

class MODPACKMANIFEST:
    """
    Represents the main manifest.json file of a CurseForge modpack.
    
    Attributes
    ----------
    minecraft : MODPACKMANIFESTALT.MINECRAFT
        Minecraft version and modloader information.
    manifestType : Optional[str]
        The manifest type, usually "minecraftModpack".
    manifestVersion : Optional[int]
        The manifest schema version (usually 1).
    name : Optional[str]
        The display name of the modpack.
    version : Optional[str]
        Version string of the modpack.
    author : Optional[str]
        Modpack author name.
    files : List[MODPACKMANIFESTALT.File]
        List of all mod entries (mods) in this manifest.
    data : Dict
        Raw manifest JSON data.
    """
    def __init__(self, data: Dict):
        self.data: Dict = data
        self.minecraft: MODPACKMANIFESTALT.MINECRAFT = MODPACKMANIFESTALT.MINECRAFT(data.get("minecraft", {}))
        self.manifestType: Optional[str] = data.get("manifestType")
        self.manifestVersion: Optional[int] = data.get("manifestVersion")
        self.name: Optional[str] = data.get("name")
        self.version: Optional[str] = data.get("version")
        self.author: Optional[str] = data.get("author")
        self.files: List[MODPACKMANIFESTALT.File] = [
            MODPACKMANIFESTALT.File(d) for d in (data.get("files") or [])
        ]

    def __repr__(self):
        return f"<MODPACKMANIFEST name={self.name!r} version={self.version!r} files={len(self.files)}>"
        
class FingerprintAlt:
    """
    Helper container classes for Fingerprint matching results.
    """

    class File:
        """
        Represents a file matched by fingerprint lookup.

        Attributes
        ----------
        id : Optional[int]
            File ID on CurseForge.
        fileName : Optional[str]
            File name string, e.g. "BetterFps-1.4.8.jar".
        downloadUrl : Optional[str]
            Direct CDN download URL.
        data : Dict
            Raw JSON data.
        """
        def __init__(self, data: Dict):
            self.data: Dict = data
            self.id: Optional[int] = data.get("id")
            self.fileName: Optional[str] = data.get("fileName")
            self.downloadUrl: Optional[str] = data.get("downloadUrl")

        def __repr__(self):
            return f"<FingerprintFile id={self.id} name={self.fileName!r}>"

    class exactMatche:
        """
        Represents an exact fingerprint match (identical hash found).

        Attributes
        ----------
        id : Optional[int]
            Matched mod ID.
        file : FingerprintAlt.File
            File metadata associated with this match.
        """
        def __init__(self, data: Dict):
            self.data: Dict = data
            self.id: Optional[int] = data.get("id")
            self.file: FingerprintAlt.File = FingerprintAlt.File(data.get("file", {}))

        def __repr__(self):
            return f"<ExactMatch id={self.id} file={self.file.fileName!r}>"

    class partialMatche:
        """
        Represents a partial fingerprint match (similar file or version).

        Attributes
        ----------
        id : Optional[int]
            Matched mod ID.
        file : FingerprintAlt.File
            File metadata for the matched file.
        """
        def __init__(self, data: Dict):
            self.data: Dict = data
            self.id: Optional[int] = data.get("id")
            self.file: FingerprintAlt.File = FingerprintAlt.File(data.get("file", {}))

        def __repr__(self):
            return f"<PartialMatch id={self.id} file={self.file.fileName!r}>"

class Fingerprint:
    """
    Represents a complete fingerprint match result returned by CurseForge's fingerprint API.

    Attributes
    ----------
    isCacheBuilt : Optional[bool]
        Indicates whether the fingerprint cache is built and ready.
    exactMatches : List[FingerprintAlt.exactMatche]
        List of exact matches.
    exactFingerprints : List[int]
        List of fingerprints that matched exactly.
    partialMatches : List[FingerprintAlt.partialMatche]
        List of partial matches.
    partialMatchFingerprints : Dict[str, int]
        Mapping of partial fingerprint IDs to mod IDs.
    installedFingerprints : List[int]
        Fingerprints found in local installation.
    unmatchedFingerprints : List[int]
        Fingerprints not matched to any known files.
    data : Dict
        Raw JSON data from the API.
    """
    def __init__(self, data: Dict):
        self.data: Dict = data
        self.isCacheBuilt: Optional[bool] = data.get("isCacheBuilt")
        self.exactMatches: List[FingerprintAlt.exactMatche] = [
            FingerprintAlt.exactMatche(d) for d in (data.get("exactMatches") or [])
        ]
        self.exactFingerprints: List[int] = data.get("exactFingerprints") or []
        self.partialMatches: List[FingerprintAlt.partialMatche] = [
            FingerprintAlt.partialMatche(d) for d in (data.get("partialMatches") or [])
        ]
        self.partialMatchFingerprints: Dict[str, int] = data.get("partialMatchFingerprints") or {}
        self.installedFingerprints: List[int] = data.get("installedFingerprints") or []
        self.unmatchedFingerprints: List[int] = data.get("unmatchedFingerprints") or []

    def __repr__(self):
        return f"<Fingerprint exact={len(self.exactMatches)} partial={len(self.partialMatches)}>"

class GAMEVERSION:
    """
    Represents a group of game versions for a specific game (like Minecraft).

    Attributes
    ----------
    type : Optional[int]
        Version type ID (e.g., 1 = release, 2 = beta, 3 = alpha).
    versions : List[GAMEVERSION.VERSION]
        List of specific version entries belonging to this type.
    data : Dict
        Raw JSON data.
    """

    class VERSION:
        """
        Represents a single version entry within a GAMEVERSION object.

        Attributes
        ----------
        id : Optional[int]
            Version ID on CurseForge.
        slug : Optional[str]
            Version slug (short text).
        name : Optional[str]
            Version name string (e.g., "1.20.1").
        data : Dict
            Raw JSON data.
        """
        def __init__(self, data: Dict):
            self.data: Dict = data
            self.id: Optional[int] = data.get("id")
            self.slug: Optional[str] = data.get("slug")
            self.name: Optional[str] = data.get("name")

        def __repr__(self):
            return f"<Version name={self.name!r}>"

    def __init__(self, data: Dict):
        self.data: Dict = data
        self.type: Optional[int] = data.get("type")
        self.versions: List["GAMEVERSION.VERSION"] = [
            GAMEVERSION.VERSION(d) for d in (data.get("versions") or [])
        ]

    def __repr__(self):
        return f"<GAMEVERSION type={self.type} versions={len(self.versions)}>"

class MODLOADERDATA:
    """
    Represents a single modloader entry from CurseForge API.

    This class follows the same style as other classes in dataTypes.py:
    - Accepts a raw dict at initialization and stores it on `.data`.
    - Provides convenience typed attributes mapping to API fields.
    - Performs light normalization (booleans, missing keys).
    - Minimal helper methods: to_dict() and __repr__().

    Example raw:
        {
            "name": "forge-9.11.1.965",
            "gameVersion": "1.6.4",
            "latest": False,
            "recommended": False,
            "dateModified": "2017-01-01T00:00:00Z"
        }
    """

    def __init__(self, data: Dict[str, Any] | None):
        """
        Initialize MODLOADERDATA from raw mapping.

        Parameters
        ----------
        data : Dict[str, Any] | None
            Raw JSON/dict returned by the API for a modloader entry.
        """
        d = data or {}
        self.data: Dict[str, Any] = d

        # Keep the attribute names identical to the API for familiarity.
        self.name: Optional[str] = d.get("name")
        self.gameVersion: Optional[str] = d.get("gameVersion")

        # Normalize booleans: accept bool-like values (0/1/"true"/None)
        self.latest: bool = bool(d.get("latest", False))
        self.recommended: bool = bool(d.get("recommended", False))

        # ISO8601 string, may be None
        self.dateModified: Optional[str] = d.get("dateModified")

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a JSON-serializable shallow dict following the API keys.

        Useful for caching or returning raw-like objects to callers.
        """
        return {
            "name": self.name,
            "gameVersion": self.gameVersion,
            "latest": self.latest,
            "recommended": self.recommended,
            "dateModified": self.dateModified,
        }

    def __repr__(self) -> str:
        return (
            f"<MODLOADERDATA name={self.name!r} gameVersion={self.gameVersion!r} "
            f"latest={self.latest} recommended={self.recommended}>"
        )

class MODLOADER(IntEnum):
    """
    Enum representing supported Minecraft mod loaders for CurseForge.

    Attributes:
        any (0):Any loader (default).
        forge (1):Forge mod loader.
        cauldron (2):Cauldron server mod loader.
        liteloader (3):LiteLoader mod loader.
        fabric (4):Fabric mod loader.
        quilt (5):Quilt mod loader.
        neoforge (6):NeoForge loader.
    """
    any=0
    forge=1
    cauldron=2
    liteloader=3
    fabric=4
    quilt=5
    neoforge=6

    @classmethod
    def name_by_id(cls, loader_id:int) -> str:
        """Return the loader name given its ID, or 'Unknown' if invalid."""
        try:
            return cls(loader_id).name.title()
        except ValueError:
            return "Unknown"

    @classmethod
    def id_by_name(cls, name:str) -> Optional[int]:
        """Return the loader ID given its name (case-insensitive), or None if not found."""
        for loader in cls:
            if loader.name.lower() == name.lower():
                return loader.value
        return None


class CURSEFORGECLASS(IntEnum):
    """
    Enum mapping CurseForge class IDs to their types.

    Example usage:
        CURSEFORGECLASS.MOD.value -> 6
        CURSEFORGECLASS.MOD.name -> "MOD"

    Common class types:
        MOD:Mod files
        RESOURCE_PACK:Resource packs
        SHADER:Shader packs
        MODPACKS:Modpacks
        WORLDS:World saves
        DATAPACKS:Minecraft datapacks
        COSMETIC:Cosmetic packs
        PLUGINS:Server plugins
    """
    MOD=6
    RESOURCE_PACK=12
    SHADER=6552
    MODPACKS=4471
    WORLDS=17
    DATAPACKS=6871
    COSMETIC=4994
    PLUGINS=5

    @classmethod
    def get_class_name(cls, class_id:int) -> str:
        """Get the readable class type name from its ID."""
        try:
            return cls(class_id).name.replace("_", " ").title()
        except ValueError:
            return "Unknown"

    @classmethod
    def get_class_id(cls, name:str) -> Optional[int]:
        """Get the class ID from a readable name (case-insensitive)."""
        for item in cls:
            if item.name.lower() == name.replace(" ", "_").lower():
                return item.value
        return None

    @classmethod
    def all_classes(cls) -> Dict[int, str]:
        """Return all class IDs mapped to their readable names."""
        return {item.value:item.name.replace("_", " ").title() for item in cls}

class CURSEFORGE:
    """
    CURSEFORGE helper class that uses CURSEFORGEAPIURLS for endpoints.

    Features:
      - Uses CURSEFORGEAPIURLS.* templates for all endpoint paths
      - Safe URL builder that accepts either endpoint attribute name or raw path
      - Low-level HTTP requester with retries/backoff and basic rate-limit handling
      - High-level convenience helpers for common CurseForge actions
      - Detailed docstrings and explicit exception types for each method

    Usage example:
      cf=CURSEFORGE(api="MY_KEY")
      url=cf.build_url("GET_MOD_FILES", mod_id=238222)
      print(url)  # https://api.curseforge.com/v1/mods/238222/files
    """

    def __init__(
        self,
        api:str,
        timeout:float=10.0,
        session:Optional[requests.Session]=None,
        default_retries:int=3,
        default_backoff:float=0.6,
    ) -> None:
        """
        Initialize CURSEFORGE helper.

        Parameters
        ----------
        api:Optional[str]
            CurseForge API key. Required for requests that access the API.
        timeout:float
            Request timeout in seconds.
        session:Optional[requests.Session]
            Optional requests.Session (useful for injecting mocked sessions/tests).
        default_retries:int
            Retries for transient errors (network, 5xx, 429).
        default_backoff:float
            Backoff multiplier for exponential backoff (wait=backoff * 2^(attempt-1)).
        """
        self.api_key=api
        self.base_url=CURSEFORGEAPIURLS.BASE_URL
        self.timeout=float(timeout)
        self.session=session or requests.Session()

        # sensible default headers; user can update session.headers directly
        self.session.headers.setdefault("Accept", "application/json")
        self.session.headers.setdefault("User-Agent", "CurseForgeDataType/0.1")
        if self.api_key:self.session.headers["x-api-key"]=self.api_key

        self.default_retries=int(default_retries)
        self.default_backoff=float(default_backoff)

    # ------------------------
    # Configuration helpers
    # ------------------------
    def set_api_key(self, api:str) -> None:
        """
        Set or replace the API key used for requests.

        Raises
        ------
        ValueError:if `api` is falsy.
        """
        if not api:raise ValueError("api must be a non-empty string")
        self.api_key=api
        self.session.headers["x-api-key"]=api

    def ensure_has_api_key(self) -> None:
        """
        Ensure an API key is set for methods that perform authenticated requests.

        Raises
        ------
        AuthError:if no API key is present.
        """
        if not self.api_key:
            raise AuthError("API key not configured. Call set_api_key() or pass api in __init__.")

    # ------------------------
    # Endpoint helpers (use CURSEFORGEAPIURLS)
    # ------------------------
    def list_endpoint_names(self) -> List[str]:
        """
        Return available endpoint names (keys) from CURSEFORGEAPIURLS.

        Returns
        -------
        List[str]:sorted list of endpoint attribute names (e.g. ['GET_MOD', 'GET_MOD_FILES', ...]).
        """
        return CURSEFORGEAPIURLS.list_names()

    def get_endpoint_template(self, name:str) -> str:
        """
        Get endpoint template path by attribute name from CURSEFORGEAPIURLS.

        Parameters
        ----------
        name:str
            Attribute name on CURSEFORGEAPIURLS, case-sensitive (e.g. 'GET_MOD').

        Returns
        -------
        str:path template (e.g. '/v1/mods/{mod_id}').

        Raises
        ------
        KeyError:if `name` is not present on CURSEFORGEAPIURLS.
        """
        if not hasattr(CURSEFORGEAPIURLS, name):
            raise KeyError(f"Unknown endpoint name:{name!r}. Available:{', '.join(self.list_endpoint_names())}")
        return getattr(CURSEFORGEAPIURLS, name)

    def build_url(self, endpoint_name_or_path:str, /, **path_params) -> str:
        """
        Build a full URL by using either:
          - endpoint attribute name from CURSEFORGEAPIURLS (preferred), or
          - a raw path (starting with '/').

        Parameters
        ----------
        endpoint_name_or_path:str
            E.g. 'GET_MOD_FILES' (uses the CURSEFORGEAPIURLS template),
            or '/v1/custom/path/{id}' for raw path usage.
        path_params:mapping
            Named parameters required by the template (e.g. mod_id=123).

        Returns
        -------
        str:full absolute URL.

        Raises
        ------
        KeyError:if endpoint name doesn't exist in CURSEFORGEAPIURLS.
        ValueError:if a required path parameter is missing when formatting.
        """
        # determine whether user provided a raw path or an endpoint name
        if endpoint_name_or_path.startswith("/"):
            template=endpoint_name_or_path
        else:
            template=self.get_endpoint_template(endpoint_name_or_path)

        # format template, produce helpful error on missing params
        try:
            path=template.format(**path_params)
        except KeyError as exc:
            missing=exc.args[0] if exc.args else "unknown"
            raise ValueError(f"Missing required path parameter:{missing} for template {template!r}")

        if not path.startswith("/"):
            path="/" + path

        return f"{self.base_url.rstrip('/')}{path}"

    # ------------------------
    # Low-level request with retry/backoff and rate-limit handling
    # ------------------------
    def _request(
        self,
        method:str,
        endpoint_or_path:str,
        *,
        params:Optional[Dict[str, Any]]=None,
        json:Optional[Any]=None,
        headers:Optional[Dict[str, str]]=None,
        path_params:Optional[Dict[str, Any]]=None,
        stream:bool=False,
        retries:Optional[int]=None,
        backoff:Optional[float]=None,
    ) -> requests.Response:
        """
        Perform HTTP request with sensible retries, exponential backoff and rate-limit handling.

        Parameters
        ----------
        method:str
            'GET', 'POST', etc.
        endpoint_or_path:str
            Endpoint name (from CURSEFORGEAPIURLS) or raw path (starting with '/').
        params:Dict | None
            Query parameters.
        json:Any | None
            JSON body for POST/PUT.
        headers:Dict | None
            Request-level headers merged over session.headers.
        path_params:Dict | None
            Named params for path formatting.
        stream:bool
            If True, returns a Response in stream mode (caller must handle .raw/.iter_content).
        retries:int | None
            Override default retries.
        backoff:float | None
            Override default backoff factor.

        Returns
        -------
        requests.Response

        Raises
        ------
        AuthError:HTTP 401/403
        NotFoundError:HTTP 404
        RateLimitError:HTTP 429
        BadRequestError:other 4xx
        ServerError:5xx after retries exhausted
        NetworkError:requests.RequestException after retries exhausted
        """
        # ensure api key present because this implementation always sets x-api-key header for requests
        self.ensure_has_api_key()

        retries=self.default_retries if retries is None else int(retries)
        backoff=self.default_backoff if backoff is None else float(backoff)
        path_params=path_params or {}

        url=self.build_url(endpoint_or_path, **path_params)

        attempt=0
        while True:
            attempt += 1
            try:
                req_headers={}
                if headers:
                    req_headers.update(headers)  # request-specific override

                resp=self.session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=req_headers,
                    timeout=self.timeout,
                    stream=stream
                )
                if resp.status_code >= 400:raise map_http_status(resp.status_code, resp.text, resp)
            except requests.RequestException as exc:
                # network-level error
                if attempt > retries:
                    raise NetworkError(f"Network error after {attempt} attempts:{exc}") from exc
                wait=backoff * (2 ** (attempt - 1))
                time.sleep(wait)
                continue

            status=resp.status_code

            # Authentication errors
            if status in (401, 403):
                raise AuthError(f"Authentication failed (HTTP {status}). Check API key and permissions.")

            # Not found
            if status == 404:
                raise NotFoundError(f"Resource not found (HTTP 404) for URL:{url}")

            # Rate limit
            if status == 429:
                # try parse Retry-After header (seconds)
                retry_after=None
                if "Retry-After" in resp.headers:
                    try:
                        retry_after=float(resp.headers["Retry-After"])
                    except Exception:
                        retry_after=None
                if attempt > retries:
                    raise RateLimitError("Rate limited and retries exhausted", retry_after)
                wait=retry_after if retry_after is not None else backoff * (2 ** (attempt - 1))
                time.sleep(wait)
                continue

            # Client error (other)
            if 400 <= status < 500:
                raise BadRequestError(f"Client error HTTP {status}:{resp.text}")

            # Server error -> retry up to retries
            if 500 <= status < 600:
                if attempt > retries:
                    raise ServerError(f"Server error HTTP {status}:{resp.text}")
                wait=backoff * (2 ** (attempt - 1))
                time.sleep(wait)
                continue

            # success
            return resp

    # ------------------------
    # JSON convenience helper
    # ------------------------
    def _get_json(self, endpoint_or_path:str, *, params:Optional[Dict[str, Any]]=None,
                  path_params:Optional[Dict[str, Any]]=None, headers:Optional[Dict[str,str]]=None) -> Any:
        """
        Perform GET request and return parsed JSON.

        Returns parsed JSON['data'] if available, otherwise full JSON.

        Raises same exceptions as _request.
        """
        resp=self._request("GET", endpoint_or_path, params=params, headers=headers, path_params=path_params)
        if resp.status_code >= 400:raise map_http_status(resp.status_code, resp.text, resp)
        # if stream was used this is not appropriate; this helper assumes non-stream
        try:
            j=resp.json()
        except ValueError as exc:
            raise CurseForgeError(f"Invalid JSON received from {resp.url}:{exc}") from exc

        # prefer 'data' envelope if present
        if isinstance(j, Dict) and "data" in j:
            return j["data"]
        return j

    # ------------------------
    # High-level convenience methods
    # ------------------------
    def search_mods(self, game_id:int, search_filter:str, page_size:int=20, index:int=0) -> Any:
        """
        Search mods using CurseForge search endpoint.

        Parameters
        ----------
        game_id:int
            Game ID (e.g., Minecraft game id).
        search_filter:str
            Text to search for in mod names/descriptions.
        page_size:int
            Number of items per page (max depends on API).
        index:int
            Page index / offset.

        Returns
        -------
        Parsed JSON 'data' from the search endpoint (usually a list/Dict with pagination).

        Raises
        ------
        AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        params={"gameId":game_id, "searchFilter":search_filter, "pageSize":page_size, "index":index}
        return self._get_json(CURSEFORGEAPIURLS.SEARCH_MODS, params=params)

    def get_mod(self, mod_id:int) -> Any:
        """
        Get mod/project metadata by ID.

        Parameters
        ----------
        mod_id:int

        Returns
        -------
        Parsed 'data' JSON for the mod (Dict).

        Raises
        ------
        NotFoundError, AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        return self._get_json(CURSEFORGEAPIURLS.GET_MOD, path_params={"mod_id":mod_id})
    
    def search_mods_advanced(self,
                         game_id: int,
                         search_filter: str | None = None,
                         class_id: int | None = None,
                         category_id: int | None = None,
                         mod_loader_type: int | None = None,
                         game_version: str | None = None,
                         sort_field: int = 2,
                         sort_order: str = "desc",
                         page_size: int = 50,
                         index: int = 0) -> Any:
        """
        Advanced search wrapper over /v1/mods/search.

        Uses: CURSEFORGEAPIURLS.SEARCH_MODS

        Parameters
        ----------
        game_id : int
            Required game id.
        search_filter : str | None
            Free-text filter (name/description).
        class_id : int | None
            classId filter (e.g., CURSEFORGE class constants).
        category_id : int | None
            categoryId filter.
        mod_loader_type : int | None
            modLoaderType (e.g., Forge/Fabric constants).
        game_version : str | None
            Specific game version string to filter compatibility.
        sort_field : int
            API sort field (default 2).
        sort_order : str
            'asc' or 'desc'.
        page_size, index : pagination.

        Returns
        -------
        Any
            API 'data' for the search (paged result).

        Raises
        ------
        AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        params: Dict[str, Any] = {
            "gameId": game_id,
            "pageSize": page_size,
            "index": index,
            "sortField": sort_field,
            "sortOrder": sort_order
        }
        if search_filter:
            params["searchFilter"] = search_filter
        if class_id is not None:
            params["classId"] = class_id
        if category_id is not None:
            params["categoryId"] = category_id
        if mod_loader_type is not None:
            params["modLoaderType"] = mod_loader_type
        if game_version:
            params["gameVersion"] = game_version

        return self._get_json(CURSEFORGEAPIURLS.SEARCH_MODS, params=params)

    def get_mods_bulk(self, mod_ids: list[int]) -> list[Dict]:
        """
        Retrieve multiple mods in a single POST call.

        Uses: CURSEFORGEAPIURLS.GET_MODS (POST)

        Parameters
        ----------
        mod_ids : list[int]
            List of mod IDs to fetch (limit determined by API; keep sizes reasonable).

        Returns
        -------
        list[Dict]
            List of mod objects in the order returned by the API.

        Raises
        ------
        ValueError: if mod_ids empty.
        AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        if not mod_ids:
            raise ValueError("mod_ids must be a non-empty list of integers")
        # use _request to allow POST
        resp = self._request("POST", CURSEFORGEAPIURLS.GET_MODS, json={"modIds": mod_ids})
        try:
            j = resp.json()
        except ValueError as e:
            raise CurseForgeError(f"Invalid JSON from GET_MODS: {e}") from e
        return j.get("data", j)

    def get_mod_files(self, mod_id:int, page_size:int=50, index:int=0) -> Any:
        """
        List files for a mod.

        Parameters
        ----------
        mod_id:int
        page_size:int
        index:int

        Returns
        -------
        Parsed JSON data containing file list (often list of file objects).

        Raises same as get_mod.
        """
        params={"pageSize":page_size, "index":index}
        return self._get_json(CURSEFORGEAPIURLS.GET_MOD_FILES, params=params, path_params={"mod_id":mod_id})
    
    def get_mod_description_html(self, mod_id: int) -> str:
        """
        Return the HTML 'Overview' / description for a mod.

        Uses: CURSEFORGEAPIURLS.GET_MOD_DESCRIPTION

        Returns
        -------
        str : HTML string

        Raises
        ------
        NotFoundError, AuthError, BadRequestError, RateLimitError, ServerError, NetworkError, CurseForgeError
        """
        resp = self._request("GET", CURSEFORGEAPIURLS.GET_MOD_DESCRIPTION, path_params={"mod_id": mod_id})
        # Description endpoints usually return raw HTML or JSON with 'data' containing HTML.
        # Use text when API returns text/html, otherwise try JSON 'data'.
        ctype = resp.headers.get("Content-Type", "")
        if "text/html" in ctype:
            return resp.text
        try:
            j = resp.json()
        except ValueError:
            raise CurseForgeError("Unexpected non-HTML, non-JSON response for mod description")
        # prefer raw data if present
        if isinstance(j, Dict) and "data" in j:return j["data"]
        # otherwise try to stringify
        return str(j)
    
    def get_mod_file_changelog(self, mod_id: int, file_id: int) -> str:
        """
        Retrieve the changelog (HTML) for a specific file.

        Uses: CURSEFORGEAPIURLS.GET_MOD_FILE_CHANGELOG

        Returns HTML string.

        Raises
        ------
        NotFoundError, AuthError, BadRequestError, RateLimitError, ServerError, NetworkError, CurseForgeError
        """
        resp = self._request("GET", CURSEFORGEAPIURLS.GET_MOD_FILE_CHANGELOG, path_params={"mod_id": mod_id, "file_id": file_id})
        ctype = resp.headers.get("Content-Type", "")
        if "text/html" in ctype:
            return resp.text
        try:
            j = resp.json()
        except ValueError:
            raise CurseForgeError("Unexpected changelog response format")
        return j.get("data", str(j))

    def featured_mods(self, game_id: int, excluded_mod_ids: Optional[list[int]] = None, game_version_type_id: Optional[int] = None) -> Any:
        """
        Request curated featured mods block.

        Uses: CURSEFORGEAPIURLS.FEATURED_MODS (POST)

        Parameters
        ----------
        game_id: int
        excluded_mod_ids: list[int] | None
        game_version_type_id: int | None

        Returns
        -------
        Any

        Raises
        ------
        AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        body = {"gameId": int(game_id)}
        if excluded_mod_ids:
            body["excludedModIds"] = excluded_mod_ids
        if game_version_type_id is not None:
            body["gameVersionTypeId"] = game_version_type_id
        resp = self._request("POST", CURSEFORGEAPIURLS.FEATURED_MODS, json=body)
        try:
            j = resp.json()
        except ValueError as e:
            raise CurseForgeError(f"Invalid JSON from featured_mods: {e}") from e
        return j.get("data", j)
    
    def get_files_bulk(self, file_ids: list[int]) -> list[Dict]:
        """
        Retrieve multiple file objects using the bulk endpoint.

        Uses: CURSEFORGEAPIURLS.MODS_FILES_BULK (preferred) or CURSEFORGEAPIURLS.FILES_BULK

        Parameters
        ----------
        file_ids : list[int]

        Returns
        -------
        list[Dict]

        Raises
        ------
        ValueError, AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        if not file_ids:
            raise ValueError("file_ids must be a non-empty list")
        try:
            endpoint = CURSEFORGEAPIURLS.MODS_FILES_BULK
        except AttributeError:
            endpoint = CURSEFORGEAPIURLS.FILES_BULK
        resp = self._request("POST", endpoint, json={"fileIds": file_ids})
        try:
            j = resp.json()
        except ValueError as e:
            raise CurseForgeError(f"Invalid JSON from files bulk: {e}") from e
        return j.get("data", j)
    
    def get_latest_compatible_file(self, mod_id: int, game_version: str, mod_loader_type: int | None = None) -> Dict | None:
        """
        Find the latest file for a mod that is compatible with a specific game_version and optional mod loader.

        Implementation:
        - Paginate through GET_MOD_FILES (or call paginate_all)
        - Filter by version(s) and modLoaderType
        - Sort by file.uploadTime or file.id (depending on API shape) and return newest

        Parameters
        ----------
        mod_id : int
        game_version : str
        mod_loader_type : int | None

        Returns
        -------
        Dict | None
            File metadata for the chosen file, or None if no compatible file found.

        Raises
        ------
        NotFoundError, AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        files = self.paginate_all(CURSEFORGEAPIURLS.GET_MOD_FILES, params=None, path_params={"mod_id": mod_id}, page_size=50)
        # best-effort: API file objects usually include 'gameVersion'/'gameVersions' and 'modLoader' info
        candidates = []
        for f in files:
            # example fields: 'gameVersions' (list) or 'gameVersion' (single)
            gvs = f.get("gameVersions") or ([f.get("gameVersion")] if f.get("gameVersion") else [])
            # normalize
            if isinstance(gvs, str):
                gvs = [gvs]
            if game_version in gvs:
                if mod_loader_type is None:
                    candidates.append(f)
                else:
                    # check modLoaderType or 'modLoaders' field
                    mlt = f.get("modLoaderType") or f.get("modLoader")
                    # modLoaders might be list with ints or Dicts
                    if mlt is None:
                        # if not provided assume compatible
                        candidates.append(f)
                    else:
                        # normalize
                        if isinstance(mlt, list):
                            if mod_loader_type in [int(x) for x in mlt]:
                                candidates.append(f)
                        else:
                            try:
                                if int(mlt) == int(mod_loader_type):
                                    candidates.append(f)
                            except Exception:
                                pass
        if not candidates:
            return None
        # sort by 'fileDate'/'fileTime'/'id' fallback; prefer newest upload time if available
        def _sort_key(x):
            for key in ("fileDate", "fileTime", "uploadedAt", "fileDateUTC", "id"):
                if key in x:
                    return x.get(key)
            return x.get("id", 0)
        candidates.sort(key=_sort_key, reverse=True)
        return candidates[0]

    def validate_api_key(self) -> bool:
        """
        Quick validation of API key by calling the GAMES endpoint.

        Returns
        -------
        bool
            True if key is valid (call succeeded), raises AuthError/other on failure.

        Raises
        ------
        AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        # if this raises AuthError, caller can handle it
        self._get_json(CURSEFORGEAPIURLS.GAMES)
        return True


    def get_file_download_url(self, mod_id:int, file_id:int) -> str:
        """
        Obtain the direct download URL for a mod file.

        Parameters
        ----------
        mod_id:int
        file_id:int

        Returns
        -------
        str:direct HTTP download URL

        Notes
        -----
        The API returns either a string or an object containing the URL in 'data';
        this method normalizes and returns a plain string.

        Raises
        ------
        NotFoundError, AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        data=self._get_json(
            CURSEFORGEAPIURLS.GET_FILE_DOWNLOAD_URL,
            path_params={"mod_id":mod_id, "file_id":file_id}
        )
        # API may return string or Dict envelope; normalize
        if isinstance(data, str):
            return data
        if isinstance(data, Dict):
            # common shape:{'url':'...'} or direct payload in 'data'
            for key in ("url", "downloadUrl"):
                if key in data and isinstance(data[key], str):
                    return data[key]
            # if there's a single string value, return it
            for v in data.values():
                if isinstance(v, str) and v.startswith("http"):
                    return v
        raise CurseForgeError("Unexpected response shape for file download URL")

    def get_categories(self, game_id:Optional[int]=None) -> Any:
        """
        Retrieve categories. Optionally filter by gameId.

        Returns parsed JSON 'data'.

        Raises same exceptions as _get_json.
        """
        params={"gameId":game_id} if game_id is not None else None
        return self._get_json(CURSEFORGEAPIURLS.CATEGORIES, params=params)

    def get_minecraft_versions(self) -> Any:
        """
        Return Minecraft version metadata (useful for compatibility checks).

        Raises same exceptions as _get_json.
        """
        return self._get_json(CURSEFORGEAPIURLS.MINECRAFT_VERSIONS)
    
    def get_game_versions_v2(self, game_id: int) -> Union[List,Dict]:
        """
        Retrieve game versions using the v2 endpoint when available.

        Uses: CURSEFORGEAPIURLS.GAME_VERSIONS_V2

        Parameters
        ----------
        game_id : int
            Numeric ID of the game.

        Returns
        -------
        Any
            Parsed 'data' object from the v2 versions endpoint (often richer metadata than v1).

        Raises
        ------
        KeyError: if CURSEFORGEAPIURLS.GAME_VERSIONS_V2 is not present (shouldn't happen).
        AuthError, NotFoundError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        return self._get_json(CURSEFORGEAPIURLS.GAME_VERSIONS_V2, path_params={"gameId": game_id})

    def download_file_stream(self, file_url:str, target_path:str, chunk_size:int=8192) -> None:
        """
        Download a file by streaming to disk (safe for large files).

        Parameters
        ----------
        file_url:str
            Direct download URL (may be from get_file_download_url()).
        target_path:str
            Local file path to write to.
        chunk_size:int
            Bytes per chunk.

        Raises
        ------
        NetworkError:if streaming fails after retries.
        CurseForgeError:for general unexpected failures.
        """
        # stream directly using session; allow transient network retries using _request wrapper with stream=True
        # we cannot use path_params here since file_url is absolute; use raw path handling by passing leading '/'
        # build a minimal temporary request using requests directly but still with basic retry loop:
        retries=self.default_retries
        backoff=self.default_backoff
        attempt=0
        while True:
            attempt += 1
            try:
                # If file_url belongs to the same base, convert it to relative by removing base; otherwise pass absolute via requests directly.
                if file_url.startswith(self.base_url):
                    # remove base to reuse _request formatting (so headers and auth applied consistently)
                    rel_path=file_url[len(self.base_url):]
                    resp=self._request("GET", rel_path, stream=True)
                else:
                    # absolute URL (external/storage); use session.request directly to preserve headers and cookies
                    resp=self.session.get(file_url, stream=True, timeout=self.timeout)
                    resp.raise_for_status()
                # write stream
                with resp:
                    with open(target_path, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=chunk_size):
                            if chunk:
                                fh.write(chunk)
                return
            except requests.RequestException as exc:
                if attempt > retries:
                    raise NetworkError(f"Download failed after {attempt} attempts:{exc}") from exc
                wait=backoff * (2 ** (attempt - 1))
                time.sleep(wait)
                continue
            except CurseForgeError:
                # re-raise library-specific errors (e.g., RateLimitError) immediately
                raise
            except Exception as exc:
                raise CurseForgeError(f"Unexpected error during download:{exc}") from exc

    # ------------------------
    # Utility helpers
    # ------------------------
    def legacy_project_url(self, slug:str) -> str:
        """
        Build legacy project URL path (older CurseForge endpoints or UI).

        This is a convenience for other modules that may need the old-style project path.

        Example:
            '/projects/{slug}'
        """
        if not slug or not isinstance(slug, str):
            raise ValueError("slug must be a non-empty string")
        return f"/projects/{slug}"
    
    def get_games(self) -> list[Dict]:
        """
        Retrieve the list of games supported by CurseForge.

        Uses: CURSEFORGEAPIURLS.GAMES

        Returns
        -------
        list[Dict]
            A list of game objects (raw JSON Dictionaries) returned by the API.

        Raises
        ------
        AuthError, BadRequestError, RateLimitError, ServerError, NetworkError, CurseForgeError
        """
        return self._get_json(CURSEFORGEAPIURLS.GAMES)
    
    def get_minecraft_modloader(self, mod_loader_name: str) -> Dict:
        """
        Retrieve metadata for a specific Minecraft modloader (e.g., 'forge', 'fabric').

        Uses: CURSEFORGEAPIURLS.MINECRAFT_MODLOADER

        Raises: AuthError, NotFoundError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        if not mod_loader_name or not isinstance(mod_loader_name, str):
            raise ValueError("mod_loader_name must be a non-empty string")
        return self._get_json(CURSEFORGEAPIURLS.MINECRAFT_MODLOADER, path_params={"modLoaderName": mod_loader_name})

    def match_fingerprints(self, fingerprints: list[int]) -> Any:
        """
        Match a list of file fingerprints across all games.

        Uses: CURSEFORGEAPIURLS.FINGERPRINTS

        Parameters
        ----------
        fingerprints : list[int]

        Returns
        -------
        Any
            Matching result object (depends on API shape).

        Raises
        ------
        ValueError, AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        if not fingerprints:
            raise ValueError("fingerprints must be a non-empty list of integers")
        resp = self._request("POST", CURSEFORGEAPIURLS.FINGERPRINTS, json={"fingerprints": fingerprints})
        try:
            j = resp.json()
        except ValueError as e:
            raise CurseForgeError(f"Invalid JSON from fingerprints: {e}") from e
        return j.get("data", j)
    
    def match_fingerprints_by_game(self, game_id: int, fingerprints: list[int]) -> Any:
        """
        Fuzzy or exact fingerprint matching limited to a specific game.

        Uses: CURSEFORGEAPIURLS.FINGERPRINTS_BY_GAME or FINGERPRINTS_FUZZY_BY_GAME

        Parameters
        ----------
        game_id : int
        fingerprints : list[int]

        Returns
        -------
        Any

        Raises
        ------
        ValueError, AuthError, BadRequestError, RateLimitError, ServerError, NetworkError
        """
        if not fingerprints:
            raise ValueError("fingerprints must be a non-empty list")
        endpoint = CURSEFORGEAPIURLS.FINGERPRINTS_BY_GAME
        resp = self._request("POST", endpoint, json={"fingerprints": fingerprints}, path_params={"gameId": game_id})
        try:
            j = resp.json()
        except ValueError as e:
            raise CurseForgeError(f"Invalid JSON from fingerprints_by_game: {e}") from e
        return j.get("data", j)

    def paginate_all(self, endpoint_or_path: str, params: Optional[Dict] = None, path_params: Optional[Dict] = None, page_size: int = 50) -> list:
        """
        Generic paginator helper: fetch all pages by incrementing 'index' until empty.

        Parameters
        ----------
        endpoint_or_path : str
            Endpoint from CURSEFORGEAPIURLS or raw path.
        params : Dict | None
            Base query params (will be copied per request).
        path_params : Dict | None
            Path parameters for the endpoint template.
        page_size : int
            Items per page.

        Returns
        -------
        list
            Combined list of items from all pages.

        Raises
        ------
        Propagates same exceptions as _get_json/_request.
        """
        out = []
        idx = 0
        base_params = Dict(params or {})
        while True:
            base_params.update({"pageSize": page_size, "index": idx})
            data = self._get_json(endpoint_or_path, params=base_params, path_params=path_params)
            # API may return Dict with pagination or direct list
            if isinstance(data, Dict) and "items" in data:
                items = data.get("items", [])
            elif isinstance(data, list):
                items = data
            elif isinstance(data, Dict) and "data" in data:
                items = data["data"]
            else:
                # if unexpected shape, attempt best-effort extraction
                items = data if isinstance(data, list) else []
            if not items:
                break
            out.extend(items)
            # if page not full, assume last page
            if len(items) < page_size:
                break
            idx += 1
        return out



class CURSEFORGEAPIURLS:
    """
    Centralized container for all CurseForge REST API endpoint paths.

    This class only stores **relative paths**. 
    You should prepend these with `BASE_URL` to build the full request URL.

    Usage:
        >>> full_url=f"{CURSEFORGEAPIURLS.BASE_URL}{CURSEFORGEAPIURLS.GET_MOD.format(mod_id=238222)}"

    Documentation Source:
        - https://docs.curseforge.com
        - CurseForge for Studios REST API Reference

    Notes:
        - All endpoints require an `x-api-key` header in requests.
        - Some endpoints use POST and accept JSON bodies (explicitly marked below).
        - Versioned endpoints (v1 / v2) may return different data structures.
        - Use `GET` unless otherwise specified.
    """

    # ------------------------------------------
    # BASE CONFIGURATION
    # ------------------------------------------
    BASE_URL="https://api.curseforge.com"
    """Base API root for CurseForge REST API."""

    LEGACY_PROJECTS="/api/projects/"
    """Legacy internal project path (kept for compatibility with older API consumers)."""

    # ------------------------------------------
    # GAMES & VERSIONS
    # ------------------------------------------
    GAMES="/v1/games"
    """GET → Retrieve a list of all supported games on CurseForge."""

    GAME="/v1/games/{gameId}"
    """GET → Retrieve metadata for a specific game by its numeric ID."""

    GAME_VERSIONS="/v1/games/{gameId}/versions"
    """GET (v1) → Returns the list of game versions for the specified game ID."""

    GAME_VERSIONS_V2="/v2/games/{gameId}/versions"
    """GET (v2) → Same as above, but uses the newer v2 schema with richer metadata."""

    GAME_VERSION_TYPES="/v1/games/{gameId}/version-types"
    """GET → Returns version categories (e.g., 'release', 'beta', 'alpha') for a given game."""

    # ------------------------------------------
    # CATEGORIES & CLASSES
    # ------------------------------------------
    CATEGORIES="/v1/categories"
    """GET → Retrieve available categories and class hierarchies.
    Query Parameters:
        - gameId:int
        - classId:int (optional)
        - classesOnly:bool (optional)
    """

    # ------------------------------------------
    # MODS / PROJECTS
    # ------------------------------------------
    SEARCH_MODS="/v1/mods/search"
    """GET → Search mods by filters.
    Query Parameters:
        - gameId, classId, categoryId, slug, etc.
    """

    GET_MOD="/v1/mods/{mod_id}"
    """GET → Retrieve a single mod’s full metadata by its mod ID."""

    GET_MODS="/v1/mods"
    """POST → Retrieve multiple mods by their IDs.
    Body Example:{ "modIds":[12345, 67890] }
    """

    GET_MOD_DESCRIPTION="/v1/mods/{mod_id}/description"
    """GET → Returns the full HTML description (“Overview” content on CurseForge)."""

    FEATURED_MODS="/v1/mods/featured"
    """POST → Retrieve a curated list of featured mods.
    Body:{ "gameId":int, "excludedModIds":[...], "gameVersionTypeId":int }
    """

    # ------------------------------------------
    # FILES
    # ------------------------------------------
    GET_MOD_FILES="/v1/mods/{mod_id}/files"
    """GET → List all uploaded files for a given mod."""

    GET_MOD_FILE="/v1/mods/{mod_id}/files/{file_id}"
    """GET → Retrieve detailed metadata for a specific file."""

    GET_MOD_FILE_CHANGELOG="/v1/mods/{mod_id}/files/{file_id}/changelog"
    """GET → Retrieve the changelog (HTML) for a specific mod file."""

    GET_FILE_DOWNLOAD_URL="/v1/mods/{mod_id}/files/{file_id}/download-url"
    """GET → Retrieve the direct CDN download URL for a mod file."""

    MODS_FILES_BULK="/v1/mods/files"
    """POST → Retrieve multiple file objects by ID list.
    Body:{ "fileIds":[111, 222, 333] }
    """

    FILES_BULK="/v1/files"
    """Alias (kept for backward naming consistency)."""

    # ------------------------------------------
    # FINGERPRINTS (FILE MATCHING)
    # ------------------------------------------
    FINGERPRINTS="/v1/fingerprints"
    """POST → Match a list of fingerprints against all games.
    Body:{ "fingerprints":[int, int, ...] }
    """

    FINGERPRINTS_BY_GAME="/v1/fingerprints/{gameId}"
    """POST → Match fingerprints restricted to a specific game ID."""

    FINGERPRINTS_FUZZY="/v1/fingerprints/fuzzy"
    """POST → Perform fuzzy (approximate) matching across all games."""

    FINGERPRINTS_FUZZY_BY_GAME="/v1/fingerprints/fuzzy/{gameId}"
    """POST → Perform fuzzy fingerprint matching within a specific game."""

    # ------------------------------------------
    # MINECRAFT-SPECIFIC UTILITIES
    # ------------------------------------------
    MINECRAFT_MODLOADERS="/v1/minecraft/modloader"
    """GET → List all known Minecraft modloaders (e.g., Forge, Fabric)."""

    MINECRAFT_MODLOADER="/v1/minecraft/modloader/{modLoaderName}"
    """GET → Retrieve metadata for a specific modloader (e.g., forge, fabric)."""

    # ------------------------------------------
    # LEGACY & AUXILIARY ENDPOINTS
    # ------------------------------------------
    GET_FILES="/v1/mods/files"
    """POST (alias for MODS_FILES_BULK). Retrieve file objects by file IDs."""

    GET_MOD_FILE_DOWNLOAD_URL="/v1/mods/{mod_id}/files/{file_id}/download-url"
    """Duplicate constant for convenience in certain code structures."""

    MODS_BULK="/v1/mods"
    """POST (alias for GET_MODS). Retrieve multiple mods in a single request."""

    PROJECTS="/api/projects/"
    """Legacy (pre-v1) project path. Kept for compatibility with internal tools."""

    # ------------------------------------------
    # DEVELOPER NOTES
    # ------------------------------------------
    # - Most GET endpoints support pagination via `index` and `pageSize` query parameters.
    # - Mod searches support extensive filters (see /v1/mods/search documentation).
    # - Description, Changelog endpoints return HTML. Convert to text if needed.
    # - v2 endpoints provide richer objects, especially for game versions and loaders.
