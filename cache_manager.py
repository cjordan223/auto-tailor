#!/usr/bin/env python3
"""
Cache Manager for JD Parser & Resume Tailoring Pipeline

Provides intelligent caching for:
1. LLM responses to avoid redundant API calls
2. Parsed job descriptions to speed up repeated processing
3. Compiled PDFs to avoid recompilation
4. Skills extraction results for similar job descriptions

Uses file-based caching with TTL (Time To Live) for automatic cleanup.
"""

import hashlib
import json
import os
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union
import gzip


class CacheManager:
    """Intelligent caching system for the resume tailoring pipeline"""

    def __init__(self, cache_dir: str = "cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600

        # Create subdirectories for different cache types
        (self.cache_dir / "llm").mkdir(exist_ok=True)
        (self.cache_dir / "parsed").mkdir(exist_ok=True)
        (self.cache_dir / "pdfs").mkdir(exist_ok=True)
        (self.cache_dir / "skills").mkdir(exist_ok=True)

    def _get_cache_key(self, data: Union[str, Dict, Any]) -> str:
        """Generate a deterministic cache key from data"""
        if isinstance(data, str):
            content = data
        elif isinstance(data, dict):
            # Sort dict items for deterministic hashing
            content = json.dumps(data, sort_keys=True)
        else:
            content = str(data)

        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _get_cache_path(self, cache_type: str, key: str, compressed: bool = True) -> Path:
        """Get the full path for a cache entry"""
        ext = ".gz" if compressed else ""
        return self.cache_dir / cache_type / f"{key}{ext}"

    def _is_expired(self, cache_path: Path) -> bool:
        """Check if a cache entry has expired"""
        if not cache_path.exists():
            return True

        file_age = time.time() - cache_path.stat().st_mtime
        return file_age > self.ttl_seconds

    def get(self, cache_type: str, key_data: Union[str, Dict, Any]) -> Optional[Any]:
        """Retrieve data from cache if it exists and is not expired"""
        key = self._get_cache_key(key_data)
        cache_path = self._get_cache_path(cache_type, key)

        if self._is_expired(cache_path):
            if cache_path.exists():
                cache_path.unlink()  # Clean up expired cache
            return None

        try:
            if cache_path.suffix == '.gz':
                with gzip.open(cache_path, 'rb') as f:
                    return pickle.load(f)
            else:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            print(f"Cache read error: {e}")
            if cache_path.exists():
                cache_path.unlink()  # Remove corrupted cache
            return None

    def set(self, cache_type: str, key_data: Union[str, Dict, Any],
            value: Any, compressed: bool = True) -> bool:
        """Store data in cache with optional compression"""
        try:
            key = self._get_cache_key(key_data)
            cache_path = self._get_cache_path(cache_type, key, compressed)

            if compressed:
                with gzip.open(cache_path, 'wb') as f:
                    pickle.dump(value, f)
            else:
                with open(cache_path, 'wb') as f:
                    pickle.dump(value, f)

            return True
        except Exception as e:
            print(f"Cache write error: {e}")
            return False

    def clear_expired(self) -> int:
        """Clear all expired cache entries and return count of removed files"""
        removed_count = 0

        for cache_type_dir in self.cache_dir.iterdir():
            if cache_type_dir.is_dir():
                for cache_file in cache_type_dir.iterdir():
                    if cache_file.is_file() and self._is_expired(cache_file):
                        cache_file.unlink()
                        removed_count += 1

        return removed_count

    def clear_all(self) -> int:
        """Clear all cache entries and return count of removed files"""
        removed_count = 0

        for cache_type_dir in self.cache_dir.iterdir():
            if cache_type_dir.is_dir():
                for cache_file in cache_type_dir.iterdir():
                    if cache_file.is_file():
                        cache_file.unlink()
                        removed_count += 1

        return removed_count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'expired_files': 0,
            'by_type': {}
        }

        for cache_type_dir in self.cache_dir.iterdir():
            if cache_type_dir.is_dir():
                cache_type = cache_type_dir.name
                type_stats = {
                    'files': 0,
                    'size_bytes': 0,
                    'expired': 0
                }

                for cache_file in cache_type_dir.iterdir():
                    if cache_file.is_file():
                        type_stats['files'] += 1
                        type_stats['size_bytes'] += cache_file.stat().st_size

                        if self._is_expired(cache_file):
                            type_stats['expired'] += 1

                stats['by_type'][cache_type] = type_stats
                stats['total_files'] += type_stats['files']
                stats['total_size_bytes'] += type_stats['size_bytes']
                stats['expired_files'] += type_stats['expired']

        return stats


# Global cache instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cache_llm_response(prompt: str, response: str) -> bool:
    """Cache an LLM response"""
    cache = get_cache_manager()
    return cache.set("llm", prompt, response)


def get_cached_llm_response(prompt: str) -> Optional[str]:
    """Get cached LLM response if available"""
    cache = get_cache_manager()
    return cache.get("llm", prompt)


def cache_parsed_jd(jd_content: str, parsed_result: Dict[str, Any]) -> bool:
    """Cache parsed job description results"""
    cache = get_cache_manager()
    return cache.set("parsed", jd_content, parsed_result)


def get_cached_parsed_jd(jd_content: str) -> Optional[Dict[str, Any]]:
    """Get cached parsed job description if available"""
    cache = get_cache_manager()
    return cache.get("parsed", jd_content)


def cache_skills_extraction(jd_content: str, skills_result: Dict[str, Any]) -> bool:
    """Cache skills extraction results"""
    cache = get_cache_manager()
    return cache.set("skills", jd_content, skills_result)


def get_cached_skills_extraction(jd_content: str) -> Optional[Dict[str, Any]]:
    """Get cached skills extraction if available"""
    cache = get_cache_manager()
    return cache.get("skills", jd_content)


def cache_pdf_compilation(tex_content: str, pdf_path: str) -> bool:
    """Cache PDF compilation result"""
    cache = get_cache_manager()
    return cache.set("pdfs", tex_content, pdf_path)


def get_cached_pdf_compilation(tex_content: str) -> Optional[str]:
    """Get cached PDF compilation if available"""
    cache = get_cache_manager()
    return cache.get("pdfs", tex_content)


def cleanup_cache() -> int:
    """Clean up expired cache entries"""
    cache = get_cache_manager()
    return cache.clear_expired()


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    cache = get_cache_manager()
    return cache.get_stats()
