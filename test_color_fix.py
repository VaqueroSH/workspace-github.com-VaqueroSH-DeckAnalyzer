#!/usr/bin/env python3
"""
Quick test to verify the color pie fix is working
"""

from scryfall_api import ScryfallAPI
from deck_parser import parse_decklist
from models import DeckAnalyzer

def test_color_analysis():
    """Test the improved color analysis."""
    print("Testing color analysis fix...")
    
    # Parse a sample deck
    deck = parse_decklist("Decklists/Sephiroth_deck.txt")
    print(f"Loaded deck with {deck.unique_cards} unique cards")
    
    # Initialize API and analyzer
    api = ScryfallAPI()
    analyzer = DeckAnalyzer(api)
    
    # Analyze the deck
    print("Analyzing deck...")
    stats = analyzer.analyze(deck)
    
    # Display color distribution
    print("\n🎨 COLOR DISTRIBUTION:")
    if stats.color_counts:
        for color_code, count in sorted(stats.color_counts.items()):
            color_name = stats.color_names.get(color_code, color_code)
            percentage = (count / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
            print(f"   {color_name} ({color_code}): {count} cards ({percentage:.1f}%)")
    else:
        print("   No colored cards found")
    
    print(f"\nTest completed! Found {len(stats.color_counts)} different color categories.")

if __name__ == "__main__":
    test_color_analysis()
