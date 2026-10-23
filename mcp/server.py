"""MCP server for job-apply-kit — thin client over the Dify service API.

Design contract (see docs/architecture.md):
- The tool surface accepts only the job ad plus flags. The candidate SSOT
  (PII-free career data; PII lives in the Dify app env var PII_JSON) is read
  from local storage server-side and injected into the workflow inputs, so
  raw PII never enters the calling agent's context.
- Generated documents contain merged PII, so they are written to OUTPUT_DIR
  and only paths are returned to the caller.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

server = MCPServer(
    name="job-apply-kit",
    instructions=(
        "Turns a job ad into a tailored CV and cover letter via a self-hosted "
        "Dify workflow. The candidate profile (SSOT, incl. PII) is read from "
        "local storage server-side and never passes through the agent context."
    ),
)

_OUTPUT_FILES = {
    "cv_md": "cv.md",
    "cover_letter_md": "cover-letter.md",
    "interview_prep_md": "interview-prep.md",
}

_SSOT_SECTIONS = ("identity", "target", "experience", "projects", "skills", "education", "prefs")


def _config() -> dict[str, Any]:
    return {
        "base_url": os.environ.get("DIFY_BASE_URL", "http://localhost/v1").rstrip("/"),
        "api_key": os.environ.get("DIFY_API_KEY", ""),
        "ssot_path": Path(os.environ.get("SSOT_PATH", "ssot.json")),
        "output_dir": Path(os.environ.get("OUTPUT_DIR", "out")),
    }


def _dify_client(cfg: dict[str, Any]) -> httpx.Client:
    if not cfg["api_key"]:
        raise RuntimeError(
            "DIFY_API_KEY is not set. Create an app API key in the Dify "
            "console (app -> API Access) and export it before starting."
        )
    return httpx.Client(
        base_url=cfg["base_url"],
        headers={"Authorization": f"Bearer {cfg['api_key']}"},
        timeout=300.0,
    )


def _load_ssot(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"cannot read SSOT at {path}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"SSOT at {path} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"SSOT at {path} must be a JSON object")
    return raw


def _run_workflow(cfg: dict[str, Any], ssot_json: str, job_ad: str, prep_interview: bool) -> dict[str, Any]:
    payload = {
        "inputs": {
            "job_ad": job_ad,
            "ssot_json": ssot_json,
            "prep_interview": "yes" if prep_interview else "no",
        },
        "response_mode": "blocking",
        "user": "mcp",
    }
    try:
        with _dify_client(cfg) as client:
            resp = client.post("/workflows/run", json=payload)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"cannot reach Dify at {cfg['base_url']}: {exc}") from exc
    if resp.status_code != 200:
        detail = ""
        if resp.headers.get("content-type", "").startswith("application/json"):
            detail = str(resp.json().get("message", ""))
        raise RuntimeError(f"Dify /workflows/run returned HTTP {resp.status_code} {detail}".rstrip())
    data = resp.json().get("data") or {}
    if data.get("status") != "succeeded":
        raise RuntimeError(
            f"workflow ended with status={data.get('status')!r}: "
            f"{data.get('error') or 'no error detail'}"
        )
    return data


@server.tool()
def draft_application(job_ad: str, prep_interview: bool = False) -> dict[str, Any]:
    """Draft a tailored CV and cover letter for a job ad.

    Reads the candidate SSOT from SSOT_PATH server-side, runs the published
    Dify job-to-cv workflow, and writes documents under OUTPUT_DIR/<timestamp>/.
    Returns file paths only — the generated documents contain real PII.
    """
    if not job_ad.strip():
        raise ValueError("job_ad is empty")
    cfg = _config()
    ssot_json = _load_ssot(cfg["ssot_path"])
    data = _run_workflow(cfg, ssot_json, job_ad, prep_interview)

    run_dir = cfg["output_dir"] / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for key, name in _OUTPUT_FILES.items():
        text = (data.get("outputs") or {}).get(key)
        if text:
            (run_dir / name).write_text(text, encoding="utf-8")
            files[key] = str(run_dir / name)
    return {
        "run_dir": str(run_dir),
        "files": files,
        "workflow_run_id": data.get("id"),
        "elapsed_time": data.get("elapsed_time"),
    }


@server.tool()
def check_ssot() -> dict[str, Any]:
    """Validate the SSOT file configured via SSOT_PATH.

    Reports which sections exist and how many entries each list holds, plus
    where the merge step will source PII (inline identity.pii or the PII_JSON
    app env var). Field values are never returned, so no PII enters the agent
    context.
    """
    cfg = _config()
    try:
        ssot = json.loads(_load_ssot(cfg["ssot_path"]))
    except RuntimeError as exc:
        return {"ok": False, "path": str(cfg["ssot_path"]), "warnings": [str(exc)]}

    sections, warnings = {}, []
    for key in _SSOT_SECTIONS:
        val = ssot.get(key)
        if val is None:
            sections[key] = "missing"
            warnings.append(f"missing section: {key}")
        elif isinstance(val, list):
            sections[key] = f"{len(val)} entr{'y' if len(val) == 1 else 'ies'}"
        else:
            sections[key] = "present"
    pii = (ssot.get("identity") or {}).get("pii")
    pii_source = "inline" if isinstance(pii, dict) and pii else "env:PII_JSON"

    return {
        "ok": not warnings,
        "path": str(cfg["ssot_path"]),
        "schema_version": ssot.get("schema_version"),
        "pii_source": pii_source,
        "sections": sections,
        "extra_keys": sorted(set(ssot) - set(_SSOT_SECTIONS) - {"_comment", "schema_version"}),
        "warnings": warnings,
    }


if __name__ == "__main__":
    server.run("stdio")
