class RetrievalService:
    def __init__(self, vector_store, top_k: int = 5):
        self.vector_store = vector_store
        self.top_k = top_k

    def retrieve(self, query: str):
        return self.vector_store.similarity_search(query, top_k=self.top_k)
