import asyncio
import re
import numpy as np
import isodate
from datetime import datetime, timezone
from core.get_youtube_client import get_youtube_client
from utils.state import LLMState

try:
    from apify_client import ApifyClient

    APIFY_AVAILABLE = True
except ImportError:
    APIFY_AVAILABLE = False

EMAIL_PATTERN = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
INSTA_PATTERN = re.compile(r"(https?://(?:www\.)?instagram\.com/[\w\.]+)")
TWITTER_PATTERN = re.compile(r"(https?://(?:www\.)?twitter\.com/[\w\.]+)")

DEAD_CHANNEL_THRESHOLD_DAYS = 180
ZOMBIE_ENGAGEMENT_THRESHOLD = 0.005
MIN_ABSOLUTE_VIEWS = 200

INDUSTRY_VIEW_FLOORS = {
    "fintech": 1000,
    "saas": 1000,
    "edtech": 2000,
    "d2c": 5000,
    "agency": 500,
    "other": 2000,
}

CTR_BENCHMARKS = {
    "tech": 0.025,
    "fintech": 0.03,
    "vlog": 0.008,
    "gaming": 0.01,
    "other": 0.015,
}


def extract_socials(text, channel_id=None):
    socials = {"email": None, "instagram": None, "twitter": None}
    if text:
        socials["email"] = next(iter(EMAIL_PATTERN.findall(text)), None)
        socials["instagram"] = next(iter(INSTA_PATTERN.findall(text)), None)
        socials["twitter"] = next(iter(TWITTER_PATTERN.findall(text)), None)
    return socials


def calculate_advanced_metrics(videos, industry):
    if not videos:
        return None

    views = [v["views"] for v in videos]
    likes = [v["likes"] for v in videos]
    comments = [v["comments"] for v in videos]

    avg_views = int(np.mean(views))
    if avg_views < MIN_ABSOLUTE_VIEWS:
        return None

    std_dev = np.std(views)
    volatility = std_dev / avg_views if avg_views > 0 else 0
    reliability = (
        "High" if volatility < 0.5 else "Medium" if volatility < 1.0 else "Low"
    )

    total_eng = sum(likes) + sum(comments)
    total_views = sum(views)
    engagement_rate = (total_eng / total_views) if total_views > 0 else 0

    total_likes = sum(likes)
    talk_rate = sum(comments) / total_likes if total_likes > 0 else 0
    trust_score = min(int((talk_rate * 50) * 100), 100)

    ctr = CTR_BENCHMARKS.get(industry, 0.015)
    est_clicks = int(avg_views * ctr)

    return {
        "avg_views": avg_views,
        "volatility": round(volatility, 2),
        "reliability": reliability,
        "engagement_rate": round(engagement_rate * 100, 2),
        "raw_engagement": engagement_rate,
        "trust_score": trust_score,
        "forecast": f"~{est_clicks} clicks/video",
    }


def validate_channel_health(metrics, brand_details, last_upload_date):
    days_inactive = (datetime.now(timezone.utc) - last_upload_date).days
    if days_inactive > DEAD_CHANNEL_THRESHOLD_DAYS:
        return False, f"Inactive for {days_inactive} days"

    if metrics["raw_engagement"] < ZOMBIE_ENGAGEMENT_THRESHOLD:
        return False, f"Suspicious engagement ({metrics['engagement_rate']}%)"

    industry = brand_details.get("industry", "other")
    price_tier = brand_details.get("product_price_range", "medium ticket").lower()

    min_view_target = INDUSTRY_VIEW_FLOORS.get(industry, 2000)

    if "high ticket" in price_tier:
        min_view_target = min_view_target * 0.5
    elif "low ticket" in price_tier:
        min_view_target = min_view_target * 2.0

    if metrics["avg_views"] < min_view_target:
        return False, f"Too small for {industry} {price_tier}"

    return True, "Pass"


def process_channel(youtube, data, campaign_ctx):
    try:
        brand = campaign_ctx.get("brand", {})
        industry = brand.get("industry", "other")

        pl_res = (
            youtube.playlistItems()
            .list(
                part="contentDetails,snippet",
                playlistId=data["uploads_id"],
                maxResults=15,
            )
            .execute()
        )

        vid_ids = [i["contentDetails"]["videoId"] for i in pl_res.get("items", [])]
        if not vid_ids:
            return None

        v_res = (
            youtube.videos()
            .list(part="statistics,snippet,contentDetails", id=",".join(vid_ids))
            .execute()
        )

        video_data = []
        full_desc = data["description"]
        latest_date = None

        for v in v_res.get("items", []):
            stats = v["statistics"]
            snippet = v["snippet"]

            pub_date = isodate.parse_datetime(snippet["publishedAt"])
            if not latest_date or pub_date > latest_date:
                latest_date = pub_date

            full_desc += " " + snippet.get("description", "")

            video_data.append(
                {
                    "title": snippet["title"],
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                }
            )

        metrics = calculate_advanced_metrics(video_data, industry)
        if not metrics:
            return None

        is_valid, reason = validate_channel_health(metrics, brand, latest_date)
        if not is_valid:
            return None

        socials = extract_socials(full_desc, data["id"])

        fair_price = (metrics["avg_views"] / 1000) * data["estimated_cpm"]

        return {
            **data,
            "metrics": metrics,
            "socials": socials,
            "valuation": round(fair_price, 2),
            "recent_videos": [
                {"title": v["title"], "views": v["views"]} for v in video_data
            ],
            "rich_context": (
                f"Channel: {data['title']}. "
                f"Bio: {data['description'][:150]}. "
                f"Performance: {metrics['reliability']} Reliability, {metrics['trust_score']} Trust. "
                f"Recent Videos: {', '.join([v['title'] for v in video_data[:5]])}."
            ),
        }

    except Exception:
        return None


async def process_channel_safe(semaphore, youtube, c_data, campaign_ctx):
    async with semaphore:
        try:
            return await asyncio.to_thread(
                process_channel, youtube, c_data, campaign_ctx
            )
        except Exception as e:
            return None


async def channel_enrichment(state: LLMState):
    print("\n--- 3. ENRICHMENT ENGINE (Dynamic Health Check) ---")

    youtube = get_youtube_client()
    channels = state["filtered_channels"]
    campaign_ctx = state["campaign_context"]

    semaphore = asyncio.Semaphore(20)

    tasks = [
        asyncio.create_task(
            process_channel_safe(semaphore, youtube, c_data, campaign_ctx)
        )
        for c_data in channels.values()
    ]

    print(f"   > Spawning {len(tasks)} enrichment tasks...")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched = []
    for res in results:
        if isinstance(res, Exception):
            print(f"     [CRITICAL] Unhandled Task Error: {res}")
            continue
        if res is None:
            continue
        enriched.append(res)

    print(f"-> Successfully enriched {len(enriched)} profiles.")
    enriched.sort(key=lambda x: x.get("valuation", 0), reverse=True)

    return {"enriched_candidates": enriched}
