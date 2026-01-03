"""
Bracket analysis module for deck evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Set, Dict
import re
import unicodedata


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


def _canon(name: str) -> str:
    """
    Canonicalize card names so different punctuation/case still matches.
    - casefold
    - remove accents
    - normalize apostrophes/quotes
    - keep alnum, spaces, commas
    - collapse whitespace
    """
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = name.casefold()

    # normalize curly apostrophes/quotes to plain
    name = name.replace("'", "'").replace("'", "'").replace(""", '"').replace(""", '"')

    # strip weird punctuation except commas (commas matter for some legends)
    name = re.sub(r"[^a-z0-9 ,'-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---- Game Changers v1.1 (from your image) ----
_GAME_CHANGERS_V11: Set[str] = {
    # White
    "Drannith Magistrate",
    "Enlightened Tutor",
    "Humility",
    "Serra's Sanctum",
    "Smothering Tithe",
    "Teferi's Protection",
    # Blue
    "Consecrated Sphinx",
    "Cyclonic Rift",
    "Expropriate",
    "Force of Will",
    "Fierce Guardianship",
    "Gifts Ungiven",
    "Intuition",
    "Jin-Gitaxias, Core Augur",
    "Mystical Tutor",
    "Narset, Parter of Veils",
    "Rhystic Study",
    "Sway of the Stars",
    "Thassa's Oracle",
    "Urza, Lord High Artificer",
    # Black
    "Bolas's Citadel",
    "Braids, Cabal Minion",
    "Demonic Tutor",
    "Imperial Seal",
    "Necropotence",
    "Opposition Agent",
    "Orcish Bowmasters",
    "Tergrid, God of Fright",
    "Vampiric Tutor",
    "Ad Nauseam",
    # Red
    "Deflecting Swat",
    "Gamble",
    "Jeska's Will",
    "Underworld Breach",
    # Green
    "Crop Rotation",
    "Food Chain",
    "Gaea's Cradle",
    "Natural Order",
    "Seedborn Muse",
    "Survival of the Fittest",
    "Vorinclex, Voice of Hunger",
    "Worldly Tutor",
    # Multicolored
    "Aura Shards",
    "Coalition Victory",
    "Grand Arbiter Augustin IV",
    "Kinnan, Bonder Prodigy",
    "Yuriko, the Tiger's Shadow",
    "Notion Thief",
    "Winota, Joiner of Forces",
    # Colorless
    "Ancient Tomb",
    "Chrome Mox",
    "Field of the Dead",
    "Glacial Chasm",
    "Grim Monolith",
    "Lion's Eye Diamond",
    "Mana Vault",
    "Mishra's Workshop",
    "Mox Diamond",
    "Panoptic Mirror",
    "The One Ring",
    "The Tabernacle at Pendrell Vale",
}

# pre-canon for fast lookup
_GAME_CHANGERS_CANON: Dict[str, str] = {_canon(n): n for n in _GAME_CHANGERS_V11}


def find_game_changers(deck_cards: Iterable[str]) -> List[str]:
    """
    Returns the deck's card names that are Game Changers (preserving your input strings).
    """
    found: List[str] = []
    for card in deck_cards:
        c = _canon(card)
        if c in _GAME_CHANGERS_CANON:
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
    cEDH signposts that happen to be on your GC list.
    """
    canon = {_canon(x) for x in game_changers_found}

    signposts = {
        _canon("Ad Nauseam"),
        _canon("Thassa's Oracle"),
        _canon("Underworld Breach"),
        _canon("Lion's Eye Diamond"),
        _canon("Chrome Mox"),
        _canon("Mox Diamond"),
        _canon("Mana Vault"),
        _canon("Grim Monolith"),
        _canon("Force of Will"),
        _canon("Fierce Guardianship"),
        _canon("Demonic Tutor"),
        _canon("Vampiric Tutor"),
        _canon("Imperial Seal"),
        _canon("Intuition"),
        _canon("Gamble"),
        _canon("Kinnan, Bonder Prodigy"),
        _canon("Urza, Lord High Artificer"),
    }

    hits = len(canon & signposts)

    # Simple thresholds:
    # - 2+ signposts is often enough to warrant "possible cEDH"
    # - OR a lot of fast mana/tutors/interaction at once
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
