# LevelForge API Contract

> **GENERATED FILE - do not hand-edit.**
> Regenerate with `python scripts/generate_api_contract.py` while the
> backend is running. Backend Agent owns this file.
>
> **Frontend Agent:** treat this as the single source of truth for
> endpoint shapes. Never invent an endpoint. If something you need is
> missing, ask Backend Agent to add it and regenerate - do not guess.

- **API title:** LevelForge API
- **API version:** 0.1.0
- **Generated:** 2026-09-09 21:32 UTC
- **Source:** `http://localhost:8000/openapi.json`

---

## Endpoints

### `GET /`

**Root**

*Tags:* `system`

| Status | Description |
|---|---|
| `200` | Successful Response |

---

### `GET /health`

**Health**

Liveness + dependency readiness.

Returns 200 only when Postgres AND Redis both genuinely respond;
otherwise 503 with per-dependency detail.

*Tags:* `system`

| Status | Description |
|---|---|
| `200` | Successful Response |

---
