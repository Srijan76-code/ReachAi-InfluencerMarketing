from dotenv import load_dotenv
import asyncio
from pprint import pprint

from langchain_core.runnables import RunnableConfig
from my_agent.agent import workflow

load_dotenv()

initial_state = {
    "brand": {
        "name": "DataLaunch",
        "website": "https://datalaunch.io",
        "industry": "edtech",
        "business_model": "b2c",
        "product_price_range": "high_ticket",
        "core_outcome": "A 12-week intensive Data Science bootcamp that guarantees a job or refunds tuition.",
    },
    "audience": {
        "target_persona": "Junior developers and fresh CS graduates looking to switch into AI/ML roles.",
        "locations": ["IN"],
        "languages": ["en", "hi"],
    },
    "campaign": {
        "goal": "signups",
        "creator_authority_level": "mentor",
        "platform": "youtube",
        "budget_total": 5000,
        "creator_count": 5,
    },
    "constraints": {
        "min_subscribers": 10000,
        "max_subscribers": 500000,
        "target_countries": ["IN"],
        "exclude_kids_content": True,
    },
}

async def main():
    config: RunnableConfig = {"configurable": {"thread_id": "1"}}
    final_state = await workflow.ainvoke(initial_state, config)
    pprint(final_state, width=120, depth=None)

asyncio.run(main())
