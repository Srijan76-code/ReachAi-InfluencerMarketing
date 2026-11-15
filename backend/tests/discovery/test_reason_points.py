"""The "Why this creator" bullets: code picks one fact per bullet, the model only words them (chosen Nov 15,
docs/MODEL_BENCHMARKS.md)."""

from app.discovery.legacy import to_legacy_lead
from app.discovery.prompts import reason_bullets
from app.discovery.reason_points import pick

HIGH = {"audience match": "high", "topic match": "high", "covers the audience's problems": "high"}


def test_strong_fit_with_a_proof_title_and_a_second_strength():
    p = pick(HIGH, ["rising"], "Strong Buy", goal="signups", metrics={"reliability": "High"},
             titles=["Gym day", "My 5AM morning routine"], topics=["morning routine"])
    assert p["why"].startswith("Their audience is the buyers") and p["proof"] == "My 5AM morning routine"
    assert p["watch"] == {"kind": "strength", "fact": "Their recent posts are doing better than usual"}
    assert p["choose"] == "A core creator for signups: book early, before their rate goes up"


def test_the_most_serious_weakness_wins():
    p = pick({**HIGH, "topic match": "low"}, ["suspicious", "country_unknown"], "Consider",
             competitor_promos=[{"brand": "Streaks", "posts": 2}], titles=["Habit app review"], topics=["habit"])
    assert p["watch"]["kind"] == "weakness" and "unusual" in p["watch"]["fact"]
    assert p["choose"] == "Only after they share their audience stats"
    assert p["proof"] is None  # off-topic: a title wouldn't prove anything


def test_a_competitor_counts_as_a_strength_when_the_brief_prefers_it():
    promos = [{"brand": "Streaks", "posts": 2}]
    assert pick(HIGH, ["competitor"], "Strong Buy", competitor_promos=promos)["watch"]["kind"] == "weakness"
    p = pick(HIGH, ["competitor"], "Strong Buy", competitor_promos=promos, competitor_mode="prefer")
    assert p["watch"]["kind"] == "strength" and "Streaks" in p["watch"]["fact"]


def test_avoid_and_no_weakness():
    assert pick({"audience match": "low", "topic match": "low"}, [], "Avoid")["choose"].startswith("Skip")
    assert pick(HIGH, [], "Strong Buy")["watch"]["fact"] == "No clear weakness in what we checked"


def test_bullets_are_parsed_and_kept_on_the_lead():
    text = "Sure!\n- Their viewers are the buyers.\n- Watch out: views swing a lot.\n- A small test deal first.\n"
    assert reason_bullets(text) == ["Their viewers are the buyers.", "Watch out: views swing a lot.", "A small test deal first."]
    assert reason_bullets("Just one sentence.") == []
    lead = to_legacy_lead({"platform_id": "UC1", "platform": "youtube"}, {}, {}, "- A.\n- B.\n- C.", "tech")
    assert lead["reason_points"] == ["A.", "B.", "C."] and lead["llm_reasoning"] == "A. B. C."
    old = to_legacy_lead({"platform_id": "UC1", "platform": "youtube"}, {}, {}, "One older sentence.", "tech")
    assert old["reason_points"] == [] and old["llm_reasoning"] == "One older sentence."
