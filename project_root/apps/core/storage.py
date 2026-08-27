"""
Custom Django storage backend for Supabase Storage.

Provides file storage operations compatible with Django's file storage API.
"""

import os
from datetime import timedelta
from django.core.files.storage import Storage
from django.core.exceptions import ImproperlyConfigured
from apps.core.supabase_client import get_supabase_client


class SupabaseStorage(Storage):
    """
    Django storage backend for Supabase Storage.

    Handles file uploads, downloads, and deletion using Supabase Storage API.
    """

    def __init__(self):
        self.bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "allocgest-storage")
        try:
            self.client = get_supabase_client()
        except ValueError as e:
            raise ImproperlyConfigured(f"Supabase not configured: {e}")

    def _open(self, name, mode="rb"):
        """
        Open a file from Supabase Storage.

        Args:
            name: Path to file in storage
            mode: File mode (not used for Supabase)

        Returns:
            File content as bytes
        """
        try:
            response = self.client.storage.from_(self.bucket_name).download(name)
            return response
        except Exception as e:
            raise FileNotFoundError(f"File {name} not found in Supabase: {e}")

    def _save(self, name, content):
        """
        Save a file to Supabase Storage.

        Args:
            name: Path where file should be saved
            content: File content

        Returns:
            Path to saved file
        """
        try:
            # Read content if it's a file-like object
            if hasattr(content, "read"):
                file_data = content.read()
            else:
                file_data = content

            # Upload to Supabase
            self.client.storage.from_(self.bucket_name).upload(
                file=file_data,
                path=name,
                file_options={"cacheControl": "3600", "upsert": "true"},
            )

            return name
        except Exception as e:
            raise IOError(f"Failed to save {name} to Supabase: {e}")

    def delete(self, name):
        """
        Delete a file from Supabase Storage.

        Args:
            name: Path to file to delete
        """
        try:
            self.client.storage.from_(self.bucket_name).remove([name])
        except Exception as e:
            raise IOError(f"Failed to delete {name} from Supabase: {e}")

    def exists(self, name):
        """
        Check if a file exists in Supabase Storage.

        Args:
            name: Path to file

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.storage.from_(self.bucket_name).download(name)
            return True
        except Exception:
            return False

    def listdir(self, path):
        """
        List contents of a directory in Supabase Storage.

        Args:
            path: Directory path

        Returns:
            Tuple of (directories, files)
        """
        try:
            response = self.client.storage.from_(self.bucket_name).list(path=path)
            directories = []
            files = []

            for item in response:
                if item.get("metadata", {}).get("mimetype") == "application/octet-stream":
                    directories.append(item["name"])
                else:
                    files.append(item["name"])

            return directories, files
        except Exception as e:
            raise IOError(f"Failed to list directory {path}: {e}")

    def size(self, name):
        """
        Return the size of a file in bytes.

        Args:
            name: Path to file

        Returns:
            File size in bytes
        """
        try:
            response = self.client.storage.from_(self.bucket_name).list(
                path=os.path.dirname(name)
            )

            for item in response:
                if item["name"] == os.path.basename(name):
                    return item.get("metadata", {}).get("size", 0)

            raise FileNotFoundError(f"File {name} not found")
        except Exception as e:
            raise IOError(f"Failed to get size of {name}: {e}")

    def url(self, name):
        """
        Return the URL to access a file.

        Args:
            name: Path to file

        Returns:
            Public URL to file
        """
        try:
            supabase_url = os.getenv("SUPABASE_URL").rstrip("/")
            return f"{supabase_url}/storage/v1/object/public/{self.bucket_name}/{name}"
        except Exception as e:
            raise ValueError(f"Failed to generate URL for {name}: {e}")

    def get_accessed_time(self, name):
        """Not supported by Supabase Storage API."""
        raise NotImplementedError("Supabase Storage does not support access time tracking")

    def get_created_time(self, name):
        """Not supported by Supabase Storage API."""
        raise NotImplementedError("Supabase Storage does not support creation time tracking")

    def get_modified_time(self, name):
        """Not supported by Supabase Storage API."""
        raise NotImplementedError("Supabase Storage does not support modification time tracking")
