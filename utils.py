"""
Shared utility functions for MTG Deck Analyzer.
Common operations used across multiple modules.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Set


def canonicalize_name(name: str) -> str:
    """
    Canonicalize card names for consistent matching.
    
    Transforms:
    - Normalizes Unicode (NFKD)
    - Removes combining characters (accents)
    - Case-folds to lowercase
    - Normalizes quotes/apostrophes
    - Keeps only alphanumeric, spaces, commas, hyphens, apostrophes
    - Collapses whitespace
    
    Args:
        name: Card name to canonicalize
        
    Returns:
        Canonicalized string for comparison
        
    Examples:
        >>> canonicalize_name("Bolas's Citadel")
        "bolas's citadel"
        >>> canonicalize_name("Thassa's Oracle")
        "thassa's oracle"
    """
    if not name:
        return ""
    
    # Normalize Unicode
    name = unicodedata.normalize("NFKD", name)
    
    # Remove combining characters (accents)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    
    # Casefold for case-insensitive comparison
    name = name.casefold()
    
    # Normalize curly apostrophes/quotes to plain
    name = name.replace("'", "'").replace("'", "'")
    name = name.replace(""", '"').replace(""", '"')
    
    # Keep only safe characters: alphanumeric, spaces, commas, hyphens, apostrophes
    name = re.sub(r"[^a-z0-9 ,'-]+", " ", name)
    
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    
    return name


# Alias for backward compatibility
_canon = canonicalize_name


def normalize_card_name(name: str) -> str:
    """
    Simple card name normalization (lowercase, stripped).
    Less aggressive than canonicalize_name - preserves more characters.
    
    Args:
        name: Card name to normalize
        
    Returns:
        Normalized string
    """
    return name.lower().strip() if name else ""


def count_matches(deck_cards: list, reference_set: Set[str]) -> int:
    """
    Count how many deck cards match a reference set using canonical matching.
    
    Args:
        deck_cards: List of card names or card dicts with 'name' key
        reference_set: Set of canonicalized card names to match against
        
    Returns:
        Count of matching cards
    """
    count = 0
    for card in deck_cards:
        # Handle both string and dict formats
        if isinstance(card, dict):
            name = card.get('name', '')
        else:
            name = str(card)
        
        if canonicalize_name(name) in reference_set:
            count += 1
    
    return count


def extract_colors_from_mana_cost(mana_cost: str) -> Set[str]:
    """
    Extract color symbols from a mana cost string.
    
    Args:
        mana_cost: Mana cost string like "{2}{U}{U}"
        
    Returns:
        Set of color symbols (W, U, B, R, G)
    """
    if not mana_cost:
        return set()
    
    colors = set()
    # Find all color symbols in the mana cost
    for color in ['W', 'U', 'B', 'R', 'G']:
        if f'{{{color}}}' in mana_cost.upper():
            colors.add(color)
    
    return colors


def is_basic_land(type_line: str) -> bool:
    """
    Check if a card is a basic land.
    
    Args:
        type_line: Card type line
        
    Returns:
        True if basic land
    """
    return "Basic Land" in type_line if type_line else False


def get_primary_type(type_line: str) -> str:
    """
    Extract the primary card type from a type line.
    
    Args:
        type_line: Full type line like "Legendary Creature — Human Noble"
        
    Returns:
        Primary type like "Creature"
    """
    if not type_line:
        return "Unknown"
    
    # Remove "Basic" prefix if present
    type_line = type_line.replace("Basic ", "")
    
    # Split on em-dash to separate main types from subtypes
    main_types = type_line.split(" — ")[0]
    
    # Common primary types in priority order
    primary_types = [
        "Land", "Creature", "Planeswalker", "Instant", "Sorcery",
        "Artifact", "Enchantment", "Battle", "Tribal"
    ]
    
    # Find the first matching primary type
    for part in main_types.split():
        if part in primary_types:
            return part
    
    # Fallback to first word
    parts = main_types.split()
    return parts[0] if parts else "Unknown"

