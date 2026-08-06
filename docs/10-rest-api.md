# 10 — REST API Design

Production-grade API surface. Versioned, authenticated, paginated, validated,
streaming, rate-limited, and documented via OpenAPI (`/docs`).

## 1. Conventions

- Prefix: `/api/v1` (version in path; breaking changes → `/v2`)
- Auth: `Authorization: Bearer <JWT>` (access, 30m) + refresh (7d)
- Errors: single envelope `{"error": {"code", "message", "details?"}}`
- Pagination: cursor-based (`?limit=50&cursor=...`) for lists
- Streaming: `text/event-stream` SSE, event names in `data:` frames
- Idempotency: `X-Idempotency-Key` header honored on writes
- Rate limits: per-user buckets enforced in gateway + API (429 envelope)

## 2. Endpoint catalog

### Auth
| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | create account | public |
| POST | `/api/v1/auth/login` | issue JWT pair | public |
| POST | `/api/v1/auth/refresh` | rotate refresh token | public |
| POST | `/api/v1/auth/logout` | revoke jti | JWT |

### Health
| GET | `/api/v1/health/live` | liveness | public |
| GET | `/api/v1/health/ready` | readiness (checks PG) | public |

### Documents
| POST | `/api/v1/workspaces/{w}/documents` | upload → 202 | member |
| GET | `/api/v1/workspaces/{w}/documents` | list | member |
| GET | `/api/v1/workspaces/{w}/documents/{id}/download` | presigned URL | viewer+ |

### Conversations
| POST | `/api/v1/workspaces/{w}/conversations` | create thread | member |
| GET | `/api/v1/workspaces/{w}/conversations/{id}` | detail | member |
| GET | `/api/v1/workspaces/{w}/conversations/{id}/messages` | history | member |
| POST | `/api/v1/workspaces/{w}/conversations/{id}/messages/stream` | SSE chat | member |
| POST | `/api/v1/workspaces/{w}/conversations/{id}/approve` | HITL resume | member |

### Usage & billing
| GET | `/api/v1/workspaces/{w}/usage/summary?from=...` | token/cost | admin |
| GET | `/api/v1/workspaces/{w}/usage/records?limit&cursor` | itemized | admin |
| GET | `/api/v1/workspaces/{w}/usage/daily` | time series | admin |

### Admin
| GET | `/api/v1/admin/audit-logs` | audit trail | platform admin |
| GET | `/api/v1/admin/workspaces` | tenant list | platform admin |

## 3. Request/response examples

### POST /api/v1/auth/login
```jsonc
// request
{ "email": "ava@midco.com", "password": "s3cret!" }
// 200
{
  "access_token": "eyJ...", "refresh_token": "eyJ...",
  "token_type": "bearer", "expires_in": 1800,
  "user": { "id": "uuid", "email": "ava@midco.com", "full_name": "Ava Analyst" }
}
```

### POST /api/v1/workspaces/{w}/documents (upload)
```jsonc
// 202 Accepted
{ "id": "uuid", "status": "pending" }
// poll GET .../documents → READY | FAILED
```

### POST /api/v1/workspaces/{w}/conversations/{id}/messages/stream
```text
POST .../messages/stream
Content-Type: application/json
{ "content": "Summarize the 2026 pricing changes in our refund policy" }

HTTP 200 text/event-stream
data: {"event":"agent_start","agent":"planner"}
data: {"event":"token","agent":"planner","delta":"I'll start by ..."}
data: {"event":"tool_call","tool":"retrieve_documents","args":{...}}
data: {"event":"evidence","notes":[...]}
data: {"event":"answer","answer":"...","citations":[...],"confidence":0.92}
data: {"event":"done"}
```

### Error envelope
```jsonc
// 429
{ "error": { "code": "rate_limited", "message": "Rate limit exceeded",
             "details": [{ "field": "conversation", "msg": "retry_after=30" }] } }
// 422
{ "error": { "code": "validation_error", "message": "Request validation failed",
             "details": [{ "field": "content", "msg": "Field required" }] } }
```

## 4. Validation & typing

- Every body is a Pydantic v2 schema; FastAPI enforces at the boundary.
- Schemas are shared with the frontend via generated TypeScript (`openapi-typescript`).
- Streaming endpoint validates before opening the SSE channel (fail fast).

## 5. Rate limiting

| Bucket | Limit | Enforced at |
|---|---|---|
| auth login | 5/min/IP | gateway |
| chat stream | 30/min/user | API (Redis) |
| document upload | 60/hr/user | API |
| LLM tokens/day | plan quota | usage service |

Redis `INCR+EXPIRE` counters; sliding window per (user, scope). Responses
include `X-RateLimit-Limit/Remaining/Reset`.

## 6. Streaming design

- `POST .../messages/stream` returns `text/event-stream`.
- Nginx SSE tweaks: `proxy_buffering off; proxy_read_timeout 300s;`.
- Client reconnect: `Last-Event-ID` re-request supported by thread checkpoint
  (LangGraph resume).
- `done` frame always terminates; `error` frame on pipeline failure.

## 7. Versioning & lifecycle

- Path versioning `/api/v1`; additive-only within a version.
- Deprecation: `Deprecation` header + sunset in OpenAPI; removals only in v2.
- OpenAPI exposed at `/openapi.json`; `docs` UI at `/docs`.