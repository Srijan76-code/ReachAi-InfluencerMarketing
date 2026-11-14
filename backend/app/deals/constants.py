"""Deal stages, terms and pricing adjustments (spec §8.1, §8.7). Starting values from market guides
(paid usage +20–50%, exclusivity +20–50%; see roadmap F7.7); tune them with real agreed prices."""

# Board columns, in order. "lost" is kept out of the board unless the user shows it.
STAGES = ("contacted", "negotiating", "agreed", "content", "live", "paid", "lost")
COMMITTED_STAGES = ("agreed", "content", "live", "paid")  # the price is a commitment from here on
POST_DUE_STAGES = ("agreed", "content")  # a post-by date in the past is overdue in these

# What the creator makes. Our fair range is for one sponsored segment inside a normal video
# ("integration"); other formats scale it.
DELIVERABLE_MULTIPLIER = {
    "integration": 1.0,
    "dedicated": 1.6,  # a whole video about the product
    "short": 0.5,
    "post": 1.0,
    "story": 0.35,
}
DEAL_TYPES = ("flat", "base_plus_commission", "affiliate", "gifted")
# Extra the brand pays for using the content beyond the creator's own channel
USAGE_UPLIFT = {"none": 0.0, "organic": 0.1, "paid_30": 0.3, "paid_60": 0.4, "paid_90": 0.5}
# Extra for the creator not working with competitors for N days
EXCLUSIVITY_UPLIFT = ((0, 0.0), (30, 0.2), (60, 0.25), (90, 0.3), (365, 0.5))  # (from days, uplift)

# Negotiation helper (spec §8.7)
WALK_AWAY_MULTIPLE = 2.0  # quote above 2× the top of the fair range: walk away (or counter at the top)
ROUND_TO = 5  # dollars
ROUND_SMALL_BELOW = 50  # prices under $50 round to the dollar (else "$10–$10" for small creators)
CONCESSION_SHARE = 0.4  # each later counter moves this share of the gap from our last offer toward their ask
MAX_ROUNDS = 3  # after this many offers from us, the next one is the final offer
QUOTE_EDIT_MERGE_SECONDS = 120  # quote edits this close together are one timeline entry
SUGGESTED_COMMISSION_PCT = 10  # base + commission deals for signup/sales goals
BASE_SHARE_WITH_COMMISSION = 0.7  # the base when offering base + commission, as a share of the counter

MAX_RATE = 10_000_000
MAX_NOTES_CHARS = 4000
MAX_REPLY_CHARS = 3000  # pasted creator reply sent to Jev

# How the founder reaches the creator (F7.10c). Email sends from Gmail; the others are copied and opened.
CHANNELS = ("email", "instagram", "twitter", "linkedin", "whatsapp", "other")
# When the creator gets paid, as agreed (words for the confirmation message)
PAY_WHEN = {
    "on_live": "when the post is live",
    "half_half": "half now, half when the post is live",
    "upfront": "before you post",
    "net_7": "within 7 days of the post going live",
}
MAX_POSTS = 10  # deliverables in one deal
TRACKING_SLUG_CHARS = 7
TRACKING_CODE_DIGITS = 2
