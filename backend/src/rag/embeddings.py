import os
from openai import OpenAI

class Embeddings:
    def __init__(self):
        # We instantiate the client. Make sure OPENAI_API_KEY is in the environment
        self.client = OpenAI()

    def embed_text(self, text: str):
        if not text.strip():
            return []
        try:
            response = self.client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return []
