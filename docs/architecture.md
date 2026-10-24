# Architecture

## Pipeline

```
                ┌─────────────────────── outside the LLM ───────────────────────┐
                │                                                               │
 job ad ──┐     │   ┌──────────┐   ┌──────────────┐   ┌───────────────┐         │
 (input)  │     │   │ ssot_json│──▶│   redact     │──▶│  redacted     │──┐      │
          │     │   │(PII-free)│   │  (Code node) │   │  ssot         │  │      │
          │     │   └──────────┘   └──────┬───────┘   └───────────────┘  │      │
          │     │                         │ pii_map (stays in-workflow)  │      │
          │     │                         ▼                            │      │
          │     │   ┌───────────────────────────────────────────────────────┐  │
          │     │   │       inside the LLM (LLM nodes only; the parse      │  │
          │     └──▶│       steps are Code nodes, not model calls)          │◀─┘
          │         │  extract JD reqs ─▶ parse ─▶ select evidence ─▶       │
          │         │  parse ─▶ draft CV ─▶ draft cover ─▶ (opt) prep       │
          │         └───────────────────────────┬───────────────────────────┘
          │                                     ▼
          │         ┌───────────────────────────────────────────┐
 PII_JSON │────────▶│  Code node: merge PII back                │◀─ map_json_resume
 (env var)│         │  (env.PII_JSON ?? pii_map)                │   (Code node: SSOT +
          │         └───────────────────────────┬───────────────┘    evidence → JSON
          ▼                                     ▼                    Resume draft)
        outputs:  cv_md · cv_json · cover_letter_md · interview_prep_md?
```

## Design rules

1. **SSOT lives outside the LLM.** The candidate profile is passed PII-free via
   `ssot_json` (or fetched from private storage). Contact PII lives in the
   `PII_JSON` app env var; the model only ever sees `redacted_ssot`.

2. **PII never enters Knowledge or a vector store.** The workflow uses **no
   retrieval/Knowledge nodes** — no embedding, no indexing of profile data.
   Vector stores would leak PII into embeddings you can't cleanly revoke.

3. **Redaction → generation → merge.** The canonical PII store is the
   `PII_JSON` app env var (secret) — keeping PII out of `ssot_json` also keeps
   it out of Dify's run history. A Code node still strips inline `identity.pii`
   into a `pii_map` *before* any LLM node (guard for stray PII); a second Code
   node substitutes real values back *after* generation (`PII_JSON` ?? `pii_map`).
   Neither `pii_map` nor `PII_JSON` may be referenced in an LLM prompt.

4. **LLM JSON is parsed, not trusted.** `extract_reqs` and `select_evidence`
   each feed a Code node that strips code fences and `json.loads`es the output
   into normalized JSON. On parse failure the raw text passes through
   (`ok=false`) rather than failing the run — downstream prompts stay usable
   and the failure is observable.

5. **Keys live in env / provider settings only.** `SECRET_KEY`, `OPENAI_API_KEY`
   (or Azure), and `SSOT_API_TOKEN` come from `.env` or Dify → Settings →
   Model Provider. Nothing secret is baked into the DSL — an exported
   `job-to-cv.yml` stays safe to commit after review.

## Output formats

- **`cv_md`** — Markdown CV, kept as the human-facing format (unchanged path).
- **`cv_json`** — [JSON Resume](https://jsonresume.org/schema/)
  (`@jsonresume/schema` ~1.x). Built by the `map_json_resume` **Code node** —
  not an LLM — from the redacted SSOT, filtered/ordered by the picked evidence
  (`picked_bullets` → `work[].highlights`, `picked_projects` → `projects`,
  `skill_focus` orders `skills[].keywords`), so no model can invent
  `resume.json` content. Contact fields carry the same `{{TOKEN}}`
  placeholders until `merge_pii` substitutes real PII (JSON-escaped) — PII
  stays env-only in `PII_JSON`. `work[].endDate` is omitted for current roles.
- **PDF** — planned later via a pinned `resumed` CLI + theme; `cv_json` is the
  interchange format it will consume. Not included yet.

## Driving Dify (control plane)

| Concern | Mechanism |
|---|---|
| Run the workflow | Dify service API: `POST {DIFY_BASE_URL}/workflows/run` with an app API key (`app-…`), inputs as strings, `response_mode: blocking` or `streaming` |
| Define the workflow | Manual once: Studio → Import DSL → `job-to-cv.yml`, then Publish |
| Automate setup (unofficial) | Dify has no public build-plane API, but the web console's internal `/console/api` is scriptable: `POST /console/api/login` (password is Base64-encoded) → cookies + `X-CSRF-TOKEN` header → `POST /console/api/apps/imports` (`{mode: "yaml-content", yaml_content, app_id?}`) → `POST /console/api/apps/{id}/workflows/publish` → `POST /console/api/apps/{id}/api-keys`. Used to bootstrap this repo's workflow; brittle across versions. **Never commit admin credentials or login scripts containing them to the repo** — keep them local-only (e.g. `.env`, which is gitignored). |
| Secrets | `.env` for infra keys; app API key per published app |
| MCP server | `mcp/server.py` — thin client over the service API. Tools take only `job_ad`; the PII-free SSOT is loaded from `SSOT_PATH` server-side and outputs are written to `OUTPUT_DIR` (paths returned, never contents), so PII stays out of the host agent's context too. `check_ssot` reports `pii_source` (`inline` vs `env:PII_JSON`) |

## Local deployment (reference)

Standard self-host: `dify/docker` → `cp .env.example .env` → `docker compose up -d`.
Services: `api`, `worker`, `web`, `db` (Postgres), `redis`, `weaviate`,
`sandbox` (Code nodes run here — note the merge step executes in the
`sandbox`/`ssrf_proxy` boundary), `plugin_daemon`, `nginx` on port 80.
