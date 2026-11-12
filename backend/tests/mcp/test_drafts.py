from app.mcp.drafts import amounts_in, check_first_message

GOOD = ("Hi Krish, your LangChain Crash Course was the clearest walkthrough I've seen. We run DataLaunch, "
        "a 12-week bootcamp, and would love to work together. Open to a quick chat?")


def check(text, **kw):
    kw = {"brand_name": "DataLaunch", "creator_name": "Krish Naik", "fair_high": 200.0, **kw}
    return check_first_message(text, **kw)


def test_amounts_are_read_in_common_formats():
    assert sorted(amounts_in("$1.5k, 800 USD, ₹5,000 and Rs 20k")) == [800.0, 1500.0, 5000.0, 20000.0]
    assert amounts_in("a 12-week bootcamp for 3 months") == []


def test_a_good_message_passes():
    assert check(GOOD) == []
    assert check(GOOD, creator_name="Krish Naik") == []  # first name is enough


def test_price_above_the_fair_high_is_rejected_and_within_is_fine():
    assert any("fair-high" in e for e in check(GOOD + " We can pay $900."))
    assert check(GOOD + " We could offer $150.") == []


def test_any_price_is_rejected_when_there_is_no_fair_price():
    errors = check(GOOD + " We can pay $50.", fair_high=None)
    assert any("no fair price" in e for e in errors)


def test_placeholders_and_internal_terms_are_rejected():
    assert any("placeholder" in e for e in check("Hi [Name], " + GOOD))
    assert any("final_score" in e for e in check(GOOD + " Your final_score is high."))
    assert any("package" in e.lower() for e in check(GOOD + " We want one dedicated integration and pinned comment."))


def test_missing_names_openers_questions_and_links_are_rejected():
    assert any("brand" in e for e in check(GOOD.replace("DataLaunch", "our team")))
    assert any("by name" in e for e in check(GOOD.replace("Krish", "there")))
    assert any("stock opener" in e for e in check("Hope this email finds you well. " + GOOD))
    assert any("questions" in e for e in check(GOOD + " Why? When? Where?"))
    assert any("links" in e for e in check(GOOD + " https://a.co https://b.co https://c.co"))


def test_length_limits():
    assert any("too short" in e for e in check("Hi Krish from DataLaunch"))
    assert any("too long" in e for e in check(GOOD + " x" * 2000))
