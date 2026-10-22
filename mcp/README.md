# mcp/ — MCP server over the Dify service API

Thin MCP wrapper for `job-to-cv.yml`. The tool surface accepts **only the job
ad** — the candidate SSOT (including PII) is read from local storage
server-side and injected into the workflow inputs, so raw PII never enters the
calling agent's context. Generated documents contain merged PII, so they are
written to disk and only paths come back.

## Tools

| Tool | Args | Returns |
|------|------|---------|
| `draft_application` | `job_ad: str`, `prep_interview: bool = false` | `run_dir`, `files` (paths to `cv.md`, `cover-letter.md`, `interview-prep.md`), `workflow_run_id`, `elapsed_time` |
| `check_ssot` | — | `ok`, section presence + entry counts, `warnings`. Never returns field values |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r mcp/requirements.txt
```

Point your MCP host at the server (stdio transport). Env vars:

| Var | Required | Default | Purpose |
|-----|----------|---------|---------|
| `DIFY_API_KEY` | yes | — | App API key (`app-…`) from Dify console → app → API Access |
| `DIFY_BASE_URL` | no | `http://localhost/v1` | Dify service API base |
| `SSOT_PATH` | no | `ssot.json` | Your real SSOT JSON — keep it outside this repo or gitignored |
| `OUTPUT_DIR` | no | `out` | Where generated documents land |

Example host config:

```json
{
  "mcpServers": {
    "job-apply-kit": {
      "command": "/path/to/job-apply-kit/.venv/bin/python",
      "args": ["/path/to/job-apply-kit/mcp/server.py"],
      "env": {
        "DIFY_API_KEY": "app-...",
        "SSOT_PATH": "/Users/you/private/ssot.json",
        "OUTPUT_DIR": "/Users/you/private/job-out"
      }
    }
  }
}
```

## Tests

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest mcp/test_server.py
```

No live Dify needed — HTTP is mocked via `httpx.MockTransport`.
