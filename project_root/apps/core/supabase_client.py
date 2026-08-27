"""
Supabase client initialization for AllocGest-DESUP.

Provides a singleton instance of the Supabase client for use throughout the application.
"""

import os
from supabase import create_client, Client

# Initialize Supabase client
supabase: Client = None

def get_supabase_client() -> Client:
    """
    Get or create the Supabase client instance.

    Returns:
        Client: Supabase client instance

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_KEY are not configured
    """
    global supabase

    if supabase is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY environment variables must be set"
            )

        supabase = create_client(supabase_url, supabase_key)

    return supabase


# Default client instance for direct import
try:
    supabase = get_supabase_client()
except ValueError:
    # Allow import even if not configured (will raise error on use)
    supabase = None
