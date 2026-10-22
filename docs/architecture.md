# Architecture

## Pipeline

```
                ┌─────────────────────── outside the LLM ───────────────────────┐
                │                                                               │
 job ad ──┐     │   ┌──────────┐   ┌──────────────┐   ┌───────────────┐         │
 (input)  │     │   │  fetch   │──▶│   redact     │──▶│  redacted     │──┐      │
          │     │   │  SSOT    │   │  (Code node) │   │  ssot         │  │      │
          │     │   └──────────┘   └──────┬───────┘   └───────────────┘  │      │
          │     │                         │ pii_map (stays in-workflow)  │      │
          │     │                         ▼                            │      │
          │     │   ┌───────────────────────────────────────────────────────┐  │
          │     │   │                 inside the LLM                        │  │
          │     └──▶│  extract JD reqs ─▶ select evidence ─▶ draft CV       │◀─┘
          │         │                                    ─▶ draft cover     │
          │         │                                    ─▶ (opt) prep      │
          │         └───────────────────────────┬───────────────────────────┘
          │                                     ▼
          │         ┌───────────────────────────────────────────┐
          │         │  Code node: merge PII back via pii_map    │
          │         └───────────────────────────┬───────────────┘
          ▼                                     ▼
        outputs:  cv_md · cover_letter_md · interview_prep_md?
```

## Design rules

1. **SSOT lives outside the LLM.** The candidate profile is fetched from private
   storage (file/DB/API) or passed in pre-redacted. The model only ever sees
   `redacted_ssot`.

2. **PII never enters Knowledge or a vector store.** The workflow uses **no
   retrieval/Knowledge nodes** — no embedding, no indexing of profile data.
   Vector stores would leak PII into embeddings you can't cleanly revoke.

3. **Redaction → generation → merge.** A Code node strips PII into a `pii_map`
   *before* any LLM node; a second Code node substitutes real values back
   *after* generation. `pii_map` is an intermediate workflow variable and must
   never be referenced in an LLM prompt.

4. **Keys live in env / provider settings only.** `SECRET_KEY`, `OPENAI_API_KEY`
   (or Azure), and `SSOT_API_TOKEN` come from `.env` or Dify → Settings →
   Model Provider. Nothing secret is baked into the DSL — an exported
   `job-to-cv.yml` stays safe to commit after review.

## Driving Dify (control plane)

| Concern | Mechanism |
|---|---|
| Run the workflow | Dify service API: `POST {DIFY_BASE_URL}/workflows/run` with an app API key (`app-…`), inputs as strings, `response_mode: blocking` or `streaming` |
| Define the workflow | Manual once: Studio → Import DSL → `job-to-cv.yml`, then Publish |
| Secrets | `.env` for infra keys; app API key per published app |
| Future CLI/MCP | Thin client over the service API — **deferred, not implemented** |

## Local deployment (reference)

Standard self-host: `dify/docker` → `cp .env.example .env` → `docker compose up -d`.
Services: `api`, `worker`, `web`, `db` (Postgres), `redis`, `weaviate`,
`sandbox` (Code nodes run here — note the merge step executes in the
`sandbox`/`ssrf_proxy` boundary), `plugin_daemon`, `nginx` on port 80.
