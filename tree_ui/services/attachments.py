from __future__ import annotations

import base64
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile

from tree_ui.models import ConversationNode, NodeAttachment


ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def validate_image_uploads(files: list[UploadedFile]) -> list[UploadedFile]:
    validated: list[UploadedFile] = []
    for file in files:
        content_type = (file.content_type or "").strip().lower()
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValueError("Only JPEG, PNG, WEBP, and GIF images are supported.")
        validated.append(file)
    return validated


def create_node_attachments(*, node: ConversationNode, files: list[UploadedFile]) -> list[NodeAttachment]:
    attachments: list[NodeAttachment] = []
    for file in validate_image_uploads(files):
        attachment = NodeAttachment.objects.create(
            node=node,
            kind=NodeAttachment.Kind.IMAGE,
            file=file,
            original_name=file.name[:255],
            content_type=(file.content_type or "")[:120],
            size_bytes=max(int(getattr(file, "size", 0) or 0), 0),
        )
        attachments.append(attachment)
    return attachments


def encode_attachment_as_data_url(*, file_path: str, content_type: str) -> str:
    mime_type = content_type.strip() or "application/octet-stream"
    encoded = base64.b64encode(Path(file_path).read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"

