# Deploy to Synology Container Manager

Self-host Dify on a Synology NAS via Container Manager (DSM 7.2+), then run
`job-to-cv.yml` on it. The MCP server stays on your Mac — only Dify moves.

## Requirements

- x86_64 Synology with Container Manager (not all ARM models support it)
- ~8 GB RAM free on the NAS — Dify runs ~15 containers; under ~4 GB the API
  container gets OOM-killed during DB migrations
- Internet access on the NAS (plugin marketplace, model calls out via OpenRouter)

## 1. Copy Dify onto the NAS

Container Manager cannot clone git — copy the **whole** `dify/docker/` directory
(it has bind-mounted config dirs, not just the compose file):

```bash
# from your Mac, repo sibling — or fresh clone:
git clone --depth 1 https://github.com/langgenius/dify.git
scp -r dify/docker nas:/volume1/docker/dify/
# or drag the docker/ folder into a \\NAS\docker share via Finder
```

## 2. Edit `.env` before first start

In `dify/docker/.env` (copy of `.env.example`):

```bash
SECRET_KEY=<openssl rand -base64 42>

# DSM's own web services already occupy 80/443 — move Dify's nginx:
EXPOSE_NGINX_PORT=8080
EXPOSE_NGINX_SSL_PORT=8443
```

Leave `CONSOLE_API_URL`/`APP_API_URL` empty — same-origin works when you reach
`http://<nas-ip>:8080`.

## 3. Create the project

Container Manager → **Project** → **Create**:

- Project name: `dify`
- Path: `/docker/dify` (the folder containing `docker-compose.yaml` + `.env`)
- It reads the compose file automatically → **Next → Build**

First pull is ~3 GB. `docker-local_sandbox-1` may restart-loop
(`-require-auth-token` flag bug in 1.17) — it only serves the optional agent
sandbox; the Code nodes used by this workflow run in `docker-sandbox-1`, so it
can be ignored or disabled.

## 4. Configure Dify

1. `http://<nas-ip>:8080/install` → create admin account
2. **Settings → Model Provider** → install OpenRouter plugin → add key
3. **Studio → Create from DSL** → import `dify/workflows/job-to-cv.yml`
4. **Publish** → **API Access** → create `app-…` key

## 5. Point your MCP server at the NAS

MCP stays on your Mac (stdio). In the host config:

```json
"env": {
  "DIFY_BASE_URL": "http://<nas-ip>:8080/v1",
  "DIFY_API_KEY": "app-...",
  "SSOT_PATH": "/Users/you/private/ssot.json",
  "OUTPUT_DIR": "/Users/you/private/job-out"
}
```

Your `ssot.json` never leaves your Mac — only the redacted profile reaches the
NAS.

## Optional: HTTPS via DSM reverse proxy

Control Panel → **Application Portal → Reverse Proxy** → source
`https://<nas-host>:443` → target `http://localhost:8080`. Then set
`CONSOLE_API_URL=https://<nas-host>` in `.env` and rebuild so generated links
are correct.

## Troubleshooting

| Symptom | Cause |
|---|---|
| nginx port bind fails | DSM owns 80/443 — set `EXPOSE_NGINX_PORT`/`EXPOSE_NGINX_SSL_PORT` |
| `api` restarts, `flask upgrade-db` killed | Not enough RAM — close other apps/VMs or upgrade |
| Plugin install fails | NAS can't reach `marketplace.dify.ai` — check DNS/proxy |
| `/v1` unreachable from Mac | Firewall rule on NAS for port 8080, or wrong IP/subnet |
