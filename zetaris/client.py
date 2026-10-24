"""Read-only Zetaris UI-proxy SQL client, shaped after zetaris/getting-started."""

from dataclasses import dataclass
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


def _load_local_env() -> None:
    """Load ignored project-local Zetaris settings without echoing secrets."""
    path = Path(__file__).resolve().parents[1] / ".env.local"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if separator and re.fullmatch(r"ZETARIS_[A-Z0-9_]+", key):
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class ZetarisConfig:
    base_url: str  # Web UI origin, not the direct REST API base.
    api_key: str
    org_id: str
    query_limit: int = 1000
    engine_id: str | None = None

    @classmethod
    def from_environment(cls) -> "ZetarisConfig | None":
        _load_local_env()
        base_url = os.environ.get("ZETARIS_BASE_URL", "").strip()
        api_key = os.environ.get("ZETARIS_API_KEY", "").strip()
        org_id = os.environ.get("ZETARIS_ORG_ID", "").strip()
        if not any((base_url, api_key, org_id)):
            return None
        if not all((base_url, api_key, org_id)):
            raise ValueError("Set ZETARIS_BASE_URL, ZETARIS_API_KEY, and numeric ZETARIS_ORG_ID")
        try:
            limit = int(os.environ.get("ZETARIS_QUERY_LIMIT", "1000").strip())
        except ValueError as exc:
            raise ValueError("ZETARIS_QUERY_LIMIT must be a positive integer") from exc
        config = cls(base_url, api_key, org_id, limit, os.environ.get("ZETARIS_ENGINE_ID") or None)
        config.validate()
        return config

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if (not parsed.netloc or parsed.username or parsed.password or parsed.path not in ("", "/")
                or parsed.params or parsed.query or parsed.fragment):
            raise ValueError("ZETARIS_BASE_URL must be a web UI origin without a path")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
            raise ValueError("ZETARIS_BASE_URL must use HTTPS, except localhost may use HTTP")
        if not re.fullmatch(r"[0-9]+", self.org_id):
            raise ValueError("ZETARIS_ORG_ID must be the numeric ID from Management → Organisation")
        if not self.api_key:
            raise ValueError("ZETARIS_API_KEY is required for this read-only UI-proxy client")
        if self.query_limit < 1:
            raise ValueError("ZETARIS_QUERY_LIMIT must be a positive integer")


@dataclass(frozen=True)
class ZetarisResult:
    status: str  # ok | unavailable | error
    rows: tuple[dict[str, Any] | tuple[Any, ...], ...] = ()
    message: str = ""
    request_id: str = ""


class ZetarisClient:
    ROUTE = "/api/proxy/sql-editor/sqls/run-query"

    def __init__(self, config: ZetarisConfig | None, timeout_seconds: int = 30):
        if config is not None:
            config.validate()
        self.config = config
        self.timeout_seconds = timeout_seconds

    def query(self, sql: str) -> ZetarisResult:
        if self.config is None:
            return ZetarisResult("unavailable", message="Zetaris UI URL, API key, or numeric org ID is not configured")
        statement = sql.strip()
        upper = statement.upper()
        if not (upper.startswith("SELECT ") or upper.rstrip(";") == "SHOW LIGHTNING DATABASES"):
            return ZetarisResult("error", message="Lens permits only SELECT and SHOW LIGHTNING DATABASES")
        # `grant` is a Lens report column, so blocking that word anywhere in a
        # SELECT rejects legitimate evidence reads. Statement type and the
        # remaining write clauses still guard this narrow read-only client.
        if ";" in statement.rstrip(";") or re.search(r"\b(INTO|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|REVOKE|TRUNCATE)\b", upper):
            return ZetarisResult("error", message="Lens refused a potentially modifying SQL statement")
        request_id = str(uuid4())
        body: dict[str, Any] = {"sql": statement, "limit": self.config.query_limit}
        if self.config.engine_id:
            body["engineId"] = self.config.engine_id
        request = Request(
            self.config.base_url.rstrip("/") + self.ROUTE,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.config.api_key}", "X-Org-ID": self.config.org_id,
                     "X-Request-ID": request_id, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as exc:
            return ZetarisResult("error", message=f"Zetaris HTTP {exc.code}", request_id=request_id)
        except (URLError, TimeoutError, OSError):
            return ZetarisResult("unavailable", message="Zetaris UI proxy could not be reached", request_id=request_id)
        except (ValueError, UnicodeDecodeError):
            return ZetarisResult("error", message="Zetaris returned invalid JSON", request_id=request_id)
        if not isinstance(payload, dict) or payload.get("error") or payload.get("errors") or payload.get("success") is False:
            return ZetarisResult("error", message="Zetaris reported a query error or unexpected response", request_id=request_id)
        data = payload.get("data")
        if not isinstance(data, list):
            return ZetarisResult("error", message="Zetaris response has no result rows field", request_id=request_id)
        if not data:
            return ZetarisResult("ok", message="Query succeeded with zero rows", request_id=request_id)
        headers = payload.get("headers")
        if all(isinstance(row, dict) for row in data):
            rows = tuple(data)
        elif all(isinstance(row, list) for row in data):
            if (isinstance(headers, list) and all(isinstance(h, str) for h in headers)
                    and all(len(row) == len(headers) for row in data)):
                rows = tuple(dict(zip(headers, row)) for row in data)
            else:
                rows = tuple(tuple(row) for row in data)
        else:
            return ZetarisResult("error", message="Zetaris row format is not recognized", request_id=request_id)
        return ZetarisResult("ok", rows=rows, message=f"Zetaris returned {len(rows)} rows", request_id=request_id)
