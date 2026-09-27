from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
import os
import asyncio
from google import genai
from .retrieval import search

router = APIRouter(prefix="/api/rag", tags=["RAG"])

@router.get("/documents")
async def list_documents():
    from .retrieval import get_store
    store = get_store()
    
    # We can fetch all documents from Chroma and distinct them by document_id and document_name
    try:
        # Get all metadata (we limit to 10000 for practicality)
        result = store.collection.get(include=["metadatas"])
        metas = result.get("metadatas", [])
        
        doc_map = {}
        for m in metas:
            if m and "document_id" in m:
                doc_map[m["document_id"]] = m.get("document_name", "Unknown Document")
                
        docs = [{"document_id": k, "document_name": v} for k, v in doc_map.items()]
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RagQueryRequest(BaseModel):
    question: str
    document_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)

class RagSource(BaseModel):
    text: str
    metadata: Dict[str, Any]
    distance: Optional[float] = None

class RagQueryResponse(BaseModel):
    answer: str
    sources: List[RagSource]

@router.post("/query", response_model=RagQueryResponse)
async def query_rag(req: RagQueryRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Server missing GEMINI_API_KEY")

    # Construct where filter
    where_filter = None
    if req.document_ids:
        if len(req.document_ids) == 1:
            where_filter = {"document_id": req.document_ids[0]}
        else:
            where_filter = {"document_id": {"$in": req.document_ids}}
            
        from services.db_service import execute_query, touch_task
        placeholders = ','.join(['?'] * len(req.document_ids))
        tasks = execute_query(f"SELECT DISTINCT task_id FROM documents WHERE document_id IN ({placeholders})", tuple(req.document_ids), fetchall=True)
        if tasks:
            for t in tasks:
                touch_task(t[0])

    try:
        results = await asyncio.to_thread(search, req.question, api_key, req.top_k, where_filter)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    if not results:
        return RagQueryResponse(
            answer="I cannot find the answer to this question in the provided documents.",
            sources=[]
        )

    # Build context
    context_blocks = []
    sources = []
    for i, r in enumerate(results):
        context_blocks.append(f"--- Context Snippet {i+1} ---\n{r['text']}")
        sources.append(RagSource(text=r['text'], metadata=r['metadata'], distance=r.get('distance')))

    context_str = "\n\n".join(context_blocks)

    prompt = f"""You are an expert AI assistant answering questions strictly based on the provided context.

Context Information:
{context_str}

User Question: {req.question}

Instructions:
1. Answer the question using ONLY the provided context.
2. If the answer cannot be found in the context, clearly state: "I cannot find the answer to this question in the provided documents."
3. Do not fabricate information, sources, or assumptions.
4. Keep the answer concise, grounded, and helpful."""

    try:
        client = genai.Client(api_key=api_key)
        # Assuming synchronous generation inside an async handler blocks slightly, but that's fine for our scope. We can also use run_in_threadpool
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[prompt]
        )
        answer = response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    return RagQueryResponse(answer=answer, sources=sources)
