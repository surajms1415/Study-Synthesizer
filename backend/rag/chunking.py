from typing import List, Dict, Any
from models import DocumentContent

class Chunk:
    def __init__(self, text: str, chunk_index: int, metadata: Dict[str, Any]):
        self.text = text
        self.chunk_index = chunk_index
        self.metadata = metadata

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Simple character-based chunking with overlap"""
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def chunk_document(doc: DocumentContent, chunk_size: int = 1000, overlap: int = 200) -> List[Chunk]:
    text_chunks = chunk_text(doc.text, chunk_size, overlap)
    result = []
    for i, t in enumerate(text_chunks):
        meta = doc.metadata.copy() if doc.metadata else {}
        meta['document_id'] = doc.document_id
        meta['document_name'] = doc.document_name
        meta['source_type'] = doc.source_type
        result.append(Chunk(text=t, chunk_index=i, metadata=meta))
    return result
