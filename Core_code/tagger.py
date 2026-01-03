"""
Card tagging utility for Scryfall data.
Deterministic, composable, safe tag extraction from card JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Dict, Any, Set, List, Optional


# ===== TYPES =====

Card = Dict[str, Any]
TagSet = Set[str]
RuleFn = Callable[[Card], TagSet]


# ===== SAFE ACCESSORS =====

def _s(card: Card, key: str, default: str = "") -> str:
    """Get a string field safely."""
    val = card.get(key, default)
    return val if isinstance(val, str) else default


def _lst(card: Card, key: str) -> List[Any]:
    """Get a list field safely."""
    val = card.get(key, [])
    return val if isinstance(val, list) else []


def _lower(s: str) -> str:
    """Lowercase a string safely."""
    return s.lower() if isinstance(s, str) else ""


def _has_type(card: Card, needle: str) -> bool:
    """Check if card type_line contains a type."""
    # Scryfall type_line like: "Creature — Human Rogue"
    return needle.lower() in _lower(_s(card, "type_line"))


def _oracle_text(card: Card) -> str:
    """Get oracle text, handling double-faced cards."""
    # For DFC cards, Scryfall often has card_faces with oracle_text per face
    if "card_faces" in card and isinstance(card["card_faces"], list):
        parts = []
        for face in card["card_faces"]:
            if isinstance(face, dict):
                parts.append(_s(face, "oracle_text"))
        return "\n".join([p for p in parts if p])
    return _s(card, "oracle_text")


def _colors(card: Card) -> Set[str]:
    """Get card colors, with fallback to color_identity."""
    # Use colors if present; fallback to color_identity
    cols = card.get("colors")
    if isinstance(cols, list) and cols:
        return set([c for c in cols if isinstance(c, str)])
    cid = card.get("color_identity")
    if isinstance(cid, list):
        return set([c for c in cid if isinstance(c, str)])
    return set()


def _cmc(card: Card) -> float:
    """Get converted mana cost safely."""
    cmc = card.get("cmc", 0)
    if isinstance(cmc, (int, float)):
        return float(cmc)
    return 0.0


def _mana_value_bucket(mv: float) -> str:
    """Convert mana value to bucket tag."""
    # Simple buckets you can align with curve_eval later
    if mv <= 1:
        return "mv_0_1"
    if mv <= 3:
        return "mv_2_3"
    if mv <= 5:
        return "mv_4_5"
    return "mv_6_plus"


def _is_permanent(card: Card) -> bool:
    """Check if card is a permanent type."""
    tl = _lower(_s(card, "type_line"))
    # Instants/Sorceries are non-permanents; everything else generally is
    return ("instant" not in tl) and ("sorcery" not in tl)


def _is_land(card: Card) -> bool:
    """Check if card is a land."""
    return _has_type(card, "Land")


def _is_creature(card: Card) -> bool:
    """Check if card is a creature."""
    return _has_type(card, "Creature")


def _is_artifact(card: Card) -> bool:
    """Check if card is an artifact."""
    return _has_type(card, "Artifact")


def _is_enchantment(card: Card) -> bool:
    """Check if card is an enchantment."""
    return _has_type(card, "Enchantment")


def _is_instant(card: Card) -> bool:
    """Check if card is an instant."""
    return _has_type(card, "Instant")


def _is_sorcery(card: Card) -> bool:
    """Check if card is a sorcery."""
    return _has_type(card, "Sorcery")


def _is_planeswalker(card: Card) -> bool:
    """Check if card is a planeswalker."""
    return _has_type(card, "Planeswalker")


# ===== TAGGING RULES =====

@dataclass(frozen=True)
class Rule:
    """A tagging rule with name and function."""
    name: str
    fn: RuleFn


def rule_basic_types(card: Card) -> TagSet:
    """Tag basic card types."""
    tags: TagSet = set()
    if _is_land(card):
        tags.add("type_land")
    if _is_creature(card):
        tags.add("type_creature")
    if _is_artifact(card):
        tags.add("type_artifact")
    if _is_enchantment(card):
        tags.add("type_enchantment")
    if _is_instant(card):
        tags.add("type_instant")
    if _is_sorcery(card):
        tags.add("type_sorcery")
    if _is_planeswalker(card):
        tags.add("type_planeswalker")
    if _is_permanent(card):
        tags.add("is_permanent")
    else:
        tags.add("is_nonpermanent")
    return tags


def rule_mana_value(card: Card) -> TagSet:
    """Tag mana value (exact and bucketed)."""
    mv = _cmc(card)
    return {f"mv:{int(mv)}", _mana_value_bucket(mv)}


def rule_color_identity(card: Card) -> TagSet:
    """Tag color identity."""
    cols = _colors(card)
    if not cols:
        return {"colorless"}
    if len(cols) == 1:
        color = next(iter(cols)).lower()
        return {f"mono_{color}", f"color_{color}"}
    # Multicolor
    color_str = ''.join(sorted([c.lower() for c in cols]))
    return {f"colors_{color_str}", "multicolor"}


def rule_keywords(card: Card) -> TagSet:
    """Tag keywords from Scryfall keywords list."""
    tags: TagSet = set()
    for kw in _lst(card, "keywords"):
        if isinstance(kw, str) and kw.strip():
            # Normalize keyword: "Double Strike" → "kw:double_strike"
            normalized = kw.strip().lower().replace(' ', '_')
            tags.add(f"kw:{normalized}")
    return tags


def rule_simple_oracle_signals(card: Card) -> TagSet:
    """
    Conservative oracle text signals.
    Keep this small to avoid false positives.
    """
    t = _lower(_oracle_text(card))
    tags: TagSet = set()
    
    # Ramp signals (conservative)
    if "search your library for a land" in t or "search your library for up to" in t and "land" in t:
        tags.add("ramp:land_tutor")
    if "add " in t and any(mana in t for mana in ["{g}", "{u}", "{b}", "{r}", "{w}", "{c}"]):
        tags.add("mana:produces")
    
    # Draw signals
    if "draw a card" in t:
        tags.add("draw:explicit")
    if "draw two cards" in t or "draw 2 cards" in t:
        tags.add("draw:two_plus")
    if "draw three cards" in t or "draw 3 cards" in t:
        tags.add("draw:three_plus")
    
    # Removal signals (basic)
    if "destroy target" in t:
        tags.add("interaction:destroy")
    if "exile target" in t:
        tags.add("interaction:exile")
    if "destroy target" in t or "exile target" in t:
        tags.add("interaction:spot_removal")
    
    # Counterspell
    if "counter target spell" in t:
        tags.add("interaction:counterspell")
    
    # Board wipes
    if "destroy all creatures" in t or "destroy all permanents" in t:
        tags.add("interaction:boardwipe")
    if "exile all creatures" in t or "exile all permanents" in t:
        tags.add("interaction:boardwipe")
    
    # Pressure/drain
    if "each opponent" in t and ("sacrifice" in t or "discard" in t or "loses" in t):
        tags.add("pressure:each_opponent")
    
    # Tutors
    if "search your library" in t and "shuffle" in t:
        tags.add("tutor:library_search")
    
    # Token production
    if "create" in t and "token" in t:
        tags.add("creates_tokens")
    
    # Sacrifice outlets
    if "sacrifice a creature" in t or "sacrifice an artifact" in t:
        tags.add("sac_outlet")
    
    # Graveyard recursion
    if "return" in t and "from your graveyard" in t:
        tags.add("recursion:graveyard")
    
    # Win conditions
    if "you win the game" in t:
        tags.add("wincon:instant_win")
    if "target player loses the game" in t or "each opponent loses the game" in t:
        tags.add("wincon:instant_win")
    
    return tags


def rule_game_changers(card: Card) -> TagSet:
    """Tag known Game Changer cards."""
    # This list should match your bracket.py game changers list
    name = _lower(_s(card, "name"))
    
    GAME_CHANGERS = {
        "ancient tomb", "mana crypt", "jeweled lotus", "grim monolith", "mana vault",
        "chrome mox", "mox diamond", "mox opal", "lion's eye diamond", "lotus petal",
        "rhystic study", "mystic remora", "smothering tithe", "necropotence",
        "esper sentinel", "trouble in pairs", "phyrexian arena",
        "demonic tutor", "vampiric tutor", "imperial seal", "mystical tutor",
        "enlightened tutor", "worldly tutor", "gamble",
        "force of will", "force of negation", "fierce guardianship", "deflecting swat",
        "pact of negation", "mana drain", "swan song", "counterspell",
        "swords to plowshares", "path to exile", "anguished unmaking", "generous gift",
        "beast within", "chaos warp", "cyclonic rift", "deadly rollick",
        "dockside extortionist", "thassa's oracle", "underworld breach",
        "ad nauseam", "peer into the abyss", "necrologia",
        "wheel of fortune", "timetwister", "time spiral", "echo of eons",
        "craterhoof behemoth", "triumph of the hordes", "finale of devastation",
        "expropriate", "insurrection"
    }
    
    if name in GAME_CHANGERS:
        return {"game_changer"}
    return set()


def rule_fast_mana(card: Card) -> TagSet:
    """Tag fast mana (0-1 CMC that produces mana)."""
    tags: TagSet = set()
    mv = _cmc(card)
    t = _lower(_oracle_text(card))
    
    if mv <= 1 and ("add " in t and any(mana in t for mana in ["{g}", "{u}", "{b}", "{r}", "{w}", "{c}"])):
        tags.add("fast_mana")
    
    # Also tag known fast mana by name
    name = _lower(_s(card, "name"))
    if name in {"mana crypt", "jeweled lotus", "chrome mox", "mox diamond", 
                "mox opal", "mox amber", "lion's eye diamond", "lotus petal",
                "sol ring", "mana vault", "ancient tomb"}:
        tags.add("fast_mana")
    
    return tags


def rule_problematic_cards(card: Card) -> TagSet:
    """Tag cards that commonly cause salt/issues."""
    tags: TagSet = set()
    name = _lower(_s(card, "name"))
    t = _lower(_oracle_text(card))
    
    # Extra turns
    if "take an extra turn" in t or "extra turn" in t:
        tags.add("extra_turns")
    if name in {"time warp", "temporal manipulation", "time stretch"}:
        tags.add("extra_turns")
    
    # Mass land destruction
    if "destroy all lands" in t or "destroy all land" in t:
        tags.add("mld")
    if name in {"armageddon", "ravages of war", "jokulhaups", "obliterate"}:
        tags.add("mld")
    
    # Stax pieces
    if any(pattern in t for pattern in ["players can't", "opponents can't", "skip your untap", "can't untap"]):
        tags.add("stax")
    if name in {"winter orb", "static orb", "trinisphere", "rule of law"}:
        tags.add("stax")
    
    return tags


# Default rule set
DEFAULT_RULES: List[Rule] = [
    Rule("basic_types", rule_basic_types),
    Rule("mana_value", rule_mana_value),
    Rule("color_identity", rule_color_identity),
    Rule("keywords", rule_keywords),
    Rule("simple_oracle_signals", rule_simple_oracle_signals),
    Rule("game_changers", rule_game_changers),
    Rule("fast_mana", rule_fast_mana),
    Rule("problematic_cards", rule_problematic_cards),
]


# ===== PUBLIC API =====

def tag_card(card: Card, rules: Optional[Iterable[Rule]] = None) -> TagSet:
    """
    Tag a single Scryfall card object (dict).
    
    Args:
        card: Scryfall card dictionary
        rules: Optional custom rule set (uses defaults if None)
        
    Returns:
        Set of string tags
    """
    if rules is None:
        rules = DEFAULT_RULES
    
    tags: TagSet = set()
    for rule in rules:
        try:
            tags |= rule.fn(card)
        except Exception:
            # Keep tagging resilient; one bad card field shouldn't kill your run
            tags.add(f"tagger_error:{rule.name}")
    return tags


def tag_many(cards: Iterable[Card], rules: Optional[Iterable[Rule]] = None) -> Dict[str, TagSet]:
    """
    Tag many cards at once.
    
    Args:
        cards: Iterable of Scryfall card dictionaries
        rules: Optional custom rule set
        
    Returns:
        Dictionary mapping card name to tags
    """
    out: Dict[str, TagSet] = {}
    for c in cards:
        name = _s(c, "name", default="(unknown)")
        out[name] = tag_card(c, rules=rules)
    return out


def merge_tags(existing: TagSet, new: TagSet) -> TagSet:
    """
    Merge two tag sets.
    
    Args:
        existing: Existing tag set
        new: New tags to add
        
    Returns:
        Combined tag set
    """
    return set(existing) | set(new)


def filter_by_tag(card_tags: Dict[str, TagSet], tag: str) -> List[str]:
    """
    Get all card names that have a specific tag.
    
    Args:
        card_tags: Dictionary from tag_many()
        tag: Tag to filter by
        
    Returns:
        List of card names
    """
    return [name for name, tags in card_tags.items() if tag in tags]


def count_tag(card_tags: Dict[str, TagSet], tag: str) -> int:
    """
    Count how many cards have a specific tag.
    
    Args:
        card_tags: Dictionary from tag_many()
        tag: Tag to count
        
    Returns:
        Count of cards with that tag
    """
    return len(filter_by_tag(card_tags, tag))


# ===== QUICK SANITY CHECK =====

if __name__ == "__main__":
    # Minimal fake card examples (mimics Scryfall shape)
    
    cultivate = {
        "name": "Cultivate",
        "type_line": "Sorcery",
        "cmc": 3,
        "color_identity": ["G"],
        "keywords": [],
        "oracle_text": "Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle."
    }
    
    sol_ring = {
        "name": "Sol Ring",
        "type_line": "Artifact",
        "cmc": 1,
        "color_identity": [],
        "keywords": [],
        "oracle_text": "{T}: Add {C}{C}."
    }
    
    rhystic_study = {
        "name": "Rhystic Study",
        "type_line": "Enchantment",
        "cmc": 3,
        "color_identity": ["U"],
        "keywords": [],
        "oracle_text": "Whenever an opponent casts a spell, you may draw a card unless that player pays {1}."
    }
    
    print("Cultivate tags:")
    print(sorted(tag_card(cultivate)))
    print()
    
    print("Sol Ring tags:")
    print(sorted(tag_card(sol_ring)))
    print()
    
    print("Rhystic Study tags:")
    print(sorted(tag_card(rhystic_study)))
    print()
    
    # Tag multiple cards
    all_cards = [cultivate, sol_ring, rhystic_study]
    all_tags = tag_many(all_cards)
    
    print("Game Changers found:")
    print(filter_by_tag(all_tags, "game_changer"))
    print()
    
    print("Fast mana count:")
    print(count_tag(all_tags, "fast_mana"))

