import chromadb
import os
from typing import List, Dict, Any, Set

class VectorStore:
    def __init__(self, persist_directory: str = "temp/chroma_db"):
        os.makedirs(persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(name="study_synthesizer")

    def add_chunks(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], documents: List[str]):
        if not ids:
            return
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

    def get_existing_hashes(self, hashes: List[str]) -> Set[str]:
        if not hashes:
            return set()
        
        existing = set()
        chunk_size = 100
        for i in range(0, len(hashes), chunk_size):
            batch = hashes[i:i+chunk_size]
            result = self.collection.get(
                where={"content_hash": {"$in": batch}},
                include=["metadatas"]
            )
            for m in result.get("metadatas", []):
                if m and "content_hash" in m:
                    existing.add(m["content_hash"])
        return existing

    def delete_document(self, document_id: str):
        self.collection.delete(
            where={"document_id": document_id}
        )

    def similarity_search(self, query_embedding: List[float], top_k: int = 5, where: Dict[str, Any] = None) -> Dict[str, Any]:
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k
        }
        if where:
            kwargs["where"] = where
            
        return self.collection.query(**kwargs)
