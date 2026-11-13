"""Turns Jev's decision into exact terms, inside the founder's limits (architecture rule 2: numbers in code).
Jev chooses the move, the deal type, the commission step and how far to move; code only does the arithmetic
and enforces: never above the ceiling (a little over fair, and never over the budget left), never below what
we already offered, never accept more than the ceiling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.deals import negotiation as N
from app.negotiation import constants as NC
from app.negotiation.context import Facts, Offer

from app.judge import constants as K

SIGNAL_FROM = K.NEGOTIATION_SIGNAL_FROM


@dataclass
class Decision:
    action: str  # agree | counter | lost | none
    offer: Optional[Offer] = None
    structure: str = "flat"
    extra: str = "none"
    final: bool = False
    reasons: list = field(default_factory=list)  # plain words for the founder


def _round_within(fee: float, ceiling: int) -> int:
    """A tidy number (rounded up to $5) that never goes over the ceiling: rounding up past it is rounded down
    instead (found by fuzzing: $2,841 used to become $2,845, over the budget)."""
    tidy = N._round(fee)
    if tidy <= ceiling:
        return tidy
    step = 1 if ceiling < N.C.ROUND_SMALL_BELOW else N.C.ROUND_TO
    return max(NC.MIN_FEE, int(step * (ceiling // step)) or ceiling)


def their_ask(answers: dict, fee_options: dict, pct_options: dict, current_fee: Optional[float] = None) -> Optional[Offer]:
    """What they asked for, from Jev's picks among the amounts code found in their message. "$10 more" on top
    of a current price of $12 is an ask of $22 (Jev says whether the amount is extra; code adds it)."""
    fee_key, pct_key = answers.get("their_fee", "none"), answers.get("their_commission", "none")
    fee = int(fee_options[fee_key].replace("$", "").replace(",", "")) if fee_key in fee_options else None
    if fee is not None and current_fee and float(answers.get("ask_is_extra", 0) or 0) >= SIGNAL_FROM:
        fee = int(round(current_fee)) + fee
    pct = float(pct_options[pct_key].rstrip("%")) if pct_key in pct_options else 0.0
    return Offer(fee, pct) if fee is not None or pct else None


def hold(answers: dict, agreed: Offer, ask: Optional[Offer]) -> Decision:
    """After you agreed: the deal stays as agreed. If they ask for more, suggest a kind reply that holds the
    agreed terms (the founder can accept the new price instead)."""
    yes = lambda q: float(answers.get(q, 0) or 0) >= SIGNAL_FROM  # noqa: E731
    if answers.get("injection", 0) > K.NEGOTIATION_INJECTION_ABOVE:
        return Decision("none", reasons=["Their message looked like it was written to instruct an AI, so it was ignored. Read it yourself."])
    if yes("declined"):
        return Decision("lost", reasons=["They're pulling out of the agreed deal."])
    more = ask is not None and ((ask.fee or 0) > (agreed.fee or 0) or ask.commission_pct > agreed.commission_pct)
    if not more:
        return Decision("none", reasons=["They wrote after you agreed. Nothing about the price changed."])
    return Decision("hold", agreed, "fee_plus_commission" if agreed.commission_pct else "flat", final=True,
                    reasons=[f"You agreed {agreed.words()}. Now they ask {ask.words()}.", f"Hold {agreed.words()}, or accept the new price."])


def decide(answers: dict, f: Facts, ask: Optional[Offer]) -> Decision:
    """`answers`: {question: value} from Jev (noul → probability, choice → key, score → level index)."""
    yes = lambda q: float(answers.get(q, 0) or 0) >= SIGNAL_FROM  # noqa: E731
    if answers.get("injection", 0) > K.NEGOTIATION_INJECTION_ABOVE:
        return Decision("none", reasons=["Their message looked like it was written to instruct an AI, so it was ignored. Read it yourself."])
    if yes("declined"):
        return Decision("lost", reasons=["They're turning it down."])
    if not f.fair_high:
        return Decision("none", reasons=["There's no fair price for this creator yet, so ReachAI can't suggest numbers."])
    ceiling = f.fair_high * NC.CEILING_OVER_FAIR
    if f.budget_left is not None:
        ceiling = min(ceiling, f.budget_left)
    ceiling = max(NC.MIN_FEE, int(ceiling))
    last = f.last_offer
    if last and last.fee and f.budget_left is not None and last.fee > f.budget_left and not yes("agrees"):
        # other deals were agreed since: even repeating our last offer would go over the budget left
        return Decision("none", reasons=[f"Your last offer of {last.words()} is now more than the budget left "
                                         f"(${max(0.0, f.budget_left):,.0f}). Decide the next step yourself."])
    if last and last.fee and last.fee > ceiling:
        ceiling = int(last.fee)  # you already offered more than the usual limit: keep to it, never go back on it
    if yes("agrees") and last:
        return Decision("agree", last, "fee_plus_commission" if last.commission_pct else "flat",
                        reasons=[f"They accepted your offer of {last.words()}."])
    if ask is None and not last:
        return Decision("none", reasons=["No price yet. Ask for their rate, or wait for it."])
    ask = ask or (f.their_asks[-1] if f.their_asks else None)

    move = answers.get("move", "counter")
    structure = answers.get("structure", "flat")
    reasons = [f"They asked {ask.words()}." if ask else "They didn't give a new price."]
    if ask and ask.fee is not None and ask.fee > NC.WALK_AWAY_MULTIPLE * f.fair_high and move == "walk_away":
        return Decision("lost", reasons=reasons + [f"That's more than {NC.WALK_AWAY_MULTIPLE:g}× the fair price and they won't move."])
    if move == "walk_away" and last and f.round > NC.MAX_ROUNDS:
        return Decision("lost", reasons=reasons + ["You've made your final offer and they're still far apart."])

    # accept: only within the ceiling
    if move == "accept" and ask and ask.fee is not None and ask.fee <= ceiling:
        return Decision("agree", Offer(ask.fee, min(ask.commission_pct, 25.0)), structure,
                        answers.get("extra", "none"), reasons=reasons + ["That's within your limit, so accept it."])
    if move == "hold" and last:
        return Decision("counter", last, structure, answers.get("extra", "none"), final=True,
                        reasons=reasons + [f"Repeat your offer of {last.words()}: you've already moved."])

    # counter / restructure: Jev's choices → numbers
    pct = float(answers.get("commission", "0")) if structure in ("fee_plus_commission", "commission_only") else 0.0
    at_limit = False
    if structure == "commission_only":
        offer = Offer(None, max(pct, 10.0))
    else:
        mid = (f.fair_low + f.fair_high) / 2
        anchor = float(last.fee) if last and last.fee else f.fair_low + NC.OPENING_FROM_LOW * (mid - f.fair_low)
        target = float(ask.fee) if ask and ask.fee else float(f.fair_high)
        level = int(round(float(answers.get("concession", 1))))
        share = NC.CONCESSION_SHARE[max(0, min(level, len(NC.CONCESSION_SHARE) - 1))] if last else 0.0
        fee = anchor + share * max(0.0, target - anchor)
        if structure == "smaller_scope" and ask and ask.fee:
            fee = ask.fee
        if pct and structure == "fee_plus_commission":
            fee *= max(0.3, 1 - pct / 100 * NC.COMMISSION_FEE_TRADE)
        if last and last.fee and (last.commission_pct or 0) >= pct:
            fee = max(fee, float(last.fee))  # never go back on what we offered
        at_limit = fee >= ceiling  # capped: this is as far as we go (rounding may land a few dollars under)
        fee = max(NC.MIN_FEE, min(fee, ceiling))
        offer = Offer(_round_within(fee, ceiling), pct)
    if ask and ask.fee is not None and offer.fee is not None and offer.fee >= ask.fee and offer.commission_pct <= ask.commission_pct:
        return Decision("agree", Offer(ask.fee, ask.commission_pct), structure, reasons=reasons + ["Your offer would reach their price, so accept it."])
    final = f.round >= NC.MAX_ROUNDS or (offer.fee or 0) >= ceiling or (structure != "commission_only" and at_limit)
    label = {"flat": "a fixed fee", "fee_plus_commission": "a fee plus commission", "commission_only": "commission only",
             "smaller_scope": "their price with a smaller scope"}.get(structure, structure)
    reasons.append(f"Offer {label}: {offer.words()}" + (" (your final offer)." if final else "."))
    return Decision("counter", offer, structure, answers.get("extra", "none"), final, reasons)
