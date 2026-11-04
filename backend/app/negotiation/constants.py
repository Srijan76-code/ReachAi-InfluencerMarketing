"""The negotiation agent (spec §8.7, roadmap F7.9): Jev reads and decides, code guards the numbers, the LLM
writes. Everything a Jev answer can map to is listed here, so no price ever comes from a model."""

# What Jev may choose from (MOVES, STRUCTURES, COMMISSION_STEPS, CONCESSION_LEVELS, EXTRAS) lives with the other
# Jev questions in app/judge/constants.py (architecture rule 3). Below: what code does with the answers.
CONCESSION_SHARE = (0.0, 0.2, 0.35, 0.5, 0.7)  # by level
COMMISSION_FEE_TRADE = 1.5  # each % of commission takes 1.5% off the fee we'd otherwise offer
OPENING_FROM_LOW = 0.5  # our first offer starts halfway between the bottom and middle of the fair range
CEILING_OVER_FAIR = 1.15  # never offer more than 15% above the top of the fair range…
WALK_AWAY_MULTIPLE = 2.5  # …and suggest walking away when they ask more than this × the top
MAX_ROUNDS = 4
MIN_FEE = 5  # dollars
MAX_HISTORY_TURNS = 12  # turns shown to Jev and the writer
MAX_TURN_CHARS = 1500
