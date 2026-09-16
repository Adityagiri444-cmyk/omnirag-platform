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
    2. Scanned PDF pages.

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
            # If the page contains no embedded images, it may be a
            # scanned page. Render the entire page and OCR it.
            #
            if not embedded_images:

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