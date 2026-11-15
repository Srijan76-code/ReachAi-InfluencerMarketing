"""The writer (spec §8.6c): the AI reads the whole context and writes the reply, choosing the move and, for a
counter-offer, the price. It follows app/replies/instructions.md. A rewrite gets Jev's scores as a separate
reviewer note, never mixed into the conversation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.billing.costs import CostContext
from app.replies import constants as R
from app.replies.context import ReplyContext

logger = logging.getLogger(__name__)
INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text()


class Price(BaseModel):
    fee: Optional[int] = Field(None, description="Fixed fee in dollars, or null for commission only")
    commission_pct: float = Field(0, description="Commission on sales or signups, 0-25")

    def words(self) -> str:
        if self.fee is None and self.commission_pct:
            return f"{self.commission_pct:g}% commission"
        fee = f"${self.fee:,}" if self.fee is not None else ""
        return f"{fee} + {self.commission_pct:g}% commission" if self.commission_pct else fee


class Draft(BaseModel):
    action: str = Field(description="One of: reply, counter, accept, close, ask_founder, wait, new_contact")
    message: str = Field("", description="The email, plain text. Empty for wait.")
    price: Optional[Price] = Field(None, description="Our offer, only for counter or accept")
    their_ask: Optional[Price] = Field(None, description="What they asked to be paid, copied from their message")
    facts_used: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list, description="Questions only the founder can answer")
    resume_on: Optional[str] = Field(None, description="YYYY-MM-DD, for wait")
    new_contact_email: Optional[str] = None
    strategy: str = Field("", description="One line: why this move")


def messages(ctx: ReplyContext, reviewer_note: Optional[dict] = None) -> list:
    from langchain_core.messages import HumanMessage, SystemMessage

    body = json.dumps(ctx.for_writer(), ensure_ascii=False, default=str)
    out = [SystemMessage(content=INSTRUCTIONS), HumanMessage(content=f"CONTEXT (JSON):\n{body}")]
    if reviewer_note:
        # the reviewer's verdict on the last draft: its own message, never part of the conversation
        out.append(HumanMessage(content="REVIEWER NOTE on your last draft (fix every point, then return a new draft):\n"
                                        + json.dumps(reviewer_note, ensure_ascii=False, default=str)))
    return out


async def write(ctx: ReplyContext, context: CostContext, reviewer_note: Optional[dict] = None) -> Optional[Draft]:
    from app.llm.client import LLMUnavailableError, achat

    try:
        draft = await achat("reply", messages(ctx, reviewer_note), Draft, context=context, temperature=0.5)
    except LLMUnavailableError:
        logger.warning("reply writer unavailable")
        return None
    if draft.action not in R.ACTIONS:
        draft.action = "ask_founder" if draft.missing_info else "reply"
    draft.message = (draft.message or "").strip()[: R.MAX_MESSAGE_CHARS * 2]
    return draft
