from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile

from tree_ui.models import ConversationNode, NodeAttachment


ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
ALLOWED_PDF_CONTENT_TYPES = {
    "application/pdf",
}

def validate_supported_uploads(files: list[UploadedFile]) -> list[UploadedFile]:
    validated: list[UploadedFile] = []
    for file in files:
        content_type = (file.content_type or "").strip().lower()
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES and content_type not in ALLOWED_PDF_CONTENT_TYPES:
            raise ValueError("Only JPEG, PNG, WEBP, GIF, and PDF files are supported.")
        validated.append(file)
    return validated


def _resolve_attachment_kind(content_type: str) -> str:
    if content_type in ALLOWED_PDF_CONTENT_TYPES:
        return NodeAttachment.Kind.PDF
    return NodeAttachment.Kind.IMAGE


def create_node_attachments(*, node: ConversationNode, files: list[UploadedFile]) -> list[NodeAttachment]:
    attachments: list[NodeAttachment] = []
    for file in validate_supported_uploads(files):
        content_type = (file.content_type or "").strip().lower()
        attachment = NodeAttachment.objects.create(
            node=node,
            kind=_resolve_attachment_kind(content_type),
            file=file,
            original_name=file.name[:255],
            content_type=content_type[:120],
            size_bytes=max(int(getattr(file, "size", 0) or 0), 0),
        )
        attachments.append(attachment)
    return attachments


def encode_attachment_as_data_url(*, file_path: str, content_type: str) -> str:
    mime_type = content_type.strip() or "application/octet-stream"
    encoded = base64.b64encode(Path(file_path).read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def render_pdf_attachment_as_data_urls(*, file_path: str, max_pages: int) -> list[str]:
    if max_pages <= 0:
        return []

    pdf_path = Path(file_path)
    if not pdf_path.exists():
        raise ValueError("PDF attachment file is missing.")

    with tempfile.TemporaryDirectory(prefix="llm_tree_pdf_") as temp_dir:
        output_prefix = Path(temp_dir) / "page"
        command = [
            "pdftoppm",
            "-png",
            "-f",
            "1",
            "-l",
            str(max_pages),
            str(pdf_path),
            str(output_prefix),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.decode("utf-8", errors="ignore").strip() or "Unable to render PDF pages."
            raise ValueError(message) from exc

        rendered_pages = sorted(Path(temp_dir).glob("page-*.png"))
        return [
            encode_attachment_as_data_url(file_path=str(page_path), content_type="image/png")
            for page_path in rendered_pages
        ]
