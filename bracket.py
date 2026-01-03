"""
Bracket analysis module for deck evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Dict

from utils import canonicalize_name as _canon
from card_lists import GAME_CHANGERS_V11, CEDH_SIGNPOSTS


class Bracket(Enum):
    EXHIBITION_CORE = "Bracket 1-2 (Exhibition/Core)"
    UPGRADED = "Bracket 3 (Upgraded)"
    OPTIMIZED = "Bracket 4 (Optimized)"
    CEDH = "cEDH"


@dataclass(frozen=True)
class BracketResult:
    game_changer_count: int
    game_changers_found: List[str]          # original card names (your deck names)
    bracket_minimum: Bracket                # what bracket you MUST be in (per GC count rules)
    cedh_flag: bool                         # heuristic (optional)
    notes: List[str]
    
    @property
    def minimum_bracket(self) -> str:
        """Return bracket as simple string for UI display (B1, B2, B3, B4)."""
        if self.bracket_minimum == Bracket.EXHIBITION_CORE:
            return "B1-2"
        elif self.bracket_minimum == Bracket.UPGRADED:
            return "B3"
        elif self.bracket_minimum == Bracket.OPTIMIZED:
            return "B4"
        elif self.bracket_minimum == Bracket.CEDH:
            return "cEDH"
        return "Unknown"
    
    @property
    def is_cedh(self) -> bool:
        """Alias for cedh_flag for UI compatibility."""
        return self.cedh_flag


def find_game_changers(deck_cards: Iterable[str]) -> List[str]:
    """
    Returns the deck's card names that are Game Changers (preserving your input strings).
    Uses the official Game Changers v1.1 list from card_lists.py.
    """
    found: List[str] = []
    for card in deck_cards:
        c = _canon(card)
        if c in GAME_CHANGERS_V11:
            found.append(card)
    return found


def bracket_from_game_changers(gc_count: int) -> Bracket:
    """
    Strict rules you listed:
    - Bracket 1 & 2: 0 Game Changers
    - Bracket 3: 1-3 Game Changers
    - Bracket 4: 4+ Game Changers (unlimited)
    """
    if gc_count <= 0:
        return Bracket.EXHIBITION_CORE
    if gc_count <= 3:
        return Bracket.UPGRADED
    return Bracket.OPTIMIZED


def cedh_heuristic(game_changers_found: Iterable[str]) -> bool:
    """
    Not official. Just a quick "this smells like cEDH" detector based on common
    cEDH signposts. Uses CEDH_SIGNPOSTS from card_lists.py.
    """
    canon = {_canon(x) for x in game_changers_found}
    hits = len(canon & CEDH_SIGNPOSTS)

    # Simple thresholds:
    # - 2+ signposts is often enough to warrant "possible cEDH"
    return hits >= 2


def evaluate_bracket(deck_cards: Iterable[str]) -> BracketResult:
    gcs = find_game_changers(deck_cards)
    count = len(gcs)
    minimum = bracket_from_game_changers(count)
    cedh_flag = cedh_heuristic(gcs)

    notes: List[str] = []
    if minimum == Bracket.EXHIBITION_CORE and count == 0:
        notes.append("0 Game Changers found: eligible for Bracket 1-2 per rules.")
    elif minimum == Bracket.UPGRADED:
        notes.append("1–3 Game Changers found: Bracket 3 minimum per rules.")
    else:
        notes.append("4+ Game Changers found: Bracket 4 minimum per rules.")

    if cedh_flag:
        notes.append("cEDH heuristic flag tripped (not official): deck likely runs cEDH-style engines/fast mana/tutors.")

    return BracketResult(
        game_changer_count=count,
        game_changers_found=sorted(gcs, key=lambda x: _canon(x)),
        bracket_minimum=minimum,
        cedh_flag=cedh_flag,
        notes=notes,
    )
