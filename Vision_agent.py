"""A deterministic vision worker; it deliberately has no autonomous reasoning.

Combines Tesseract OCR (exact text) with a local VLM served by Ollama

(scene/chart/diagram understanding) into one combined_text blob per image.

That blob is meant to flow into the RetrievalWorker's ingestion pipeline

exactly like PDF/CSV text does - this worker's job stops at "image -> text".
"""

from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf as fitz
import pytesseract
import requests
from PIL import Image

IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".webp",
}


@dataclass(frozen=True)
class VisionSettings:
    """Runtime settings, all controllable without code changes."""

    ollama_url: str = os.getenv(
        "OLLAMA_URL",
        "http://127.0.0.1:11434"
    )

    vlm_model: str = os.getenv(
        "VLM_MODEL",
        "qwen3-vl:8b"
    )

    vlm_system_prompt: str = (
        "You are a precise visual description assistant. Describe only what is visibly present in the image. "
        "If any number, label, or piece of text is blurry, cropped, or ambiguous, say so explicitly instead of "
        "guessing a value. Never state a number or label with confidence unless you can actually read it clearly."
    )

    vlm_prompt: str = (
        "Describe this image factually and in detail. Include: any text, numbers, or labels visible; "
        "if it is a chart or graph, state the type, axes, and the actual data trend or values shown; "
        "if it is a diagram, describe the components and how they connect; "
        "if it is a photo or screenshot, describe the concrete visual content. "
        "Do not speculate beyond what is visibly present."
    )

    request_timeout: float = 120.0
    render_dpi: int = 200
    min_native_text_chars: int = 20
    ocr_lang: str = os.getenv("OCR_LANG", "eng")


class VLMRequestError(RuntimeError):
    """Wraps any failure talking to the local Ollama server."""

    pass


class UnsupportedImageError(RuntimeError):
    """Raised when a non-image file is handed to this worker directly."""

    pass


class VisionWorker:
    """Turns an image, or a scanned PDF page, into searchable text via OCR + a local VLM."""

    def __init__(self, settings: VisionSettings | None = None) -> None:

        self.settings = settings or VisionSettings()

        # Automatically detect Windows standard Tesseract-OCR installation paths if present
        for candidate in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]:
            if Path(candidate).is_file():
                pytesseract.pytesseract.tesseract_cmd = candidate
                break

    # ------------------------------------------------------------------ #
    # Low-level building blocks
    # ------------------------------------------------------------------ #

    @staticmethod
    def _encode_b64(image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")

    def _run_ocr(self, image_bytes: bytes, source_label: str = "") -> str:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(
                image,
                lang=self.settings.ocr_lang
            )
            return text.strip()

        except Exception as err:
            return (
                f"[OCR Notice: Tesseract unavailable or OCR failed: {err}]"
            )

    def _run_vlm(self, image_bytes: bytes, source_label: str = "") -> str:
        try:
            try:
                from model_router import get_model_router
                vlm_model = get_model_router().get_model("vision", default=self.settings.vlm_model)
            except Exception:
                vlm_model = self.settings.vlm_model

            response = requests.post(
                f"{self.settings.ollama_url}/api/chat",
                json={
                    "model": vlm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": self.settings.vlm_system_prompt,
                        },
                        {
                            "role": "user",
                            "content": self.settings.vlm_prompt,
                            "images": [
                                self._encode_b64(image_bytes)
                            ],
                        },
                    ],
                    "stream": False,
                },
                timeout=self.settings.request_timeout,
            )

            response.raise_for_status()

            payload = response.json()

            return payload.get(
                "message",
                {}
            ).get(
                "content",
                ""
            ).strip()

        except Exception:
            return (
                "[VLM Notice: Local Qwen3-VL model unavailable. "
                "Live visual understanding could not be performed.]"
            )

    def _process_image_bytes(
        self,
        image_bytes: bytes,
        source_label: str
    ) -> dict[str, Any]:

        ocr_text = self._run_ocr(
            image_bytes,
            source_label=source_label
        )

        vlm_description = self._run_vlm(
            image_bytes,
            source_label=source_label
        )

        combined_sections = []

        if vlm_description:
            combined_sections.append(
                f"[AI-generated visual description - may contain errors]\n"
                f"{vlm_description}"
            )

        if ocr_text:
            combined_sections.append(
                f"[Exact text extracted via OCR]\n"
                f"{ocr_text}"
            )

        combined_text = "\n\n".join(
            combined_sections
        )

        return {
            "source": source_label,
            "ocr_text": ocr_text,
            "vlm_description": vlm_description,
            "combined_text": combined_text,
            "source_type": "vision_worker",
        }

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #

    def process_image(
        self,
        image_path: str | Path
    ) -> dict[str, Any]:

        path = Path(image_path).resolve()

        if not path.is_file():
            raise FileNotFoundError(
                f"Not a readable file: {path}"
            )

        if path.suffix.lower() not in IMAGE_SUFFIXES:
            raise UnsupportedImageError(
                f"{path.name}: not a recognized image type "
                f"{sorted(IMAGE_SUFFIXES)}."
            )

        image_bytes = path.read_bytes()

        return self._process_image_bytes(
            image_bytes,
            source_label=path.name
        )

    def process_pdf_page(
        self,
        pdf_path: str | Path,
        page_number: int
    ) -> dict[str, Any]:

        path = Path(pdf_path).resolve()

        if not path.is_file():
            raise FileNotFoundError(
                f"Not a readable file: {path}"
            )

        with fitz.open(path) as pdf:

            if not (
                0 <= page_number < pdf.page_count
            ):
                raise ValueError(
                    f"Page {page_number} out of range for "
                    f"{path.name} ({pdf.page_count} pages)."
                )

            page = pdf.load_page(page_number)
            native_text = page.get_text("text").strip()

            pixmap = page.get_pixmap(
                dpi=self.settings.render_dpi
            )

            image_bytes = pixmap.tobytes("png")

        result = self._process_image_bytes(
            image_bytes,
            source_label=f"{path.name} (page {page_number + 1})"
        )

        if native_text:
            result["native_text"] = native_text
            existing_combined = result.get("combined_text", "")
            result["combined_text"] = (
                f"[Document Native Text]\n{native_text}\n\n{existing_combined}".strip()
            )

        return result

    def find_scanned_pages(
        self,
        pdf_path: str | Path
    ) -> list[int]:

        path = Path(pdf_path).resolve()

        if not path.is_file():
            raise FileNotFoundError(
                f"Not a readable file: {path}"
            )

        scanned_pages: list[int] = []

        with fitz.open(path) as pdf:

            for index, page in enumerate(pdf):

                native_text = page.get_text(
                    "text"
                ).strip()

                if len(native_text) < self.settings.min_native_text_chars:
                    scanned_pages.append(index)

        return scanned_pages

    def process_scanned_pdf(
        self,
        pdf_path: str | Path
    ) -> list[dict[str, Any]]:

        scanned_pages = self.find_scanned_pages(
            pdf_path
        )

        if not scanned_pages:
            with fitz.open(Path(pdf_path).resolve()) as pdf:
                scanned_pages = list(range(pdf.page_count))

        return [
            self.process_pdf_page(
                pdf_path,
                page_number
            )
            for page_number in scanned_pages
        ]