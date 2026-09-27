from typing import List, Dict, Any
from models import DocumentContent
from .chunking import chunk_document
from .metadata import generate_content_hash, sanitize_metadata
from .embeddings import generate_embeddings
from .vector_store import VectorStore

_store = None

def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store

def index_documents(docs: List[DocumentContent], api_key: str = None, emit_cb=None):
    store = get_store()
    
    if emit_cb:
        emit_cb({"type": "rag_status", "step": "CHUNKING"})
        
    all_chunks = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))
        
    if not all_chunks:
        return
        
    ids = []
    texts = []
    metadatas = []
    
    for chunk in all_chunks:
        chash = generate_content_hash(chunk.text)
        meta = sanitize_metadata(chunk.metadata, chash)
        meta['chunk_index'] = chunk.chunk_index
        
        chunk_id = f"{chunk.metadata.get('document_id', 'unknown')}_{chunk.chunk_index}"
        
        ids.append(chunk_id)
        texts.append(chunk.text)
        metadatas.append(meta)
        
    hashes_to_check = [m['content_hash'] for m in metadatas]
    existing_hashes = store.get_existing_hashes(hashes_to_check)
    
    new_ids = []
    new_texts = []
    new_metadatas = []
    
    for i, cid in enumerate(ids):
        if metadatas[i]['content_hash'] not in existing_hashes:
            new_ids.append(cid)
            new_texts.append(texts[i])
            new_metadatas.append(metadatas[i])
            
    if new_texts:
        if emit_cb:
            emit_cb({"type": "rag_status", "step": "EMBEDDING"})
        embeddings = generate_embeddings(new_texts, api_key)
        
        if emit_cb:
            emit_cb({"type": "rag_status", "step": "STORING"})
        store.add_chunks(new_ids, embeddings, new_metadatas, new_texts)
        
    if emit_cb:
        emit_cb({"type": "rag_status", "step": "INDEXING_COMPLETED"})

def delete_document(document_id: str):
    get_store().delete_document(document_id)

def search(query: str, api_key: str = None, top_k: int = 5, filter_metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    store = get_store()
    query_embed = generate_embeddings([query], api_key)[0]
    results = store.similarity_search(query_embed, top_k=top_k, where=filter_metadata)
    
    formatted = []
    if results and results.get("ids") and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results and results["distances"] else None
            })
    return formatted
