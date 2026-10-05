from pathlib import Path

from .chunking import TextChunker
from .document_loader import DocumentLoader
from .reranker import RerankerService
from .retrieval import RetrievalService
from .vector_store import VectorStore


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


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
        
        # Tambahkan skor kemiripan agar bisa dilihat langsung di UI
        top_scores = [str(doc.get("score", 0)) for doc in top_documents]
        score_info = f" (Skor Kemiripan: {', '.join(top_scores)})"
        source += score_info
        
        context = "\n\n".join(snippets)
        
        # Use OpenAI LLM to generate conversational answer
        try:
            from openai import OpenAI
            client = OpenAI()
            prompt = f"Gunakan informasi berikut untuk menjawab pertanyaan pengguna.\n\nKonteks:\n{context}\n\nPertanyaan: {query}\n\nJawablah dengan sopan dan gunakan bahasa Indonesia yang baik."
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Anda adalah asisten AI yang membantu menjawab pertanyaan berdasarkan dokumen kebijakan/informasi perusahaan. Jawab hanya berdasarkan konteks yang diberikan."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            llm_reply = response.choices[0].message.content
        except Exception as e:
            print(f"Error calling LLM: {e}")
            llm_reply = (
                "Berdasarkan dokumen knowledge base, konteks paling relevan yang saya temukan:\n\n"
                + context
            )

        return {
            "reply": llm_reply,
            "source": source
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
