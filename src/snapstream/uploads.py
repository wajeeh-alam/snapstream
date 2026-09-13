"""Private S3 upload URL generation and uploaded-object verification."""

import asyncio
from typing import Any
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from .config import Settings
from .schemas import MediaReference, UploadPresignRequest, UploadPresignResponse

_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}


class InvalidMedia(ValueError):
    """The requested or uploaded object violates the media contract."""


class MediaServiceUnavailable(RuntimeError):
    """S3 could not be reached to verify media."""


def validate_media_contract(content_type: str, size_bytes: int, settings: Settings) -> None:
    if content_type not in settings.allowed_media_types:
        raise InvalidMedia(f"unsupported media type: {content_type}")
    if size_bytes > settings.max_media_size_bytes:
        raise InvalidMedia(
            f"media exceeds the {settings.max_media_size_bytes}-byte size limit"
        )


def create_presigned_upload(
    s3: Any,
    user_id: str,
    request: UploadPresignRequest,
    settings: Settings,
) -> UploadPresignResponse:
    if not settings.s3_bucket:
        raise MediaServiceUnavailable("S3_BUCKET is not configured")
    validate_media_contract(request.content_type, request.size_bytes, settings)
    extension = _EXTENSIONS.get(request.content_type, "")
    key = f"uploads/{user_id}/{uuid4().hex}{extension}"
    headers = {
        "Content-Type": request.content_type,
        "Content-Length": str(request.size_bytes),
        "x-amz-meta-owner-id": user_id,
        "x-amz-server-side-encryption": "AES256",
    }
    params = {
        "Bucket": settings.s3_bucket,
        "Key": key,
        "ContentType": request.content_type,
        "ContentLength": request.size_bytes,
        "Metadata": {"owner-id": user_id},
        "ServerSideEncryption": "AES256",
    }
    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=settings.upload_url_ttl_seconds,
            HttpMethod="PUT",
        )
    except (BotoCoreError, ClientError) as exc:
        raise MediaServiceUnavailable("could not create upload URL") from exc
    return UploadPresignResponse(
        upload_url=url,
        bucket=settings.s3_bucket,
        key=key,
        headers=headers,
        expires_in=settings.upload_url_ttl_seconds,
    )


async def verify_uploaded_media(
    s3: Any,
    user_id: str,
    media: MediaReference,
    settings: Settings,
) -> None:
    validate_media_contract(media.content_type, media.size_bytes, settings)
    if not media.key.startswith(f"uploads/{user_id}/"):
        raise InvalidMedia("media key does not belong to the authenticated user")
    try:
        metadata = await asyncio.to_thread(
            s3.head_object,
            Bucket=settings.s3_bucket,
            Key=media.key,
        )
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"403", "404", "NoSuchKey", "NotFound"}:
            raise InvalidMedia("uploaded media was not found") from exc
        raise MediaServiceUnavailable("could not verify uploaded media") from exc
    except BotoCoreError as exc:
        raise MediaServiceUnavailable("could not verify uploaded media") from exc

    if int(metadata.get("ContentLength", -1)) != media.size_bytes:
        raise InvalidMedia("uploaded media size does not match the post metadata")
    if str(metadata.get("ContentType", "")).lower() != media.content_type:
        raise InvalidMedia("uploaded media type does not match the post metadata")
    owner_id = metadata.get("Metadata", {}).get("owner-id")
    if owner_id != user_id:
        raise InvalidMedia("uploaded media ownership metadata is invalid")
