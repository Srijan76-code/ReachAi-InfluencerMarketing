"""The agent's memory for one founder (spec §8.6c): facts they told it, rules about their style, and lessons from
Jev's checks. Everything here is visible to the founder and can be switched off (bad memories must not stick)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_memory import AgentMemory
from app.replies import constants as R

# a Jev check that failed → the standing rule the writer gets once it keeps failing
LESSON_TEXT = {
    "grounded": "Don't state anything that isn't in the facts, the conversation or their posts.",
    "answers": "Answer every question the creator asked, or list it in missing_info.",
    "promise": "Don't promise anything the founder hasn't decided (extra pay, reposts, dates, rights).",
    "rude": "Stay warm and respectful; no pressure.",
    "template": "Write like a person: no stock phrases or generic praise.",
    "voice": "Match the founder's own messages: their length, greeting and sign-off.",
    "price_rule": "Write the price exactly as decided, and no other amounts.",
    "fair": "Don't offer an amount that would feel insulting for a creator of this size.",
    "value": "Don't overpay: stay near the fair range unless there's a clear reason.",
}


@dataclass
class Memory:
    facts: list[dict] = field(default_factory=list)  # [{"id", "text"}]
    style_rules: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)


async def load(db: AsyncSession, user_id: str, campaign_id: Optional[str]) -> Memory:
    rows = (await db.execute(select(AgentMemory).where(
        AgentMemory.user_id == user_id, AgentMemory.active.is_(True),
        or_(AgentMemory.campaign_id.is_(None), AgentMemory.campaign_id == campaign_id))
        .order_by(AgentMemory.updated_at.desc()))).scalars().all()
    m = Memory()
    for r in rows:
        if r.kind == "fact" and len(m.facts) < R.MAX_MEMORY_FACTS:
            m.facts.append({"id": f"m:{r.memory_id[:8]}", "text": r.text})
        elif r.kind == "style" and len(m.style_rules) < R.MAX_STYLE_RULES:
            m.style_rules.append(r.text)
        elif r.kind == "lesson" and r.count >= R.LESSON_FROM_FAILS and len(m.lessons) < R.MAX_LESSONS:
            m.lessons.append(r.text)
    return m


async def remember_fact(db: AsyncSession, user_id: str, question: str, answer: str, campaign_id: Optional[str]) -> None:
    """The founder answered a creator's question: kept as a fact for every creator after (this campaign, or all
    of the founder's campaigns when it isn't campaign-specific; the founder can change that)."""
    text = f"{question.strip().rstrip('?')}? {answer.strip()}"
    db.add(AgentMemory(user_id=user_id, campaign_id=campaign_id, kind="fact", key=question[:200], text=text[:1500],
                       source="founder_answer"))


async def remember_style(db: AsyncSession, user_id: str, rule: str) -> None:
    rule = rule.strip()
    if not rule:
        return
    same = (await db.execute(select(AgentMemory).where(AgentMemory.user_id == user_id, AgentMemory.kind == "style",
                                                       AgentMemory.text == rule))).scalar_one_or_none()
    if same:
        same.count += 1
        same.active = True
    else:
        db.add(AgentMemory(user_id=user_id, kind="style", text=rule[:400], source="founder_edit"))


async def note_failures(db: AsyncSession, user_id: str, failed: list[str]) -> None:
    """Counts which checks this founder's drafts fail; a repeated one becomes a lesson for the writer."""
    for key in dict.fromkeys(failed):
        if key not in LESSON_TEXT:
            continue
        row = (await db.execute(select(AgentMemory).where(AgentMemory.user_id == user_id, AgentMemory.kind == "lesson",
                                                          AgentMemory.key == key))).scalar_one_or_none()
        if row:
            row.count += 1
        else:
            db.add(AgentMemory(user_id=user_id, kind="lesson", key=key, text=LESSON_TEXT[key], source="jev", count=1))
