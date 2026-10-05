import math
from .embeddings import Embeddings

class VectorStore:
    """In-memory vector store using OpenAI embeddings and cosine similarity."""

    def __init__(self):
        self.documents = []
        self.embedder = Embeddings()

    def add_documents(self, documents):
        self.documents = []
        for index, document in enumerate(documents):
            content = document.get("content", "")
            embedding = self.embedder.embed_text(content)
            self.documents.append({
                **document,
                "id": index,
                "embedding": embedding
            })

    def similarity_search(self, query: str, top_k: int = 5):
        query_embedding = self.embedder.embed_text(query)
        if not query_embedding or not self.documents:
            return []

        results = []
        for document in self.documents:
            doc_embedding = document.get("embedding", [])
            if not doc_embedding:
                continue

            score = self._cosine_similarity(query_embedding, doc_embedding)
            
            # Threshold: Hanya terima dokumen dengan kemiripan di atas 0.35
            if score > 0.35:
                results.append({
                    "content": document["content"],
                    "metadata": document.get("metadata", {}),
                    "score": round(score, 4)
                })

        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]
        
    @staticmethod
    def _cosine_similarity(v1, v2):
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
