# Going live with agent access (F9.8 and what came before it)

What this ships, in the order to do it, how to check each step, and how to undo it. Everything below is on the branch
`brief-from-url`. Nothing has been tried against production or with a real agent client yet: this runbook is how
that first try is done safely.

## What ships
- Website box: paste your site, ReachAI fills the brief and asks only about what it isn't sure of (Jina + Jev).
- Over MCP the founder's agent uses its own AI: brief (`read_website`), search strategy, "why this creator" bullets, replies and follow-ups; ReachAI checks all of it.
- Agent sending (`send_message`): preview, the founder's yes, then send; first emails with their own permission.
- Device login (`/device`), personal keys on a short allowlist of web endpoints, `account_status`, `connect_gmail`, `buy_credits`.
- Permissions (`/grant`, Agents page), the campaign tools, and the `reachai` command (`cli/`, not published yet).

## 1. Before anything: environment (Vercel project settings)
| Variable | Needed for | Check |
|---|---|---|
| `APP_URL` | Every link an agent hands over (approval pages, Gmail connect, checkout return) and the emails to the founder | Must be the production origin, no trailing slash. A wrong value sends founders to the wrong site |
| `MCP_PUBLIC_URL` | MCP host check | Already set for F9.1; must match `APP_URL` + `/api/mcp` |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Gmail connect, sending, and signing the send preview token | Set already if Gmail works today. The redirect `APP_URL/api/gmail/callback` must be listed in Google Cloud |
| `TOKEN_ENCRYPTION_KEY` | Optional override of the key above | **Leave it unset if Gmail is already connected for anyone**: changing the key makes every stored Gmail token unreadable and everyone must reconnect |
| `JINA_API_KEY` | Website reading | Optional. Without it Jina allows about 20 reads a minute for all users together; add a free key before many founders try it |
| `AI_GATEWAY_API_KEY` (or the Vercel OIDC token), `GOOGLE_API_KEY`, `GROQ_API_KEY` | The `brief_from_site` route and every other AI route | Haiku 5.5 comes through the gateway. Without its key the backups answer (slower, a bit less careful) |
| `TYPESAFE_API_KEY` | Jev: field checks, strategy and bullet checks, reply checks | Without it ReachAI falls back to a plain AI judge: answers differ from the real Jev |
| `DODO_*`, `DODO_TEST_USERS` | `buy_credits` | In test mode only listed users can buy; the tool says "payments aren't open" for everyone else |
| `CLERK_SECRET_KEY`, `CLERK_JWKS_URL` | Website sign-in for the approval pages | Already set |
| `INNGEST_SIGNING_KEY`, `INNGEST_EVENT_KEY` | Background runs and the hourly `expire_agent_grants` | Already set |

## 2. Migrations (apply BEFORE deploying; they only add tables)
Vercel deploys don't run migrations (roadmap K8). Two new ones, in order:
1. `17d3bde3df1f` adds `device_codes` (device login).
2. `17a2c5c4c86d` adds `agent_grants` (permissions).

```sql
-- what production is at now (the last migration before these two is c5e7a9b1d3f4, the reply agent; expect that or older)
select version_num from alembic_version;
```
```bash
cd backend && DATABASE_URL=<production url, from a trusted machine> alembic upgrade head
```
Check afterwards: `select version_num from alembic_version;` shows `17a2c5c4c86d`, and `\d device_codes`, `\d agent_grants` list the tables. Old code ignores them, so applying first is safe. Undo: `alembic downgrade -1` twice drops them (only device codes and permissions are lost; nothing else uses them).
If production shows an older version, `alembic upgrade head` applies the missing ones first, in order: read what they are before you run it.

## 3. Deploy
1. Merge `brief-from-url` (open the pull request when you are ready; CI doesn't exist yet, so run the checks yourself: `cd backend && pytest tests -q`, `cd frontend && npx tsc --noEmit && npm run build`, `cd cli && npm test`).
2. Wait for the Vercel deploy. Then check the Inngest dashboard lists the new function `expire_agent_grants` (K23: re-sync the app if it doesn't).
3. Open `/llms.txt` on production: it should mention "device login".

## 4. Smoke test (about 5 minutes; it reads and asks, and with `--grant` it also creates a Track key on your first campaign)
```bash
cd cli
node bin/reachai.mjs login --client none --url https://<production> --name "smoke test"   # approve the code in your browser
node bin/reachai.mjs doctor --url https://<production>
node bin/reachai.mjs doctor --grant      # also asks for one permission: approve it on the page it prints
```
Every line should say PASS (the permission line says skip without `--grant`). `doctor` never starts a search, sends or changes a plan. Afterwards remove the "smoke test" key and the test permission on the Agents page, and run `node bin/reachai.mjs logout`.
A FAIL names the cause: a missing tool or a mention missing from `/llms.txt` means the new version isn't deployed; "expected 403" means a key can reach something it must not (stop and tell me).

## 5. With real agents (once each; use a throwaway campaign)
Use a test creator whose email is your own second address, so nothing reaches a stranger.
| Step | Do | Expect |
|---|---|---|
| Connect | Paste the line from the Agents page into Claude Code, then Codex and Cursor | It connects itself through the device login (or you sign in), and `account_status` answers |
| Brief | "Here is my website: ..." | It uses `read_website`, fills `create_campaign`, asks for the country, does not start a search |
| Search | "Find creators" | A preview with the cost and a strategy task; nothing starts until it writes a strategy and you agree |
| Links | "Connect my Gmail", "Buy 10 credits" | A link each; nothing happens until you open it; credits appear after paying (test mode) |
| Permission | "Add the best three to my deals" | It asks for `manage_campaign` and gives a link; `/grant` shows plain words; after Approve it works; after Remove on the Agents page it stops |
| Sending, ask | Allow `send_replies` (ask); reply to your own test email | A draft in the chat; `send_message` preview, you say yes, it sends; chat says "Sent by your agent"; you get the email and a bell line |
| Sending, unattended | Allow `send_replies` unattended with 1 a day | One message sends without asking; the second is refused with the limit message |
| Ends | Shorten a permission to 1 day, or remove it mid-run | The next send is refused with "permission ended" |

Write down anything that surprised you: that is the list of what to fix before opening to others.

## 6. Watch for the first week
- Vercel runtime errors (`get_runtime_errors`), especially `/api/device/*`, `/api/grants/*` and `/api/mcp`.
- `cost_events` with route `brief_from_site`: about a cent or less per read; a spike means someone is looping.
- `select count(*) from agent_grants where status = 'approved'` and `device_codes` created per hour (the per-IP limit is 10 an hour).
- Inngest: `expire_agent_grants` runs hourly and returns how many it ended.

## 7. The big red button
All agent access is keys. To cut every agent off at once (MCP and web endpoints), revoke every key:
```sql
update api_keys set revoked_at = now() where revoked_at is null;
```
They get 401 at once; founders reconnect with a new approval. To undo only one founder's grant, remove it on their Agents page (or set its `status` to `revoked`; the hourly job and the tools stop honouring it). Reverting the deploy is also safe: the new tables are additive.

## Not covered here (needs the owner)
- Publish the `reachai` package to npm (the name was free when checked on Nov 16): `cd cli && npm publish`, then move "coming soon" in the docs to shipped.
- Google's app verification before founders outside the 100 test users can connect Gmail (F6.5b).
- Your own domain, Clerk production, Dodo business verification (F2.5).
