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
    rarity: str
    price_usd: Optional[float] = None
    
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
        
    def get_card(self, card_name: str, set_code: str = None) -> Optional[CardInfo]:
        """
        Fetch card information from Scryfall API.
        
        Args:
            card_name: The exact name of the card to fetch
            set_code: Optional set code for more accurate pricing
            
        Returns:
            CardInfo object if found, None otherwise
        """
        # Create cache key that includes set code if available
        cache_key = f"{card_name}|{set_code}" if set_code else card_name
        
        # Check cache first
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Try to get specific set version first if set code is provided
        if set_code:
            card_info = self._get_card_from_set(card_name, set_code)
            if card_info:
                self.cache[cache_key] = card_info
                return card_info
        
        # Fallback to general card lookup
        url = f"{self.base_url}/cards/named"
        params = {'exact': card_name}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                card_info = self._parse_card_data(data)
                
                # Cache the result
                self.cache[cache_key] = card_info
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
    
    def _get_card_from_set(self, card_name: str, set_code: str) -> Optional[CardInfo]:
        """
        Try to fetch a card from a specific set for more accurate pricing.
        
        Args:
            card_name: The exact name of the card to fetch
            set_code: The set code to search in
            
        Returns:
            CardInfo object if found, None otherwise
        """
        url = f"{self.base_url}/cards/named"
        params = {
            'exact': card_name,
            'set': set_code.lower()
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_card_data(data)
            else:
                # If specific set lookup fails, we'll fall back to general lookup
                return None
                
        except Exception:
            # If there's any error with set-specific lookup, fall back to general
            return None
    
    def _parse_card_data(self, data: Dict) -> CardInfo:
        """Parse card data from Scryfall API response."""
        name = data['name']
        colors = set(data.get('colors', []))
        mana_value = int(data.get('cmc', 0))
        type_line = data.get('type_line', '')
        is_land = 'Land' in type_line
        rarity = data.get('rarity', 'unknown')
        
        # Parse price (USD)
        price_usd = None
        if 'prices' in data and data['prices'].get('usd'):
            try:
                price_usd = float(data['prices']['usd'])
            except (ValueError, TypeError):
                price_usd = None
        
        return CardInfo(
            name=name,
            colors=colors,
            mana_value=mana_value,
            type_line=type_line,
            is_land=is_land,
            rarity=rarity,
            price_usd=price_usd
        )
    
    def get_cards_batch(self, card_requests: list, delay: float = 0.1) -> Dict[str, Optional[CardInfo]]:
        """
        Fetch multiple cards with rate limiting.
        
        Args:
            card_requests: List of (card_name, set_code) tuples or card names
            delay: Delay between requests in seconds (default: 0.1 for 10 req/sec)
            
        Returns:
            Dictionary mapping card names to CardInfo objects (or None if not found)
        """
        results = {}
        total = len(card_requests)
        
        for i, request in enumerate(card_requests, 1):
            if isinstance(request, tuple):
                card_name, set_code = request
                print(f"Fetching {i}/{total}: {card_name} ({set_code})")
                results[card_name] = self.get_card(card_name, set_code)
            else:
                card_name = request
                print(f"Fetching {i}/{total}: {card_name}")
                results[card_name] = self.get_card(card_name)
            
            # Rate limiting - don't delay after the last request
            if i < total:
                time.sleep(delay)
        
        return results
