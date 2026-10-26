"""Authenticated review storage. Public mode uses Supabase Auth and PostgREST."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class StorageError(Exception):
    pass


class Unauthorized(StorageError):
    pass


class NotFound(StorageError):
    pass


class Conflict(StorageError):
    pass


class Busy(StorageError):
    pass


class PayloadTooLarge(StorageError):
    pass


def public_mode():
    return bool(os.environ.get("SUPABASE_URL"))


def _settings():
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not all((base, anon, service)) or not base.startswith("https://"):
        raise StorageError("Public storage is not configured")
    return base, anon, service


def public_config():
    if not public_mode():
        return {"auth_mode": "local"}
    base, anon, _ = _settings()
    return {"auth_mode": "supabase", "supabase_url": base, "supabase_anon_key": anon}


def _request(url, method="GET", payload=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "Accept": "application/json", **(headers or {})})
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise Unauthorized("Sign in again") from exc
        raise StorageError(f"Review service returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise StorageError("Review service is unavailable; please retry") from exc


def authenticate(authorization):
    if not public_mode():
        return {"id": "local", "email": None}
    base, anon, _ = _settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise Unauthorized("Sign in to access reviews")
    token = authorization.removeprefix("Bearer ").strip()
    if not token or len(token) > 8192:
        raise Unauthorized("Sign in to access reviews")
    user = _request(f"{base}/auth/v1/user", headers={"apikey": anon, "Authorization": f"Bearer {token}"})
    if not isinstance(user, dict) or not user.get("id"):
        raise Unauthorized("Sign in again")
    return {"id": user["id"], "email": user.get("email")}


def _admin_headers():
    _, _, service = _settings()
    return {"apikey": service, "Authorization": f"Bearer {service}"}


def _local_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, title TEXT NOT NULL, state TEXT NOT NULL, row_version INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    return db


def list_reviews(owner, path):
    if public_mode():
        base, _, _ = _settings()
        return _request(f"{base}/rest/v1/lens_reviews?owner_id=eq.{quote(owner)}&select=id,title,created_at,updated_at,row_version&order=updated_at.desc", headers=_admin_headers())
    with closing(_local_db(path)) as db:
        rows = db.execute("SELECT id,title,created_at,updated_at,row_version FROM reviews WHERE owner_id=? ORDER BY updated_at DESC", (owner,)).fetchall()
    return [dict(zip(("id", "title", "created_at", "updated_at", "row_version"), row)) for row in rows]


def create_review(owner, title, path):
    title = str(title or "Untitled review").strip()
    if not title or len(title) > 120:
        raise ValueError("Review name must be 1 to 120 characters")
    now = datetime.now(timezone.utc).isoformat()
    row = {"id": str(uuid.uuid4()), "owner_id": owner, "title": title,
           "state": {"phase": "empty", "revision": 0}, "row_version": 0,
           "created_at": now, "updated_at": now}
    if public_mode():
        base, _, _ = _settings()
        result = _request(f"{base}/rest/v1/lens_reviews", "POST", row,
                          _admin_headers() | {"Prefer": "return=representation"})
        if not isinstance(result, list) or len(result) != 1:
            raise StorageError("Could not create review")
    else:
        with closing(_local_db(path)) as db:
            db.execute("INSERT INTO reviews(id,owner_id,title,state,row_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                       (row["id"], owner, title, json.dumps(row["state"]), 0, now, now))
            db.commit()
    return {key: row[key] for key in ("id", "title", "created_at", "updated_at", "row_version")}


def read_review(owner, review_id, path):
    try:
        review_id = str(uuid.UUID(str(review_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise NotFound("Review not found") from exc
    if public_mode():
        base, _, _ = _settings()
        rows = _request(f"{base}/rest/v1/lens_reviews?id=eq.{review_id}&owner_id=eq.{quote(owner)}&select=id,title,state,meterless_data,row_version", headers=_admin_headers())
        row = rows[0] if isinstance(rows, list) and rows else None
    else:
        with closing(_local_db(path)) as db:
            result = db.execute("SELECT id,title,state,row_version FROM reviews WHERE id=? AND owner_id=?", (review_id, owner)).fetchone()
        row = {"id": result[0], "title": result[1], "state": json.loads(result[2]), "row_version": result[3], "meterless_data": None} if result else None
    if not row:
        raise NotFound("Review not found")
    return row


def save_review(owner, review_id, state, version, meterless_data, path):
    now = datetime.now(timezone.utc).isoformat()
    if public_mode():
        base, _, _ = _settings()
        patch = {"state": state, "meterless_data": meterless_data, "row_version": version + 1, "updated_at": now}
        rows = _request(f"{base}/rest/v1/lens_reviews?id=eq.{review_id}&owner_id=eq.{quote(owner)}&row_version=eq.{version}",
                        "PATCH", patch, _admin_headers() | {"Prefer": "return=representation"})
        if not isinstance(rows, list) or len(rows) != 1:
            raise Conflict("This review changed in another tab. Reload before editing.")
    else:
        with closing(_local_db(path)) as db:
            cursor = db.execute("UPDATE reviews SET state=?,row_version=row_version+1,updated_at=? WHERE id=? AND owner_id=? AND row_version=?",
                                (json.dumps(state), now, review_id, owner, version))
            db.commit()
        if cursor.rowcount != 1:
            raise Conflict("This review changed in another tab. Reload before editing.")
    return version + 1
