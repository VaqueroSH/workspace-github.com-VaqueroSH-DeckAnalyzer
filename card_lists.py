"""
Single source of truth for card classification lists.
All card names are stored in lowercase for consistent matching.

IMPORTANT: Use utils.canonicalize_name() for matching deck cards against these lists.
"""
from __future__ import annotations

from typing import Set, FrozenSet


# =========================================================================
# GAME CHANGERS v1.1 (Official Bracket Classification)
# Cards that automatically affect deck bracket classification.
# Source: Official EDH Bracket Guidelines v1.1
# =========================================================================
GAME_CHANGERS_V11: FrozenSet[str] = frozenset({
    # White
    "drannith magistrate",
    "enlightened tutor",
    "humility",
    "serra's sanctum",
    "smothering tithe",
    "teferi's protection",
    # Blue
    "consecrated sphinx",
    "cyclonic rift",
    "expropriate",
    "force of will",
    "fierce guardianship",
    "gifts ungiven",
    "intuition",
    "jin-gitaxias, core augur",
    "mystical tutor",
    "narset, parter of veils",
    "rhystic study",
    "sway of the stars",
    "thassa's oracle",
    "urza, lord high artificer",
    # Black
    "bolas's citadel",
    "braids, cabal minion",
    "demonic tutor",
    "imperial seal",
    "necropotence",
    "opposition agent",
    "orcish bowmasters",
    "tergrid, god of fright",
    "vampiric tutor",
    "ad nauseam",
    # Red
    "deflecting swat",
    "gamble",
    "jeska's will",
    "underworld breach",
    # Green
    "crop rotation",
    "food chain",
    "gaea's cradle",
    "natural order",
    "seedborn muse",
    "survival of the fittest",
    "vorinclex, voice of hunger",
    "worldly tutor",
    # Multicolored
    "aura shards",
    "coalition victory",
    "grand arbiter augustin iv",
    "kinnan, bonder prodigy",
    "yuriko, the tiger's shadow",
    "notion thief",
    "winota, joiner of forces",
    # Colorless
    "ancient tomb",
    "chrome mox",
    "field of the dead",
    "glacial chasm",
    "grim monolith",
    "lion's eye diamond",
    "mana vault",
    "mishra's workshop",
    "mox diamond",
    "panoptic mirror",
    "the one ring",
    "the tabernacle at pendrell vale",
})


# =========================================================================
# FAST MANA
# Cards that provide significant mana acceleration.
# =========================================================================
FAST_MANA: FrozenSet[str] = frozenset({
    # Moxen & Lotuses
    "mox diamond",
    "chrome mox",
    "mox opal",
    "mox amber",
    "jeweled lotus",
    "lotus petal",
    "lion's eye diamond",
    # Rocks that produce more than they cost
    "mana crypt",
    "sol ring",
    "mana vault",
    "grim monolith",
    "basalt monolith",
    "ancient tomb",
    # Rituals
    "dark ritual",
    "cabal ritual",
    "seething song",
    "desperate ritual",
    "pyretic ritual",
    "rite of flame",
    "culling the weak",
    # Green fast mana
    "elvish spirit guide",
    "simian spirit guide",
    "carpet of flowers",
    # Specific powerful mana producers
    "dockside extortionist",
    "jeska's will",
    "gaea's cradle",
    "serra's sanctum",
    "mishra's workshop",
})


# =========================================================================
# TUTORS (Search Library)
# Cards that tutor for specific cards or card types.
# =========================================================================
TUTORS: FrozenSet[str] = frozenset({
    # Universal Tutors
    "demonic tutor",
    "vampiric tutor",
    "imperial seal",
    "diabolic intent",
    "diabolic tutor",
    "grim tutor",
    # Creature Tutors
    "worldly tutor",
    "green sun's zenith",
    "finale of devastation",
    "chord of calling",
    "eldritch evolution",
    "neoform",
    "natural order",
    "pattern of rebirth",
    "survival of the fittest",
    "fauna shaman",
    # Artifact Tutors
    "enlightened tutor",
    "fabricate",
    "tezzeret the seeker",
    "whir of invention",
    "tribute mage",
    "trophy mage",
    "trinket mage",
    # Enchantment Tutors
    "idyllic tutor",
    "academy rector",
    "sterling grove",
    # Instant/Sorcery Tutors
    "mystical tutor",
    "personal tutor",
    "merchant scroll",
    "spellseeker",
    # Land Tutors
    "crop rotation",
    "expedition map",
    "sylvan scrying",
    "hour of promise",
    "tempt with discovery",
    # Red Tutors
    "gamble",
    "imperial recruiter",
    "recruiter of the guard",
    # Other
    "intuition",
    "gifts ungiven",
    "buried alive",
    "entomb",
    "final parting",
})


# =========================================================================
# DRAW ENGINES
# Cards that provide sustained card advantage.
# =========================================================================
DRAW_ENGINES: FrozenSet[str] = frozenset({
    # Blue Enchantments
    "rhystic study",
    "mystic remora",
    "consecrated sphinx",
    # Black Draw
    "necropotence",
    "phyrexian arena",
    "sign in blood",
    "read the bones",
    "night's whisper",
    "ad nauseam",
    "peer into the abyss",
    # White Draw
    "smothering tithe",
    "esper sentinel",
    "trouble in pairs",
    "land tax",
    # Green Draw
    "sylvan library",
    "greater good",
    "beast whisperer",
    "the great henge",
    "guardian project",
    # Artifact Draw
    "skullclamp",
    "the one ring",
    "staff of nin",
    # Wheels
    "wheel of fortune",
    "timetwister",
    "windfall",
    "echo of eons",
    "time spiral",
    # Creature-Based
    "toski, bearer of secrets",
    "ohran frostfang",
    "edric, spymaster of trest",
})


# =========================================================================
# FREE INTERACTION
# Counterspells and interaction that don't cost mana.
# =========================================================================
FREE_INTERACTION: FrozenSet[str] = frozenset({
    # Free Counterspells
    "force of will",
    "force of negation",
    "fierce guardianship",
    "pact of negation",
    "misdirection",
    "commandeer",
    "mental misstep",
    # Free Removal
    "deflecting swat",
    "deadly rollick",
    "flawless maneuver",
    "obscuring haze",
    # Free Protection
    "teferi's protection",
    "force of vigor",
    # Pacts
    "summoner's pact",
    "slaughter pact",
})


# =========================================================================
# SELECTION (Card Quality/Filtering)
# Cards that filter draws or improve card quality.
# =========================================================================
SELECTION: FrozenSet[str] = frozenset({
    "brainstorm",
    "ponder",
    "preordain",
    "serum visions",
    "opt",
    "consider",
    "impulse",
    "telling time",
    "frantic search",
    "faithless looting",
    "careful study",
    "chart a course",
    "scroll rack",
    "sensei's divining top",
    "sylvan library",
    "worldly tutor",
    "mystical tutor",
    "vampiric tutor",
})


# =========================================================================
# PROBLEMATIC CARDS
# Cards that may create unfun game experiences.
# =========================================================================
MLD_CARDS: FrozenSet[str] = frozenset({
    "armageddon",
    "ravages of war",
    "cataclysm",
    "catastrophe",
    "decree of annihilation",
    "obliterate",
    "jokulhaups",
    "ruination",
    "sunder",
    "global ruin",
    "epicenter",
    "wildfire",
    "burning of xinye",
    "death cloud",
    "boom // bust",
})

STAX_PIECES: FrozenSet[str] = frozenset({
    "winter orb",
    "static orb",
    "stasis",
    "smokestack",
    "tangle wire",
    "sphere of resistance",
    "thorn of amethyst",
    "trinisphere",
    "nether void",
    "the tabernacle at pendrell vale",
    "drannith magistrate",
    "rule of law",
    "arcane laboratory",
    "deafening silence",
    "rest in peace",
    "grafdigger's cage",
    "torpor orb",
    "cursed totem",
    "collector ouphe",
    "null rod",
    "vorinclex, voice of hunger",
    "grand arbiter augustin iv",
    "narset, parter of veils",
})

EXTRA_TURN_CARDS: FrozenSet[str] = frozenset({
    "time warp",
    "temporal manipulation",
    "time stretch",
    "expropriate",
    "walk the aeons",
    "capture of jingzhou",
    "temporal mastery",
    "nexus of fate",
    "karn's temporal sundering",
    "alchemist's gambit",
    "extra turn",
})

INFINITE_COMBO_PIECES: FrozenSet[str] = frozenset({
    "thassa's oracle",
    "demonic consultation",
    "tainted pact",
    "underworld breach",
    "lion's eye diamond",
    "brain freeze",
    "grinding station",
    "basalt monolith",
    "power artifact",
    "isochron scepter",
    "dramatic reversal",
    "deadeye navigator",
    "peregrine drake",
    "food chain",
    "squee, the immortal",
    "misthollow griffin",
    "eternal scourge",
    "niv-mizzet, parun",
    "curiosity",
    "ophidian eye",
    "tandem lookout",
    "heliod, sun-crowned",
    "walking ballista",
    "spike feeder",
})


# =========================================================================
# cEDH SIGNPOST CARDS
# Cards commonly found in competitive EDH decks.
# =========================================================================
CEDH_SIGNPOSTS: FrozenSet[str] = frozenset({
    "ad nauseam",
    "thassa's oracle",
    "underworld breach",
    "lion's eye diamond",
    "chrome mox",
    "mox diamond",
    "mana vault",
    "grim monolith",
    "force of will",
    "fierce guardianship",
    "demonic tutor",
    "vampiric tutor",
    "imperial seal",
    "intuition",
    "gamble",
    "kinnan, bonder prodigy",
    "urza, lord high artificer",
    "mana crypt",
    "jeweled lotus",
    "dockside extortionist",
    "tymna the weaver",
    "thrasios, triton hero",
    "kraum, ludevic's opus",
    "najeela, the blade-blossom",
    "kenrith, the returned king",
})


def is_game_changer(card_name: str) -> bool:
    """Check if a card is in the Game Changers v1.1 list."""
    from utils import canonicalize_name
    return canonicalize_name(card_name) in GAME_CHANGERS_V11


def is_fast_mana(card_name: str) -> bool:
    """Check if a card is fast mana."""
    from utils import canonicalize_name
    return canonicalize_name(card_name) in FAST_MANA


def is_tutor(card_name: str) -> bool:
    """Check if a card is a tutor."""
    from utils import canonicalize_name
    return canonicalize_name(card_name) in TUTORS


def is_draw_engine(card_name: str) -> bool:
    """Check if a card is a draw engine."""
    from utils import canonicalize_name
    return canonicalize_name(card_name) in DRAW_ENGINES


def is_free_interaction(card_name: str) -> bool:
    """Check if a card is free interaction."""
    from utils import canonicalize_name
    return canonicalize_name(card_name) in FREE_INTERACTION


def is_problematic(card_name: str) -> Set[str]:
    """
    Check if a card is in any problematic category.
    Returns set of categories the card belongs to.
    """
    from utils import canonicalize_name
    canonical = canonicalize_name(card_name)
    
    categories = set()
    if canonical in MLD_CARDS:
        categories.add("mld")
    if canonical in STAX_PIECES:
        categories.add("stax")
    if canonical in EXTRA_TURN_CARDS:
        categories.add("extra_turns")
    if canonical in INFINITE_COMBO_PIECES:
        categories.add("infinite_combo")
    
    return categories

