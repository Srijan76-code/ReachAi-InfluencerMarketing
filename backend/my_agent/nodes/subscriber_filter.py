from core.get_youtube_client  import get_youtube_client

from utils.state import LLMState
INDUSTRY_CPM = {
    "fintech": 35.0,
    "saas": 28.0,
    "edtech": 22.0,
    "tech": 15.0,
    "health": 12.0,
    "gaming": 6.0,
    "other": 8.0,
}


def get_geo_multiplier(country_code):
    tier_1 = ["US", "UK", "AU", "CA", "DE"]
    tier_2 = ["AE", "SG", "FR", "ES", "IT"]
    tier_3 = ["IN", "BR", "PH", "ID"]
    if country_code in tier_1:
        return 1.0
    if country_code in tier_2:
        return 0.6
    if country_code in tier_3:
        return 0.25
    return 0.5


def subscriber_filter(state: LLMState):
    print("\n--- 2. SUBSCRIBER & COUNTRY FILTER ---")
    youtube = get_youtube_client()
    ids = state.get("candidate_channel_ids", [])

    ctx = state.get("campaign_context", {})
    constraints = state.get("constraints", {})

    target_countries = constraints.get("target_countries", [])
    if target_countries:
        target_countries = [c.upper() for c in target_countries]
        print(f"   [Constraint] Allowed Countries: {target_countries}")

    min_subs = constraints.get("min_subscribers", 1000)
    industry = ctx.get("industry", "other")
    base_cpm = INDUSTRY_CPM.get(industry, 8.0)

    passed_channels = {}

    for i in range(0, len(ids), 50):
        batch_ids = ids[i : i + 50]
        try:
            res = (
                youtube.channels()
                .list(part="statistics,snippet,contentDetails", id=",".join(batch_ids))
                .execute()
            )

            for item in res.get("items", []):
                stats = item["statistics"]
                snippet = item["snippet"]
                cid = item["id"]

                channel_country = snippet.get("country", "Unknown").upper()

                if target_countries:
                    if channel_country not in target_countries:
                        continue

                subs = int(stats.get("subscriberCount", 0))
                if subs < min_subs:
                    continue

                video_count = int(stats.get("videoCount", 0))
                view_count = int(stats.get("viewCount", 0))

                if video_count < 5 or view_count == 0:
                    continue

                geo_mult = get_geo_multiplier(channel_country)
                estimated_cpm = round(base_cpm * geo_mult, 2)

                passed_channels[cid] = {
                    "id": cid,
                    "title": snippet["title"],
                    "description": snippet.get("description", ""),
                    "country": channel_country,
                    "uploads_id": item["contentDetails"]["relatedPlaylists"]["uploads"],
                    "subscribers": subs,
                    "video_count": video_count,
                    "estimated_cpm": estimated_cpm,
                    "lifetime_health": (
                        view_count / video_count if video_count > 0 else 0
                    ),
                }

        except Exception as e:
            print(f"Batch Filter Error: {e}")

    print(f"-> {len(passed_channels)} qualified channels (Geo + Size + Health).")
    return {"filtered_channels": passed_channels}
