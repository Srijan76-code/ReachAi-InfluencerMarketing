from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.cache.memory import InMemoryCache
from langgraph.types import RetryPolicy, CachePolicy

from .utils.state import LLMState

from .nodes import (
    campaign_understanding,
    keyword_generator,
    youtube_search_gate,
    subscriber_filter,
    channel_enrichment,
    semantic_processor,
    reranker_node,
    final_scoring_node,
)



graph = StateGraph(LLMState)

graph.add_node("campaign_understanding", campaign_understanding, retry_policy=RetryPolicy())
graph.add_node("keyword_generator", keyword_generator, retry_policy=RetryPolicy())
graph.add_node("youtube_search_gate", youtube_search_gate, retry_policy=RetryPolicy())
graph.add_node("subscriber_filter", subscriber_filter, retry_policy=RetryPolicy())
graph.add_node("channel_enrichment", channel_enrichment, retry_policy=RetryPolicy(), cache_policy=CachePolicy(ttl=120))
graph.add_node("semantic_processor", semantic_processor, retry_policy=RetryPolicy())
graph.add_node("reranker_node", reranker_node, retry_policy=RetryPolicy())
graph.add_node("final_scoring_node", final_scoring_node, retry_policy=RetryPolicy())

graph.add_edge(START, "campaign_understanding")
graph.add_edge("campaign_understanding", "keyword_generator")
graph.add_edge("keyword_generator", "youtube_search_gate")
graph.add_edge("youtube_search_gate", "subscriber_filter")
graph.add_edge("subscriber_filter", "channel_enrichment")
graph.add_edge("channel_enrichment", "semantic_processor")
graph.add_edge("semantic_processor", "reranker_node")
graph.add_edge("reranker_node", "final_scoring_node")
graph.add_edge("final_scoring_node", END)

checkpointer = InMemorySaver()

workflow = graph.compile(
    checkpointer=checkpointer,
    cache=InMemoryCache(),
)
