import os
from google import genai
from typing import List

def get_embedding_client(api_key: str = None):
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is required for embeddings")
    return genai.Client(api_key=key)

def generate_embeddings(texts: List[str], api_key: str = None) -> List[List[float]]:
    if not texts:
        return []
    client = get_embedding_client(api_key)
    response = client.models.embed_content(
        model="text-embedding-004",
        contents=texts
    )
    return [e.values for e in response.embeddings]
