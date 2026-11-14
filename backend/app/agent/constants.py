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
    "pitch",  # the first message to a creator, from a pitch run (one text per channel)
    "confirm_terms",  # after agreeing: what was agreed, their link and code (written by code)
)
MESSAGE_KINDS = ("send_counter", "agree", "follow_up", "chase_post", "mark_lost", "hold_terms", "pitch", "confirm_terms")  # approving one sends it
CHAT_KINDS = ("send_counter", "agree", "mark_lost", "follow_up", "hold_terms", "pitch", "confirm_terms", "chase_post")  # drafts shown in the chat's message box
OWN_KEYS = ("nego:", "pitch:", "confirm:", "bounce:")  # suggestions made outside the time-based generator: refresh leaves them alone

FOLLOW_UP_AFTER_DAYS = 4  # no answer this long after our last message → suggest a follow-up
MAX_FOLLOW_UPS = 2  # then stop (the second is a polite close)
CHASE_AGAIN_AFTER_DAYS = 3  # a late post is chased again after this many days
MAX_CHASES = 3
MAX_REPLY_EVENT_CHARS = 3000  # pasted reply kept on the timeline (untrusted, never shown to an LLM)

# --- autopilot (decided Nov 14): outreach runs by itself once the founder starts it ------------------------
# Sent without asking: first emails (unless the founder checks them first), follow-ups, late-post nudges, the
# agent's counter-offers and replies that keep agreed terms, and the confirmation after the founder agrees.
AUTO_KINDS = ("pitch", "follow_up", "chase_post", "send_counter", "hold_terms", "confirm_terms")
# Always the founder's call, with a notification: they accepted (Agree), they declined or opted out (mark lost).
DECISION_KINDS = ("agree", "mark_lost")
REPLY_DELAY_MINUTES = 10  # answer a creator ~10 minutes after they write, not in the same second
FIRST_EMAIL_GAP_MINUTES = (2, 6)  # random gap between two new conversations from one inbox
MAX_SENDS_PER_RUN = 60  # one background run sends at most this many, then the next run carries on
MAX_SLEEP_MINUTES = 30  # if nothing is due sooner, the run ends; the 30-minute check starts the next one
SEND_HOURS = (8, 19)  # first emails go out in the creator's daytime (their country's main time zone)
MAX_AUTO_FAILURES = 2  # a message that failed to send this often waits for the founder
COUNTRY_TZ = {
    "US": "America/New_York", "CA": "America/Toronto", "GB": "Europe/London", "IE": "Europe/Dublin",
    "IN": "Asia/Kolkata", "AU": "Australia/Sydney", "NZ": "Pacific/Auckland", "DE": "Europe/Berlin",
    "FR": "Europe/Paris", "ES": "Europe/Madrid", "IT": "Europe/Rome", "NL": "Europe/Amsterdam",
    "SE": "Europe/Stockholm", "NO": "Europe/Oslo", "DK": "Europe/Copenhagen", "FI": "Europe/Helsinki",
    "PL": "Europe/Warsaw", "PT": "Europe/Lisbon", "BR": "America/Sao_Paulo", "MX": "America/Mexico_City",
    "AR": "America/Argentina/Buenos_Aires", "SG": "Asia/Singapore", "MY": "Asia/Kuala_Lumpur",
    "ID": "Asia/Jakarta", "PH": "Asia/Manila", "AE": "Asia/Dubai", "SA": "Asia/Riyadh", "PK": "Asia/Karachi",
    "BD": "Asia/Dhaka", "NG": "Africa/Lagos", "KE": "Africa/Nairobi", "ZA": "Africa/Johannesburg",
    "JP": "Asia/Tokyo", "KR": "Asia/Seoul", "CN": "Asia/Shanghai", "HK": "Asia/Hong_Kong", "TW": "Asia/Taipei",
    "TH": "Asia/Bangkok", "VN": "Asia/Ho_Chi_Minh", "TR": "Europe/Istanbul", "IL": "Asia/Jerusalem",
    "EG": "Africa/Cairo", "CH": "Europe/Zurich", "AT": "Europe/Vienna", "BE": "Europe/Brussels",
}
# held: why autopilot left a message for the founder (shown in the chat and counted in the bell)
HELD = {
    "review_first": "You asked to check first emails before they go.",
    "needs_review": "The draft didn't pass the checks. Fix it and send it yourself.",
    "contacted_before": "You wrote to this address in another campaign recently.",
    "no_email": "No email address: send it as a DM.",
    "question": "They asked something only you can answer.",
    "needs_human": "Their message raises payment, contract or usage terms. Read it yourself.",
    "failed": "Sending failed twice. Check it and send it yourself.",
}
