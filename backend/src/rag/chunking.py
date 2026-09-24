class TextChunker:
    def __init__(self, chunk_size: int = 900, overlap: int = 160):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, documents):
        """Split loaded documents into overlapping word chunks."""
        if isinstance(documents, str):
            documents = [{"content": documents, "metadata": {}}]

        chunks = []
        for document in documents:
            text = document.get("content", "")
            metadata = document.get("metadata", {})
            words = text.split()
            if not words:
                continue

            start = 0
            chunk_index = 0
            while start < len(words):
                end = min(start + self.chunk_size, len(words))
                chunk_text = " ".join(words[start:end])
                chunks.append({
                    "content": chunk_text,
                    "metadata": {**metadata, "chunk": chunk_index}
                })

                if end == len(words):
                    break
                start = max(end - self.overlap, start + 1)
                chunk_index += 1

        return chunks
