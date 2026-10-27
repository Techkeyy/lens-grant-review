"""Bounded Nightshift routing for Lens's next evidence question.

The model may prioritize one supported follow-up. It cannot change source links,
arithmetic, finding status, or the SQL that the Zetaris adapter is allowed to run.
"""

from __future__ import annotations

import json
import os
import sys
from urllib import error, parse, request

from zetaris.client import _load_local_env


SUPPORTED = ("OVERALLOCATED_SOURCE", "ACTIVITY_SUPPORT_GAP")


def _base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        raise ValueError("Nightshift URL is missing")
    if "://" not in value:
        value = "http://" + value
    parts = parse.urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("Nightshift URL is invalid")
    if parts.scheme == "http" and parts.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("A remote Nightshift endpoint must use HTTPS")
    path = parts.path
    for suffix in ("/chat/completions", "/models", "/healthz"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
    path = path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    if path:
        raise ValueError("Nightshift URL must point to the runtime root or /v1")
    return parse.urlunsplit((parts.scheme, parts.netloc, "/v1", "", ""))


def choose_followup(findings: list[dict]) -> dict:
    """Ask Nightshift to prioritize one open, allowlisted finding.

    Returns an explicit status for trace/UI. A failure never masquerades as a
    successful model call, and never changes the deterministic reconciliation.
    """
    _load_local_env()
    candidates = [
        {"code": item["code"], "status": item["status"], "arithmetic": item.get("arithmetic")}
        for item in findings if item.get("code") in SUPPORTED and item.get("status") != "clear"
    ]
    if not candidates:
        return {"status": "no_candidate", "selected_code": None}
    url = os.environ.get("NIGHTSHIFT_BASE_URL", "").strip()
    token = os.environ.get("NIGHTSHIFT_RUNTIME_TOKEN", "").strip()
    model = os.environ.get("NIGHTSHIFT_MODEL", "meterless/auto").strip()
    if not url or not token or token == "rt-local" or not model.startswith("meterless/"):
        return {"status": "not_configured", "selected_code": None}
    try:
        base = _base_url(url)
        headers = {"Authorization": "Bearer " + token, "meterless-app": "lens"}
        models_req = request.Request(base + "/models", headers=headers)
        with request.urlopen(models_req, timeout=15) as response:
            model_data = response.read(64_001)
        if len(model_data) > 64_000:
            raise ValueError("Nightshift model list exceeds limit")
        models = json.loads(model_data)
        if not isinstance(models, dict) or not isinstance(models.get("data"), list):
            raise ValueError("Nightshift model list is invalid")
        if not any(isinstance(item, dict) and str(item.get("id", "")).startswith("meterless/")
                   for item in models.get("data", [])):
            return {"status": "offline", "selected_code": None, "model": model}
        endpoint = base + "/chat/completions"
        body = json.dumps({
            "model": model, "temperature": 0,
            "messages": [
                {"role": "system", "content": "You prioritize a grant evidence follow-up. Return only JSON with a selected_code matching one candidate code. Do not infer wrongdoing, compliance, identities, or new evidence."},
                {"role": "user", "content": json.dumps({"task": "Choose which evidence gap a human should inspect next", "candidates": candidates})},
            ],
        }).encode("utf-8")
        req = request.Request(endpoint, data=body, method="POST", headers={
            **headers, "Content-Type": "application/json", "meterless-scope": "user"})
        with request.urlopen(req, timeout=180) as response:
            data = response.read(64_001)
            if len(data) > 64_000:
                raise ValueError("Nightshift response exceeds limit")
            result = json.loads(data)
        content = result["choices"][0]["message"]["content"]
        choice = json.loads(content)
        selected = choice["selected_code"]
        if selected not in {item["code"] for item in candidates}:
            raise ValueError("Nightshift selected an unsupported follow-up")
        return {"status": "used", "selected_code": selected, "model": result.get("model", model),
                "request_id": result.get("id")}
    except error.HTTPError as exc:
        return {"status": "unauthorized" if exc.code in (401, 403) else "unavailable",
                "selected_code": None, "model": model}
    except (error.URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return {"status": "unavailable", "selected_code": None, "model": model}


if __name__ == "__main__":
    # Synthetic request only. Never print the bearer token or private evidence.
    outcome = choose_followup([{"code": "OVERALLOCATED_SOURCE", "status": "needs_correction",
                                "arithmetic": {"allocated_total": "8", "source_total": "4", "unit": "hours"}}])
    print(json.dumps(outcome, sort_keys=True))
    sys.exit(0 if outcome["status"] == "used" else 1)
