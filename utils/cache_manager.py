import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib

class CacheManager:
    def __init__(self, cache_dir: str = "static/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def get_cache_key(self, data: Any) -> str:
        """Generate cache key from data"""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def get(self, key: str, ttl: int = 3600) -> Optional[Any]:
        """Get cached data if not expired"""
        cache_file = self.cache_dir / f"{key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is expired
            if time.time() - cache_data['timestamp'] > ttl:
                cache_file.unlink()
                return None
            
            return cache_data['data']
        except:
            return None
    
    def set(self, key: str, data: Any):
        """Cache data with timestamp"""
        cache_file = self.cache_dir / f"{key}.json"
        
        cache_data = {
            'timestamp': time.time(),
            'data': data
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
    
    def clear_old(self, max_age: int = 86400):
        """Clear old cache files"""
        cutoff = time.time() - max_age
        
        for cache_file in self.cache_dir.glob('*.json'):
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                if cache_data['timestamp'] < cutoff:
                    cache_file.unlink()
            except:
                cache_file.unlink()