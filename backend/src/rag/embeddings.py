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

        api_key = settings.get_llm_api_key()
        base_url = os.getenv("LLM_BASE_URL") or None
        if not base_url and api_key and api_key.startswith("gsk_"):
            base_url = "https://api.groq.com/openai/v1"

        self.client = OpenAI(api_key=api_key or "dummy", base_url=base_url)

    def embed_text(self, text: str):
        if not text.strip():
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
