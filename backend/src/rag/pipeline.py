"""
pipeline.py - RAG pipeline: load dokumen, chunk, embed, retrieve, dan jawab.

FIX dari versi sebelumnya:
- LLM client dibangun menggunakan settings (konsisten dengan api.py),
  bukan hardcode OpenAI() yang gagal ketika pakai Groq.
- Error LLM menggunakan logging, bukan print().
- Model LLM untuk RAG bisa di-override lewat LLM_RAG_MODEL di .env.
"""

import os
import logging
from pathlib import Path

from .chunking import TextChunker
from .document_loader import DocumentLoader
from .reranker import RerankerService
from .retrieval import RetrievalService
from .vector_store import VectorStore

logger = logging.getLogger("kore.rag")

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def _build_llm_client():
    """
    FIX: Bangun LLM client menggunakan settings (sama dengan api.py),
    bukan hardcode OpenAI() yang akan gagal kalau pakai Groq.
    """
    # Import di sini supaya tidak circular-import
    from src.config import settings

    api_key = settings.get_llm_api_key()
    if not api_key:
        return None, None
    try:
        from openai import OpenAI
        base_url = os.getenv("LLM_BASE_URL") or None
        if not base_url and api_key.startswith("gsk_"):
            # Groq kompatibel OpenAI API
            base_url = "https://api.groq.com/openai/v1"
        client = OpenAI(api_key=api_key, base_url=base_url)
        # Model RAG bisa di-override lewat LLM_RAG_MODEL, fallback ke model utama
        model = os.getenv("LLM_RAG_MODEL") or settings.llm_model
        return client, model
    except Exception:
        logger.exception("Gagal membuat LLM client di RAG pipeline")
        return None, None


class RAGPipeline:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.loader = DocumentLoader()
        self.chunker = TextChunker()
        self.vector_store = VectorStore()
        self.retriever = RetrievalService(self.vector_store, top_k=5)
        self.reranker = RerankerService()
        self.loaded_files = []
        self.chunk_count = 0
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        documents = []
        for file_path in sorted(self.data_dir.iterdir()):
            if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            loaded_documents = self.loader.load(str(file_path))
            if loaded_documents:
                documents.extend(loaded_documents)
                self.loaded_files.append(file_path.name)

        chunks = self.chunker.split(documents)
        self.vector_store.add_documents(chunks)
        self.chunk_count = len(chunks)

    def answer(self, query: str):
        retrieved_documents = self.retriever.retrieve(query)
        ranked_documents = self.reranker.rerank(query, retrieved_documents)

        if not ranked_documents:
            return {
                "reply": "Maaf, saya tidak menemukan informasi yang relevan di dalam dokumen.",
                "source": "Tidak ada dokumen yang relevan"
            }

        top_documents = ranked_documents[:3]
        snippets = [self._format_snippet(document) for document in top_documents]
        source = self._format_sources(top_documents)

        # Tambahkan skor kemiripan agar bisa dilihat di UI
        top_scores = [str(doc.get("score", 0)) for doc in top_documents]
        score_info = f" (Skor Kemiripan: {', '.join(top_scores)})"
        source += score_info

        context = "\n\n".join(snippets)

        # FIX: Gunakan _build_llm_client() alih-alih hardcode OpenAI()
        # sehingga Groq dan provider lain juga berfungsi dengan benar.
        llm_client, llm_model = _build_llm_client()
        if llm_client is not None:
            try:
                prompt = (
                    "Gunakan informasi berikut untuk menjawab pertanyaan pengguna.\n\n"
                    f"Konteks:\n{context}\n\n"
                    f"Pertanyaan: {query}\n\n"
                    "Jawablah dengan sopan dan gunakan bahasa Indonesia yang baik."
                )
                response = llm_client.chat.completions.create(
                    model=llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Anda adalah asisten AI yang membantu menjawab pertanyaan "
                                "berdasarkan dokumen kebijakan/informasi perusahaan. "
                                "Jawab hanya berdasarkan konteks yang diberikan."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )
                llm_reply = response.choices[0].message.content
            except Exception:
                # FIX: Gunakan logger, bukan print()
                logger.exception("Error calling LLM di RAG pipeline")
                llm_reply = None
        else:
            llm_reply = None

        # Fallback: tampilkan konteks mentah jika LLM tidak tersedia
        if not llm_reply:
            llm_reply = (
                "Berdasarkan dokumen knowledge base, konteks paling relevan yang saya temukan:\n\n"
                + context
            )

        return {
            "reply": llm_reply,
            "source": source,
        }

    @staticmethod
    def _format_snippet(document):
        metadata = document.get("metadata", {})
        page = metadata.get("page")
        label = metadata.get("source", "Knowledge base")
        if page:
            label = f"{label}, halaman {page}"

        content = document.get("content", "")
        if len(content) > 850:
            content = content[:850].rsplit(" ", 1)[0] + "..."

        return f"[{label}]\n{content}"

    @staticmethod
    def _format_sources(documents):
        sources = []
        for document in documents:
            metadata = document.get("metadata", {})
            source = metadata.get("source", "Knowledge base")
            page = metadata.get("page")
            label = f"{source} hal. {page}" if page else source
            if label not in sources:
                sources.append(label)
        return ", ".join(sources)


_pipeline = None


def get_rag_pipeline():
    global _pipeline
    if _pipeline is None:
        backend_dir = Path(__file__).resolve().parents[2]
        _pipeline = RAGPipeline(backend_dir / "data")
    return _pipeline


def run_rag_pipeline(query: str):
    return get_rag_pipeline().answer(query)
