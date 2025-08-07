"""
Scryfall API client for fetching Magic: The Gathering card information.
"""

import requests
import time
from typing import Optional, Dict, Set
from dataclasses import dataclass


@dataclass
class CardInfo:
    """Represents essential information about a Magic card."""
    name: str
    colors: Set[str]
    mana_value: int
    type_line: str
    is_land: bool
    
    @property
    def color_identity(self) -> Set[str]:
        """Returns the card's color identity (same as colors for most cards)."""
        return self.colors


class ScryfallAPI:
    """Client for interacting with the Scryfall API."""
    
    def __init__(self):
        self.base_url = "https://api.scryfall.com"
        self.headers = {
            'User-Agent': 'MTGDeckAnalyzer/1.0',
            'Accept': 'application/json;q=0.9,*/*;q=0.8'
        }
        self.cache: Dict[str, CardInfo] = {}
        
    def get_card(self, card_name: str) -> Optional[CardInfo]:
        """
        Fetch card information from Scryfall API.
        
        Args:
            card_name: The exact name of the card to fetch
            
        Returns:
            CardInfo object if found, None otherwise
        """
        # Check cache first
        if card_name in self.cache:
            return self.cache[card_name]
        
        url = f"{self.base_url}/cards/named"
        params = {'exact': card_name}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                card_info = self._parse_card_data(data)
                
                # Cache the result
                self.cache[card_name] = card_info
                return card_info
                
            elif response.status_code == 404:
                print(f"Card not found: {card_name}")
                return None
            else:
                print(f"API error for {card_name}: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            print(f"Network error fetching {card_name}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error fetching {card_name}: {e}")
            return None
    
    def _parse_card_data(self, data: Dict) -> CardInfo:
        """Parse card data from Scryfall API response."""
        name = data['name']
        colors = set(data.get('colors', []))
        mana_value = int(data.get('cmc', 0))
        type_line = data.get('type_line', '')
        is_land = 'Land' in type_line
        
        return CardInfo(
            name=name,
            colors=colors,
            mana_value=mana_value,
            type_line=type_line,
            is_land=is_land
        )
    
    def get_cards_batch(self, card_names: list, delay: float = 0.1) -> Dict[str, Optional[CardInfo]]:
        """
        Fetch multiple cards with rate limiting.
        
        Args:
            card_names: List of card names to fetch
            delay: Delay between requests in seconds (default: 0.1 for 10 req/sec)
            
        Returns:
            Dictionary mapping card names to CardInfo objects (or None if not found)
        """
        results = {}
        total = len(card_names)
        
        for i, card_name in enumerate(card_names, 1):
            print(f"Fetching {i}/{total}: {card_name}")
            results[card_name] = self.get_card(card_name)
            
            # Rate limiting - don't delay after the last request
            if i < total:
                time.sleep(delay)
        
        return results
