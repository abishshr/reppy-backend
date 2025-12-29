"""Supabase Storage client for image uploads."""

import base64
import os
from datetime import datetime
from uuid import uuid4

import httpx


class SupabaseStorageClient:
    """Client for uploading images to Supabase Storage."""

    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.bucket = os.getenv("SUPABASE_BUCKET", "meal-images")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.key}",
            "apikey": self.key,
        }

    @property
    def _storage_url(self) -> str:
        return f"{self.url}/storage/v1"

    async def upload_image(
        self,
        image_data: bytes,
        content_type: str = "image/jpeg",
        user_id: str | None = None,
    ) -> str:
        """
        Upload an image to Supabase Storage.

        Args:
            image_data: Raw image bytes
            content_type: MIME type (image/jpeg, image/png)
            user_id: Optional user ID for organizing files

        Returns:
            Public URL of the uploaded image
        """
        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid4().hex[:8]
        extension = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]

        if user_id:
            filename = f"{user_id}/{timestamp}_{unique_id}.{extension}"
        else:
            filename = f"uploads/{timestamp}_{unique_id}.{extension}"

        # Upload to Supabase Storage
        upload_url = f"{self._storage_url}/object/{self.bucket}/{filename}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                upload_url,
                content=image_data,
                headers={
                    **self._headers,
                    "Content-Type": content_type,
                },
            )

            if response.status_code not in (200, 201):
                raise Exception(f"Failed to upload image: {response.text}")

        # Return public URL
        public_url = f"{self.url}/storage/v1/object/public/{self.bucket}/{filename}"
        return public_url

    async def upload_base64_image(
        self,
        base64_data: str,
        content_type: str = "image/jpeg",
        user_id: str | None = None,
    ) -> str:
        """
        Upload a base64-encoded image to Supabase Storage.

        Args:
            base64_data: Base64-encoded image string (without data URI prefix)
            content_type: MIME type
            user_id: Optional user ID

        Returns:
            Public URL of the uploaded image
        """
        # Remove data URI prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]

        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)

        return await self.upload_image(image_bytes, content_type, user_id)

    async def delete_image(self, file_path: str) -> bool:
        """
        Delete an image from Supabase Storage.

        Args:
            file_path: Path within the bucket (e.g., "user_id/filename.jpg")

        Returns:
            True if deleted successfully
        """
        delete_url = f"{self._storage_url}/object/{self.bucket}/{file_path}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                delete_url,
                headers=self._headers,
            )

            return response.status_code == 200


# Singleton instance
storage_client = SupabaseStorageClient() if os.getenv("SUPABASE_URL") else None
