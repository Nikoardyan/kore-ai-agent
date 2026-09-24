from collections import Counter
import math
import re


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


class VectorStore:
    """Small in-memory lexical store for local RAG without model downloads."""

    def __init__(self):
        self.documents = []
        self.document_frequencies = Counter()
        self.document_count = 0

    def add_documents(self, documents):
        self.documents = []
        self.document_frequencies = Counter()

        for index, document in enumerate(documents):
            tokens = self._tokenize(document.get("content", ""))
            token_counts = Counter(tokens)
            stored_document = {
                **document,
                "id": index,
                "_tokens": token_counts,
                "_token_set": set(token_counts)
            }
            self.documents.append(stored_document)
            self.document_frequencies.update(stored_document["_token_set"])

        self.document_count = len(self.documents)

    def similarity_search(self, query: str, top_k: int = 5):
        query_tokens = self._tokenize(query)
        if not query_tokens or not self.documents:
            return []

        query_counts = Counter(query_tokens)
        results = []
        query_text = " ".join(query_tokens)

        for document in self.documents:
            score = 0.0
            document_tokens = document["_tokens"]
            document_token_set = document["_token_set"]

            for token, query_count in query_counts.items():
                if token not in document_tokens:
                    continue
                idf = math.log((self.document_count + 1) / (self.document_frequencies[token] + 1)) + 1
                score += (1 + math.log(document_tokens[token])) * idf * query_count

            overlap = len(set(query_tokens) & document_token_set)
            score += overlap / max(len(set(query_tokens)), 1)

            if query_text and query_text in " ".join(document["_token_set"]):
                score += 1.5

            if score > 0:
                results.append({
                    "content": document["content"],
                    "metadata": document.get("metadata", {}),
                    "score": round(score, 4)
                })

        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]

    @staticmethod
    def _tokenize(text: str):
        return [token.lower() for token in TOKEN_PATTERN.findall(text)]
