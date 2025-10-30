"""
Deck list parsing utilities for Magic: The Gathering.
"""

import re
from typing import Optional, Dict
from pathlib import Path
from models import Deck


class DeckParser:
    """Parser for various Magic: The Gathering decklist formats."""
    
    def __init__(self):
        # Regex patterns for different decklist formats
        self.patterns = [
            # "1 Card Name (SET) 123 *F*" - full format with set and collector number
            re.compile(r'^(\d+)x?\s+(.+?)\s+\(([A-Z0-9]+)\)\s+\d+(?:\s+\*[A-Z]*\*)?$', re.IGNORECASE),
            # "1 Card Name (SET)" - format with set but no collector number  
            re.compile(r'^(\d+)x?\s+(.+?)\s+\(([A-Z0-9]+)\)$', re.IGNORECASE),
            # "1 Card Name" or "1x Card Name" - legacy format
            re.compile(r'^(\d+)x?\s+(.+)$', re.IGNORECASE),
            # "Card Name" (assumes quantity 1) - legacy format
            re.compile(r'^([^0-9]+)$'),
        ]
        
        # Lines to ignore (comments, sections, empty lines)
        self.ignore_patterns = [
            re.compile(r'^\s*$'),  # Empty lines
            re.compile(r'^\s*#'),  # Comments starting with #
            re.compile(r'^\s*//'), # Comments starting with //
            re.compile(r'^(sideboard|maybeboard|commanders?):?$', re.IGNORECASE),  # Section headers
        ]
    
    def parse_file(self, file_path: str) -> Deck:
        """
        Parse a decklist file and return a Deck object.
        
        Args:
            file_path: Path to the decklist file
            
        Returns:
            Deck object containing the parsed cards
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is invalid
        """
        path = Path(file_path)
        
        # Set deck name from file name, removing extension and replacing underscores/hyphens
        deck_name = path.stem.replace('_', ' ').replace('-', ' ').title()

        if not path.exists():
            raise FileNotFoundError(f"Decklist file not found: {file_path}")
            
        cards = {}
        card_sets = {}
        commander = None
        first_card = None  # Track the first card parsed (likely the commander)
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(path, 'r', encoding='latin-1') as f:
                lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if self._should_ignore_line(line):
                continue
            
            # Try to parse the line
            parsed = self._parse_line(line)
            if parsed is None:
                # Parsing warnings handled by Streamlit interface
                continue
            
            if len(parsed) == 3:
                quantity, card_name, set_code = parsed
                card_sets[card_name] = set_code
            else:
                quantity, card_name = parsed
            
            # Track first card (often the commander in Commander decks)
            if first_card is None and quantity == 1:
                first_card = card_name
            
            # Add to deck
            if card_name in cards:
                cards[card_name] += quantity
            else:
                cards[card_name] = quantity
        
        if not cards:
            raise ValueError(f"No valid cards found in {file_path}")
        
        # Try to identify commander (simple heuristic: legendary creature with quantity 1)
        commander = self._identify_commander(cards, card_sets, first_card)
        
        # Create and return the Deck object with the parsed information
        return Deck(
            cards=cards,
            card_sets=card_sets,
            commander=commander,
            name=deck_name  # Include the deck name
        )
    
    def _identify_commander(self, cards: Dict[str, int], card_sets: Dict[str, str], first_card: Optional[str] = None) -> Optional[str]:
        """
        Identify the commander from a deck using various heuristics.

        Args:
            cards: Dictionary of card names to quantities
            card_sets: Dictionary of card names to set codes
            first_card: The first card parsed from the list (often the commander)

        Returns:
            Commander card name if identified, None otherwise
        """
        # Priority 1: If the first card has quantity 1 and looks like a commander, use it
        if first_card and cards.get(first_card) == 1:
            card_lower = first_card.lower()
            # Check if first card name suggests it's a legendary/commander
            commander_indicators = [
                'legendary', 'commander', 'the ', 'lord', 'queen', 'king',
                'master', 'captain', 'general', 'overseer'
            ]
            if any(indicator in card_lower for indicator in commander_indicators):
                return first_card
        
        # Priority 2: Look for cards with quantity 1 that might be commanders
        potential_commanders = []
        for card_name, quantity in cards.items():
            if quantity == 1:  # Commanders are typically single cards
                # Check if it's a legendary creature or planeswalker
                # We'll use simple heuristics based on common commander names
                card_lower = card_name.lower()

                # Common commander indicators
                commander_indicators = [
                    'legendary creature',
                    'legendary planeswalker',
                    'the ur-dragon',
                    'captain sisay',
                    'karona',
                    'child of alara',
                    'reaper king',
                    'malfegor',
                    'kaalia of the vast',
                    'prossh',
                    'skyfire kirin',
                    'mayael the anima',
                    'sharuum the hegemon',
                    'edric',
                    'spymaster of trest',
                    'gaddock teeg',
                    'melira',
                    'sylvok outcast',
                    'karador',
                    'ghost chieftain',
                    'animar',
                    'soul of elements',
                    'command tower',  # Sometimes used as commander
                ]

                # Check if card name suggests it's a commander
                is_potential_commander = False

                # Check for legendary indicators in card name
                if any(indicator in card_lower for indicator in commander_indicators):
                    is_potential_commander = True

                # Check for planeswalker names
                planeswalker_names = [
                    'jace', 'liliana', 'chandra', 'nissa', 'gideon', 'elspeth',
                    'ajani', 'sorin', 'tezzeret', 'venser', 'tamiyo', 'kiora',
                    'nahiri', 'dovin', 'angrath', 'asha', 'freyalise', 'minsc'
                ]
                if any(pw in card_lower for pw in planeswalker_names):
                    is_potential_commander = True

                # Check for legendary creature indicators
                legendary_indicators = [
                    'the', 'lord', 'queen', 'king', 'master', 'archangel',
                    'primarch', 'overseer', 'commander', 'captain', 'general'
                ]
                if any(indicator in card_lower for indicator in legendary_indicators):
                    is_potential_commander = True

                if is_potential_commander:
                    potential_commanders.append(card_name)

        # If we found potential commanders, return the first one
        if potential_commanders:
            return potential_commanders[0]

        # Fallback: if no commander identified, check if there's a single legendary card
        # This is a basic fallback that might not always be accurate
        return None

    def _should_ignore_line(self, line: str) -> bool:
        """Check if a line should be ignored during parsing."""
        for pattern in self.ignore_patterns:
            if pattern.match(line):
                return True
        return False
    
    def _parse_line(self, line: str) -> Optional[tuple]:
        """
        Parse a single line of a decklist.
        
        Returns:
            Tuple of (quantity, card_name, set_code) for new format
            or (quantity, card_name) for legacy format
            or None if parsing failed
        """
        line = line.strip()
        
        # Try new format with set and collector number first
        match = self.patterns[0].match(line)
        if match:
            quantity = int(match.group(1))
            card_name = match.group(2).strip()
            set_code = match.group(3).upper()
            return quantity, card_name, set_code
        
        # Try new format with just set code
        match = self.patterns[1].match(line)
        if match:
            quantity = int(match.group(1))
            card_name = match.group(2).strip()
            set_code = match.group(3).upper()
            return quantity, card_name, set_code
        
        # Try legacy "1 Card Name" format
        match = self.patterns[2].match(line)
        if match:
            quantity = int(match.group(1))
            card_name = match.group(2).strip()
            return quantity, card_name
        
        # Try legacy "Card Name" format (quantity = 1)
        match = self.patterns[3].match(line)
        if match:
            card_name = match.group(1).strip()
            # Skip very short names (likely parsing errors)
            if len(card_name) >= 2:
                return 1, card_name
        
        return None
    
    def _clean_card_name(self, name: str) -> str:
        """Clean up card name by removing extra whitespace and common artifacts."""
        # Remove multiple spaces and trim
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Remove common set codes or collector numbers at the end
        # e.g. "Lightning Bolt (M10)" -> "Lightning Bolt"
        name = re.sub(r'\s+\([^)]+\)$', '', name)
        
        return name


def parse_decklist(file_path: str) -> Deck:
    """
    Convenience function to parse a decklist file.
    
    Args:
        file_path: Path to the decklist file
        
    Returns:
        Deck object
    """
    parser = DeckParser()
    return parser.parse_file(file_path)
