"""
image_extractor.py
Shared image-extraction helper for OmniRAG's ingestion pipeline.

Supports:
1. OCR of embedded images inside PDFs.
2. OCR of scanned PDF pages where the page itself is an image.

Requires:
    pip install pymupdf pytesseract pillow
"""

import io
import os
import platform

import fitz
import pytesseract
from PIL import Image
from langchain_core.documents import Document


# Windows Tesseract location
if platform.system() == "Windows":
    _default_windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    if os.path.exists(_default_windows_path):
        pytesseract.pytesseract.tesseract_cmd = _default_windows_path


# Ignore OCR results shorter than this.
MIN_OCR_TEXT_LENGTH = 20

# A page with fewer extractable text characters than this is treated as
# having no real text layer - i.e. a genuine scan, not a normal digital
# page that simply happens to contain no embedded raster images.
MIN_PAGE_TEXT_LENGTH = 20

# Resolution used when rendering scanned PDF pages.
# 200 DPI is a reasonable balance between OCR quality and speed.
SCAN_DPI = 200


def _ocr_image(image: Image.Image) -> str:
    """Run Tesseract OCR on a PIL image."""
    return pytesseract.image_to_string(image).strip()


def extract_images_from_pdf(filepath: str, source_label: str) -> list:
    """
    Extract OCR text from:

    1. Embedded images inside a PDF.
    2. Scanned PDF pages (pages with no extractable text layer at all).

    A page is only treated as "scanned" - and rendered + OCR'd in full -
    if it has both no embedded images AND no extractable text via
    page.get_text(). Checking only for embedded images was wrong: a
    completely normal digital text page (no photos/figures on it) also
    has zero embedded images, so that condition alone was triggering a
    full-page render+OCR pass on every plain text page in every PDF -
    redundant with pypdf's own clean text extraction, and much slower.

    Returns LangChain Document objects with:
        chunk_type="image"
    """

    image_docs = []

    try:
        pdf = fitz.open(filepath)
    except Exception as e:
        print(f"  Could not open {source_label} for image extraction: {e}")
        return image_docs

    try:
        for page_num in range(len(pdf)):
            page = pdf[page_num]

            # ---------------------------------------------------------
            # 1. OCR EMBEDDED IMAGES
            # ---------------------------------------------------------
            embedded_images = page.get_images(full=True)

            for img_idx, img in enumerate(embedded_images):
                xref = img[0]

                try:
                    base_image = pdf.extract_image(xref)
                    image_bytes = base_image["image"]

                    pil_image = Image.open(
                        io.BytesIO(image_bytes)
                    ).convert("RGB")

                    ocr_text = _ocr_image(pil_image)

                    if len(ocr_text) < MIN_OCR_TEXT_LENGTH:
                        continue

                    caption = (
                        f"Image from {source_label}, "
                        f"page {page_num + 1} "
                        f"(OCR text)."
                    )

                    content = f"{caption}\n\n{ocr_text}"

                    image_docs.append(
                        Document(
                            page_content=content,
                            metadata={
                                "source": source_label,
                                "chunk_type": "image",
                                "page": page_num + 1,
                                "image_index": img_idx,
                                "ocr_type": "embedded_image",
                            },
                        )
                    )

                except pytesseract.TesseractNotFoundError:
                    print(
                        "  Tesseract OCR engine not found. "
                        "Check the Tesseract installation."
                    )
                    return []

                except Exception as e:
                    print(
                        f"  Could not OCR embedded image "
                        f"on page {page_num + 1}: {e}"
                    )

            # ---------------------------------------------------------
            # 2. OCR SCANNED PDF PAGE
            # ---------------------------------------------------------
            #
            # Only if the page has no embedded images AND no real text
            # layer - that combination is what actually means "this page
            # is a scan", not just "no embedded images".
            #
            page_text_length = len(page.get_text().strip())
            is_scanned_page = (
                not embedded_images
                and page_text_length < MIN_PAGE_TEXT_LENGTH
            )

            if is_scanned_page:

                try:
                    zoom = SCAN_DPI / 72
                    matrix = fitz.Matrix(zoom, zoom)

                    pix = page.get_pixmap(
                        matrix=matrix,
                        alpha=False
                    )

                    page_image = Image.open(
                        io.BytesIO(pix.tobytes("png"))
                    ).convert("RGB")

                    ocr_text = _ocr_image(page_image)

                    if len(ocr_text) < MIN_OCR_TEXT_LENGTH:
                        continue

                    caption = (
                        f"Scanned page from {source_label}, "
                        f"page {page_num + 1} "
                        f"(OCR text)."
                    )

                    content = f"{caption}\n\n{ocr_text}"

                    image_docs.append(
                        Document(
                            page_content=content,
                            metadata={
                                "source": source_label,
                                "chunk_type": "image",
                                "page": page_num + 1,
                                "image_index": None,
                                "ocr_type": "scanned_page",
                            },
                        )
                    )

                except pytesseract.TesseractNotFoundError:
                    print(
                        "  Tesseract OCR engine not found. "
                        "Check the Tesseract installation."
                    )
                    return []

                except Exception as e:
                    print(
                        f"  Could not OCR scanned page "
                        f"{page_num + 1}: {e}"
                    )

    finally:
        pdf.close()

    return image_docs