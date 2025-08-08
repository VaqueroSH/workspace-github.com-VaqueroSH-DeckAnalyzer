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
    card_sets: Dict[str, str] = None  # card_name -> set_code
    commander: Optional[str] = None
    name: Optional[str] = None
    
    def __post_init__(self):
        """Initialize card_sets if not provided."""
        if self.card_sets is None:
            self.card_sets = {}
    
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
    
    def get_set_breakdown(self) -> Dict[str, int]:
        """Get breakdown of cards by set."""
        set_counts = defaultdict(int)
        for card_name, quantity in self.cards.items():
            set_code = self.card_sets.get(card_name, 'Unknown')
            set_counts[set_code] += quantity
        return dict(set_counts)


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
        'G': 'Green',
        'C': 'Colorless'
    }
    
    # Mana curve
    mana_curve: Dict[int, int]  # Mana value -> count
    average_mana_value: float
    
    # Card type distribution
    card_types: Dict[str, int]  # Card type -> count
    
    # Price analysis
    total_deck_value: float
    most_expensive_cards: List[tuple]  # [(name, price), ...]
    
    # Rarity breakdown
    rarity_counts: Dict[str, int]  # Rarity -> count
    
    # Interaction suite
    interaction_counts: Dict[str, int]  # Interaction type -> count
    interaction_cards: Dict[str, List[str]]  # Interaction type -> [card names]
    
    # Set breakdown
    set_counts: Dict[str, int]  # Set code -> count of cards
    set_names: Dict[str, str]  # Set code -> full set name
    
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
    
    def _categorize_interaction(self, card_name: str, type_line: str) -> List[str]:
        """
        Categorize cards by their interactive function.
        
        Returns:
            List of interaction categories this card belongs to
        """
        categories = []
        card_name_lower = card_name.lower()
        type_line_lower = type_line.lower()
        
        # Removal spells
        removal_keywords = [
            'destroy', 'exile', 'return to hand', 'fatal push', 'path to exile',
            'swords to plowshares', 'lightning bolt', 'doom blade', 'murder',
            'toxic deluge', 'wrath', 'damnation', 'blasphemous edict',
            'the meathook massacre', 'feed the swarm', 'tragic slip',
            'flare of malice', 'withering torment'
        ]
        
        if any(keyword in card_name_lower for keyword in removal_keywords):
            categories.append('Removal')
        
        # Tutors
        tutor_keywords = [
            'tutor', 'search your library', 'diabolic intent', 'grim tutor',
            'demonic tutor', 'vampiric tutor'
        ]
        
        if any(keyword in card_name_lower for keyword in tutor_keywords):
            categories.append('Tutors')
        
        # Card draw engines
        card_draw_keywords = [
            'draw', 'dark confidant', 'phyrexian arena', 'dark prophecy',
            'black market connections', 'the one ring', 'skullclamp',
            'deadly dispute', 'village rites', 'peer into the abyss'
        ]
        
        if any(keyword in card_name_lower for keyword in card_draw_keywords):
            categories.append('Card Draw')
        
        # Comprehensive mana rock and ramp detection
        
        # Specific mana rocks (exact names) - most reliable method
        mana_rocks = {
            # Sol Ring family
            'sol ring', 'sol talisman',
            
            # Signets (all 10 two-color combinations)
            'azorius signet', 'boros signet', 'dimir signet', 'golgari signet',
            'gruul signet', 'izzet signet', 'orzhov signet', 'rakdos signet',
            'selesnya signet', 'simic signet',
            
            # Talismans (all 10 two-color combinations)
            'talisman of progress', 'talisman of conviction', 'talisman of dominance',
            'talisman of resilience', 'talisman of impulse', 'talisman of creativity',
            'talisman of hierarchy', 'talisman of indulgence', 'talisman of unity',
            'talisman of curiosity',
            
            # Diamonds (all 5 colors)
            'fire diamond', 'marble diamond', 'sky diamond', 'charcoal diamond', 'moss diamond',
            
            # Moxen
            'mox amber', 'mox diamond', 'mox opal', 'mox ruby', 'mox sapphire',
            'mox jet', 'mox emerald', 'mox pearl', 'chrome mox', 'mox tantalite',
            
            # Common 2-mana rocks
            'mind stone', 'fellwar stone', 'prismatic lens', 'thought vessel',
            'everflowing chalice', 'guardian idol', 'coldsteel heart',
            'star compass', 'liquimetal torque', 'fractured powerstone',
            'rampant growth', 'worn powerstone', 'fire diamond',
            
            # 3-mana rocks
            'coalition relic', 'chromatic lantern', 'commander\'s sphere',
            'darksteel ingot', 'cultivator\'s caravan', 'heraldic banner',
            'obelisk of urd', 'pristine talisman', 'unstable obelisk',
            'wayfarers\' bauble', 'manalith', 'spinning wheel',
            
            # Expensive rocks
            'thran dynamo', 'gilded lotus', 'hedron archive', 'dreamstone hedron',
            'ur-golem\'s eye', 'sisay\'s ring', 'khalni gem', 'nyx lotus',
            'empowered autogenerator', 'tome of the guildpact',
            
            # Fast mana
            'mana crypt', 'mana vault', 'lotus petal', 'lion\'s eye diamond',
            'jeweled lotus', 'black lotus', 'lotus bloom', 'simian spirit guide',
            'elvish spirit guide', 'basalt monolith', 'grim monolith',
            
            # Medallions
            'sapphire medallion', 'ruby medallion', 'emerald medallion',
            'jet medallion', 'pearl medallion',
            
            # Modern/newer rocks
            'arcane signet', 'talisman of creativity', 'orzhov locket',
            'boros locket', 'izzet locket', 'golgari locket', 'selesnya locket',
            'dimir locket', 'gruul locket', 'azorius locket', 'rakdos locket',
            'simic locket', 'honored heirloom', 'power depot', 'liquimetal torque',
            'the mightstone and weakstone', 'the temporal anchor'
        }
        
        # Ritual spells
        ritual_spells = {
            'dark ritual', 'cabal ritual', 'seething song', 'pyretic ritual',
            'desperate ritual', 'rite of flame', 'lotus ritual', 'rain of filth',
            'culling the weak', 'sacrifice', 'burnt offering', 'songs of the damned',
            'bubbling muck', 'cabal stronghold', 'bog witch'
        }
        
        # Mana dorks (creatures that produce mana)
        mana_dorks = {
            'llanowar elves', 'elvish mystic', 'fyndhorn elves', 'elves of deep shadow',
            'birds of paradise', 'noble hierarch', 'deathrite shaman',
            'priest of titania', 'elvish archdruid', 'wirewood channeler',
            'crypt ghast', 'magus of the coffers', 'priest of gix',
            'silver myr', 'gold myr', 'iron myr', 'copper myr', 'leaden myr',
            'palladium myr', 'alloy myr', 'plague myr', 'sol ring bearer'
        }
        
        # Land ramp spells
        land_ramp = {
            'rampant growth', 'cultivate', 'kodama\'s reach', 'explosive vegetation',
            'skyshroud claim', 'nature\'s lore', 'three visits', 'farseek',
            'into the north', 'edge of autumn', 'solemn simulacrum'
        }
        
        # Check for exact matches first (most reliable)
        is_mana_rock = card_name_lower in mana_rocks
        is_ritual = card_name_lower in ritual_spells  
        is_dork = card_name_lower in mana_dorks
        is_land_ramp = card_name_lower in land_ramp
        
        # For artifacts, check if it's likely a mana rock by name patterns
        is_artifact_ramp = False
        if 'artifact' in type_line_lower and not any([is_mana_rock, is_ritual, is_dork]):
            # Safe patterns that are very likely mana rocks
            safe_rock_patterns = ['signet', 'talisman', 'medallion', 'mox']
            # More specific patterns to avoid false positives
            specific_patterns = [
                'mana', 'sol ', 'lotus', 'dynamo', 'monolith', 'sphere', 
                'lantern', 'crypt', 'vault', 'obelisk', 'ingot'
            ]
            
            is_artifact_ramp = (
                any(pattern in card_name_lower for pattern in safe_rock_patterns) or
                any(pattern in card_name_lower for pattern in specific_patterns)
            )
        
        is_ramp = is_mana_rock or is_ritual or is_dork or is_land_ramp or is_artifact_ramp
        
        if is_ramp:
            categories.append('Ramp')
        
        # Counterspells/Protection
        protection_keywords = [
            'counter', "imp's mischief", 'deadly rollick'
        ]
        
        if any(keyword in card_name_lower for keyword in protection_keywords):
            categories.append('Protection')
        
        return categories
    
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
        # Analysis progress handled by Streamlit interface
        
        # Fetch card information with set codes when available
        card_requests = []
        for card_name in deck.get_card_names():
            set_code = deck.card_sets.get(card_name)
            if set_code:
                card_requests.append((card_name, set_code))
            else:
                card_requests.append(card_name)
        
        card_data = self.api.get_cards_batch(card_requests)
        
        # Initialize counters
        lands = 0
        color_counts = defaultdict(int)
        mana_curve = defaultdict(int)
        card_types = defaultdict(int)
        rarity_counts = defaultdict(int)
        interaction_counts = defaultdict(int)
        interaction_cards = defaultdict(list)
        set_counts = defaultdict(int)
        missing_cards = []
        total_mana_value = 0
        nonland_cards = 0
        total_deck_value = 0.0
        card_prices = []  # For tracking most expensive cards
        
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
            if card_info.colors:
                for color in card_info.colors:
                    color_counts[color] += 1
            else:
                # Card has no colors, so it's colorless
                color_counts['C'] += 1
            
            # Card type tracking (count unique cards, not copies)
            primary_type = self._parse_primary_type(card_info.type_line)
            card_types[primary_type] += 1
            
            # Rarity tracking (count unique cards, not copies)
            rarity_counts[card_info.rarity] += 1
            
            # Price analysis
            if card_info.price_usd is not None:
                card_total_price = card_info.price_usd * quantity
                total_deck_value += card_total_price
                card_prices.append((card_name, card_info.price_usd))
            
            # Interaction categorization
            interaction_categories = self._categorize_interaction(card_name, card_info.type_line)
            for category in interaction_categories:
                interaction_counts[category] += 1
                interaction_cards[category].append(card_name)
            
            # Set tracking (count unique cards, not copies)
            set_code = deck.card_sets.get(card_name, 'Unknown')
            set_counts[set_code] += 1
        
        # Calculate average mana value (nonlands only)
        avg_mana_value = total_mana_value / nonland_cards if nonland_cards > 0 else 0
        
        # Find most expensive cards (top 5)
        most_expensive = sorted(card_prices, key=lambda x: x[1], reverse=True)[:5]
        
        # Basic set name mapping (can be expanded with API calls if needed)
        set_names = {
            'FIN': 'Final Fantasy',
            'MH3': 'Modern Horizons 3',
            'CLB': 'Commander Legends: Battle for Baldur\'s Gate',
            'MB2': 'Mystery Booster 2',
            'CMM': 'Commander Masters',
            'ELD': 'Throne of Eldraine',
            'IKO': 'Ikoria: Lair of Behemoths',
            'SLD': 'Secret Lair Drop',
            'FDN': 'Foundations',
            'LTC': 'The Lord of the Rings: Tales of Middle-earth Commander',
            'LTR': 'The Lord of the Rings: Tales of Middle-earth',
            'ZNR': 'Zendikar Rising',
            'AFR': 'Adventures in the Forgotten Realms',
            'WAR': 'War of the Spark',
            'DMU': 'Dominaria United',
            'MID': 'Midnight Hunt',
            'THB': 'Theros Beyond Death',
            'DSK': 'Duskmourn: House of Horror'
        }
        
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
            total_deck_value=total_deck_value,
            most_expensive_cards=most_expensive,
            rarity_counts=dict(rarity_counts),
            interaction_counts=dict(interaction_counts),
            interaction_cards=dict(interaction_cards),
            set_counts=dict(set_counts),
            set_names=set_names,
            missing_cards=missing_cards
        )
        
        return stats
