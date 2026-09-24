class RerankerService:
    def rerank(self, query: str, documents: list):
        # Current retriever already scores documents. Keep this service separate so
        # a model reranker can replace it later without changing the API layer.
        return sorted(documents, key=lambda document: document.get("score", 0), reverse=True)
