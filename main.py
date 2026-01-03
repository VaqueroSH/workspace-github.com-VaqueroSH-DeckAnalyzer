#!/usr/bin/env python3
"""
MTG Deck Analyzer - Analyze Magic: The Gathering decklists
"""

import argparse
import sys
from pathlib import Path

from scryfall_api import ScryfallAPI
from deck_parser import parse_decklist
from models import DeckAnalyzer


def print_deck_stats(stats):
    """Print formatted deck statistics."""
    
    print("\n" + "="*60)
    print("🃏 DECK ANALYSIS RESULTS")
    print("="*60)
    
    # Basic counts
    print(f"\n📊 BASIC STATISTICS")
    print(f"   Total cards: {stats.total_cards}")
    print(f"   Unique cards: {stats.unique_cards}")
    print(f"   Lands: {stats.lands} ({stats.land_percentage:.1f}%)")
    print(f"   Nonlands: {stats.nonlands} ({stats.nonland_percentage:.1f}%)")
    
    # Color distribution
    print(f"\n🎨 COLOR DISTRIBUTION")
    if stats.color_counts:
        for color_code, count in sorted(stats.color_counts.items()):
            color_name = stats.color_names.get(color_code, color_code)
            percentage = (count / stats.unique_cards * 100)
            print(f"   {color_name} ({color_code}): {count} cards ({percentage:.1f}%)")
    else:
        print("   Colorless deck")
    
    # Mana curve
    print(f"\n📈 MANA CURVE (Nonlands only)")
    if stats.mana_curve:
        print(f"   Average mana value: {stats.average_mana_value:.2f}")
        print(f"   Distribution:")
        for mana_value in sorted(stats.mana_curve.keys()):
            count = stats.mana_curve[mana_value]
            if mana_value == 0:
                print(f"      0 CMC: {count:2d}")
            elif mana_value >= 7:
                # Group 7+ together
                if mana_value == 7:
                    high_cmc_count = sum(stats.mana_curve.get(i, 0) for i in range(7, 20))
                    print(f"      7+ CMC: {high_cmc_count:2d}")
                # Skip individual 8, 9, etc. since we grouped them
            else:
                print(f"      {mana_value} CMC: {count:2d}")
    else:
        print("   No nonland cards to analyze")
    
    # Card type distribution
    print(f"\n🃏 CARD TYPE BREAKDOWN")
    if stats.card_types:
        # Sort by count (descending) then by name for consistent display
        sorted_types = sorted(stats.card_types.items(), key=lambda x: (-x[1], x[0]))
        
        for card_type, count in sorted_types:
            percentage = (count / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
            print(f"   {card_type}: {count:2d} cards ({percentage:.1f}%)")
    else:
        print("   No card type data available")
    
    # Price analysis
    print(f"\n💰 PRICE ANALYSIS")
    if stats.total_deck_value > 0:
        print(f"   Total deck value: ${stats.total_deck_value:.2f}")
        if stats.most_expensive_cards:
            print(f"   Most expensive cards:")
            for card_name, price in stats.most_expensive_cards:
                print(f"      • {card_name}: ${price:.2f}")
    else:
        print("   Price information not available")
    
    # Rarity breakdown
    print(f"\n⭐ RARITY BREAKDOWN")
    if stats.rarity_counts:
        rarity_order = ['mythic', 'rare', 'uncommon', 'common', 'special', 'bonus']
        rarity_names = {
            'mythic': 'Mythic Rare',
            'rare': 'Rare', 
            'uncommon': 'Uncommon',
            'common': 'Common',
            'special': 'Special',
            'bonus': 'Bonus'
        }
        
        for rarity in rarity_order:
            if rarity in stats.rarity_counts:
                count = stats.rarity_counts[rarity]
                percentage = (count / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
                rarity_display = rarity_names.get(rarity, rarity.title())
                print(f"   {rarity_display}: {count} cards ({percentage:.1f}%)")
        
        # Handle any unknown rarities
        for rarity, count in stats.rarity_counts.items():
            if rarity not in rarity_order:
                percentage = (count / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
                print(f"   {rarity.title()}: {count} cards ({percentage:.1f}%)")
    else:
        print("   Rarity information not available")
    
    # Interaction suite
    print(f"\n🎯 INTERACTION SUITE")
    if stats.interaction_counts:
        for interaction_type in ['Removal', 'Tutors', 'Card Draw', 'Ramp', 'Protection']:
            if interaction_type in stats.interaction_counts:
                count = stats.interaction_counts[interaction_type]
                print(f"   {interaction_type}: {count} cards")
                
                # Show up to 3 example cards
                if interaction_type in stats.interaction_cards:
                    examples = stats.interaction_cards[interaction_type][:3]
                    example_str = ", ".join(examples)
                    if len(stats.interaction_cards[interaction_type]) > 3:
                        example_str += ", ..."
                    print(f"      ({example_str})")
    else:
        print("   No interaction cards identified")
    
    # Missing cards warning
    if stats.missing_cards:
        print(f"\n⚠️  MISSING CARDS")
        print(f"   Could not find information for {len(stats.missing_cards)} cards:")
        for card in stats.missing_cards:
            print(f"   - {card}")
    
    print("\n" + "="*60)


def main():
    """Main entry point for the deck analyzer."""
    
    parser = argparse.ArgumentParser(
        description="Analyze Magic: The Gathering decklists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py Sephiroth_deck.txt
  python main.py my_deck.txt --verbose
  
Supported formats:
  - "1 Card Name"
  - "4x Lightning Bolt"  
  - "Card Name" (assumes quantity 1)
  
The program will automatically fetch card information from Scryfall.
        """
    )
    
    parser.add_argument(
        'decklist',
        help='Path to the decklist file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed progress information'
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    decklist_path = Path(args.decklist)
    if not decklist_path.exists():
        print(f"Error: Decklist file '{args.decklist}' not found.")
        sys.exit(1)
    
    try:
        # Parse the decklist
        print(f"📄 Parsing decklist: {decklist_path.name}")
        deck = parse_decklist(str(decklist_path))
        
        if args.verbose:
            print(f"Found {deck.unique_cards} unique cards, {deck.total_cards} total cards")
        
        # Initialize API and analyzer
        print("🌐 Connecting to Scryfall API...")
        api = ScryfallAPI()
        analyzer = DeckAnalyzer(api)
        
        # Analyze the deck
        stats = analyzer.analyze(deck)
        
        # Display results
        print_deck_stats(stats)
        
        # Success message
        success_rate = ((stats.unique_cards - len(stats.missing_cards)) / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
        print(f"✅ Analysis complete! Successfully analyzed {success_rate:.1f}% of cards.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
