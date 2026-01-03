"""
Role classification module for card analysis.
Determines what job each card performs in the deck.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Set, Optional
from collections import defaultdict
import re


class Role(Enum):
    """Card role classifications"""
    # Mana
    LAND = auto()
    RAMP = auto()
    FAST_MANA = auto()
    MANA_FIXING = auto()
    
    # Card Advantage
    CARD_DRAW = auto()
    CARD_SELECTION = auto()
    TUTOR = auto()
    
    # Interaction
    INTERACTION = auto()
    COUNTERSPELL = auto()
    REMOVAL = auto()
    BOARD_WIPE = auto()
    
    # Protection
    PROTECTION = auto()
    
    # Value
    ENGINE = auto()
    PAYOFF = auto()
    WINCON = auto()
    
    # Recursion
    RECURSION = auto()
    
    # Disruption
    STAX = auto()
    TAX = auto()
    
    # Synergy
    TRIBAL = auto()
    TOKEN = auto()
    
    # Cost
    COST_REDUCTION = auto()


@dataclass
class Card:
    """
    Simplified card model for role classification.
    In practice, this comes from your Scryfall data.
    """
    name: str
    cmc: float
    type_line: str
    oracle_text: str
    keywords: Set[str]
    colors: Set[str]
    mana_cost: str = ""
    produced_mana: Optional[Set[str]] = None
    qty: int = 1
    
    @property
    def is_land(self) -> bool:
        return "Land" in self.type_line
    
    @property
    def is_creature(self) -> bool:
        return "Creature" in self.type_line
    
    @property
    def is_artifact(self) -> bool:
        return "Artifact" in self.type_line
    
    @property
    def is_enchantment(self) -> bool:
        return "Enchantment" in self.type_line
    
    @property
    def is_instant(self) -> bool:
        return "Instant" in self.type_line
    
    @property
    def is_sorcery(self) -> bool:
        return "Sorcery" in self.type_line
    
    @property
    def is_planeswalker(self) -> bool:
        return "Planeswalker" in self.type_line


@dataclass
class CardRoles:
    """Roles assigned to a single card with reasons"""
    card_name: str
    roles: Set[Role] = field(default_factory=set)
    reasons: Dict[Role, List[str]] = field(default_factory=lambda: defaultdict(list))
    
    def add_role(self, role: Role, reason: str):
        """Add a role with an explanation"""
        self.roles.add(role)
        self.reasons[role].append(reason)


@dataclass
class RoleSummary:
    """Deck-level role aggregation"""
    role_counts: Dict[Role, int]
    cards_by_role: Dict[Role, List[str]]
    
    def get_role_count(self, role: Role) -> int:
        """Get count for a specific role"""
        return self.role_counts.get(role, 0)
    
    def get_cards_for_role(self, role: Role) -> List[str]:
        """Get all cards with a specific role"""
        return self.cards_by_role.get(role, [])


@dataclass
class Deck:
    """Simplified deck model for role classification"""
    cards: List[Card]
    commander: Optional[Card] = None
    
    def get_card_by_name(self, name: str) -> Optional[Card]:
        """Find a card by name"""
        for card in self.cards:
            if card.name.lower() == name.lower():
                return card
        return None


# ===== LAYER 1: HARD TYPE RULES =====

def detect_hard_roles(card: Card, roles: CardRoles):
    """
    Layer 1: Deterministic type-based role assignment.
    No debate - these are facts.
    """
    text_lower = card.oracle_text.lower()
    
    # Lands
    if card.is_land:
        roles.add_role(Role.LAND, "Card type: Land")
        
        # Mana fixing for nonbasic lands
        if "Basic Land" not in card.type_line:
            # Check if it produces multiple colors
            if card.produced_mana and len(card.produced_mana) > 1:
                roles.add_role(Role.MANA_FIXING, "Produces multiple colors of mana")
            elif any(phrase in text_lower for phrase in ["any color", "one mana of any"]):
                roles.add_role(Role.MANA_FIXING, "Can produce mana of any color")
        
        return  # Lands don't get other roles in layer 1
    
    # Mana production (artifacts and creatures)
    if "add {" in text_lower or "adds {" in text_lower or "add one mana" in text_lower:
        if card.is_artifact:
            roles.add_role(Role.RAMP, "Artifact that produces mana")
            if card.cmc <= 1:
                roles.add_role(Role.FAST_MANA, "0-1 CMC mana artifact")
        elif card.is_creature:
            roles.add_role(Role.RAMP, "Creature that produces mana")
            if card.cmc <= 1:
                roles.add_role(Role.FAST_MANA, "0-1 CMC mana creature")
        else:
            roles.add_role(Role.RAMP, "Produces mana")
    
    # Planeswalker ultimates that win
    if card.is_planeswalker:
        if any(phrase in text_lower for phrase in [
            "you win the game",
            "target player loses the game",
            "exile all permanents",
            "restart the game"
        ]):
            roles.add_role(Role.WINCON, "Planeswalker ultimate wins game")


# ===== LAYER 2: ORACLE TEXT KEYWORD RULES =====

# Pattern definitions
DRAW_PATTERNS = {
    "draw a card",
    "draw cards",
    "draw two cards",
    "draw three cards",
    "draws a card",
    "draws cards",
    "you may draw",
    "each player draws",
}

SELECTION_PATTERNS = {
    "scry",
    "surveil",
    "look at the top",
    "reveal the top",
    "manifest",
    "impulse",
}

TUTOR_PATTERNS = {
    "search your library",
    "search target player's library",
    "tutor",
}

COUNTER_PATTERNS = {
    "counter target spell",
    "counter target",
    "counter all",
    "can't be countered",  # Not actually a counter, but interaction
}

REMOVAL_PATTERNS = {
    "destroy target creature",
    "destroy target permanent",
    "exile target creature",
    "exile target permanent",
    "destroy target artifact",
    "destroy target enchantment",
    "destroy target planeswalker",
    "exile target artifact",
    "exile target enchantment",
    "target creature gets -",
    "destroy all",
    "exile all",
    "each opponent sacrifices",
    "target player sacrifices",
    "return target creature",
    "return target permanent",
    "bounce",
}

BOARD_WIPE_PATTERNS = {
    "destroy all creatures",
    "exile all creatures",
    "destroy all permanents",
    "exile all permanents",
    "all creatures get -",
    "-x/-x to each",
    "each creature gets -",
    "wrath",
}

RECURSION_PATTERNS = {
    "return target card from your graveyard",
    "return target creature card from your graveyard",
    "return all",
    "from your graveyard to",
    "return up to",
    "reanimate",
    "unearth",
}

PROTECTION_PATTERNS = {
    "hexproof",
    "shroud",
    "indestructible",
    "protection from",
    "can't be the target",
    "prevent all damage",
    "phase out",
    "phases out",
}

STAX_PATTERNS = {
    "players can't",
    "opponents can't",
    "can't cast",
    "can't activate",
    "can't attack",
    "can't be played",
    "enters the battlefield tapped",
    "skip their",
}

TAX_PATTERNS = {
    "costs {x} more",
    "costs more",
    "unless its controller pays",
    "unless that player pays",
    "pay {x} or",
}

COST_REDUCTION_PATTERNS = {
    "costs {x} less",
    "costs less",
    "cost less",
    "cost {x} less to cast",
    "without paying",
    "affinity for",
    "convoke",
    "delve",
}

TOKEN_PATTERNS = {
    "create a",
    "create X",
    "create one",
    "create two",
    "put a token",
    "token creature",
}


def detect_oracle_roles(card: Card, roles: CardRoles):
    """
    Layer 2: Pattern-based detection from oracle text.
    """
    text_lower = card.oracle_text.lower()
    
    # Skip if no oracle text
    if not text_lower:
        return
    
    # Card Draw
    for pattern in DRAW_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.CARD_DRAW, f"Oracle text contains '{pattern}'")
            break
    
    # Card Selection
    for pattern in SELECTION_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.CARD_SELECTION, f"Oracle text contains '{pattern}'")
            break
    
    # Tutors
    for pattern in TUTOR_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.TUTOR, f"Oracle text contains '{pattern}'")
            break
    
    # Counterspells
    for pattern in COUNTER_PATTERNS:
        if pattern in text_lower and "counter" in text_lower:
            roles.add_role(Role.COUNTERSPELL, f"Oracle text contains '{pattern}'")
            roles.add_role(Role.INTERACTION, "Can counter spells")
            break
    
    # Board Wipes (check before single-target removal)
    for pattern in BOARD_WIPE_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.BOARD_WIPE, f"Oracle text contains '{pattern}'")
            roles.add_role(Role.INTERACTION, "Mass removal")
            break
    
    # Single-target Removal
    if Role.BOARD_WIPE not in roles.roles:  # Don't double-count wipes
        for pattern in REMOVAL_PATTERNS:
            if pattern in text_lower:
                roles.add_role(Role.REMOVAL, f"Oracle text contains '{pattern}'")
                roles.add_role(Role.INTERACTION, "Single-target removal")
                break
    
    # Recursion
    for pattern in RECURSION_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.RECURSION, f"Oracle text contains '{pattern}'")
            break
    
    # Protection
    for pattern in PROTECTION_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.PROTECTION, f"Oracle text contains '{pattern}'")
            break
    
    # Check keywords too
    for keyword in card.keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in ["hexproof", "shroud", "indestructible", "ward"]:
            roles.add_role(Role.PROTECTION, f"Has keyword: {keyword}")
    
    # Stax
    for pattern in STAX_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.STAX, f"Oracle text contains '{pattern}'")
            break
    
    # Tax
    for pattern in TAX_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.TAX, f"Oracle text contains '{pattern}'")
            break
    
    # Cost Reduction
    for pattern in COST_REDUCTION_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.COST_REDUCTION, f"Oracle text contains '{pattern}'")
            break
    
    # Tokens
    for pattern in TOKEN_PATTERNS:
        if pattern in text_lower:
            roles.add_role(Role.TOKEN, f"Oracle text contains '{pattern}'")
            break
    
    # Wincons (direct win conditions)
    if any(phrase in text_lower for phrase in [
        "you win the game",
        "target player loses the game",
        "each opponent loses the game",
    ]):
        roles.add_role(Role.WINCON, "Oracle text contains win condition")


# ===== LAYER 3: STRUCTURAL / COST-BASED RULES =====

def detect_structural_roles(card: Card, roles: CardRoles):
    """
    Layer 3: Structural and cost-based detection.
    """
    text_lower = card.oracle_text.lower()
    
    # Fast mana (already partially covered in layer 1)
    if card.cmc <= 1:
        if Role.RAMP in roles.roles:
            if Role.FAST_MANA not in roles.roles:
                roles.add_role(Role.FAST_MANA, "0-1 CMC mana source")
    
    # Land ramp spells
    if not card.is_land and card.cmc <= 4:
        if any(phrase in text_lower for phrase in [
            "search your library for a land",
            "search your library for a basic land",
            "search your library for a forest",
            "search your library for a plains",
            "search your library for an island",
            "search your library for a swamp",
            "search your library for a mountain",
            "search your library for up to two basic lands",
            "put a land card from your hand onto the battlefield",
        ]):
            if Role.RAMP not in roles.roles:
                roles.add_role(Role.RAMP, "Land ramp spell")
    
    # Engines (repeatable value)
    engine_indicators = [
        "at the beginning of",
        "whenever",
        "whenever a",
        "whenever you",
        "each upkeep",
        "each end step",
        "each combat",
    ]
    
    if any(indicator in text_lower for indicator in engine_indicators):
        # Check if it generates value repeatedly
        if any(value in text_lower for value in ["draw", "create", "add", "put", "return"]):
            roles.add_role(Role.ENGINE, "Repeatable triggered ability")
    
    # Also mark as engine if it's an enchantment/artifact that draws/creates
    if (card.is_enchantment or card.is_artifact) and not card.is_creature:
        if Role.CARD_DRAW in roles.roles or Role.TOKEN in roles.roles:
            if Role.ENGINE not in roles.roles:
                roles.add_role(Role.ENGINE, "Permanent that generates ongoing value")
    
    # Payoffs (expensive cards that reward a strategy)
    if card.cmc >= 5:
        # Check for obvious payoff patterns
        payoff_indicators = [
            "for each",
            "for every",
            "equal to the number",
            "equal to the total",
            "x is equal to",
        ]
        if any(indicator in text_lower for indicator in payoff_indicators):
            roles.add_role(Role.PAYOFF, "High-cost card that scales with board state")
    
    # Alternative wincons (combos, infinites)
    if any(phrase in text_lower for phrase in [
        "infinite",
        "extra turn",
        "extra turns",
        "take another turn",
        "combat phase after this one",
    ]):
        roles.add_role(Role.WINCON, "Enables game-winning loops or extra turns")


# ===== LAYER 4: CONTEXTUAL / DECK-AWARE RULES =====

def detect_contextual_roles(card: Card, deck: Deck, roles: CardRoles):
    """
    Layer 4: Contextual detection based on deck composition.
    """
    text_lower = card.oracle_text.lower()
    
    # Tribal synergy
    if deck.commander and deck.commander.is_creature:
        # Extract creature types from commander
        commander_types = extract_creature_types(deck.commander.type_line)
        card_types = extract_creature_types(card.type_line)
        
        # Check if card shares a type with commander
        if commander_types & card_types:
            roles.add_role(Role.TRIBAL, f"Shares creature type with commander: {', '.join(commander_types & card_types)}")
        
        # Check if card cares about commander's types
        for ctype in commander_types:
            if ctype.lower() in text_lower:
                roles.add_role(Role.TRIBAL, f"References {ctype} creatures")
    
    # Check for general tribal indicators
    tribal_keywords = [
        "zombie", "goblin", "elf", "dragon", "angel", "demon", "wizard",
        "soldier", "knight", "warrior", "vampire", "werewolf", "sliver",
        "merfolk", "human", "artifact", "enchantment"
    ]
    
    for keyword in tribal_keywords:
        if keyword in text_lower and keyword != "artifact":  # artifact is too generic
            # Check if it's a tribal payoff (not just being that type)
            if f"{keyword} you control" in text_lower or f"other {keyword}s" in text_lower:
                roles.add_role(Role.TRIBAL, f"Tribal payoff for {keyword}s")


def extract_creature_types(type_line: str) -> Set[str]:
    """Extract creature types from a type line"""
    if "Creature" not in type_line:
        return set()
    
    # Split on "—" to get subtypes
    parts = type_line.split("—")
    if len(parts) < 2:
        return set()
    
    # Get everything after the em-dash
    subtypes = parts[1].strip()
    
    # Split on spaces to get individual types
    types = {t.strip() for t in subtypes.split()}
    
    return types


# ===== ORCHESTRATOR =====

def classify_card_roles(card: Card, deck: Deck) -> CardRoles:
    """
    Main classification function - runs all layers in order.
    
    Args:
        card: Card to classify
        deck: Full deck context
        
    Returns:
        CardRoles with all detected roles and reasons
    """
    roles = CardRoles(card_name=card.name)
    
    # Run detection layers in order
    detect_hard_roles(card, roles)
    detect_oracle_roles(card, roles)
    detect_structural_roles(card, roles)
    detect_contextual_roles(card, deck, roles)
    
    return roles


def assign_roles(deck: Deck) -> Dict[str, CardRoles]:
    """
    Assign roles to all cards in a deck.
    
    Args:
        deck: Deck object with cards
        
    Returns:
        Dictionary mapping card name to CardRoles
    """
    results = {}
    
    for card in deck.cards:
        card_roles = classify_card_roles(card, deck)
        results[card.name] = card_roles
    
    return results


# ===== DECK-LEVEL AGGREGATION =====

def summarize_roles(card_roles: Dict[str, CardRoles]) -> RoleSummary:
    """
    Aggregate roles across all cards in deck.
    
    Args:
        card_roles: Dictionary from assign_roles()
        
    Returns:
        RoleSummary with counts and card lists per role
    """
    role_counts = defaultdict(int)
    cards_by_role = defaultdict(list)
    
    for card_name, cr in card_roles.items():
        for role in cr.roles:
            role_counts[role] += 1
            cards_by_role[role].append(card_name)
    
    return RoleSummary(
        role_counts=dict(role_counts),
        cards_by_role=dict(cards_by_role)
    )


# ===== REPORTING / DISPLAY =====

def generate_role_report(card_roles: Dict[str, CardRoles], summary: RoleSummary) -> str:
    """Generate a human-readable role report"""
    lines = [
        "Role Classification Summary",
        "=" * 60,
        "",
        "Role Counts:",
    ]
    
    # Sort roles by count
    sorted_roles = sorted(summary.role_counts.items(), key=lambda x: -x[1])
    
    for role, count in sorted_roles:
        lines.append(f"  {role.name}: {count}")
    
    lines.append("")
    lines.append("=" * 60)
    lines.append("")
    
    # Show cards for each role
    for role, count in sorted_roles:
        lines.append(f"{role.name} ({count}):")
        cards = summary.get_cards_for_role(role)
        for card in cards[:10]:  # Limit to first 10
            lines.append(f"  • {card}")
        if len(cards) > 10:
            lines.append(f"  ... and {len(cards) - 10} more")
        lines.append("")
    
    return "\n".join(lines)


def get_role_explanation(card_roles: CardRoles, role: Role) -> List[str]:
    """Get explanation for why a card has a specific role"""
    return card_roles.reasons.get(role, [])
