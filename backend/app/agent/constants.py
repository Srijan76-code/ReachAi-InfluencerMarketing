"""The "Needs you" queue (spec §7.8, roadmap F6.8): when the agent suggests a next step. All in code."""

KINDS = (
    "send_counter",  # the negotiation agent's next offer
    "agree",  # the agent: their ask is acceptable, or they accepted our offer
    "follow_up",  # no answer since we last wrote
    "chase_post",  # the post-by date has passed and there's no post
    "mark_live",  # the post link is in: move to Live
    "mark_paid",  # the post is live: record the payment once the founder has paid
    "mark_lost",  # the agent: they turned it down, or it's not worth it (with a polite closing message)
    "hold_terms",  # the agent: after you agreed they ask for more; a kind reply keeping the agreed price
)
MESSAGE_KINDS = ("send_counter", "agree", "follow_up", "chase_post", "mark_lost", "hold_terms")  # approving one sends it
CHAT_KINDS = ("send_counter", "agree", "mark_lost", "follow_up", "hold_terms")  # drafts shown in the chat's message box

FOLLOW_UP_AFTER_DAYS = 4  # no answer this long after our last message → suggest a follow-up
MAX_FOLLOW_UPS = 2  # then stop (the second is a polite close)
CHASE_AGAIN_AFTER_DAYS = 3  # a late post is chased again after this many days
MAX_CHASES = 3
MAX_REPLY_EVENT_CHARS = 3000  # pasted reply kept on the timeline (untrusted, never shown to an LLM)
