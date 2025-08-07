"""
Data models for MTG deck analysis.
"""

from dataclasses import dataclass
from typing import Dict, Set, List, Optional
from collections import defaultdict


@dataclass
class Deck:
    """Represents a Magic: The Gathering deck."""
    cards: Dict[str, int]  # card_name -> quantity
    commander: Optional[str] = None
    name: Optional[str] = None
    
    @property
    def total_cards(self) -> int:
        """Total number of cards in the deck."""
        return sum(self.cards.values())
    
    @property
    def unique_cards(self) -> int:
        """Number of unique cards in the deck."""
        return len(self.cards)
    
    def get_card_names(self) -> List[str]:
        """Get a list of all unique card names."""
        return list(self.cards.keys())


@dataclass
class DeckStats:
    """Statistics calculated from a deck analysis."""
    total_cards: int
    unique_cards: int
    lands: int
    nonlands: int
    
    # Color distribution
    color_counts: Dict[str, int]  # Color -> number of cards with that color
    color_names = {
        'W': 'White',
        'U': 'Blue', 
        'B': 'Black',
        'R': 'Red',
        'G': 'Green'
    }
    
    # Mana curve
    mana_curve: Dict[int, int]  # Mana value -> count
    average_mana_value: float
    
    # Card type distribution
    card_types: Dict[str, int]  # Card type -> count
    
    # Card details for manual review
    missing_cards: List[str]  # Cards that couldn't be found
    
    def __post_init__(self):
        """Calculate derived statistics."""
        self.land_percentage = (self.lands / self.total_cards * 100) if self.total_cards > 0 else 0
        self.nonland_percentage = 100 - self.land_percentage
    
    def get_color_summary(self) -> str:
        """Get a human-readable summary of color distribution."""
        if not self.color_counts:
            return "Colorless"
        
        colors = []
        for color_code, count in self.color_counts.items():
            color_name = self.color_names.get(color_code, color_code)
            colors.append(f"{color_name}: {count}")
        
        return ", ".join(colors)
    
    def get_mana_curve_summary(self) -> List[str]:
        """Get a human-readable mana curve breakdown."""
        curve = []
        for mana_value in sorted(self.mana_curve.keys()):
            count = self.mana_curve[mana_value]
            if mana_value == 0:
                curve.append(f"0 CMC: {count} cards")
            elif mana_value >= 7:
                curve.append(f"7+ CMC: {count} cards")
            else:
                curve.append(f"{mana_value} CMC: {count} cards")
        return curve
    
    def get_card_type_summary(self) -> List[str]:
        """Get a human-readable card type breakdown."""
        if not self.card_types:
            return ["No card type data available"]
        
        # Sort by count (descending) then by name
        sorted_types = sorted(self.card_types.items(), key=lambda x: (-x[1], x[0]))
        
        summary = []
        for card_type, count in sorted_types:
            percentage = (count / self.unique_cards * 100) if self.unique_cards > 0 else 0
            summary.append(f"{card_type}: {count} ({percentage:.1f}%)")
        
        return summary


class DeckAnalyzer:
    """Analyzes Magic: The Gathering decks and calculates statistics."""
    
    def __init__(self, scryfall_api):
        self.api = scryfall_api
    
    def _parse_primary_type(self, type_line: str) -> str:
        """
        Extract the primary card type from a type line.
        
        Examples:
        - "Legendary Creature — Human Noble" -> "Creature"
        - "Instant" -> "Instant" 
        - "Artifact — Equipment" -> "Artifact"
        - "Basic Land — Swamp" -> "Land"
        """
        if not type_line:
            return "Unknown"
        
        # Remove "Basic" prefix if present
        type_line = type_line.replace("Basic ", "")
        
        # Split on — to separate main types from subtypes
        main_types = type_line.split(" — ")[0]
        
        # Split on spaces and find the primary type
        type_parts = main_types.split()
        
        # Common primary types (in order of priority for parsing)
        primary_types = ["Land", "Creature", "Planeswalker", "Instant", "Sorcery", 
                        "Artifact", "Enchantment", "Battle", "Tribal"]
        
        # Find the first matching primary type
        for part in type_parts:
            if part in primary_types:
                return part
        
        # If no standard type found, return the first word (handles edge cases)
        return type_parts[0] if type_parts else "Unknown"
    
    def analyze(self, deck: Deck) -> DeckStats:
        """
        Analyze a deck and return comprehensive statistics.
        
        Args:
            deck: The deck to analyze
            
        Returns:
            DeckStats object with all calculated statistics
        """
        print(f"Analyzing deck with {deck.unique_cards} unique cards...")
        
        # Fetch card information
        card_names = deck.get_card_names()
        card_data = self.api.get_cards_batch(card_names)
        
        # Initialize counters
        lands = 0
        color_counts = defaultdict(int)
        mana_curve = defaultdict(int)
        card_types = defaultdict(int)
        missing_cards = []
        total_mana_value = 0
        nonland_cards = 0
        
        # Process each card
        for card_name, quantity in deck.cards.items():
            card_info = card_data.get(card_name)
            
            if card_info is None:
                missing_cards.append(card_name)
                continue
            
            # Count lands
            if card_info.is_land:
                lands += quantity
            else:
                nonland_cards += quantity
                total_mana_value += card_info.mana_value * quantity
                
                # Mana curve (only nonlands)
                mana_curve[card_info.mana_value] += quantity
            
            # Color identity (count unique cards, not copies)
            for color in card_info.colors:
                color_counts[color] += 1
            
            # Card type tracking (count unique cards, not copies)
            primary_type = self._parse_primary_type(card_info.type_line)
            card_types[primary_type] += 1
        
        # Calculate average mana value (nonlands only)
        avg_mana_value = total_mana_value / nonland_cards if nonland_cards > 0 else 0
        
        # Create statistics object
        stats = DeckStats(
            total_cards=deck.total_cards,
            unique_cards=deck.unique_cards,
            lands=lands,
            nonlands=deck.total_cards - lands,
            color_counts=dict(color_counts),
            mana_curve=dict(mana_curve),
            average_mana_value=avg_mana_value,
            card_types=dict(card_types),
            missing_cards=missing_cards
        )
        
        return stats
