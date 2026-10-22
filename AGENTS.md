# Agent brief — job-apply-kit

Short map for coding agents. Execution conventions (commits, branches, PRs) live **in this file**.

## What this is

Open-source skeleton for a **self-hosted Dify Workflow** that turns a job ad into a
tailored CV + cover letter, with optional interview prep. The career profile lives in an
external **single source of truth (SSOT)**; the workflow sends the LLM a **redacted**
version and merges real PII back in a Code node after generation. See `README.md` and
`docs/architecture.md`.

## Layout

| Path | Role |
|------|------|
| `dify/workflows/job-to-cv.yml` | Real exported DSL — importable in Dify Studio |
| `dify/workflows/job-to-cv.yml.example` | Annotated spec stub for readers; intentionally not valid YAML (`var?` annotations) |
| `mcp/` | MCP server (Python, `mcp` SDK 2.x) — thin client over the Dify service API; SSOT is read server-side so tools take only the job ad |
| `examples/` | Fictional job ad + SSOT, PII-safe |
| `docs/` | Architecture notes |
| `.env.example` | Template only — no real values |

## Hard boundaries

1. **No real personal data** — examples, tests, and docs stay fictional. Never commit
   real résumés, identities, or career history.
2. **No secrets** — API keys live in the Dify provider settings / local env, never in
   the DSL or this repo.
3. **PII stays out of model context** — redaction happens before LLM nodes; the merge
   runs after. Do not rewire nodes so raw PII reaches a model.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`

- `type` — required: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `ci`, `perf`
- `scope` — required; short area: `dify`, `workflow`, `docs`, `examples`, `ci`, `repo`
- `summary` — imperative, lowercase after the colon, ≤72 chars total, no trailing period
- Body — optional; explain **why**, not a file list
- Subject line **ASCII-only** — CJK/emoji goes in the body

```text
✅ feat(workflow): add interview-prep branch to job-to-cv DSL
✅ docs(repo): document SSOT redaction contract

❌ Add interview prep                    # missing type(scope)
❌ feat: stuff                           # missing scope; vague
❌ feat(workflow): Added prep branch.    # past tense + trailing period
```

## Branch names

[Conventional Branch](https://conventionalbranch.org/) prefixes: `feat/…` (or `feature/…`),
`fix/…` (or `bugfix/…`), `hotfix/…`, `release/…`, `chore/…`. Slug is lowercase,
hyphen-separated — e.g. `fix/redact-node-empty-pii`. There is no `ci/`, `docs/`, or
`test/` branch — docs / CI / test-only work branches under `chore/…`. CI rejects PRs
whose head branch does not match.

## Pull requests

- **Title** — same format as commit subjects (`type(scope): summary`, ≤72 chars,
  ASCII-only). CI's `conventions` job rejects non-conforming titles and commit subjects.
- **Body** — follow `.github/pull_request_template.md`: `## Summary`, `#### Test plan`,
  plus the `ADR:` / `Breaking:` lines.

## Feature work

- **Never commit on `main`.** New work → fresh branch off latest `main`, one branch +
  PR per change.
- Dify DSL edits: keep `job-to-cv.yml` a real Studio export; document hand-built
  structure in the `.example` stub instead.
