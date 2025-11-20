"""
client.py - Core CurseForge client (Group 1: Core / Initialization / Request Layer)

Provides the CurseForge class that is the primary entrypoint for library users.
This module focuses on safe HTTP handling, retries/backoff, optional local JSON caching,
and a clean, documented interface for higher-level API helpers to call.

Usage example:
    from curseforgepy.client import CurseForge
    cf = CurseForge(api_key="MY_KEY")
    mods = cf._request("GET", CURSEFORGEAPIURLS.SEARCH_MODS, params={"gameId": 432, "searchFilter": "optifine"})
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import threading
from pathlib import Path
from typing import *
import logging

import requests

from .dataTypes import CURSEFORGEAPIURLS,CURSEFORGE
from .types_models import *

from .exceptions import (
    CurseForgeError,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    ManifestError,
    NotFoundError,
    RateLimitError,
    ServerError,
)

logger = logging.getLogger(__name__)
DEFAULT_USER_AGENT = "curseforgepy/0.1 (+https://github.com/Cavanshirpro/)"

# small lock for cache writes
_cache_lock = threading.Lock()


def _simple_exponential_backoff(attempt: int, base: float = 0.5, cap: float = 60.0) -> float:
    """
    Compute exponential backoff delay given attempt number (1-based).

    Parameters
    ----------
    attempt : int
        1-based attempt number.
    base : float
        base seconds to scale.
    cap : float
        maximum backoff seconds.

    Returns
    -------
    float
        seconds to sleep.
    """
    # jitterless backoff (caller can add jitter if desired)
    delay = base * (2 ** (attempt - 1))
    if delay > cap:
        delay = cap
    return delay


def _map_http_status(code: int, content: str = "") -> CurseForgeError:
    """
    Map HTTP status codes to library exceptions.

    Returns an instance of the appropriate exception with a helpful message.
    """
    if code == 400:
        return BadRequestError(f"400 Bad Request: {content}")
    if code == 401:
        return UnauthorizedError(f"401 Unauthorized: {content}")
    if code == 403:
        return ForbiddenError(f"403 Forbidden: {content}")
    if code == 404:
        return NotFoundError(f"404 Not Found: {content}")
    if code == 429:
        return RateLimitError(f"429 Too Many Requests / Rate limited: {content}")
    if 500 <= code <= 599:
        return ServerError(f"{code} Server Error: {content}")
    return CurseForgeError(f"HTTP {code}: {content}")


class CurseForge:
    """
    High-level HTTP client wrapper for the CurseForge REST API.

    Responsibilities:
      - Manage a requests.Session with proper headers (x-api-key).
      - Build endpoint URLs from CURSEFORGEAPIURLS constants.
      - Provide a resilient `_request()` method with retries/backoff and optional caching.
      - Provide small convenience methods for changing API key / base URL / cache directory.

    Parameters
    ----------
    api_key : Optional[str]
        Your CurseForge x-api-key. Can be set later via set_api_key().
    base_url : Optional[str]
        Custom API base URL (defaults to CURSEFORGEAPIURLS.BASE_URL).
    timeout : float
        Default per-request timeout in seconds.
    max_retries : int
        Default maximum attempts for idempotent requests via `_request`.
    backoff_base : float
        Base seconds for exponential backoff.
    cache_dir : Optional[str | Path]
        If provided, enable simple file-based JSON caching for GET requests.
        Cache files are stored as JSON under this directory keyed by hashed URL+params.
    cache_ttl : Optional[int]
        Time-to-live for cached entries in seconds. If None, cache never expires (use with care).

    Examples
    --------
    >>> cf = CurseForge(api_key="MY_KEY")
    >>> cf.set_base_url("https://api.curseforge.com")
    >>> data = cf._request("GET", CURSEFORGEAPIURLS.SEARCH_MODS, params={"gameId":432, "searchFilter":"foo"})
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        backoff_base: float = 0.6,
        cache_dir: Optional[Path | str] = None,
        cache_ttl: Optional[int] = None,
        default_user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.api_key: Optional[str] = api_key
        self.base_url: str = (base_url or getattr(CURSEFORGEAPIURLS, "BASE_URL", "https://api.curseforge.com")).rstrip(
            "/"
        )
        self.timeout = float(timeout)
        self.max_retries = max(1, int(max_retries))
        self.backoff_base = float(backoff_base)

        # Session: persistent connections + headers
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": default_user_agent})
        if self.api_key:
            self.session.headers["x-api-key"] = self.api_key

        self.cf=CURSEFORGE(self.api_key,self.timeout,self.session)
        # Caching
        self.cache_dir: Optional[Path] = Path(cache_dir).expanduser().resolve() if cache_dir else None
        self.cache_ttl: Optional[int] = int(cache_ttl) if cache_ttl is not None else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # Configuration helpers
    def set_api_key(self, api_key: Optional[str]):
        """
        Set or update the x-api-key header for subsequent requests.

        Parameters
        ----------
        api_key : Optional[str]
            API key string or None to remove it.
        """
        self.api_key = api_key
        if api_key:self.session.headers["x-api-key"]=api_key;self.cf.set_api_key(api_key)
        else:self.session.headers.pop("x-api-key", None)

    def set_base_url(self, base_url: str):
        """
        Change the base URL used for building endpoints.

        Ensures a safe http(s) scheme and strips trailing slash.

        Parameters
        ----------
        base_url : str
            New base URL (e.g., "https://api.curseforge.com")
        """
        if not isinstance(base_url, str) or not base_url.startswith("http"):
            raise ValueError("base_url must be an http/https URL")
        self.base_url = base_url.rstrip("/")

    def set_cache_dir(self, cache_dir: Optional[Path | str], ttl: Optional[int] = None):
        """
        Enable or change the on-disk JSON response cache.

        Parameters
        ----------
        cache_dir : Optional[Path|str]
            Directory path to store cached GET JSON responses. Set to None to disable caching.
        ttl : Optional[int]
            Time-to-live for cache entries in seconds. If None, cached entries never expire.
        """
        if cache_dir:
            p = Path(cache_dir).expanduser().resolve()
            p.mkdir(parents=True, exist_ok=True)
            self.cache_dir = p
            self.cache_ttl = int(ttl) if ttl is not None else None
        else:
            self.cache_dir = None
            self.cache_ttl = None

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Return summary information about the local cache (number of entries, total size, ttl).

        Returns
        -------
        dict with keys: count, total_bytes, ttl_seconds, path (or None)
        """
        if not self.cache_dir:
            return {"count": 0, "total_bytes": 0, "ttl_seconds": self.cache_ttl, "path": None}
        total = 0
        count = 0
        for f in self.cache_dir.glob("*.json"):
            try:
                count += 1
                total += f.stat().st_size
            except Exception:
                pass
        return {"count": count, "total_bytes": total, "ttl_seconds": self.cache_ttl, "path": str(self.cache_dir)}

    def clear_cache(self) -> int:
        """
        Clear all cached responses. Returns the number of files removed.
        """
        if not self.cache_dir:
            return 0
        removed = 0
        with _cache_lock:
            for f in self.cache_dir.glob("*.json"):
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass
        return removed

    # Cache helpers
    def _cache_key_for(self, method: str, path_or_endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Build a stable cache filename (sha1) from method+URL+sorted params.

        Returns the cache filename (basename, without path).
        """
        # Build canonical identity
        identity = f"{method.upper()} {self.base_url}{path_or_endpoint} "
        if params:
            try:
                # deterministic ordering
                identity += json.dumps(params, sort_keys=True, default=str)
            except Exception:
                identity += str(params)
        h = hashlib.sha1(identity.encode("utf-8")).hexdigest()
        return f"cfcache-{h}.json"

    def _save_cache(self, cache_name: str, payload: Any) -> None:
        """Write payload JSON to cache file atomically."""
        if not self.cache_dir:
            return
        tmp = self.cache_dir / (cache_name + ".tmp")
        final = self.cache_dir / cache_name
        data = {"timestamp": int(time.time()), "payload": payload}
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(str(tmp), str(final))
        except Exception:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    def _load_cache(self, cache_name: str) -> Optional[Any]:
        """Load cached payload if present and not expired. Return payload or None."""
        if not self.cache_dir:
            return None
        fpath = self.cache_dir / cache_name
        if not fpath.exists():
            return None
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("timestamp")
            if self.cache_ttl is not None and ts is not None:
                if int(time.time()) - int(ts) > int(self.cache_ttl):
                    # expired
                    try:
                        fpath.unlink()
                    except Exception:
                        pass
                    return None
            return data.get("payload")
        except Exception:
            # corrupt cache entry: remove it
            try:
                fpath.unlink()
            except Exception:
                pass
            return None

    # URL builder
    def _build_url(self, endpoint_or_path: str, **path_params) -> str:
        """
        Build a fully qualified URL from either:
          - an endpoint constant name in CURSEFORGEAPIURLS (e.g. "GET_MOD_FILE"), or
          - a relative path template (e.g. "/v1/mods/{mod_id}/files")

        Path parameters passed via **path_params will be substituted into templates.

        Example:
            _build_url(CURSEFORGEAPIURLS.GET_MOD_FILE, mod_id=123, file_id=456)

        Returns
        -------
        str: fully qualified URL
        """
        # If endpoint_or_path looks like a constant attribute on CURSEFORGEAPIURLS, try to treat it as such.
        path_template = None
        if isinstance(endpoint_or_path, str) and hasattr(CURSEFORGEAPIURLS, endpoint_or_path):
            path_template = getattr(CURSEFORGEAPIURLS, endpoint_or_path)
        else:
            # maybe the user passed the template string directly
            path_template = endpoint_or_path

        try:
            # fill in placeholders
            path = path_template.format(**path_params) if path_params else path_template
        except Exception as e:
            raise ValueError(f"Failed to format endpoint path '{path_template}' with {path_params}: {e}") from e

        # ensure leading slash
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url.rstrip('/')}{path}"

    # Central request method
    def _request(
        self,
        method: str,
        endpoint_or_path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        path_params: Optional[Dict[str, Any]] = None,
        allow_cache: bool = False,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        raise_for_status: bool = True,
    ) -> Any:
        """
        Perform an HTTP request against the CurseForge API with robust error handling and optional caching.

        Parameters
        ----------
        method : str
            HTTP method (GET/POST/PUT/...).
        endpoint_or_path : str
            Either CURSEFORGEAPIURLS.<NAME> or relative path template (e.g. "/v1/mods/{mod_id}").
        params : dict, optional
            Query parameters.
        json_body : Any, optional
            JSON body for methods like POST/PUT.
        data : Any, optional
            Form data or bytes to send.
        headers : dict, optional
            Extra request headers (merged with session headers).
        path_params : dict, optional
            Variables to format into the endpoint path.
        allow_cache : bool
            If True and method is GET, will read/write from simple on-disk JSON cache if configured.
        timeout : float, optional
            Overrides default timeout for this call.
        max_retries : int, optional
            Override client's default max_retries for this call.
        raise_for_status : bool
            If True raise mapped library exception for HTTP >= 400 responses.

        Returns
        -------
        Decoded JSON `data` value if present (resp.json()["data"]), otherwise full resp.json()

        Raises
        ------
        CurseForgeError subclass : for various HTTP and network errors.
        """
        method = method.upper()
        timeout = float(timeout) if timeout is not None else self.timeout
        retries = int(max_retries) if max_retries is not None else self.max_retries
        path_params = path_params or {}

        url = self._build_url(endpoint_or_path, **path_params)

        # Simple caching (only for GET)
        cache_name = None
        if allow_cache and method == "GET" and self.cache_dir:
            cache_name = self._cache_key_for(method, endpoint_or_path, params)
            cached = self._load_cache(cache_name)
            if cached is not None:
                logger.debug("CF_CACHE: hit %s", cache_name)
                return cached

        last_exc: Optional[Exception] = None
        attempt = 0
        while attempt < retries:
            attempt += 1
            try:
                req_headers = dict(self.session.headers)  # base headers
                if headers:
                    req_headers.update(headers)

                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    data=data,
                    headers=req_headers,
                    timeout=timeout,
                )

                # If HTTP error codes, map to exceptions. Respect 429 Retry-After.
                if resp.status_code >= 400:
                    content_text = resp.text[:1000] if resp.text else ""
                    if resp.status_code == 429:
                        # Honor Retry-After if possible
                        ra = None
                        try:
                            ra_header = resp.headers.get("Retry-After")
                            if ra_header:
                                ra = int(float(ra_header))
                        except Exception:
                            ra = None
                        if ra and attempt < retries:
                            logger.warning("Rate limited; waiting %s seconds before retrying", ra)
                            time.sleep(ra)
                            continue
                        # else, raise mapped error
                        raise _map_http_status(resp.status_code, content_text)

                    # On other client/server errors, map and raise or retry depending on code
                    mapped = _map_http_status(resp.status_code, content_text)
                    # for server errors (5xx) we may retry
                    if isinstance(mapped, ServerError) and attempt < retries:
                        backoff = _simple_exponential_backoff(attempt, base=self.backoff_base)
                        logger.debug("Server error (%s), retrying after %.2fs", resp.status_code, backoff)
                        time.sleep(backoff)
                        continue
                    if raise_for_status:
                        raise mapped
                    else:
                        # caller asked not to raise; return raw response object
                        return resp

                # Success (2xx)
                # parse json if any
                if resp.headers.get("Content-Type", "").lower().startswith("application/json"):
                    parsed = resp.json()
                    # Many CurseForge endpoints return {"data": ...}; return data by default
                    payload = parsed.get("data", parsed)
                else:
                    # Non-json return (e.g., file download) => return raw response
                    payload = resp

                # Save to cache if requested
                if cache_name:
                    try:
                        # Save lightweight payload (must be json-serializable)
                        self._save_cache(cache_name, payload)
                    except Exception:
                        logger.debug("Failed to save cache %s", cache_name, exc_info=True)

                return payload

            except requests.RequestException as re:
                last_exc = re
                # Network-layer error; retry with backoff
                if attempt < retries:
                    backoff = _simple_exponential_backoff(attempt, base=self.backoff_base)
                    logger.debug("Network error on attempt %d/%d: %s; sleeping %.2fs", attempt, retries, re, backoff)
                    time.sleep(backoff)
                    continue
                # exhausted retries
                raise CurseForgeError(f"Connection error after {attempt} attempts: {re}") from re
            except CurseForgeError:
                # Mapped Curl/HTTP error, re-raise
                raise
            except Exception as exc:
                # Unexpected error parsing response, etc.
                last_exc = exc
                if attempt < retries:
                    backoff = _simple_exponential_backoff(attempt, base=self.backoff_base)
                    logger.debug("Transient error parsing response: %s; retrying in %.2fs", exc, backoff)
                    time.sleep(backoff)
                    continue
                raise CurseForgeError(f"Unhandled error during request: {exc}") from exc

        # If we exit loop without returning, raise the last exception
        if isinstance(last_exc, CurseForgeError):
            raise last_exc
        raise CurseForgeError("Request failed after retries")

    def get(self, endpoint_or_path: str, *, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Convenience wrapper for GET requests (passes allow_cache=True by default)."""
        return self._request("GET", endpoint_or_path, params=params, allow_cache=True, **kwargs)

    def post(self, endpoint_or_path: str, *, json_body: Optional[Any] = None, **kwargs) -> Any:
        """Convenience wrapper for POST requests."""
        return self._request("POST", endpoint_or_path, json_body=json_body, **kwargs)

    def put(self, endpoint_or_path: str, *, json_body: Optional[Any] = None, **kwargs) -> Any:
        """Convenience wrapper for PUT requests."""
        return self._request("PUT", endpoint_or_path, json_body=json_body, **kwargs)

    def delete(self, endpoint_or_path: str, *, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Convenience wrapper for DELETE requests."""
        return self._request("DELETE", endpoint_or_path, params=params, **kwargs)

    def get_games(self) -> List[GAME]:
        """
        Retrieve the List of games supported by CurseForge.

        Returns
        -------
        List[types.GAME]
            A List of typed GAME dataclass instances representing each supported game.

        Notes
        -----
        - This method uses the `CURSEFORGEAPIURLS.GAMES` endpoint.
        - Results are cached if `cache_dir` was configured at construction time.
        - If the API returns a single dict, it is wrapped into a List for consistency.

        Example
        -------
        >>> games = cf.get_games()
        >>> for g in games:
        ...     print(g.id, g.name)
        """
        try:
            payload = self.get(CURSEFORGEAPIURLS.GAMES)
            
            results:List[GAME] = []
            if isinstance(payload, list):
                for item in payload:
                    try:
                        results.append(GAME.from_dict(item))
                    except Exception:
                        # best-effort: keep raw payload wrapped
                        results.append(GAME(item))
            elif isinstance(payload, dict):
                try:
                    results.append(GAME.from_dict(payload))
                except Exception:
                    results.append(GAME(payload))
            return results
        except Exception as exc:
            logger.debug("get_games error: %s", exc, exc_info=True)
            raise

    def get_game(self, game_id: int)->GAME:
        """
        Retrieve metadata for a specific game by numeric ID.

        Parameters
        ----------
        game_id : int
            Numeric game ID (e.g. 432 for Minecraft).

        Returns
        -------
        types.GAME
            Typed GAME instance containing metadata (id, name, slug, assets, status, ...).

        Example
        -------
        >>> mc = cf.get_game(432)
        >>> print(mc.name)
        """
        try:
            payload = self.get(CURSEFORGEAPIURLS.GAME, path_params={"gameId": game_id})
            if isinstance(payload, dict):
                return GAME.from_dict(payload)
            # if API returned something unexpected, try to coerce
            return GAME.from_dict(payload) if payload else GAME({})
        except Exception as exc:
            logger.debug("get_game(%s) error: %s", game_id, exc, exc_info=True)
            raise

    def get_game_versions(self, game_id: int) -> List[GAMEVERSION]:
        """
        Return the version groups for a given game (grouped by version-type).

        This function is robust to several possible shapes returned by the API:
        - a requests.Response object (will be .json()-ed)
        - a dict like {"data": [...] } or {"data": {...}}
        - a list of group dicts
        - a single group dict

        Each returned item is converted to a typed GAMEVERSION instance using
        GAMEVERSION.from_dict when possible. If nested "versions" entries are
        plain dicts they are converted using GAMEVERSION.VERSION.from_dict.

        Parameters
        ----------
        game_id : int
            Numeric game ID.

        Returns
        -------
        List[GAMEVERSION]
            A list of GAMEVERSION dataclass instances.
        """
        try:

            raw = self.cf.get_game_versions_v2(game_id)

            # Detect Response-like objects (requests.Response has .status_code and .json)
            if hasattr(raw, "status_code") and hasattr(raw, "json"):
                data = raw.json()
            else:
                data = raw.get("data", raw) if isinstance(raw, dict) else raw

            results: List[GAMEVERSION] = []

            groups = data if isinstance(data, list) else ([data] if data else [])
            
            for grp in groups:
                if not isinstance(grp, dict):
                    # If group is not a dict, skip or wrap into dict
                    continue

                # Try to use dataclass factory if present
                try:
                    results.append(GAMEVERSION.from_dict(grp))
                except Exception:
                    # Last-resort: construct GAMEVERSION directly if it accepts dict in constructor
                    try:
                        results.append(GAMEVERSION(grp))
                    except Exception:
                        # If even that fails, skip the group (or optionally raise)
                        logger.debug("Skipping malformed game version group: %r", grp)
                        continue

            return results

        except Exception as exc:
            logger.debug("get_game_versions(%s) error: %s", game_id, exc, exc_info=True)
            raise


    def get_minecraft_versions(self) -> List[GAMEVERSION]:
        """
        Convenience helper returning Minecraft versions.

        Returns
        -------
        List[types.GAMEVERSION]
            Same structure as `get_game_versions`, but defaulted to Minecraft's game id.

        Why this exists
        ----------------
        - Many users want Minecraft-specific helpers; this provides a convenient default.
        """
        return self.get_game_versions(432)

    def get_minecraft_modloaders(self) -> List[MODLOADERDATA_DT]:
        """
        Return the known Minecraft modloaders (Forge, Fabric, Quilt, ...).

        Returns
        -------
        List[dict]
            A List of modloader metadata dicts as returned by the API. The exact
            structure depends on the API version (we keep the raw dict so callers
            can inspect fields).

        Notes
        -----
        - Attempts to use CURSEFORGEAPIURLS.MINECRAFT_MODLOADERS constant.
        - If that constant is missing, it will try a few common fallbacks.
        """
        # resolve endpoint name safely
        endpoint_attr = None
        for candidate in ("MINECRAFT_MODLOADERS", "MINECRAFT_MODLOADER", "MINECRAFT_MODLOADERS_V2"):
            if hasattr(CURSEFORGEAPIURLS, candidate):
                endpoint_attr = getattr(CURSEFORGEAPIURLS, candidate)
                break
        if endpoint_attr is None:
            # fallback to common literal path (best-effort)
            endpoint_attr = "/v1/minecraft/modloader"

        try:
            payload = self.get(endpoint_attr)
            # payload typically a List of dicts; return as-is (raw dicts) for flexibility
            if isinstance(payload, list):
                return [MODLOADERDATA_DT.from_dict(d) for d in payload]
            if isinstance(payload, dict):
                # some APIs may return {"data": [...]}, but self.get already unwraps that.
                # try to extract common keys
                if "modloaders" in payload and isinstance(payload["modloaders"], list):
                    return (MODLOADERDATA_DT.from_dict(d) for d in payload["modloaders"])
                return [MODLOADERDATA_DT.from_dict(payload)]
            return []
        except Exception as exc:
            logger.debug("get_minecraft_modloaders error: %s", exc, exc_info=True)
            raise

    def get_categories(self, game_id: int) -> List[CATEGORY]:
        """
        Retrieve categories for a specific game.

        Parameters
        ----------
        game_id : int
            Game ID (e.g. 432 for Minecraft)

        Returns
        -------
        List[CATEGORY]
            List of CATEGORY dataclass instances.
        """
        try:
            payload = self.get(CURSEFORGEAPIURLS.CATEGORIES, params={"gameId": game_id})
            results: List[CATEGORY] = []
            if isinstance(payload, list):
                for item in payload:
                    results.append(CATEGORY.from_dict(item))
            elif isinstance(payload, dict):
                # sometimes API returns {"data": [...]}, get() unwraps; but tolerate single dict->list
                results.append(CATEGORY.from_dict(payload))
            return results
        except Exception as exc:
            logger.debug("get_categories(%s) error: %s", game_id, exc, exc_info=True)
            raise

    def get_class_categories(self, class_id: int, game_id: Optional[int] = None) -> List[CATEGORY]:
        """
        Return categories filtered by classId (e.g. modpacks/resource packs).

        Parameters
        ----------
        class_id : int
            Class identifier to filter categories.
        game_id : Optional[int]
            If provided, restrict to a specific game.

        Returns
        -------
        List[CATEGORY]
        """
        try:
            params = {"classId": class_id}
            if game_id:
                params["gameId"] = game_id
            payload = self.get(CURSEFORGEAPIURLS.CATEGORIES, params=params)
            results: List[CATEGORY] = []
            if isinstance(payload, list):
                for item in payload:
                    results.append(CATEGORY.from_dict(item))
            elif isinstance(payload, dict):
                results.append(CATEGORY.from_dict(payload))
            return results
        except Exception as exc:
            logger.debug("get_class_categories(%s) error: %s", class_id, exc, exc_info=True)
            raise

    def list_tags(self) -> List[Dict[str, Any]]:
        """
        List tags available on CurseForge.

        Notes
        -----
        - The official 'tags' endpoint may not exist on some API versions.
        - If CURSEFORGEAPIURLS.TAGS is not present or returns 404, we fall back to categories.
        """
        # try configured constant first
        try:
            if hasattr(CURSEFORGEAPIURLS, "TAGS"):
                payload = self.get(CURSEFORGEAPIURLS.TAGS)
                if isinstance(payload, list):
                    return payload
                if isinstance(payload, dict) and "tags" in payload:
                    return payload["tags"]
            # fallback -> use categories (many tag-like uses are in categories)
            cats = self.get(CURSEFORGEAPIURLS.CATEGORIES)
            if isinstance(cats, list):
                return cats
            if isinstance(cats, dict):
                return [cats]
            return []
        except NotFoundError:
            # fallback to categories gracefully
            try:
                cats = self.get(CURSEFORGEAPIURLS.CATEGORIES)
                return cats if isinstance(cats, list) else [cats]
            except Exception as exc:
                logger.debug("list_tags fallback error: %s", exc, exc_info=True)
                raise CurseForgeError("Tags endpoint not available and categories fallback failed.") from exc
        except Exception as exc:
            logger.debug("list_tags error: %s", exc, exc_info=True)
            raise

    def list_game_tag_mappings(self, game_id: int) -> Dict[str, Any]:
        """
        Attempt to fetch tag mappings for a specific game.

        Many APIs don't provide a direct 'tag mappings' endpoint; we'll attempt sensible fallbacks:
          - categories by game
          - version types by game (if available)

        Returns a raw dict for flexibility.
        """
        try:
            categories = self.get(CURSEFORGEAPIURLS.CATEGORIES, params={"gameId": game_id})
            result: Dict[str, Any] = {"categories": categories}
            # try version types (best-effort)
            if hasattr(CURSEFORGEAPIURLS, "GAME_VERSION_TYPES"):
                try:
                    vt = self.get(CURSEFORGEAPIURLS.GAME_VERSION_TYPES, path_params={"gameId": game_id})
                    result["versionTypes"] = vt
                except Exception:
                    pass
            return result
        except Exception as exc:
            logger.debug("list_game_tag_mappings(%s) error: %s", game_id, exc, exc_info=True)
            raise

    def search_mods(
        self,
        game_id: int,
        search_filter: Optional[str] = None,
        category_id: Optional[int] = None,
        slug: Optional[str] = None,
        page_size: int = 20,
        index: Optional[int]=0,
        **extra_filters,
    ) -> List[MODINFO]:
        """
        Search mods/projects using CurseForge search endpoint.

        Parameters
        ----------
        game_id : int
        search_filter : Optional[str]
            Text to search.
        category_id : Optional[int]
        slug : Optional[str]
        page_size : int
        extra_filters : dict
            Pass-through for any additional supported query parameters.

        Returns
        -------
        List[MODINFO]
        """
        params: Dict[str, Any] = {"gameId": game_id, "pageSize": page_size}
        if search_filter:params["searchFilter"] = search_filter
        if category_id:params["categoryId"] = category_id
        if slug:params["slug"] = slug
        if index:params['index'] = index
        params.update(extra_filters or {})

        try:
            payload = self.get(CURSEFORGEAPIURLS.SEARCH_MODS, params=params)
            results: List[MODINFO] = []
            if isinstance(payload, list):
                for item in payload:
                    results.append(MODINFO.from_dict(item))
            elif isinstance(payload, dict):
                # sometimes payload may be {"items": [...] } or similar; try to detect list-like content
                if "data" in payload and isinstance(payload["data"], list):
                    for item in payload["data"]:
                        results.append(MODINFO.from_dict(item))
                elif "results" in payload and isinstance(payload["results"], list):
                    for item in payload["results"]:
                        results.append(MODINFO.from_dict(item))
                else:
                    # treat as single object
                    results.append(MODINFO.from_dict(payload))
            return results
        except Exception as exc:
            logger.debug("search_mods error: %s", exc, exc_info=True)
            raise

    def get_mod(self, mod_id: int) -> MODINFO:
        """
        Get detailed metadata for a project/mod.

        Parameters
        ----------
        mod_id : int

        Returns
        -------
        MODINFO
        """
        try:
            payload = self.get(CURSEFORGEAPIURLS.GET_MOD, path_params={"mod_id": mod_id})
            if isinstance(payload, dict):
                return MODINFO.from_dict(payload)
            # fallback
            return MODINFO.from_dict(payload if payload else {})
        except Exception as exc:
            logger.debug("get_mod(%s) error: %s", mod_id, exc, exc_info=True)
            raise

    def get_mods_bulk(self, mod_ids: List[int]) -> List[MODINFO]:
        """
        Get multiple mods in a single request.

        Note: API expects POST { "modIds": [ ... ] } to /v1/mods in some variants.

        Parameters
        ----------
        mod_ids : List[int]

        Returns
        -------
        List[MODINFO]
        """
        try:
            body = {"modIds": list(mod_ids)}
            payload = self.post(CURSEFORGEAPIURLS.GET_MODS, json_body=body)
            results: List[MODINFO] = []
            if isinstance(payload, list):
                for item in payload:
                    results.append(MODINFO.from_dict(item))
            elif isinstance(payload, dict):
                # some APIs return {"data": [...]} or similar
                if isinstance(payload.get("data"), list):
                    for item in payload.get("data"):
                        results.append(MODINFO.from_dict(item))
                else:
                    results.append(MODINFO.from_dict(payload))
            return results
        except Exception as exc:
            logger.debug("get_mods_bulk error: %s", exc, exc_info=True)
            raise

    def get_featured_mods(self, game_id: int, excluded: Optional[List[int]] = None, gameVersionTypeId: Optional[int] = None) -> List[MODINFO]:
        """
        Get featured/curated mods for a game.

        Parameters
        ----------
        game_id : int
        excluded : Optional[List[int]]
        gameVersionTypeId : Optional[int]

        Returns
        -------
        List[MODINFO]
        """
        body = {"gameId": game_id}
        if excluded:
            body["excludedModIds"] = excluded
        if gameVersionTypeId is not None:
            body["gameVersionTypeId"] = gameVersionTypeId
        try:
            payload = self.post(CURSEFORGEAPIURLS.FEATURED_MODS, json_body=body)
            results: List[MODINFO] = []
            if isinstance(payload, list):
                for item in payload:
                    results.append(MODINFO.from_dict(item))
            elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
                for item in payload.get("data"):
                    results.append(MODINFO.from_dict(item))
            return results
        except Exception as exc:
            logger.debug("get_featured_mods error: %s", exc, exc_info=True)
            raise

    def get_mod_description(self, mod_id: int) -> str:
        """
        Return the HTML description (overview) for a mod as a string.

        Parameters
        ----------
        mod_id : int

        Returns
        -------
        str : HTML content
        """
        try:
            resp = self._request("GET", CURSEFORGEAPIURLS.GET_MOD_DESCRIPTION, path_params={"mod_id": mod_id}, allow_cache=True)
            # If the endpoint returned a raw Response (non-JSON), _request returns that Response object.
            if hasattr(resp, "text"):
                return resp.text
            # If it returned JSON, it may include the HTML in a field
            if isinstance(resp, dict):
                # common keys: 'description', 'data' etc.
                for k in ("description", "overview", "data", "html"):
                    if k in resp:
                        return resp[k] if isinstance(resp[k], str) else json.dumps(resp[k])
                return json.dumps(resp)
            return str(resp)
        except Exception as exc:
            logger.debug("get_mod_description(%s) error: %s", mod_id, exc, exc_info=True)
            raise

    def get_mod_files(self, mod_id: int, game_version: Optional[str] = None, pageSize: int = 50, **extra_filters) -> List[MODFILE]:
        """
        List all files for a given mod, optionally filtered by Minecraft version.

        Parameters
        ----------
        mod_id : int
            The mod ID to fetch files for.
        game_version : Optional[str]
            Optional Minecraft version filter (e.g., "1.20.1").
        pageSize : int
            Number of files to retrieve (default 50).
        extra_filters : dict
            Pass-through for any additional supported query parameters.

        Returns
        -------
        List[MODFILE]
            A list of MODFILE objects representing available files.
        """
        try:
            params = {"pageSize": pageSize, "index": 0}
            if game_version:
                params["gameVersion"] = game_version
            params.update(extra_filters or {})

            payload = self.get(
                CURSEFORGEAPIURLS.GET_MOD_FILES,
                path_params={"mod_id": mod_id},
                params=params
            )

            results: List[MODFILE] = []
            if isinstance(payload, list):
                for item in payload:
                    results.append(MODFILE.from_dict(item))
            elif isinstance(payload, dict):
                if isinstance(payload.get("data"), list):
                    for item in payload.get("data"):
                        results.append(MODFILE.from_dict(item))
                else:
                    results.append(MODFILE.from_dict(payload))

            return results

        except Exception as exc:
            logger.debug("get_mod_files(%s, %s) error: %s", mod_id, game_version, exc, exc_info=True)
            raise


    def get_mod_file(self, mod_id: int, file_id: int) -> MODFILE:
        """
        Get metadata for a specific file of a mod.

        Parameters
        ----------
        mod_id : int
        file_id : int

        Returns
        -------
        MODFILE
        """
        try:
            payload = self.get(CURSEFORGEAPIURLS.GET_MOD_FILE, path_params={"mod_id": mod_id, "file_id": file_id})
            if isinstance(payload, dict):
                return MODFILE.from_dict(payload)
            return MODFILE.from_dict(payload or {})
        except Exception as exc:
            logger.debug("get_mod_file(%s,%s) error: %s", mod_id, file_id, exc, exc_info=True)
            raise

    def get_mod_file_changelog(self, mod_id: int, file_id: int) -> str:
        """
        Return changelog HTML/text for a file.
        """
        try:
            resp = self._request("GET", CURSEFORGEAPIURLS.GET_MOD_FILE_CHANGELOG, path_params={"mod_id": mod_id, "file_id": file_id})
            if hasattr(resp, "text"):
                return resp.text
            if isinstance(resp, dict):
                # often the API returns {"data": "<html>..."}
                return resp.get("data") or json.dumps(resp)
            return str(resp)
        except Exception as exc:
            logger.debug("get_mod_file_changelog(%s,%s) error: %s", mod_id, file_id, exc, exc_info=True)
            raise

    def get_file_download_url(self, mod_id: int, file_id: int) -> Optional[str]:
        """
        Get the CDN download URL for a mod file.

        Returns the direct URL string or None if not resolvable.
        """
        try:
            payload = self.get(CURSEFORGEAPIURLS.GET_FILE_DOWNLOAD_URL, path_params={"mod_id": mod_id, "file_id": file_id})
            # endpoint typically returns a plain URL in `data` (self.get unwrapped it).
            if isinstance(payload, str):
                return payload
            if isinstance(payload, dict):
                # look for common keys
                for k in ("data", "downloadUrl", "url"):
                    if k in payload:
                        val = payload[k]
                        if isinstance(val, str):
                            return val
                        if isinstance(val, dict) and "url" in val:
                            return val["url"]
                # if payload itself contains the URL as only key
                return None
            return None
        except Exception as exc:
            logger.debug("get_file_download_url(%s,%s) error: %s", mod_id, file_id, exc, exc_info=True)
            raise

    def download_file(self, mod_id: int, file_id: int, dest_folder: Path, *, filename: Optional[str] = None, expected_hashes: Optional[Dict[str, str]] = None, progress_cb: Optional[Callable] = None) -> Path:
        """
        Download a mod file into dest_folder. Uses download manager if available, otherwise falls back to streaming.

        Returns Path to the downloaded file on success; raises CurseForgeError on failure.
        """
        # resolve url
        try:
            url = self.get_file_download_url(mod_id, file_id)
            if not url:
                raise CurseForgeError("Download URL could not be resolved.")
            # prefer using the project's DownloadManager if present
            try:
                from .download import DownloadManager
                dm = DownloadManager(session=self.session, user_agent=self.session.headers.get("User-Agent", DEFAULT_USER_AGENT))
                res = dm.download_url_to_folder(url, Path(dest_folder), filename=filename, expected_hashes=expected_hashes, progress_cb=progress_cb)
                if not res.success:
                    raise CurseForgeError(f"Download failed: {res.error}")
                return Path(res.path)
            except Exception:
                # fallback simple streaming
                dest_folder = Path(dest_folder)
                dest_folder.mkdir(parents=True, exist_ok=True)
                if not filename:
                    filename = os.path.basename(url.split("?")[0]) or f"{mod_id}-{file_id}"
                dest_path = dest_folder / filename
                # streaming
                with self.session.get(url, stream=True, timeout=self.timeout) as r:
                    r.raise_for_status()
                    tmp = dest_path.with_suffix(dest_path.suffix + ".part")
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    # atomic replace
                    os.replace(str(tmp), str(dest_path))
                # verify hash if provided
                if expected_hashes:
                    ok, computed = self._verify_hashes_local(dest_path, expected_hashes)
                    if not ok:
                        try:
                            dest_path.unlink()
                        except Exception:
                            pass
                        raise CurseForgeError("Checksum mismatch after download.")
                return dest_path
        except Exception as exc:
            logger.debug("download_file(%s,%s) error: %s", mod_id, file_id, exc, exc_info=True)
            raise

    def match_fingerprints(self, fingerprints: List[int]) -> Fingerprint:
        """
        Match a list of fingerprints against CurseForge index.

        Returns
        -------
        Fingerprint dataclass
        """
        try:
            body = {"fingerprints": fingerprints}
            payload = self.post(CURSEFORGEAPIURLS.FINGERPRINTS, json_body=body)
            if isinstance(payload, dict):
                return Fingerprint.from_dict(payload)
            # fallback if API returned list or other shape
            return Fingerprint.from_dict({"exactMatches": payload}) if payload else Fingerprint.from_dict({})
        except Exception as exc:
            logger.debug("match_fingerprints error: %s", exc, exc_info=True)
            raise

    def match_fingerprints_by_game(self, game_id: int, fingerprints: List[int]) -> Fingerprint:
        """
        Match fingerprints restricted to a specific game ID.
        """
        try:
            payload = self.post(CURSEFORGEAPIURLS.FINGERPRINTS_BY_GAME.format(gameId=game_id), json_body={"fingerprints": fingerprints})
            if isinstance(payload, dict):
                return Fingerprint.from_dict(payload)
            return Fingerprint.from_dict({})
        except Exception as exc:
            logger.debug("match_fingerprints_by_game(%s) error: %s", game_id, exc, exc_info=True)
            raise

    def match_fingerprints_fuzzy(self, fingerprints: List[int]) -> Fingerprint:
        """
        Perform fuzzy (approximate) fingerprint matching.
        """
        try:
            payload = self.post(CURSEFORGEAPIURLS.FINGERPRINTS_FUZZY, json_body={"fingerprints": fingerprints})
            if isinstance(payload, dict):
                return Fingerprint.from_dict(payload)
            return Fingerprint.from_dict({})
        except Exception as exc:
            logger.debug("match_fingerprints_fuzzy error: %s", exc, exc_info=True)
            raise

    def match_fingerprints_fuzzy_by_game(self, game_id: int, fingerprints: List[int]) -> Fingerprint:
        """
        Fuzzy fingerprint match limited to a specific game.
        """
        try:
            path = CURSEFORGEAPIURLS.FINGERPRINTS_FUZZY_BY_GAME.format(gameId=game_id) if hasattr(CURSEFORGEAPIURLS, "FINGERPRINTS_FUZZY_BY_GAME") else f"/v1/fingerprints/fuzzy/{game_id}"
            payload = self.post(path, json_body={"fingerprints": fingerprints})
            if isinstance(payload, dict):
                return Fingerprint.from_dict(payload)
            return Fingerprint.from_dict({})
        except Exception as exc:
            logger.debug("match_fingerprints_fuzzy_by_game error: %s", exc, exc_info=True)
            raise

    def get_modpack_manifest(self, source: Union[str, Path, Dict[str, Any]]) -> MODPACKMANIFEST:
        """
        Read/parse a modpack manifest from:
          - a dict (already parsed)
          - a path to a manifest.json
          - a zip file containing manifest.json (will extract in tempdir)

        Returns MODPACKMANIFEST dataclass.
        """
        try:
            # if already dict
            if isinstance(source, dict):
                return MODPACKMANIFEST.from_dict(source)
            p = Path(source)
            if p.is_file() and p.suffix.lower() == ".json":
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return MODPACKMANIFEST.from_dict(data)
            if p.is_file() and p.suffix.lower() == ".zip":
                # extract manifest.json from zip (best-effort)
                import zipfile, tempfile
                tmpdir = Path(tempfile.mkdtemp(prefix="cf-manifest-"))
                try:
                    with zipfile.ZipFile(p, "r") as z:
                        cands = [n for n in z.namelist() if n.endswith("manifest.json")]
                        if not cands:
                            raise ManifestError("No manifest.json found inside zip")
                        candidate = min(cands, key=lambda n: (n.count("/"), n))
                        z.extract(candidate, path=tmpdir)
                        manifest_path = tmpdir / candidate
                        with open(manifest_path, "r", encoding="utf-8") as mf:
                            data = json.load(mf)
                        # attempt to set _overrides_extracted_path for caller if overrides exist
                        return MODPACKMANIFEST.from_dict(data)
                finally:
                    # keep temp dir (user/installer may want overrides); we do not auto-delete here to avoid losing overrides
                    pass
            # if neither, try to load as json string path
            raise ManifestError("Unsupported source for modpack manifest")
        except Exception as exc:
            logger.debug("get_modpack_manifest error: %s", exc, exc_info=True)
            raise

    def install_modpack(self, manifest_source: Union[str, Path, Dict[str, Any]], instance_root: Union[str, Path], **kwargs) -> Any:
        """
        High-level convenience to install a modpack using the internal ModPackInstaller if available.

        Parameters
        ----------
        manifest_source : path/dict/zip
        instance_root : target path
        kwargs forwarded to installer.install_from_manifest

        Returns
        -------
        installer.ModPackInstallReport or raises if installer not present.
        """
        try:
            from .installer import ModPackInstaller
        except Exception:
            raise CurseForgeError("ModPackInstaller module not available in this environment.")
        try:
            installer = ModPackInstaller(self, **{"concurrency": kwargs.pop("concurrency", 4)})
            report = installer.install_from_manifest(manifest_source, Path(instance_root), **kwargs)
            return report
        except Exception as exc:
            logger.debug("install_modpack error: %s", exc, exc_info=True)
            raise

    def slugify(self, text: str) -> str:
        """
        Simple filesystem-safe slugifier for names.
        """
        if not text:
            return "item"
        s = str(text).strip().lower()
        # convert whitespace to hyphens, keep a-z0-9._-
        import re
        s = re.sub(r"\s+", "-", s)
        s = re.sub(r"[^a-z0-9\-\._]", "", s)
        s = re.sub(r"-{2,}", "-", s)
        return s or "item"

    def sanitize_html(self, html_content: str, keep_basic_tags: bool = False) -> str:
        """
        Lightweight HTML sanitizer / text extractor.

        Parameters
        ----------
        html_content : str
        keep_basic_tags : bool
            If True, allow simple tags (<b>, <i>, <code>, <pre>), otherwise strip to plaintext.

        Returns
        -------
        str : sanitized HTML (or plaintext)
        """
        if not html_content:
            return ""
        # quick path: if user wants basic tags, remove scripts/styles only
        import re
        if keep_basic_tags:
            # remove <script> and <style> contents
            html_content = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html_content)
            return html_content.strip()
        # strip all tags
        text = re.sub(r"(?s)<.*?>", "", html_content)
        # unescape HTML entities
        try:
            from html import unescape
            text = unescape(text)
        except Exception:
            pass
        return text.strip()

    def format_file_size(self, size_bytes: Optional[int]) -> str:
        """
        Convert a byte count into human readable string (B, KB, MB, GB).
        """
        if size_bytes is None:
            return "unknown"
        size = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024.0 or unit == "TB":
                return f"{size:3.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}B"

    def _verify_hashes_local(self, path: Union[str, Path], expected: Dict[str, str]) -> Tuple[bool, Dict[str, str]]:
        """
        Internal helper to compute common hashes and compare to expected dict.
        Returns (match, computed_hashes)
        """
        p = Path(path)
        if not p.exists():
            return False, {}
        import hashlib
        computed: Dict[str, str] = {}
        try:
            with open(p, "rb") as f:
                data = f.read()
            for algo in ("sha1", "sha256", "md5"):
                try:
                    h = hashlib.new(algo)
                    h.update(data)
                    computed[algo] = h.hexdigest()
                except Exception:
                    computed[algo] = ""
            # compare
            norm_expected = {k.lower(): v.lower() for k, v in (expected or {}).items()}
            for a, val in norm_expected.items():
                if a in computed and computed[a] and computed[a].lower() == val:
                    return True, computed
            return False, computed
        except Exception:
            return False, {}

    def verify_file_hash(self, path: Union[str, Path], expected_hash: str, algo: str = "sha1") -> bool:
        """
        Public helper: verify a single expected_hash (string) for a file using algo.
        """
        ok, comp = self._verify_hashes_local(path, {algo: expected_hash})
        return bool(ok)

    def retry_on_fail(self, retries: int = 3, base_backoff: float = 0.5):
        """
        Decorator factory that retries a function on exception with exponential backoff.

        Usage:
            @cf.retry_on_fail(retries=3)
            def fn(...):
                ...
        """
        def _decorator(fn):
            def _wrapped(*args, **kwargs):
                last = None
                for attempt in range(1, retries + 1):
                    try:
                        return fn(*args, **kwargs)
                    except Exception as exc:
                        last = exc
                        wait = _simple_exponential_backoff(attempt, base=base_backoff)
                        logger.debug("Retrying %s/%s after error: %s", attempt, retries, exc, exc_info=True)
                        time.sleep(wait)
                        continue
                raise last
            _wrapped.__name__ = fn.__name__
            return _wrapped
        return _decorator

    def ping(self) -> bool:
        """
        Simple connectivity check: attempts to fetch games list. Returns True on success.
        """
        try:
            _ = self.get(CURSEFORGEAPIURLS.GAMES)
            return True
        except Exception:
            return False

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Attempts to return rate-limit-like headers by doing a HEAD request to a safe endpoint.

        Returned dict keys may include common fields if present: X-RateLimit-Limit, X-RateLimit-Remaining, Retry-After.
        """
        try:
            url = self._build_url(CURSEFORGEAPIURLS.GAMES)
            resp = self.session.head(url, timeout=self.timeout)
            headers = resp.headers
            info = {
                "limit": headers.get("X-RateLimit-Limit"),
                "remaining": headers.get("X-RateLimit-Remaining"),
                "retry-after": headers.get("Retry-After") or headers.get("X-RateLimit-Reset"),
                "status_code": resp.status_code,
            }
            return info
        except Exception as exc:
            logger.debug("get_rate_limit_status error: %s", exc, exc_info=True)
            return {"error": str(exc)}

    def debug_request(self, method: str, endpoint_or_path: str, **kwargs) -> Any:
        """
        Developer helper: perform a raw request and return the raw response object (no unwrapping).
        """
        return self._request(method, endpoint_or_path, raise_for_status=False, **kwargs)

    def dump_raw_response(self, endpoint_or_path: str, out_file: Union[str, Path], *, params: Optional[Dict[str, Any]] = None):
        """
        Fetch endpoint and dump raw JSON payload to file path.
        """
        try:
            payload = self.get(endpoint_or_path, params=params)
            out = Path(out_file)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return out
        except Exception as exc:
            logger.debug("dump_raw_response error: %s", exc, exc_info=True)
            raise
    # context manager helpers and small utilities
    def set_user_agent(self, user_agent: str) -> None:
        """
        Set the User-Agent header for subsequent requests.

        Parameters
        ----------
        user_agent : str
            User agent string to present in requests.
        """
        if not user_agent or not isinstance(user_agent, str):
            raise ValueError("user_agent must be a non-empty string")
        self.session.headers["User-Agent"] = user_agent

    def get_session(self) -> requests.Session:
        """
        Expose the underlying requests.Session for advanced users who need custom behavior.
        """
        return self.session

    def close(self) -> None:
        """
        Close the underlying requests session and free resources.
        """
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self) -> "CurseForge":
        """
        Allow use as a context manager.
        """
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """
        Automatically close the session on context exit.
        """
        self.close()

    def __repr__(self) -> str:
        return f"<CurseForge base_url={self.base_url!r} api_key_set={bool(self.api_key)}>"

# module-level helper: convenience factory
def create_client(api_key: Optional[str] = None, *, cache_dir: Optional[Union[str, Path]] = None, **kwargs) -> CurseForge:
    """
    Convenience factory to create a configured CurseForge client.

    Parameters
    ----------
    api_key : Optional[str]
        API key to set on the client.
    cache_dir : Optional[str|Path]
        Optional cache directory for GET responses.
    kwargs : additional args forwarded to CurseForge constructor.

    Returns
    -------
    CurseForge
    """
    return CurseForge(api_key=api_key, cache_dir=cache_dir, **kwargs)
