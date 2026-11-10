"""Sending and reading email from the founder's own Gmail (spec §7.5, roadmap F6.5). Free: Gmail API only."""

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
# send: send approved messages; readonly: read creators' replies in threads we started. Nothing else.
SCOPES = ("https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly")
CALLBACK_PATH = "/api/gmail/callback"

STATE_MAX_AGE_SECONDS = 600  # the Google sign-in must finish within 10 minutes
DAILY_SEND_CAP = 40  # new messages per inbox per day (spec §7.5 guardrail)
SYNC_EVERY_MINUTES = 2  # opening Deals re-checks a thread at most this often
SYNC_CRON = "*/30 * * * *"  # background check for replies (each run wakes the database, so not too often)
MAX_THREADS_PER_SYNC = 25
HTTP_TIMEOUT_SECONDS = 15
MAX_BODY_CHARS = 3000
