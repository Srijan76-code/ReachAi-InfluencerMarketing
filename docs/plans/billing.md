# Billing: live plan (Phase 2)

Live task state for coding agents. Design: `docs/TECHNICAL_SPEC.md` §5. Roadmap: Phase 2 (F2.1–F2.6). Update the checklist as you go.

## Decisions (made by the user, Nov 12 2026)
| Question | Decision |
|---|---|
| Tax and payments | Dodo Payments as merchant of record (global tax, UPI, INR). Replaces Cashfree. Paddle is the fallback |
| Model | Subscription with credits + packs. Only creator searches cost credits; everything else unlimited on every plan |
| Credits per search | YouTube 1 · X 3 · Instagram 4 · LinkedIn 8 · "Find more" half |
| Plans | Free 3/mo · Solo $12 / ₹499, 25/mo · Pro $29 / ₹1,299, 80/mo · annual 2 months free · packs 10 = $8 (₹299), 30 = $20 (₹799), never expire |
| Extras in v1 | Welcome credits (5), refund guarantee (<10 creators), INR prices, referrals (10 each) |
| Not in v1 | Early-user price lock, other local currencies, teams |

## Build order (one PR each)
1. **F2.1 credits** (`billing-credits`): tables + migration, `app/billing/constants.py`, ledger (reserve/commit/release/refund, bucket order monthly → rollover → pack/bonus), lazy monthly grants with rollover, welcome credits, guarantee, reservation sweeper (Inngest), `/api/billing/balance`, cost check in `campaign_runs.start_run` (web + MCP), MCP `credits` tool and cost in `start_search`. Existing users get the Free plan + welcome credits. No money yet.
2. **F2.3 billing UI** (`billing-page`): credits pill, `/billing`, cost line by the Run button, inline "buy credits" (disabled until F2.2), public `/pricing`, `pricing.mdx`, changelog.
3. **F2.2 Dodo** (`dodo-payments`): products, checkout, webhooks (signature + `billing_events` idempotency), portal, past-due grace. Test mode only.
4. **F2.4 referrals** (`referrals`).
5. **F2.5 go live (user):** domain, Clerk production, Dodo verification, CA, refund policy; then `DODO_ENV=live`.

## Tests to write
- Concurrent reservations never overspend (Postgres, `PG_TEST_URL`).
- Failed run releases; guarantee refunds; commit never exceeds reserve.
- Month rollover: monthly expires, one month rolls over (paid only), packs untouched, grants idempotent.
- Webhooks: bad signature 401, duplicate event ignored, out-of-order renew/cancel handled.
- MCP `start_search` without `confirm` shows the cost and starts nothing.

## User actions
- [ ] Create a Dodo Payments account (test mode is enough to build); add `DODO_API_KEY` and `DODO_WEBHOOK_SECRET` in Vercel yourself (never paste keys in chat).
- [ ] Submit the YouTube quota form (`docs/plans/youtube-quota.md`).
- [ ] Domain, then CA on GST/LUT before live payments.
