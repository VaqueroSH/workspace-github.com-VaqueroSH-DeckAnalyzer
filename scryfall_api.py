"""
Scryfall API client for fetching Magic: The Gathering card information.
"""

import requests
import time
import random
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


@dataclass
class CardImage:
    """Represents image URLs for a Magic card."""
    normal: Optional[str] = None
    large: Optional[str] = None
    art_crop: Optional[str] = None
    border_crop: Optional[str] = None


class ScryfallAPI:
    """Client for interacting with the Scryfall API."""
    
    def __init__(self):
        self.base_url = "https://api.scryfall.com"
        self.headers = {
            'User-Agent': 'MTGDeckAnalyzer/1.0',
            'Accept': 'application/json;q=0.9,*/*;q=0.8'
        }
        self.cache: Dict[str, CardInfo] = {}
        self.last_request_time = 0
        self.min_delay = 0.1  # Minimum 100ms between requests (10 req/sec max)
    
    def _make_request_with_retry(self, url: str, params: Dict, max_retries: int = 3) -> Optional[requests.Response]:
        """
        Make a request with exponential backoff retry for rate limiting.
        
        Args:
            url: The URL to request
            params: Query parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            Response object if successful, None if all retries failed
        """
        for attempt in range(max_retries + 1):
            # Rate limiting - ensure we don't exceed our request rate
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_delay:
                time.sleep(self.min_delay - time_since_last)
            
            try:
                self.last_request_time = time.time()
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 404:
                    # Card not found - don't retry
                    return response
                elif response.status_code == 429:
                    # Rate limited - implement exponential backoff
                    if attempt < max_retries:
                        # Extract retry-after header if available
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                wait_time = float(retry_after)
                            except ValueError:
                                wait_time = 2 ** attempt  # Exponential backoff
                        else:
                            wait_time = 2 ** attempt + random.uniform(0, 1)  # Jitter
                        
                        time.sleep(wait_time)
                        continue
                    else:
                        # Max retries exceeded
                        return None
                else:
                    # Other HTTP error - don't retry
                    return None
                    
            except requests.RequestException:
                if attempt < max_retries:
                    # Network error - retry with exponential backoff
                    wait_time = 2 ** attempt + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
                else:
                    return None
        
        return None
        
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
            response = self._make_request_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                card_info = self._parse_card_data(data)
                
                # Cache the result
                self.cache[cache_key] = card_info
                return card_info
                
            elif response and response.status_code == 404:
                # Card not found - silently return None for cleaner web interface
                return None
            else:
                # API error or no response - silently return None for cleaner web interface
                return None
                
        except Exception as e:
            # Unexpected error - silently return None for cleaner web interface
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
            response = self._make_request_with_retry(url, params)
            
            if response and response.status_code == 200:
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
    
    def get_cards_batch(self, card_requests: list) -> Dict[str, Optional[CardInfo]]:
        """
        Fetch multiple cards with built-in rate limiting and retry logic.
        
        Args:
            card_requests: List of (card_name, set_code) tuples or card names
            
        Returns:
            Dictionary mapping card names to CardInfo objects (or None if not found)
        """
        results = {}
        
        for request in card_requests:
            if isinstance(request, tuple):
                card_name, set_code = request
                # Progress reporting handled by Streamlit interface
                results[card_name] = self.get_card(card_name, set_code)
            else:
                card_name = request
                # Progress reporting handled by Streamlit interface
                results[card_name] = self.get_card(card_name)
        
        return results

    def get_card_image(self, card_name: str, set_code: Optional[str] = None) -> Optional[CardImage]:
        """
        Fetch image URLs for a specific card.

        Args:
            card_name: Name of the card
            set_code: Optional set code for specific printing

        Returns:
            CardImage object with image URLs, or None if not found
        """
        # First try to get the card data
        response = self._make_request_with_retry(
            f"{self.base_url}/cards/named",
            {'exact': card_name, 'set': set_code} if set_code else {'exact': card_name}
        )

        if not response or response.status_code != 200:
            return None

        data = response.json()

        # Extract image URLs
        image_uris = data.get('image_uris', {})

        # For double-faced cards, try to get the front face
        if not image_uris and 'card_faces' in data:
            front_face = data['card_faces'][0] if data['card_faces'] else {}
            image_uris = front_face.get('image_uris', {})

        return CardImage(
            normal=image_uris.get('normal'),
            large=image_uris.get('large'),
            art_crop=image_uris.get('art_crop'),
            border_crop=image_uris.get('border_crop')
        )
