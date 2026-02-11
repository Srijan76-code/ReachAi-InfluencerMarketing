import asyncio
from core.get_youtube_client import get_youtube_client

from utils.state import LLMState

MAX_CONCURRENT_REQUESTS = 3

def _search_channels_blocking(keyword):

    youtube = get_youtube_client()
    req = youtube.search().list(
        part="snippet",
        q=keyword,
        type="channel",
        maxResults=50
    )
    res = req.execute()
    return {
        item["snippet"]["channelId"]
        for item in res.get("items", [])
    }

async def _search_with_limit(keyword, semaphore):
    async with semaphore:
        return await asyncio.to_thread(_search_channels_blocking, keyword)



async def youtube_search_gate(state: LLMState):

    keywords = state["search_keywords"][:10]  
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    tasks = [
        asyncio.create_task(_search_with_limit(keyword, semaphore))
        for keyword in keywords
    ]


    results = await asyncio.gather(*tasks, return_exceptions=True)

    found_ids = set()
    for r in results:
        if isinstance(r, Exception):
            continue
        found_ids.update(r)

    print(f"-> Found {len(found_ids)} unique raw candidates.")

    return {"candidate_channel_ids": list(found_ids)}












