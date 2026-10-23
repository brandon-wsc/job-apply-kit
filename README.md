# job-apply-kit

Open-source skeleton for a **self-hosted Dify Workflow** that turns a job ad into a
tailored **CV + cover letter**, with optional **interview prep**.

The core idea: your **single source of truth (SSOT)** for career data lives *outside*
the LLM. The workflow consumes a **redacted** version of your profile, generates
documents against the job description, and a **Code step merges real PII back in**
after generation. No personal data is ever embedded, indexed, or sent to a model
provider in raw form.

## Requirements

- Docker + Docker Compose
- [Dify](https://github.com/langgenius/dify) self-hosted (tested against Dify 1.x
  `docker compose` deployment)
- An LLM provider — the shipped DSL uses **OpenRouter**
  (`langgenius/openrouter/openrouter` plugin) with `deepseek/deepseek-chat` as
  the default model. Install the OpenRouter plugin (or swap `model.provider`
  in the DSL / Studio) and add your key under *Settings → Model Provider*.
  OpenRouter region-gates some providers (e.g. Anthropic, OpenAI, Google) in
  certain countries — pick a model that routes for you.

## Quick start

1. **Start Dify** (see also `docs/architecture.md`):

   ```bash
   git clone https://github.com/langgenius/dify.git
   cd dify/docker
   cp .env.example .env   # set SECRET_KEY etc.
   docker compose up -d
   ```

   Then open `http://localhost/install` and create the admin account.

2. **Configure a model provider** — Dify console → *Settings → Model Provider*.
   The DSL expects the OpenRouter plugin; keys live in Dify's provider settings,
   never in the workflow definition.

3. **Import the workflow DSL** — Studio → *Create from DSL* → pick
   `dify/workflows/job-to-cv.yml` (a real exported workflow). The sibling
   `job-to-cv.yml.example` file documents the node/variable design for readers
   who want to build it by hand.

4. **Publish the app and create an API key** — the workflow can then be driven
   via the Dify service API:

   ```bash
   curl -X POST "$DIFY_BASE_URL/workflows/run" \
     -H "Authorization: Bearer $DIFY_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "inputs": {
         "job_ad": "<contents of examples/job-ad.md>",
         "ssot_json": "<contents of examples/ssot.example.json>",
         "prep_interview": "yes"
       },
       "response_mode": "blocking",
       "user": "local"
     }'
   ```

   `ssot_json` is the **full** profile — the workflow's `redact` Code node strips
   `identity.pii` before any LLM call and merges it back afterwards.

5. **Try the examples** — `examples/job-ad.md` + `examples/ssot.example.json`
   (fake identity only) are ready to paste in.

### Optional: drive it via MCP

`mcp/server.py` wraps the service API so an agent only ever sends the job ad —
your real SSOT (incl. PII) is read from a local path server-side, and generated
documents are written to disk rather than returned through the agent context.
Setup and host config: `mcp/README.md`.

## Deploy on a Docker host

This repo ships no image of its own — deploying means running the Dify stack on
any Docker host (NAS, VPS, home server) and pointing your client at it.

1. Copy the **whole** `dify/docker/` directory to the host — the compose file
   uses bind-mounted config and volume dirs, so the YAML alone is not enough.
2. Edit `.env` on the host:
   - `SECRET_KEY` — required (`openssl rand -base64 42`)
   - `EXPOSE_NGINX_PORT` / `EXPOSE_NGINX_SSL_PORT` — change if 80/443 are taken
     (e.g. `8080`/`8443` when the host OS already owns them)
3. Start the stack. Budget **~8 GB free RAM** — under ~4 GB the API container is
   OOM-killed during DB migrations. x86_64 hosts only.
4. Open `http://<host>:<port>/install`, then follow quick start steps 2–4.
5. Keep the MCP server on your workstation and set
   `DIFY_BASE_URL=http://<host>:<port>/v1` — your `ssot.json` (PII included)
   never leaves the client machine.

Optional HTTPS: put the host's own reverse proxy in front of the nginx port and
set `CONSOLE_API_URL`/`APP_API_URL` in `.env` accordingly so generated links are
correct.

## What is NOT included

- No real résumés, identities, or career data — the example SSOT is fictional.
- No API keys or secrets — `.env.example` is a template only.
- No production SSOT service — wire your own storage (file, DB, or API) behind
  the fetch/redact step.
- `job-to-cv.yml.example` is a spec stub for documentation; the importable DSL
  is `job-to-cv.yml`.

## Roadmap

- [x] Export real `dify/workflows/job-to-cv.yml` from Dify (built + verified
      end-to-end via `/v1/workflows/run` on Dify 1.17)
- [x] MCP server to drive the workflow via the Dify service API — see
      `mcp/` (tool surface takes only the job ad; SSOT is injected server-side)

## License

[MIT](LICENSE)
