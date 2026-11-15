"""Asking the founder by email: the email they get, and reading their answer from the thread."""

import base64

from app.replies.ask import email_body, founder_reply


def msg(text):
    data = base64.urlsafe_b64encode(text.encode()).decode()
    return {"payload": {"mimeType": "text/plain", "body": {"data": data}, "headers": []}}


def test_the_email_quotes_their_message_and_links_to_the_chat():
    body = email_body("Priya", ["Do you pay upfront?"], "Hey!   Do you pay upfront?", "https://app/campaign/c1/outreach")
    assert "- Do you pay upfront?" in body and "> Hey! Do you pay upfront?" in body and "https://app/campaign/c1/outreach" in body


def test_the_answer_is_the_founders_reply_without_the_quoted_question():
    thread = {"messages": [msg("Priya asked ..."), msg("Half upfront, half after.\n\nOn Mon, ReachAI wrote:\n> Priya asked ...")]}
    assert founder_reply(thread) == "Half upfront, half after."
    assert founder_reply({"messages": [msg("Priya asked ...")]}) is None  # no answer yet
