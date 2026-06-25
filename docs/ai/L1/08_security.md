# 08 · Security

> Trust boundaries, secret handling, and auth for the custom-llm recipe.

## Trust boundaries

| Hop                              | Auth                                                                   |
| -------------------------------- | ---------------------------------------------------------------------- |
| Browser → agent backend          | None in local dev (the `/api/*` rewrite is same-origin).               |
| Agent backend → Agora cloud      | Token007, generated from `AGORA_APP_ID` + `AGORA_APP_CERTIFICATE`.     |
| Agora cloud → custom LLM endpoint | `Authorization: Bearer <CUSTOM_LLM_API_KEY>` (sent by Agora cloud). The mock does not validate it; **a production endpoint should**. |

## Secret handling

- **Server-only secrets:** `AGORA_APP_CERTIFICATE` and `CUSTOM_LLM_API_KEY` live only in `server/.env.local` and never reach the browser. The browser receives a short-lived token, never the certificate or the LLM key.
- `server/.env.local` is gitignored; `server/.env.example` ships placeholders only.
- Tokens (`generate_convo_ai_token`) expire after 3600s and are minted per `get_config` call for a concrete non-zero UID.

## Public backend surface

Because the backend must be publicly reachable for `/llm/chat/completions`, the token endpoints (`/get_config`, `/startAgent`, `/stopAgent`) are also exposed to the internet. They are **unauthenticated** in this recipe. Add auth, rate-limiting, or ingress access control before any real deployment.

## CORS

Both the agent backend and `llm.app` set `CORSMiddleware` with `allow_origins=["*"]` — open by design for a local/dev recipe. **Lock this down to known origins before any production deployment.**

## Validation

- `Agent.__init__` rejects missing `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `CUSTOM_LLM_URL`, or `CUSTOM_LLM_API_KEY` with `ValueError`.
- `Agent.start()` rejects empty `channel_name` and non-positive `agent_uid`/`user_uid` before issuing tokens.
- Route errors are sanitized: `_log_route_error` logs only non-`None` context; SDK exceptions map to 400/500 without leaking internals to the client beyond the message.

## Deployment notes

- Set `AGENT_BACKEND_URL` only to a backend you control; the rewrite forwards browser requests there verbatim.
- The published Docker image is **backend-only** (`:8000`); it does not bundle secrets.
- In production, the `CUSTOM_LLM_URL` endpoint (your `/llm/chat/completions` replacement) should validate `Authorization: Bearer` to prevent unauthorized LLM calls billed to your account.

## Related Deep Dives

- None.
