"""Storage infrastructure."""

from app.infrastructure.storage.supabase_client import SupabaseStorageClient, storage_client

__all__ = ["SupabaseStorageClient", "storage_client"]
