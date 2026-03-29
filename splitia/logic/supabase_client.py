"""
Supabase client helpers for SplitIA.

This module keeps environment parsing isolated so the rest of the codebase can
decide whether to use Supabase or local in-memory storage.
"""

import os

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - depends on runtime environment
    create_client = None


_supabase_client = None


def get_supabase_settings():
    """Return Supabase settings from environment variables."""
    url = (
        os.getenv('SUPABASE_URL', '').strip()
        or os.getenv('NEXT_PUBLIC_SUPABASE_URL', '').strip()
    )
    key = (
        os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()
        or os.getenv('SUPABASE_ANON_KEY', '').strip()
        or os.getenv('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY', '').strip()
    )
    return {
        'url': url,
        'key': key,
    }


def has_supabase_config():
    """Return True when enough configuration exists to use Supabase."""
    settings = get_supabase_settings()
    return bool(settings['url'] and settings['key'])


def get_supabase_client():
    """Return a lazy singleton Supabase client."""
    global _supabase_client

    settings = get_supabase_settings()
    if not settings['url'] or not settings['key']:
        raise RuntimeError(
            'Supabase configuration is missing. Set SUPABASE_URL and a public or service key.'
        )

    if create_client is None:
        raise RuntimeError(
            'Supabase Python client is not installed. Run `pip install -r requirements.txt`.'
        )

    if _supabase_client is None:
        _supabase_client = create_client(settings['url'], settings['key'])

    return _supabase_client
