# MCP agent access: live plan (F9)

Live task state for coding agents. Roadmap: `docs/ROADMAP.md` Phase 9. Design: `docs/TECHNICAL_SPEC.md` §15. Update the checklist as you go.

## Status
- **F9.1 done** (PR #57, branch `mcp-server`): server at `/api/mcp`, personal API keys, Clerk OAuth (built, unverified), 8 read/shortlist tools, Agents page, docs.
- **F9.2 built** (branch `mcp-write-tools`, based on `mcp-server`): write tools, setup files, prompts, inbox and Track read tools. Needs its PR and then F9.1b.
- **F9.1b steps 1–3 done (Nov 12)**: Clerk MCP server registered on the instance prod uses (audience claim and client ID metadata documents on), `MCP_PUBLIC_URL` and `APP_URL` set in Vercel production, migrations applied to Neon production (head `f6d4e9b3a2c8`). Left: steps 4–5 after deploy.

## Decisions (made by the user, Nov 10 2026)
| Question | Decision |
|---|---|
| Auth | Clerk OAuth + personal API keys |
| Who writes text | The user's agent writes; the server supplies facts and validates. Never sends. |
| Start a search from an agent | Allowed, but the tool is marked costly (agent must confirm with the user) and the server caps agent-started searches per user per day |
| Where agent drafts go | Into the creator's chat as a draft tagged `agent`, same place as the app's own drafts. Founder sends in the app. |
| Setup | `/llms.txt` + `/skill.md` + docs page. No CLI. |
| Extras in F9.2 | `/llms.txt`, `/skill.md`, slash prompts, read tools for Outreach inbox and Track |
| Out of scope | Sending, agreeing terms, marking paid (always need the founder in the app); MCP Apps (F9.3); directory listings (F9.4) |

## F9.2 checklist
- [x] Read how the app creates a run (`campaign.py` generate), drafts (`outreach/drafts.py`, `AgentProposal`) and the validator (`validate_bundle`); fit the tools to them
- [x] `create_campaign(brief)` + `start_search(campaign_id)`: cost-marked, daily cap, returns id to poll with `campaign_status`
- [x] `pitch_context(campaign_id, creator_id)`: facts, fair range, rules, creator text under `untrusted`
- [x] `save_draft(...)`: server validates numbers/claims, stores a draft tagged `agent` in the creator's chat
- [x] Read tools: inbox (who replied / waiting on you), deals, Track (spend, views, who is late)
- [x] Prompts: `/reachai-new-campaign`, `/reachai-draft-pitches`, `/reachai-check-inbox` (reply-all dropped: replies stay in the app, F9.2b)
- [x] `/llms.txt` and `/skill.md` served by the backend; the address comes from `MCP_PUBLIC_URL` only, never from request headers
- [x] Tests in `backend/tests/mcp/` (no live APIs); update ROADMAP, spec §15, docs `mcp.mdx` and changelog
- [x] Checks: `pytest tests -q` (376 pass), `npx tsc --noEmit`, `npm run build`; PR #58

## Clerk sign-in checklist (user action, F9.1b)
Needed before Claude/ChatGPT connectors can sign in. Taken from Clerk's MCP guide (Express version), so confirm names in the dashboard.
1. Clerk dashboard → Agents → MCP servers → Add MCP server. MCP URL = `https://<production host>/api/mcp`. Turn on "Allow public clients to connect".
2. Vercel env (backend): `CLERK_SECRET_KEY`, `MCP_PUBLIC_URL` (same URL as step 1), `APP_URL` (web app URL). `CLERK_ISSUER_URL` only if it differs from the host of `CLERK_JWKS_URL`. Optional: `MCP_RUNS_PER_DAY` (default 3).
3. Run `alembic upgrade head` on the production database (creates `api_keys` and `agent_runs`).
4. Redeploy, then check `https://<host>/.well-known/oauth-protected-resource/api/mcp` returns JSON served by the backend.
5. Add `https://<host>/api/mcp` in Claude (Customize → Connectors → Add custom connector) and sign in; tell the agent the result.

## Conventions to keep
- Tools return markdown (via `app/mcp/format.py`) plus structured data. Creator text only under `untrusted`.
- Expected errors raise `ToolError`; anything else is hidden from the model.
- Never log or return secrets. No AI attribution in commits, PRs or docs.
