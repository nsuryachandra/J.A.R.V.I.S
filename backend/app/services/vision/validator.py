"""Image format, size, header magic bytes, and privacy validation for Vision Agent."""

import base64
import binascii
from typing import Tuple
from app.core.exceptions import ValidationError

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB limit


class VisionValidator:
    """Security and format validator for multimodal vision frames and images."""

    @classmethod
    def clean_and_decode_base64(cls, raw_data: str) -> Tuple[bytes, str]:
        """Strip data URI prefix if present and decode base64 bytes, detecting or verifying media type."""
        if not raw_data or not isinstance(raw_data, str):
            raise ValidationError("Image data cannot be empty.")

        cleaned = raw_data.strip()
        media_type = "image/png"

        # Handle data URI prefix e.g. "data:image/jpeg;base64,..."
        if cleaned.startswith("data:"):
            header, _, payload = cleaned.partition(",")
            cleaned = payload
            if ";" in header:
                media_type = header[5:].split(";")[0].lower()

        try:
            image_bytes = base64.b64decode(cleaned, validate=True)
        except (binascii.Error, ValueError) as err:
            raise ValidationError(f"Invalid base64 encoded image string: {err}")

        if len(image_bytes) == 0:
            raise ValidationError("Decoded image content is 0 bytes.")

        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValidationError(
                f"Image size exceeds maximum limit of {MAX_IMAGE_BYTES // (1024 * 1024)}MB."
            )

        detected_type = cls.verify_magic_bytes(image_bytes)
        return image_bytes, detected_type or media_type

    @classmethod
    def verify_magic_bytes(cls, image_bytes: bytes) -> str:
        """Inspect binary header to ensure valid image magic bytes and prevent file upload spoofing."""
        if len(image_bytes) < 4:
            raise ValidationError("Image byte sequence is too short to be a valid image file.")

        # PNG: \x89PNG\r\n\x1a\n
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"

        # JPEG: \xff\xd8\xff
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"

        # WEBP: RIFF....WEBP
        if image_bytes.startswith(b"RIFF") and len(image_bytes) >= 12 and image_bytes[8:12] == b"WEBP":
            return "image/webp"

        # GIF: GIF87a or GIF89a
        if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
            return "image/gif"

        # If magic bytes do not match standard formats, raise error
        raise ValidationError(
            "Unsupported or unrecognized image header magic bytes. Supported formats: PNG, JPEG, WEBP, GIF."
        )

    @classmethod
    def validate_session_constraints(
        cls,
        session_type: str,
        consent_granted: bool,
    ) -> None:
        """Ensure explicit user consent and valid session configuration."""
        valid_types = {"IMAGE_UPLOAD", "SCREEN_SHARE", "CAMERA_STREAM"}
        if session_type.upper() not in valid_types:
            raise ValidationError(
                f"Invalid vision session type '{session_type}'. Must be one of: {', '.join(sorted(valid_types))}."
            )

        if not consent_granted:
            raise ValidationError(
                "Explicit user consent is mandatory to initiate vision, camera, or screen share inspection."
            )
