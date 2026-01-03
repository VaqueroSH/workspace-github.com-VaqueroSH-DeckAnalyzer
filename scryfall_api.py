"""
Scryfall API client for fetching Magic: The Gathering card information.
Enhanced with persistent caching, connection pooling, and V2 features.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import random
import pickle
import sys
import re
from pathlib import Path
from typing import Optional, Dict, Set, Callable
from dataclasses import dataclass, field


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
    
    # V2 fields for enhanced analysis
    oracle_text: str = ""
    keywords: Set[str] = field(default_factory=set)
    legalities: Dict[str, str] = field(default_factory=dict)
    produced_mana: Set[str] = field(default_factory=set)
    power: Optional[int] = None
    toughness: Optional[int] = None
    mana_cost: str = ""
    
    @property
    def color_identity(self) -> Set[str]:
        """Returns the card's color identity (same as colors for most cards)."""
        return self.colors


@dataclass
class CachedCardInfo:
    """Wrapper for cached card info with expiration support."""
    card_info: CardInfo
    cached_at: float  # timestamp
    ttl: int = 86400  # 24 hours in seconds for price data


@dataclass
class CardImage:
    """Represents image URLs for a Magic card."""
    normal: Optional[str] = None
    large: Optional[str] = None
    art_crop: Optional[str] = None
    border_crop: Optional[str] = None


class ScryfallAPI:
    """Client for interacting with the Scryfall API with persistent caching."""
    
    def __init__(self, cache_file: str = 'data/scryfall_cache.pkl'):
        """
        Initialize the Scryfall API client.
        
        Args:
            cache_file: Path to the persistent cache file
        """
        self.base_url = "https://api.scryfall.com"
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, CachedCardInfo] = self._load_cache()
        self.last_request_time = 0
        self.min_delay = 0.1  # Minimum 100ms between requests (10 req/sec max)
        
        # Connection pooling with session
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=retry_strategy
        )
        self.session.mount('https://', adapter)
        self.session.headers.update({
            'User-Agent': 'MTGDeckAnalyzer/2.0',
            'Accept': 'application/json;q=0.9,*/*;q=0.8'
        })
        
        # Cache statistics
        self._cache_hits = 0
        self._cache_misses = 0
    
    def _load_cache(self) -> Dict[str, CachedCardInfo]:
        """Load cache from disk if it exists."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    # Convert old format (Dict[str, CardInfo]) to new format if needed
                    if cache_data and isinstance(next(iter(cache_data.values())), CardInfo):
                        # Migrate old cache format
                        new_cache = {}
                        for key, card_info in cache_data.items():
                            new_cache[key] = CachedCardInfo(
                                card_info=card_info,
                                cached_at=time.time(),
                                ttl=86400
                            )
                        return new_cache
                    return cache_data
            except Exception:
                # If cache is corrupted, start fresh
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception:
            # Silently fail if cache can't be saved
            pass
    
    def _is_cache_valid(self, cached: CachedCardInfo) -> bool:
        """
        Check if cached data is still valid.
        
        Args:
            cached: CachedCardInfo object to validate
            
        Returns:
            True if cache is valid, False otherwise
        """
        # Non-price data never expires (or use very long TTL)
        if cached.card_info.price_usd is None:
            return True
        
        # Price data expires after TTL
        age = time.time() - cached.cached_at
        return age < cached.ttl
    
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
                response = self.session.get(url, params=params, timeout=10)
                
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
    
    def get_card(self, card_name: str, set_code: str = None, use_fuzzy: bool = False) -> Optional[CardInfo]:
        """
        Fetch card information from Scryfall API.
        
        Args:
            card_name: The exact name of the card to fetch
            set_code: Optional set code for more accurate pricing
            use_fuzzy: If True, try fuzzy matching if exact match fails
            
        Returns:
            CardInfo object if found, None otherwise
        """
        # Create cache key that includes set code if available
        cache_key = f"{card_name}|{set_code}" if set_code else card_name
        
        # Check cache first
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if self._is_cache_valid(cached):
                self._cache_hits += 1
                return cached.card_info
            else:
                # Cache expired, remove it
                del self.cache[cache_key]
        
        self._cache_misses += 1
        
        # Try to get specific set version first if set code is provided
        if set_code:
            card_info = self._get_card_from_set(card_name, set_code)
            if card_info:
                self._cache_card(cache_key, card_info)
                return card_info
        
        # Fallback to general card lookup
        url = f"{self.base_url}/cards/named"
        params = {'fuzzy' if use_fuzzy else 'exact': card_name}
        
        try:
            response = self._make_request_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                card_info = self._parse_card_data(data)
                
                # Cache the result
                self._cache_card(cache_key, card_info)
                return card_info
                
            elif response and response.status_code == 404:
                # Card not found - try fuzzy search if not already tried
                if not use_fuzzy:
                    return self.get_card(card_name, set_code, use_fuzzy=True)
                return None
            else:
                # API error or no response
                return None
                
        except Exception:
            # Unexpected error
            return None
    
    def _cache_card(self, cache_key: str, card_info: CardInfo):
        """Cache a card with timestamp."""
        self.cache[cache_key] = CachedCardInfo(
            card_info=card_info,
            cached_at=time.time(),
            ttl=86400 if card_info.price_usd is not None else 604800  # 24h for prices, 7 days for non-price
        )
        self._save_cache()
    
    def search_card_fuzzy(self, card_name: str) -> Optional[CardInfo]:
        """
        Try fuzzy matching if exact match fails.
        
        Args:
            card_name: The card name to search for
            
        Returns:
            CardInfo object if found, None otherwise
        """
        return self.get_card(card_name, use_fuzzy=True)
    
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
        
        # V2 fields
        oracle_text = data.get('oracle_text', '')
        keywords = set(data.get('keywords', []))
        legalities = data.get('legalities', {})
        
        # Parse produced mana (for mana rocks/dorks)
        produced_mana = set()
        if 'produced_mana' in data:
            produced_mana = set(data['produced_mana'])
        elif 'mana_cost' in data and '{T}' in oracle_text:
            # Try to infer from oracle text for basic lands
            if 'Add' in oracle_text and 'mana' in oracle_text:
                # Extract mana symbols from oracle text (simplified)
                mana_symbols = re.findall(r'\{([WUBRGC])\}', oracle_text)
                produced_mana = set(mana_symbols)
        
        # Parse power/toughness
        power = toughness = None
        if 'power' in data and data['power'] not in ['*', '', None]:
            try:
                power = int(data['power'])
            except (ValueError, TypeError):
                pass
        
        if 'toughness' in data and data['toughness'] not in ['*', '', None]:
            try:
                toughness = int(data['toughness'])
            except (ValueError, TypeError):
                pass
        
        # Parse mana cost (e.g., "{2}{U}{U}")
        mana_cost = data.get('mana_cost', '')
        
        return CardInfo(
            name=name,
            colors=colors,
            mana_value=mana_value,
            type_line=type_line,
            is_land=is_land,
            rarity=rarity,
            price_usd=price_usd,
            oracle_text=oracle_text,
            keywords=keywords,
            legalities=legalities,
            produced_mana=produced_mana,
            power=power,
            toughness=toughness,
            mana_cost=mana_cost
        )
    
    def get_cards_batch(
        self, 
        card_requests: list,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Optional[CardInfo]]:
        """
        Fetch multiple cards with built-in rate limiting and retry logic.
        
        Args:
            card_requests: List of (card_name, set_code) tuples or card names
            progress_callback: Optional function(current, total, card_name) for progress updates
            
        Returns:
            Dictionary mapping card names to CardInfo objects (or None if not found)
        """
        results = {}
        total = len(card_requests)
        
        for idx, request in enumerate(card_requests):
            if isinstance(request, tuple):
                card_name, set_code = request
                results[card_name] = self.get_card(card_name, set_code)
            else:
                card_name = request
                results[card_name] = self.get_card(card_name)
            
            if progress_callback:
                progress_callback(idx + 1, total, card_name)
        
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
    
    # Cache management methods
    
    def clear_cache(self):
        """Clear all cached data from memory and disk."""
        self.cache.clear()
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
            except Exception:
                pass
        self._cache_hits = 0
        self._cache_misses = 0
    
    def invalidate_prices(self):
        """Force refresh of price data on next request by removing price entries."""
        current_time = time.time()
        expired_keys = []
        
        for key, cached in self.cache.items():
            if cached.card_info.price_usd is not None:
                # Mark price data as expired
                cached.cached_at = 0
        
        # Remove expired entries
        for key in expired_keys:
            del self.cache[key]
        
        self._save_cache()
    
    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate cache size
        cache_size_bytes = sys.getsizeof(self.cache)
        for key, value in self.cache.items():
            cache_size_bytes += sys.getsizeof(key) + sys.getsizeof(value)
        
        return {
            'total_entries': len(self.cache),
            'cache_size_mb': cache_size_bytes / 1024 / 1024,
            'hit_rate': hit_rate,
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'total_requests': total_requests
        }
