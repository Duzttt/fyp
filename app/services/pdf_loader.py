import os
import tempfile
from typing import List

try:
    from langchain_community.document_loaders import PyPDFLoader
except ImportError:
    PyPDFLoader = None


class PDFLoaderError(Exception):
    pass


class PDFLoader:
    def __init__(self, documents_path: str):
        self.documents_path = documents_path

    def _extract_text_with_langchain(self, pdf_file_path: str) -> str:
        if PyPDFLoader is None:
            raise PDFLoaderError(
                "LangChain PDF loader is not installed. Install "
                "'langchain-community' and 'pypdf'."
            )

        loader = PyPDFLoader(pdf_file_path)
        documents = loader.load()
        pages: List[str] = [
            document.page_content.strip()
            for document in documents
            if document.page_content and document.page_content.strip()
        ]
        return "\n".join(pages)

    def extract_text(self, pdf_file_path: str) -> str:
        if not os.path.exists(pdf_file_path):
            raise PDFLoaderError(f"PDF file not found: {pdf_file_path}")

        try:
            return self._extract_text_with_langchain(pdf_file_path)
        except Exception as e:
            raise PDFLoaderError(f"Failed to extract text from PDF: {str(e)}")

    def extract_text_from_bytes(self, pdf_bytes: bytes, filename: str) -> str:
        safe_name = os.path.basename(filename) if filename else "uploaded.pdf"
        suffix = os.path.splitext(safe_name)[1] or ".pdf"
        temp_file_path = ""

        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
            ) as temp_pdf:
                temp_pdf.write(pdf_bytes)
                temp_file_path = temp_pdf.name

            return self._extract_text_with_langchain(temp_file_path)
        except Exception as e:
            raise PDFLoaderError(f"Failed to extract text from PDF: {str(e)}")
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def save_pdf(self, pdf_bytes: bytes, filename: str) -> str:
        os.makedirs(self.documents_path, exist_ok=True)
        file_path = os.path.join(self.documents_path, filename)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)
        return file_path
