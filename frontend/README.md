# Conductor Frontend

Next.js 14 (App Router, TypeScript, Tailwind CSS) streaming chat client for
the LangGraph multi-agent backend.

## Development

```bash
npm install
npm run dev          # http://localhost:3000
```

Point the client at the API:

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Streaming chat

`components/ChatWindow.tsx` consumes the SSE endpoint:

```
POST /api/v1/conversations/{id}/messages/stream?content=...
Authorization: Bearer <jwt>
```

Backend events (`Application` type "ts/events"):
- `agent.started` → chip showing the working agent
- `token` → appended to the assistant bubbles in real time
- `done` / `error` / `usage`

Reference in `auth-hook.ts` for the bearer token from local storage.