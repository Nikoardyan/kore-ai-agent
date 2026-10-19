"""
rag_tools.py - Tool untuk mencari dokumen dari knowledge base (RAG).

FIX dari versi sebelumnya:
- Sebelumnya hanya dummy yang return string palsu tanpa retrieval nyata.
- Sekarang memanggil RAG pipeline sungguhan untuk mencari dokumen.
"""

import logging

logger = logging.getLogger("kore.tools.rag")


def retrieve_documents(query: str, top_k: int = 3) -> list:
    """
    Mencari dokumen relevan dari knowledge base PDF menggunakan RAG pipeline.

    Args:
        query: Pertanyaan atau kata kunci pencarian
        top_k: Jumlah dokumen teratas yang dikembalikan

    Returns:
        List string berisi konten dokumen yang relevan
    """
    if not query or not query.strip():
        return []
    try:
        from src.rag.pipeline import get_rag_pipeline
        pipeline = get_rag_pipeline()
        retrieved = pipeline.retriever.retrieve(query)
        ranked = pipeline.reranker.rerank(query, retrieved)
        results = []
        for doc in ranked[:top_k]:
            content = doc.get("content", "").strip()
            metadata = doc.get("metadata", {})
            source = metadata.get("source", "Knowledge base")
            page = metadata.get("page")
            label = f"{source} hal. {page}" if page else source
            results.append(f"[{label}]\n{content}")
        return results
    except Exception:
        logger.exception("Gagal mengambil dokumen dari knowledge base untuk query: %s", query)
        return []


def answer_from_documents(query: str) -> dict:
    """
    Menjalankan full RAG pipeline: retrieve + rerank + generate jawaban.

    Args:
        query: Pertanyaan user

    Returns:
        Dict berisi 'reply' (jawaban) dan 'source' (asal dokumen)
    """
    if not query or not query.strip():
        return {"reply": "Pertanyaan tidak boleh kosong.", "source": ""}
    try:
        from src.rag.pipeline import run_rag_pipeline
        return run_rag_pipeline(query)
    except Exception:
        logger.exception("Gagal menjalankan RAG pipeline untuk: %s", query)
        return {
            "reply": "Terjadi kesalahan saat mencari di dokumen. Silakan coba lagi.",
            "source": "",
        }
