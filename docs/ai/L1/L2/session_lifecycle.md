# Deep Dive — Session Lifecycle

> **When to Read This:** You are touching client-side join/leave logic, token renewal, the agent start/stop orchestration, or the RTM transcript/metrics pipeline. For the high-level picture see [02_architecture](../02_architecture.md).

## Browser orchestration overview

1. `LandingPage.tsx` calls `getConfig()` → receives `{ app_id, token, uid, channel_name, agent_uid }`.
2. `startAgent(channelName, rtcUid, userUid)` → receives `agent_id`.
3. `ConversationComponent.tsx` joins the RTC channel (mic published, audio subscribed).
4. RTM delivers transcript turns and pipeline metrics; `normalizeTranscript` maps `uid === '0'` to the local UID.
5. On hang-up: `stopAgent(agentId)` → RTC leave → RTM logout.

## Token + UID contract

- `GET /api/get_config` mints one Token007 for a concrete non-zero `uid`. Zero or negative UIDs are replaced by a random value server-side.
- The same token covers RTC + RTM; `agent_uid` is a separate random integer reserved for the agent.
- Tokens expire in 3600s. The current recipe does not refresh mid-session; long calls will disconnect at expiry.

## RTC / RTM ownership

- RTC (audio publish/subscribe) and RTM (transcript/metrics) lifecycle are owned by `web/` (`ConversationComponent.tsx`, `LandingPage.tsx`).
- The agent backend only starts and stops the Agora-managed session; it does not manage client-side RTC.

## Transcript normalization

`normalizeTranscript` in `web/src/lib/conversation.ts`:
- Maps `uid === '0'` items to the local user UID (speaker attribution).
- Normalizes spacing after punctuation.
- `getMessageList` filters out `TurnStatus.IN_PROGRESS` items for the finalized transcript display.
- `getCurrentInProgressMessage` returns the single in-progress turn for live display.

## Stop path

`Agent.stop()` in `server/src/agent.py`:
1. Pops `agent_id` from `_sessions`; if present, calls `session.stop()`.
2. If the session is not in `_sessions` (e.g. after a restart), falls back to `client.stop_agent(agent_id)` (stateless SDK call). `test_agent.py` covers both paths.

## Related L1

- [02_architecture](../02_architecture.md) · [06_interfaces](../06_interfaces.md)
