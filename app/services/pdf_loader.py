import io
import os
from typing import List

import pdfplumber


class PDFLoaderError(Exception):
    pass


class PDFLoader:
    def __init__(self, documents_path: str):
        self.documents_path = documents_path

    def extract_text(self, pdf_file_path: str) -> str:
        if not os.path.exists(pdf_file_path):
            raise PDFLoaderError(f"PDF file not found: {pdf_file_path}")

        try:
            with pdfplumber.open(pdf_file_path) as pdf:
                text_pages = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_pages.append(page_text)
                return "\n".join(text_pages)
        except Exception as e:
            raise PDFLoaderError(f"Failed to extract text from PDF: {str(e)}")

    def extract_text_from_bytes(self, pdf_bytes: bytes, filename: str) -> str:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text_pages = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_pages.append(page_text)
                return "\n".join(text_pages)
        except Exception as e:
            raise PDFLoaderError(f"Failed to extract text from PDF: {str(e)}")

    def save_pdf(self, pdf_bytes: bytes, filename: str) -> str:
        os.makedirs(self.documents_path, exist_ok=True)
        file_path = os.path.join(self.documents_path, filename)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)
        return file_path
