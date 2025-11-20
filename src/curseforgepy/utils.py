from __future__ import annotations

import os,time,json,tempfile,logging,threading,functools,requests,random,hashlib,re,html
from packaging import version
from tqdm import tqdm
from typing import *
from pathlib import Path
from email.utils import parsedate_to_datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .exceptions import (
    CurseForgeError, InvalidResponseError, map_http_status as errors_map_http_status
)

__all__ = [
    "logger_setup",
    "session_factory",
    "atomic_write",
    "ensure_dir",
    "retry_on_exception",
]

DEFAULT_USER_AGENT = "curseforgepy/0.1 (+https://github.com/Cavanshirpro/)"

def logger_setup(name: str,
                 level: int = logging.INFO,
                 *,
                 log_to_file: Optional[str] = None,
                 file_level: Optional[int] = None,
                 fmt: str = "%(asctime)s %(name)s %(levelname)s: %(message)s",
                 datefmt: str = "%Y-%m-%d %H:%M:%S") -> logging.Logger:
    """
    Create and return a configured logger for the library.

    Behavior:
        - Creates a logger with the given `name`.
        - Adds a console (StreamHandler) with the given `level`.
        - If `log_to_file` is provided, also adds a rotating file handler (via standard FileHandler).
          The file handler level defaults to `level` unless `file_level` is set.
        - Multiple calls with the same `name` will not duplicate handlers (idempotent).

    Parameters
    ----------
    name : str
        Logger name (usually package name).
    level : int
        Logging level for console (e.g., logging.INFO).
    log_to_file : Optional[str]
        If provided, path of file to log to (created if missing).
    file_level : Optional[int]
        Logging level for file handler (defaults to `level` if None).
    fmt : str
        Log message format string.
    datefmt : str
        Date format used by formatter.

    Returns
    -------
    logging.Logger
        Configured logger instance.

    Example
    -------
    >>> logger = logger_setup("curseforge", level=logging.DEBUG, log_to_file="curseforge.log")
    >>> logger.info("ready")
    """
    logger = logging.getLogger(name)
    logger.setLevel(min(level, logging.DEBUG))  # library-level: don't make it more verbose than DEBUG internally

    # Avoid adding handlers repeatedly
    if not getattr(logger, "_curseforge_setup_done", False):
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # Optional file handler
        if log_to_file:
            fh = logging.FileHandler(log_to_file, encoding="utf-8")
            fh.setLevel(file_level if file_level is not None else level)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

        # Mark that we've configured this logger
        logger._curseforge_setup_done = True

    return logger

def session_factory(api_key: Optional[str] = None,
                    user_agent: Optional[str] = None,
                    *,
                    timeout: float = 10.0,
                    pool_maxsize: int = 10,
                    pool_connections: int = 10,
                    max_retries: int = 0,
                    backoff_factor: float = 0.0,
                    status_forcelist: Optional[Iterable[int]] = (429, 500, 502, 503, 504),
                    raise_on_status: bool = False,
                    default_headers: Optional[Dict[str, str]] = None) -> requests.Session:
    """
    Create a configured requests.Session for the library.

    Features:
      - Sets sensible default headers (Accept, User-Agent, x-api-key if provided)
      - Installs an HTTPAdapter with connection pooling and optional urllib3 Retry
      - Returns a Session object ready for use in CURSEFORGE calls

    Parameters
    ----------
    api_key : Optional[str]
        API key to set in `x-api-key` header (if provided).
    user_agent : Optional[str]
        User-Agent string to set. If None, DEFAULT_USER_AGENT is used.
    timeout : float
        Default per-request timeout (consumers still pass timeout to requests; this value is provided as guideline).
    pool_maxsize : int
        Max connection pool size for the adapter.
    pool_connections : int
        Pool connections count for the adapter.
    max_retries : int
        Number of retries for idempotent requests handled by urllib3.Retry. If 0, retries disabled.
    backoff_factor : float
        Backoff factor for urllib3.Retry (exponential backoff).
    status_forcelist : Iterable[int]
        HTTP statuses that trigger a retry (when max_retries > 0).
    raise_on_status : bool
        If True, urllib3 Retry will raise on status; typically False to keep control in application.
    default_headers : Optional[Dict[str,str]]
        Additional headers to set on session.headers (merged with defaults).

    Returns
    -------
    requests.Session

    Example
    -------
    >>> s = session_factory(api_key="XXX", user_agent="MyAgent/1.0", max_retries=3)
    >>> r = s.get("https://api.curseforge.com/v1/games", timeout=10)
    """
    session = requests.Session()

    # Base headers
    headers = {
        "Accept": "application/json",
        "User-Agent": user_agent or DEFAULT_USER_AGENT
    }
    if api_key:
        headers["x-api-key"] = api_key
    if default_headers:
        headers.update(default_headers)
    session.headers.update(headers)

    # Configure urllib3 Retry if requested
    if max_retries and max_retries > 0:
        retry = Retry(
            total=max_retries,
            read=max_retries,
            connect=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=tuple(status_forcelist or ()),
            raise_on_status=raise_on_status,
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS", "PUT", "DELETE"])  # idempotent methods by default
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_connections, pool_maxsize=pool_maxsize)
    else:
        adapter = HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize)

    # Mount adapter for both http and https
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Attach small convenience properties for callers (informational)
    session._cf_default_timeout = float(timeout)  # not used by requests automatically; callers can use this
    session._cf_pool_maxsize = int(pool_maxsize)

    return session

def atomic_write(path: str, data: Union[bytes, str], *, mode: str = "wb", tmp_dir: Optional[str] = None) -> None:
    """
    Atomically write `data` to `path`.

    Implementation:
      1. Write to a temporary file in the same directory (or tmp_dir if provided).
      2. Flush and fsync to ensure data on disk.
      3. Replace (os.replace) the destination with the temp file atomically.

    Parameters
    ----------
    path : str
        Destination file path.
    data : bytes | str
        Content to write. If str, it will be encoded as UTF-8 when mode includes 'b'.
    mode : str
        File mode for writing, 'wb' or 'w' recommended. Mode must be consistent with data type.
    tmp_dir : Optional[str]
        Temporary directory to use for the temp file. If None, the destination directory is used.

    Raises
    ------
    ValueError: if mode is incompatible with data type.
    OSError / IOError: on filesystem errors (propagated).
    """
    # Validate mode vs data type
    binary_mode = "b" in mode
    if binary_mode and isinstance(data, str):
        # user provided text but mode wants bytes => encode
        data_bytes = data.encode("utf-8")
    elif not binary_mode and isinstance(data, bytes):
        raise ValueError("mode expects text (no 'b') but `data` is bytes; use binary mode 'wb'")
    else:
        data_bytes = data if isinstance(data, (bytes, bytearray)) else str(data)

    dest_dir = tmp_dir or os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(dest_dir, exist_ok=True)

    # Create temp file in same directory to ensure os.replace is atomic on same FS
    fd = None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode=mode, dir=dest_dir, delete=False) as tmp:
            tmp_path = tmp.name
            # Write
            if binary_mode:
                tmp.write(data_bytes)  # bytes
            else:
                # text mode
                if isinstance(data_bytes, (bytes, bytearray)):
                    tmp.write(data_bytes.decode("utf-8"))
                else:
                    tmp.write(str(data_bytes))
            tmp.flush()
            os.fsync(tmp.fileno())
        # Atomic replace
        os.replace(tmp_path, path)
    except Exception:
        # Cleanup temporary file if still exists
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise

def ensure_dir(path: str, exist_ok: bool = True, mode: int = 0o755) -> None:
    """
    Ensure the directory at `path` exists.

    Parameters
    ----------
    path : str
        Directory path to ensure.
    exist_ok : bool
        If True, no error raised when directory already exists.
    mode : int
        Permission bits for created directories (umask is applied afterwards).

    Raises
    ------
    OSError: If creation fails (permission errors, etc).
    """
    if not path:
        raise ValueError("path must be a non-empty string")
    os.makedirs(path, mode=mode, exist_ok=exist_ok)

def retry_on_exception(max_attempts: int = 3,
                       backoff_factor: float = 0.6,
                       jitter: bool = True,
                       retry_on: Optional[Callable[[BaseException], bool]] = None,
                       exceptions: Tuple[Type[BaseException], ...] = (Exception,),
                       on_retry: Optional[Callable[[int, BaseException, float], None]] = None):
    """
    Decorator to retry a function on exceptions using exponential backoff with optional jitter.

    Behavior:
      - Retries up to `max_attempts` times (initial attempt + retries = max_attempts).
      - Wait time = backoff_factor * (2 ** (attempt - 1))  (attempt starts at 1 for first retry)
      - If `jitter` is True a random jitter between 0 and wait*0.1 is added.
      - If `retry_on` predicate provided, it is used to decide whether to retry for a caught exception.
      - `exceptions` tuple filters which exception types are considered for retry. Others are re-raised immediately.
      - `on_retry` callback (optional) called before each wait with signature (attempt_number, exception, wait_seconds).

    Parameters
    ----------
    max_attempts : int
        Total attempts (including the initial attempt). Must be >= 1.
    backoff_factor : float
        Backoff base multiplier in seconds.
    jitter : bool
        Add small jitter to avoid thundering herd.
    retry_on : Optional[Callable[[BaseException], bool]]
        Additional predicate that receives the caught exception and returns True to retry.
    exceptions : Tuple[type,...]
        Tuple of exception types to catch and consider for retry.
    on_retry : Optional[Callable[[int, BaseException, float], None]]
        Called before each sleep when a retry will happen.

    Returns
    -------
    Callable
        Decorated function wrapper.

    Example
    -------
    >>> @retry_on_exception(max_attempts=5, backoff_factor=0.5, exceptions=(NetworkError,))
    ... def fetch():
    ...     ...
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            last_exc: Optional[BaseException] = None
            while True:
                attempt += 1
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    # evaluate predicate
                    should_retry = True
                    if retry_on is not None:
                        try:
                            should_retry = bool(retry_on(exc))
                        except Exception:
                            # if predicate fails, be conservative (do not retry)
                            should_retry = False

                    if not should_retry:
                        raise

                    if attempt >= max_attempts:
                        # exhausted attempts; re-raise last exception
                        raise

                    # compute wait
                    wait = backoff_factor * (2 ** (attempt - 1))
                    if jitter:
                        # small random jitter
                        import random
                        wait += random.random() * (wait * 0.1)

                    # callback for logging / telemetry
                    try:
                        if on_retry:
                            on_retry(attempt, exc, wait)
                    except Exception:
                        # never allow on_retry to break retry loop
                        pass

                    time.sleep(wait)
                except BaseException:
                    # non-caught exception types should bubble up immediately
                    raise
        return wrapper
    return decorator

def exponential_backoff(attempt: int, base: float = 0.5, factor: float = 2.0, max_interval: float = 30.0) -> float:
    """
    Calculate an exponential backoff delay time in seconds.

    Parameters
    ----------
    attempt : int
        Current retry attempt number (1 for first retry).
    base : float
        Base delay in seconds for the first retry attempt.
    factor : float
        Multiplicative factor applied each attempt (exponential growth).
    max_interval : float
        Maximum allowed delay in seconds; the returned delay will not exceed this.

    Returns
    -------
    float
        Computed delay in seconds (includes a small jitter to reduce thundering-herd).

    Raises
    ------
    ValueError
        If `attempt` < 1 or parameters are invalid.
    """
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    if base < 0 or factor <= 0 or max_interval <= 0:
        raise ValueError("base, factor and max_interval must be positive numbers")

    # exponential component
    raw = base * (factor ** (attempt - 1))
    delay = min(raw, max_interval)

    # small jitter: +/- 10% uniform
    jitter_amount = delay * 0.10
    jitter = (random.random() * 2 - 1) * jitter_amount
    final = max(0.0, delay + jitter)
    return float(round(final, 4))


def parse_retry_after(value: Optional[Union[str, int, float]]) -> float:
    """
    Parse an HTTP 'Retry-After' header value and return delay in seconds.

    Parameters
    ----------
    value : Optional[Union[str,int,float]]
        The value of the 'Retry-After' header. Supported forms:
          - integer number of seconds (e.g. "120" or 120)
          - HTTP-date string (e.g. "Wed, 21 Oct 2015 07:28:00 GMT")
          - None -> returns 0.0

    Returns
    -------
    float
        Number of seconds to wait. Returns 0.0 for invalid/unknown values.

    Raises
    ------
    None
        This helper is tolerant and does not raise for malformed input; it returns 0.0 instead.
    """
    if value is None:
        return 0.0

    # direct numeric values
    try:
        if isinstance(value, (int, float)):
            sec = float(value)
            if sec < 0:
                return 0.0
            return sec
        s = str(value).strip()
        if s.isdigit():
            sec = float(int(s))
            return sec
    except Exception:
        # fall through to date parsing
        pass

    # try to parse as HTTP-date per RFC 7231
    try:
        dt = parsedate_to_datetime(str(value))
        # parsedate_to_datetime returns a timezone-aware datetime when timezone present; convert to UTC epoch
        now = time.time()
        retry_ts = dt.timestamp()
        wait = retry_ts - now
        return float(wait if wait > 0 else 0.0)
    except Exception:
        return 0.0


def map_http_status_to_error(status: int, message: str = "", response: Optional[object] = None) -> Exception:
    """
    Map an HTTP status code and optional message into an appropriate library exception.

    This helper wraps the library's centralized mapping (`errors.map_http_status`) when available,
    or falls back to a sensible mapping that returns a CurseForgeError subclass instance.

    Parameters
    ----------
    status : int
        HTTP status code (e.g. 200, 404, 429).
    message : str
        Optional human-readable message or response text used to build the exception message.
    response : Optional[object]
        Optional raw response object (requests.Response) or payload; included on the returned exception
        in its `response` attribute when possible.

    Returns
    -------
    Exception
        A concrete exception instance corresponding to the HTTP status. Examples:
          - 401/403 -> AuthError (or returned mapping)
          - 404 -> NotFoundError
          - 429 -> RateLimitError
          - 5xx -> ServerError
          - Otherwise -> CurseForgeError

    Raises
    ------
    None
        This function returns an Exception instance and does not raise by itself.
    """
    try:
        # prefer centralized mapper if present
        exc = errors_map_http_status(status, message, response)
        return exc
    except Exception:
        # safe fallback mapping
        code = int(status)
        msg = message or f"HTTP {code}"
        if code in (401, 403):
            return CurseForgeError(f"Authentication error {code}: {msg}")
        if code == 404:
            return CurseForgeError(f"Not found {code}: {msg}")
        if code == 429:
            e = CurseForgeError(f"Rate limited (HTTP {code}): {msg}")
            setattr(e, "retry_after", None)
            return e
        if 400 <= code < 500:
            return CurseForgeError(f"Client error {code}: {msg}")
        if 500 <= code < 600:
            return CurseForgeError(f"Server error {code}: {msg}")
        return CurseForgeError(f"HTTP {code}: {msg}")


def safe_json(payload: Union[str, bytes, dict, list, None], *, default: Optional[Union[dict, list]] = None) -> Optional[Union[dict, list]]:
    """
    Safely parse JSON payloads into Python objects.

    This helper accepts:
      - `requests.Response` .text/.content can be passed externally as str/bytes
      - Raw JSON strings (str or bytes)
      - Already-parsed dict/list (returns as-is)
      - None -> returns `default`

    Parameters
    ----------
    payload : Union[str, bytes, dict, list, None]
        The JSON source to parse or normalize.
    default : Optional[Union[dict, list]]
        Value to return when payload is None or parsing fails.

    Returns
    -------
    Optional[Union[dict, list]]
        Parsed JSON object (dict or list), or `default` on failure or when payload is None.

    Raises
    ------
    InvalidResponseError
        If the payload appears to be JSON but cannot be parsed (malformed) and `default` is None.
    """
    if payload is None:
        return default

    # If already parsed
    if isinstance(payload, (dict, list)):
        return payload

    # If bytes, decode
    try:
        if isinstance(payload, (bytes, bytearray)):
            text = payload.decode("utf-8", errors="replace")
        else:
            text = str(payload)
    except Exception as exc:
        if default is not None:
            return default
        raise InvalidResponseError(f"Failed to coerce payload to text: {exc}")

    # Empty string -> return default
    if not text:
        return default

    # Try JSON parse
    try:
        parsed = json.loads(text)
        # Normalize envelope: prefer 'data' key if present
        if isinstance(parsed, dict) and "data" in parsed:
            return parsed["data"]
        return parsed
    except json.JSONDecodeError as exc:
        if default is not None:
            return default
        raise InvalidResponseError(f"Invalid JSON payload: {exc}") from exc


def ttl_cache(ttl: int = 60):
    """
    Decorator implementing a simple in-memory TTL cache for pure functions.

    The decorated function's return values are cached per-call-arguments for `ttl` seconds.
    Cache entries are stored in-process and are not persisted. This is intended for
    low-volume metadata caching (games list, tags, versions) — not large binary data.

    Parameters
    ----------
    ttl : int
        Time-to-live in seconds for cache entries.

    Returns
    -------
    Callable
        A decorator that can be applied to functions.

    Raises
    ------
    ValueError
        If ttl is not a positive integer.
    """
    if not isinstance(ttl, (int, float)) or ttl <= 0:
        raise ValueError("ttl must be a positive number")

    def decorator(func: Callable):
        cache: Dict[Tuple[Tuple[Any, ...], Tuple[Tuple[str, Any], ...]], Tuple[Any, float]] = {}
        lock = threading.RLock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # create a cache key from args and kwargs (kwargs sorted by key)
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            with lock:
                if key in cache:
                    value, ts = cache[key]
                    if now - ts < ttl:
                        return value
                # cache miss or expired
                result = func(*args, **kwargs)
                cache[key] = (result, now)
                return result

        def cache_clear():
            """Clear the in-memory cache for this wrapped function."""
            with lock:
                cache.clear()

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator

def sha1_sum(path:str,chunk_size:int=8192)->str:
    """
    Calculate SHA1 checksum for a file.

    Parameters
    ----------
    path : str
        Path to the file to be hashed.
    chunk_size : int
        Read buffer size in bytes for iterative hashing.

    Returns
    -------
    str
        Hexadecimal SHA1 hash string (lowercase).

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    OSError
        If the file cannot be read due to permissions or I/O error.
    """
    sha1=hashlib.sha1()
    file_path=Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(file_path,"rb") as f:
        while True:
            chunk=f.read(chunk_size)
            if not chunk:break
            sha1.update(chunk)
    return sha1.hexdigest()


def sha256_sum(path:str,chunk_size:int=8192)->str:
    """
    Calculate SHA256 checksum for a file.

    Parameters
    ----------
    path : str
        Path to the file to be hashed.
    chunk_size : int
        Read buffer size in bytes for iterative hashing.

    Returns
    -------
    str
        Hexadecimal SHA256 hash string (lowercase).

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    OSError
        If the file cannot be read due to permissions or I/O error.
    """
    sha=hashlib.sha256()
    file_path=Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(file_path,"rb") as f:
        while True:
            data=f.read(chunk_size)
            if not data:break
            sha.update(data)
    return sha.hexdigest()


def md5_sum(path:str,chunk_size:int=8192)->str:
    """
    Calculate MD5 checksum for a file.

    Parameters
    ----------
    path : str
        Path to the file to be hashed.
    chunk_size : int
        Read buffer size in bytes for iterative hashing.

    Returns
    -------
    str
        Hexadecimal MD5 hash string (lowercase).

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    OSError
        If the file cannot be read due to permissions or I/O error.
    """
    md5=hashlib.md5()
    file_path=Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(file_path,"rb") as f:
        while True:
            data=f.read(chunk_size)
            if not data:break
            md5.update(data)
    return md5.hexdigest()


def fingerprint_from_file(path:str,algorithm:str="sha1")->str:
    """
    Generate a file fingerprint using the specified algorithm.

    Parameters
    ----------
    path : str
        Path to the file to fingerprint.
    algorithm : str
        Hash algorithm to use ("sha1", "sha256", "md5").

    Returns
    -------
    str
        Fingerprint as a hexadecimal string.

    Raises
    ------
    ValueError
        If unsupported algorithm specified.
    FileNotFoundError
        If the file does not exist.
    OSError
        If reading the file fails.
    """
    algorithm=algorithm.lower()
    if algorithm=="sha1":
        return sha1_sum(path)
    elif algorithm=="sha256":
        return sha256_sum(path)
    elif algorithm=="md5":
        return md5_sum(path)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def fingerprint_from_bytes(data:bytes,algorithm:str="sha1")->str:
    """
    Generate a fingerprint from a bytes object.

    Parameters
    ----------
    data : bytes
        Binary data to hash.
    algorithm : str
        Hash algorithm to use ("sha1", "sha256", "md5").

    Returns
    -------
    str
        Fingerprint as a hexadecimal string.

    Raises
    ------
    ValueError
        If an unsupported algorithm is specified.
    TypeError
        If data is not bytes.
    """
    if not isinstance(data,(bytes,bytearray)):
        raise TypeError("data must be bytes or bytearray")
    algorithm=algorithm.lower()
    if algorithm=="sha1":
        return hashlib.sha1(data).hexdigest()
    elif algorithm=="sha256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm=="md5":
        return hashlib.md5(data).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

def download_with_progress(url: str, target_path: str, chunk_size: int = 8192):
    """
    Download a file from a URL with a progress bar.

    Parameters
    ----------
    url : str
        The file's direct download URL.
    target_path : str
        Destination file path on local storage.
    chunk_size : int
        Size of each data chunk (in bytes) for streamed download.

    Raises
    ------
    requests.RequestException
        If network issues or invalid responses occur.
    OSError
        If file write fails due to I/O or permission errors.
    """
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        with open(target_path, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, desc=target_path, ncols=80
        ) as bar:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))

def parse_html_to_text(html_string: str) -> str:
    """
    Convert HTML content to plain text by stripping tags.

    Parameters
    ----------
    html_string : str
        Input HTML content.

    Returns
    -------
    str
        Clean text content without HTML tags.
    """
    text = re.sub(r"<[^>]+>", "", html_string)
    return html.unescape(text).strip()

def sanitize_html(html_string: str) -> str:
    """
    Sanitize HTML content by removing potentially unsafe tags and scripts.

    Parameters
    ----------
    html_string : str
        HTML content to sanitize.

    Returns
    -------
    str
        Safe HTML string without <script> or <iframe> content.
    """
    sanitized = re.sub(r"(?is)<(script|iframe|object|embed).*?>.*?</\\1>", "", html_string)
    return sanitized.strip()

def slugify(value: str) -> str:
    """
    Convert a string into a URL-safe, lowercase slug.

    Parameters
    ----------
    value : str
        Input text to convert into a slug.

    Returns
    -------
    str
        Lowercase, hyphen-separated slug suitable for URLs.
    """
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)

def parse_version(ver_str: str) -> version.Version:
    """
    Parse a version string into a standardized Version object.

    Parameters
    ----------
    ver_str : str
        Version string (e.g., '1.20.1').

    Returns
    -------
    packaging.version.Version
        Parsed version object for comparison operations.

    Raises
    ------
    InvalidVersion
        If the version string cannot be parsed.
    """
    return version.parse(ver_str)

def disk_cache(cache_dir: str = ".cache", ttl: int = 3600):
    """
    Persistent on-disk cache decorator.

    Parameters
    ----------
    cache_dir : str
        Directory path where cached responses will be stored.
    ttl : int
        Time-to-live in seconds; after expiry, cache is automatically invalidated.

    Returns
    -------
    Callable
        Decorator function that caches function outputs on disk.

    Raises
    ------
    OSError
        If the cache directory cannot be created or written to.
    """
    os.makedirs(cache_dir, exist_ok=True)
    lock = threading.RLock()

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}_{hash((args, tuple(sorted(kwargs.items()))))}.json"
            file_path = os.path.join(cache_dir, key)
            now = time.time()

            with lock:
                # Try to load existing cache
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if now - data["timestamp"] < ttl:
                            return data["result"]
                    except Exception:
                        pass

                # Cache miss → compute and save
                result = func(*args, **kwargs)
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump({"timestamp": now, "result": result}, f)
                except Exception:
                    pass
                return result
        return wrapper
    return decorator


def chunked(iterable: Iterable[Any], size: int) -> Generator[List[Any], None, None]:
    """
    Yield successive chunks from an iterable.

    Parameters
    ----------
    iterable : Iterable[Any]
        Input iterable (list, tuple, generator, etc.).
    size : int
        Maximum number of elements per chunk.

    Yields
    ------
    List[Any]
        Sub-lists of the given iterable with up to `size` elements each.

    Raises
    ------
    ValueError
        If `size` <= 0.
    """
    if size <= 0:
        raise ValueError("Chunk size must be positive")
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def batch(iterable: Iterable[Any], batch_size: int) -> Generator[List[Any], None, None]:
    """
    Group items into batches of fixed size for bulk operations.

    Parameters
    ----------
    iterable : Iterable[Any]
        Any iterable source (e.g., list of IDs or objects).
    batch_size : int
        Size of each batch.

    Yields
    ------
    List[Any]
        Batches of elements for sequential processing.

    Raises
    ------
    ValueError
        If batch_size <= 0.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    it = iter(iterable)
    while True:
        batch = list()
        try:
            for _ in range(batch_size):
                batch.append(next(it))
        except StopIteration:
            pass
        if not batch:
            break
        yield batch


def rate_limiter(max_calls: int, period: float = 1.0):
    """
    Decorator that limits the number of function calls per time period.

    Parameters
    ----------
    max_calls : int
        Maximum number of allowed calls per period.
    period : float
        Time window (in seconds) for counting calls.

    Returns
    -------
    Callable
        Wrapped function with rate-limiting behavior.

    Raises
    ------
    ValueError
        If parameters are invalid (<=0).
    """
    if max_calls <= 0 or period <= 0:
        raise ValueError("max_calls and period must be positive numbers")

    lock = threading.Lock()
    call_times: List[float] = []

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                now = time.time()
                # remove old timestamps
                while call_times and call_times[0] <= now - period:
                    call_times.pop(0)
                if len(call_times) >= max_calls:
                    sleep_time = period - (now - call_times[0])
                    time.sleep(max(0.001, sleep_time))
                call_times.append(time.time())
            return func(*args, **kwargs)
        return wrapper
    return decorator


class metrics_collector:
    """
    Simple in-memory performance and usage metrics collector.

    Provides counters, timers, and summaries for function execution.
    Useful for logging and diagnostics in larger systems.
    Thread-safe and lightweight.

    Example
    -------
    >>> metrics = metrics_collector()
    >>> with metrics.timer("api_call"):
    ...     call_api()
    >>> metrics.increment("success_count")
    >>> print(metrics.summary())
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def increment(self, key: str, value: int = 1):
        """
        Increment a counter metric.

        Parameters
        ----------
        key : str
            Metric name.
        value : int
            Amount to increment by (default = 1).
        """
        with self._lock:
            self._data[key] = self._data.get(key, 0) + value

    def timer(self, key: str):
        """
        Context manager that measures execution time of a code block.

        Parameters
        ----------
        key : str
            Metric name to record elapsed time under.
        """
        collector = self
        class _Timer:
            def __enter__(self):
                self.start = time.time()
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                elapsed = time.time() - self.start
                with collector._lock:
                    collector._data.setdefault(key, []).append(elapsed)
        return _Timer()

    def summary(self) -> Dict[str, Any]:
        """
        Return all collected metrics with basic statistics.

        Returns
        -------
        dict
            Dictionary of metrics with counts and timing summaries.
        """
        with self._lock:
            summary = {}
            for k, v in self._data.items():
                if isinstance(v, list) and v:
                    summary[k] = {
                        "count": len(v),
                        "avg_time": round(sum(v) / len(v), 4),
                        "max_time": round(max(v), 4),
                        "min_time": round(min(v), 4),
                    }
                else:
                    summary[k] = v
            return summary