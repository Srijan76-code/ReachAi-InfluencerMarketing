"""Thresholds, limits and rubric weights for the reply agent (spec §8.6c). Humans tune these; nothing else
in app/replies holds a number that changes behaviour."""

MAX_REWRITES = 2  # write, then at most 2 rewrites from Jev's feedback (research: 2-3 passes is the useful cap)
MAX_HISTORY_TURNS = 20  # the whole conversation, up to this many messages (oldest dropped first)
MAX_TURN_CHARS = 1500
MAX_POSTS = 3  # the creator's latest posts shown to the writer
MAX_EXAMPLES = 4  # the founder's own messages shown as the voice to copy
MAX_MEMORY_FACTS = 30
MAX_STYLE_RULES = 10
MAX_LESSONS = 6
MAX_SENTENCES = 14  # sentences of a draft checked one by one for grounding
MAX_MESSAGE_CHARS = 1400

# --- Jev's rubric: a draft passes only when every check passes --------------------------------------------
GROUNDED_MIN = 0.7  # each sentence: supported by our facts, the conversation or their posts (or states no fact)
ANSWERS_MIN = 0.6  # addresses everything the creator asked
PROMISE_MAX = 0.35  # commits the brand to something nobody decided
RUDE_MAX = 0.3
TEMPLATE_MAX = 0.6  # reads like a template or AI-written email
ASK_READ_MIN = 0.6  # the price the writer says they asked for is what they wrote
VOICE_MIN_LEVEL = 1  # Score 0..3: at least "plausibly the founder"
FAIR_MIN_LEVEL = 1  # Score 0..3: the offer is not insulting for this creator
VALUE_MIN = 0.55  # the offer is a sensible use of the founder's money
SAFE_TO_SEND_MIN = 0.7  # Jev: the founder could send it as is
NEEDS_FOUNDER_FROM = 0.6  # the creator asked for something our sources don't hold → ask the founder
OPT_OUT_FROM = 0.8  # "stop emailing me": never contacted again
INJECTION_ABOVE = 0.5

# --- hard limits in code (safety only; Jev may make them stricter, never looser) --------------------------
CEILING_OVER_FAIR = 1.15  # never offer more than 15% above the top of the fair range, nor above the budget left
MAX_COMMISSION_PCT = 25
MIN_FEE = 5
LESSON_FROM_FAILS = 2  # a check failed this often for one founder → a standing rule in the writer's instructions

ACTIONS = ("reply", "counter", "accept", "close", "ask_founder", "wait", "new_contact")
