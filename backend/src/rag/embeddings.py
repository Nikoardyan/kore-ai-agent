"""
embeddings.py - Menghasilkan vektor embedding dari teks menggunakan OpenAI API.

FIX dari versi sebelumnya:
- Gunakan api_key dari settings, bukan default OpenAI() yang membaca
  OPENAI_API_KEY secara langsung (gagal ketika variable bernama LLM_API_KEY).
- base_url otomatis diset ke Groq jika key diawali gsk_.
- Error menggunakan logging, bukan print().
"""

import os
import logging

logger = logging.getLogger("kore.embeddings")


class Embeddings:
    def __init__(self):
        # FIX: Baca api_key dari settings agar konsisten dengan api.py dan pipeline.py
        from src.config import settings
        from openai import OpenAI

        self.api_key = settings.get_llm_api_key()
        base_url = os.getenv("LLM_BASE_URL") or None
        if not base_url and self.api_key and self.api_key.startswith("gsk_"):
            base_url = "https://api.groq.com/openai/v1"

        self.client = OpenAI(api_key=self.api_key or "dummy", base_url=base_url)

    def embed_text(self, text: str):
        if not text.strip() or (self.api_key and self.api_key.startswith("gsk_")):
            # Groq hanya mendukung chat/completions, bukan embeddings.
            # RAG secara otomatis menggunakan TF-IDF / lexical matching yang cepat & akurat.
            return []
        try:
            response = self.client.embeddings.create(
                input=text,
                model="text-embedding-3-small",
            )
            return response.data[0].embedding
        except Exception:
            # FIX: Gunakan logger, bukan print() — muncul di log server, bukan stdout
            logger.exception("Error generating embedding")
            return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Menghasilkan embedding untuk beberapa teks sekaligus (batching) agar startup cepat."""
        if not texts or (self.api_key and self.api_key.startswith("gsk_")):
            return [[] for _ in texts]

        results = [[] for _ in texts]
        batch_size = 50
        try:
            for i in range(0, len(texts), batch_size):
                batch_slice = texts[i : i + batch_size]
                clean_slice = [t.strip() if t.strip() else " " for t in batch_slice]
                response = self.client.embeddings.create(
                    input=clean_slice,
                    model="text-embedding-3-small",
                )
                for item in response.data:
                    results[i + item.index] = item.embedding
            return results
        except Exception:
            logger.exception("Error generating batch embeddings, falling back to individual")
            return [self.embed_text(t) for t in texts]
