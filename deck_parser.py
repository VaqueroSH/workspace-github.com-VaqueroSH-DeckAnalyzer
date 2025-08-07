"""
Deck list parsing utilities for Magic: The Gathering.
"""

import re
from typing import Optional
from pathlib import Path
from models import Deck


class DeckParser:
    """Parser for various Magic: The Gathering decklist formats."""
    
    def __init__(self):
        # Regex patterns for different decklist formats
        self.patterns = [
            # "1 Card Name" or "1x Card Name"
            re.compile(r'^(\d+)x?\s+(.+)$', re.IGNORECASE),
            # "Card Name" (assumes quantity 1)
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
        
        if not path.exists():
            raise FileNotFoundError(f"Decklist file not found: {file_path}")
        
        cards = {}
        commander = None
        deck_name = path.stem  # Use filename as deck name
        
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
                print(f"Warning: Could not parse line {line_num}: '{line}'")
                continue
            
            quantity, card_name = parsed
            
            # Handle potential commander identification
            # (This is heuristic-based, could be improved with better format detection)
            if quantity == 1 and len(cards) == 0:
                # First single card might be commander - we'll determine this later
                pass
            
            # Add to deck
            if card_name in cards:
                cards[card_name] += quantity
            else:
                cards[card_name] = quantity
        
        if not cards:
            raise ValueError(f"No valid cards found in {file_path}")
        
        # Try to identify commander (simple heuristic: legendary creature with quantity 1)
        # For now, we'll leave this for future enhancement
        
        return Deck(cards=cards, name=deck_name, commander=commander)
    
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
            Tuple of (quantity, card_name) or None if parsing failed
        """
        line = line.strip()
        
        # Try "1 Card Name" format first
        match = self.patterns[0].match(line)
        if match:
            quantity = int(match.group(1))
            card_name = match.group(2).strip()
            return quantity, card_name
        
        # Try "Card Name" format (quantity = 1)
        match = self.patterns[1].match(line)
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
