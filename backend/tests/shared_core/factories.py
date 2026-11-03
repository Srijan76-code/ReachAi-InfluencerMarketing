from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)


def post(i, views=10_000, likes=None, comments=None, days_ago=None, short=False, text=None):
    likes = int(views * 0.04) if likes is None and views is not None else (likes or 0)
    comments = int(likes * 0.05) if comments is None else comments
    return {
        "post_id": f"p{i}",
        "text": text or f"Video {i} about machine learning careers",
        "published_at": NOW - timedelta(days=days_ago if days_ago is not None else 3 + i * 7),
        "views": views,
        "likes": likes,
        "comments": comments,
        "is_short_form": short,
    }


def profile(platform="youtube", followers=200_000, posts=None, country="IN", **extra):
    return {
        "platform": platform,
        "platform_id": "UC123",
        "display_name": "Test Creator",
        "bio": "I teach machine learning to new graduates.",
        "followers": followers,
        "country": country,
        "recent_posts": posts if posts is not None else [post(i) for i in range(15)],
        **extra,
    }
