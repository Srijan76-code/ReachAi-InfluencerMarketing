"""Gmail helpers: encrypted tokens, signed sign-in state, the emails we build and the replies we read."""

import base64

import pytest

from app.gmail import crypto, mail


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")


def test_tokens_are_encrypted_and_need_the_same_secret(monkeypatch):
    enc = crypto.encrypt("1//refresh-token")
    assert "refresh" not in enc and crypto.decrypt(enc) == "1//refresh-token"
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "rotated")
    assert crypto.decrypt(enc) is None  # rotating the secret means reconnecting, never a crash


def test_no_secret_means_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET")
    with pytest.raises(crypto.NotConfigured):
        crypto.encrypt("x")


def test_state_is_signed_short_lived_and_tamper_proof():
    s = crypto.sign_state("u1", "/campaign/c1/deals", now=1000)
    assert crypto.verify_state(s, now=1100) ["u"] == "u1"
    assert crypto.verify_state(s, now=1000 + 601) is None  # older than 10 minutes
    body, mac = s.split(".")
    forged = base64.urlsafe_b64encode(b'{"u":"someone-else","r":"/","t":1000}').decode().rstrip("=")
    assert crypto.verify_state(f"{forged}.{mac}", now=1100) is None
    assert crypto.verify_state("garbage", now=1100) is None


def _decode(raw):
    return base64.urlsafe_b64decode(raw).decode()


def test_built_email_threads_and_strips_header_injection():
    raw = mail.build(sender="me@gmail.com", to="them@x.io\r\nBcc: evil@x.io", subject="Hi\nBcc: evil@x.io",
                     body="Hello", in_reply_to="<abc@mail.gmail.com>")
    text = _decode(raw)
    assert "In-Reply-To: <abc@mail.gmail.com>" in text and "References: <abc@mail.gmail.com>" in text
    assert "\nBcc:" not in text and "Hello" in text
    assert mail.reply_subject("Collab with ReachAI") == "Re: Collab with ReachAI" and mail.reply_subject("RE: x") == "RE: x"


def _msg(text, sender="Creator <them@x.io>"):
    data = base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
    return {"id": "m1", "payload": {"mimeType": "multipart/alternative", "headers": [{"name": "From", "value": sender}],
                                    "parts": [{"mimeType": "text/html", "body": {"data": "PGI+aGk8L2I+"}},
                                              {"mimeType": "text/plain", "body": {"data": data}}]}}


def test_reply_text_is_only_what_they_wrote():
    m = _msg("Sounds great, my rate is $300.\n\nThanks!\n\nOn Tue, Nov 4, 2026 at 10:00 PM Founder <me@gmail.com> wrote:\n> Hi there, our budget is $180")
    assert mail.reply_text(m) == "Sounds great, my rate is $300.\n\nThanks!"
    assert mail.sender_email(m) == "them@x.io"
