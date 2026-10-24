import math
from .embeddings import Embeddings

class VectorStore:
    """In-memory vector store using OpenAI embeddings and cosine similarity."""

    def __init__(self):
        self.documents = []
        self.embedder = Embeddings()

    def add_documents(self, documents):
        self.documents = []
        if not documents:
            return
        contents = [doc.get("content", "") for doc in documents]
        embeddings = self.embedder.embed_batch(contents)
        for index, (document, embedding) in enumerate(zip(documents, embeddings)):
            self.documents.append({
                **document,
                "id": index,
                "embedding": embedding
            })

    def similarity_search(self, query: str, top_k: int = 5):
        query_embedding = self.embedder.embed_text(query)
        results = []
        if query_embedding:
            for document in self.documents:
                doc_embedding = document.get("embedding", [])
                if not doc_embedding:
                    continue
                score = self._cosine_similarity(query_embedding, doc_embedding)
                if score > 0.35:
                    results.append({
                        "content": document["content"],
                        "metadata": document.get("metadata", {}),
                        "score": round(score, 4)
                    })
            if results:
                return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]

        # FALLBACK: Keyword / Lexical matching (ketika pakai Groq / tanpa OpenAI embedding)
        return self._keyword_search(query, top_k=top_k)

    def _keyword_search(self, query: str, top_k: int = 5):
        import re
        stopwords = {
            "yang", "di", "dari", "dan", "ini", "itu", "untuk", "pada", "ke", "saya",
            "kamu", "aku", "adalah", "apa", "apakah", "bagaimana", "bisa", "ada", "atau",
            "dengan", "oleh", "hal", "kami", "mereka", "kita", "juga", "sudah", "akan",
            "berapa", "siapa", "gimana", "kapan", "kenapa", "mengapa", "tolong",
        }
        raw_tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        tokens = [t for t in raw_tokens if t not in stopwords]
        # Jika semua kata tereliminasi sebagai stopword, pakai raw_tokens
        if not tokens:
            tokens = raw_tokens
        if not tokens or not self.documents:
            return []

        scored = []
        for document in self.documents:
            content = document.get("content", "")
            lower_content = content.lower()
            matched = sum(1 for t in tokens if t in lower_content)
            if matched > 0:
                overlap = matched / len(tokens)
                score = round(min(0.95, 0.45 + overlap * 0.5), 4)
                scored.append({
                    "content": content,
                    "metadata": document.get("metadata", {}),
                    "score": score
                })

        return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]
        
    @staticmethod
    def _cosine_similarity(v1, v2):
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
