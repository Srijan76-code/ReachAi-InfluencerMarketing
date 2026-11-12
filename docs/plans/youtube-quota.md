# YouTube API quota increase: what to submit (F2.6)

The default quota is 10,000 units a day for the whole app. One creator search uses about 1,250 units (≈11 `search.list` calls at 100 units each, plus channel and video lookups), so the app can run about 8 searches a day in total. The increase is free but needs Google's **YouTube API Services Audit and Quota Extension Form** (find it from the YouTube Data API page in Google Cloud Console → Quotas, or search "YouTube API Services audit and quota extension form"). The form wording changes, so map these answers onto whatever it asks.

## Before submitting (checklist)
- [x] Stored YouTube data is refreshed or deleted within 30 days (`app/creators/refresh.py`, nightly; privacy page says so).
- [x] Terms of service link YouTube's Terms of Service; privacy policy links Google's Privacy Policy (added Nov 12).
- [x] Every creator name links back to the YouTube channel; we never download or re-host videos.
- [ ] Record a 2–3 minute screen video: sign in → create a brief → search runs → creators table and creator panel (YouTube stats shown) → Track tab (post views and comment summary). Upload it unlisted and paste the link in the form.
- [ ] Use the Google Cloud project that owns `YOUTUBE_API_KEY` (its project number is on the Cloud Console home page).

## Answers

**API client name:** ReachAI
**Website:** https://reach-ai-influencer-marketing.vercel.app (update when the own domain is live)
**Terms:** /terms · **Privacy:** /privacy

**What does your API client do?**
ReachAI helps small businesses and solo founders find YouTube creators whose audience fits their product, see a fair sponsorship price, contact them and track the sponsored videos. The founder writes a short brief; ReachAI searches public YouTube channels and videos, ranks the creators that fit, and later reads the public stats and comments of the sponsored video the creator posted, so the founder can see how it performed.

**Who uses it?** Business users (founders and small marketing teams), signed in with an account. It is not a consumer app and does not act on behalf of YouTube viewers; no YouTube user sign-in (OAuth) is used.

**Which API data do you use and why?**
- `search.list`: find channels and videos that match the brief's topic.
- `channels.list`: public channel details (name, subscriber count, country, description) to judge fit and size.
- `playlistItems.list` + `videos.list`: recent public uploads and their views, likes and comment counts, to measure typical performance and engagement.
- `commentThreads.list`: once, 3 days after a sponsored video goes live, the top public comments are summarised (how viewers reacted to the sponsorship) for that founder only.

**How is the data stored and refreshed?** Public channel and video statistics are cached in our database so the same channel is not fetched again for every search. A nightly job refreshes cached data or deletes it before 30 days; campaign results older than 30 days are updated from the refreshed data. No video or audio content is stored.

**How is it shown?** In the signed-in app only: a ranked creators table, a creator detail panel (stats with a link to the channel), and the Track tab for sponsored videos. Share links a founder creates show the same public stats to their teammates and never include contact details.

**Do you charge users?** Yes, a subscription for the service (finding creators, outreach and tracking). YouTube data is not sold or offered separately, and we don't charge for access to YouTube data.

**Quota requested:** 250,000 units/day.
Calculation (first 6 months):
| Use | Per day | Units |
|---|---|---|
| Creator searches (≈1,250 units each, reduced by our cache) | 180 | 225,000 |
| Nightly refresh of cached creators (≈1 unit each + batched lookups) | 15,000 creators | 16,000 |
| Track: daily stats for live sponsored videos + one-time comment reads | 3,000 videos | 9,000 |
| **Total** | | **250,000** |

Usage is capped in code: per-user daily search limits, credits per search, and a per-agent daily cap for searches started through our MCP server.
