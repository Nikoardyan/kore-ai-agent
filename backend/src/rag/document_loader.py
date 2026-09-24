from pathlib import Path
import re

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import fitz
except ImportError:
    fitz = None


class DocumentLoader:
    """Load supported knowledge-base files into page-sized documents."""

    def load(self, path: str):
        file_path = Path(path)
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return self._load_pdf(file_path)
        if suffix in {".txt", ".md"}:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            return [{
                "content": self._clean_text(text),
                "metadata": {"source": file_path.name, "page": None}
            }]

        return []

    def _load_pdf(self, file_path: Path):
        if pdfplumber is not None:
            return self._load_pdf_with_pdfplumber(file_path)

        if fitz is not None:
            return self._load_pdf_with_pymupdf(file_path)

        raise RuntimeError(
            "PDF parser belum tersedia. Install salah satu dependency: pdfplumber atau pymupdf."
        )

    def _load_pdf_with_pdfplumber(self, file_path: Path):
        assert pdfplumber is not None
        documents = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                text = self._clean_text(page.extract_text() or "")
                if text:
                    documents.append({
                        "content": text,
                        "metadata": {"source": file_path.name, "page": page_index}
                    })
        return documents

    def _load_pdf_with_pymupdf(self, file_path: Path):
        assert fitz is not None
        documents = []
        with fitz.open(str(file_path)) as pdf:
            for page_index, page in enumerate(pdf, start=1):
                text = self._clean_text(page.get_text("text") or "")
                if text:
                    documents.append({
                        "content": text,
                        "metadata": {"source": file_path.name, "page": page_index}
                    })
        return documents

    @staticmethod
    def _clean_text(text: str):
        return re.sub(r"\s+", " ", text).strip()
