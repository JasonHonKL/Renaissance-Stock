# data/cache.py
import json
import time
import logging
from datetime import datetime
from config import CACHE_EXPIRY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Cache:
    """Simple in-memory cache with expiration."""
    
    def __init__(self):
        self._cache = {}
    
    def get(self, key):
        """Get a value from the cache if it exists and is not expired."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if time.time() > entry['expiry']:
            # Entry has expired
            del self._cache[key]
            return None
        
        return entry['value']
    
    def set(self, key, value, expiry=CACHE_EXPIRY):
        """Set a value in the cache with an expiration time."""
        self._cache[key] = {
            'value': value,
            'expiry': time.time() + expiry
        }
        return True
    
    def delete(self, key):
        """Delete a key from the cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self):
        """Clear all entries from the cache."""
        self._cache = {}
        return True
    
    def clean_expired(self):
        """Clean all expired entries from the cache."""
        current_time = time.time()
        expired_keys = [k for k, v in self._cache.items() if current_time > v['expiry']]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)

# Initialize a global cache instance
cache = Cache()