import pytest
import os
import json
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from models import DocumentContent
from rag.chunking import chunk_document
from rag.retrieval import index_documents, search, get_store, delete_document
from rag.metadata import generate_content_hash

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test_key")

# --- RAG Tests ---
def test_rag_chunking():
    doc = DocumentContent(
        document_id="doc1", document_name="Test", source_type="pdf",
        text="A" * 1500, metadata={"page_number": 1}
    )
    chunks = chunk_document(doc, chunk_size=1000, chunk_overlap=200)
    assert len(chunks) == 2
    assert chunks[0].text == "A" * 1000
    assert chunks[1].text == "A" * 700

@patch('rag.retrieval.generate_embeddings')
@patch('rag.retrieval.get_store')
def test_rag_indexing_and_duplicates(mock_get_store, mock_generate_embeddings):
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store
    mock_generate_embeddings.return_value = [[0.1, 0.2]]
    
    doc1 = DocumentContent(document_id="doc1", document_name="Doc1", source_type="pdf", text="Hello world", metadata={})
    
    # Indexing
    mock_store.get_existing_hashes.return_value = set()
    index_documents([doc1], api_key="fake")
    assert mock_store.add_chunks.called
    
    # Duplicate detection (content hash)
    mock_store.add_chunks.reset_mock()
    mock_store.get_existing_hashes.return_value = {generate_content_hash("Hello world")}
    index_documents([doc1], api_key="fake")
    assert not mock_store.add_chunks.called

@patch('rag.retrieval.generate_embeddings')
@patch('rag.retrieval.get_store')
def test_rag_retrieval_and_metadata_filter(mock_get_store, mock_generate_embeddings):
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store
    mock_generate_embeddings.return_value = [[0.1]]
    
    mock_store.similarity_search.return_value = {
        "ids": [["c1"]], "documents": [["Relevant text"]], 
        "metadatas": [[{"document_name": "Doc", "source_type": "pdf"}]], "distances": [[0.1]]
    }
    
    results = search("Query", filter_metadata={"document_id": "doc1"})
    mock_store.similarity_search.assert_called_with([0.1], top_k=5, where={"document_id": "doc1"})
    assert len(results) == 1
    assert results[0]["text"] == "Relevant text"

@patch('rag.retrieval.get_store')
def test_rag_deletion(mock_get_store):
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store
    delete_document("doc1")
    mock_store.delete_document.assert_called_with("doc1")

# --- Ask AI Tests ---
@patch('rag.api.get_store')
@patch('rag.api.generate_embeddings')
@patch('rag.api.client')
def test_ask_ai_supported_question(mock_genai, mock_embed, mock_get_store):
    mock_embed.return_value = [[0.1]]
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store
    mock_store.similarity_search.return_value = {
        "ids": [["c1"]], "documents": [["Data"]], "metadatas": [[{"document_name": "Test", "source_type": "pdf"}]], "distances": [[0.1]]
    }
    mock_response = MagicMock()
    mock_response.text = "Answer"
    mock_genai.models.generate_content.return_value = mock_response

    res = client.post("/api/rag/query", json={"question": "Test?"})
    assert res.status_code == 200
    assert res.json()["answer"] == "Answer"
    assert len(res.json()["sources"]) == 1

@patch('rag.api.get_store')
@patch('rag.api.generate_embeddings')
def test_ask_ai_empty_retrieval(mock_embed, mock_get_store):
    mock_embed.return_value = [[0.1]]
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store
    mock_store.similarity_search.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    res = client.post("/api/rag/query", json={"question": "Test?"})
    assert res.status_code == 200
    assert "I cannot find the answer" in res.json()["answer"]

def test_ask_ai_invalid_document():
    res = client.post("/api/rag/query", json={"question": "What?", "document_ids": "not_an_array"})
    assert res.status_code == 422 

@patch('rag.api.get_store')
@patch('rag.api.generate_embeddings')
@patch('rag.api.client')
def test_ask_ai_gemini_failure(mock_genai, mock_embed, mock_get_store):
    mock_embed.return_value = [[0.1]]
    mock_get_store.return_value.similarity_search.return_value = {
        "ids": [["c1"]], "documents": [["Data"]], "metadatas": [[{"document_name": "Test"}]], "distances": [[0.1]]
    }
    mock_genai.models.generate_content.side_effect = Exception("Gemini Down")
    
    res = client.post("/api/rag/query", json={"question": "Test?"})
    assert res.status_code == 500
    assert "Gemini Down" in res.json()["detail"]

# --- Security Tests ---
@patch('services.web_service.requests.get')
def test_security_ssrf(mock_get):
    from services.web_service import scrape_article
    with pytest.raises(Exception) as excinfo:
        asyncio.run(scrape_article("http://127.0.0.1/admin"))
    assert "not allowed" in str(excinfo.value) or "Private" in str(excinfo.value)

@patch('services.web_service.requests.get')
def test_security_oversized_webpage(mock_get):
    from services.web_service import scrape_article
    mock_resp = MagicMock()
    mock_resp.iter_content.return_value = [b"a" * 1024 * 1024] * 6 # 6MB
    mock_get.return_value = mock_resp
    with pytest.raises(Exception) as excinfo:
        asyncio.run(scrape_article("http://example.com"))
    assert "exceeds" in str(excinfo.value).lower() or "too large" in str(excinfo.value).lower()

# --- Inputs & Regression Tests ---
@patch('services.ingestion_service.ingest_youtube_transcript')
@patch('services.download_service.download_video_from_url')
@patch('services.ai_service.analyze_video_content')
def test_regression_pipeline_youtube(mock_ai, mock_dl, mock_yt):
    mock_yt.return_value = []
    mock_dl.return_value = "temp/fake_video.mp4"
    mock_ai.return_value = {
        "detailed_notes": "Detailed",
        "one_line_points": "Points",
        "definitions": "Defs",
        "quiz": "Quiz",
        "flashcards": [{"q": "q1", "a": "a1"}]
    }
    
    res = client.post("/api/process", data={"url": "https://youtube.com/watch?v=12345"})
    assert res.status_code == 200
    task_id = res.json()["task_id"]
    
    # We can connect to SSE
    sse_res = client.get(f"/api/stream/{task_id}")
    assert sse_res.status_code == 200
    assert "event-stream" in sse_res.headers["content-type"]

@patch('services.ai_service.analyze_video_content')
def test_regression_pipeline_files(mock_ai):
    mock_ai.return_value = {"detailed_notes": "A", "one_line_points": "B", "definitions": "C", "quiz": "D", "flashcards": []}
    
    # We mock out ingestion to avoid writing real valid PDFs
    with patch('main.handle_document_ingestion') as mock_ingest:
        mock_ingest.return_value = [DocumentContent(document_id="doc1", document_name="test.pdf", source_type="pdf", text="Test", metadata={})]
        
        # We need a dummy file
        res = client.post(
            "/api/process", 
            files={"docs": ("test.pdf", b"fake pdf data", "application/pdf")}
        )
        assert res.status_code == 200
        assert "task_id" in res.json()

def test_regression_docx_export():
    task_id = "fake_task"
    os.makedirs("output", exist_ok=True)
    with open(f"output/{task_id}_detailed.docx", "w") as f:
        f.write("fake docx")
        
    res = client.get(f"/api/download/{task_id}/detailed")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    os.remove(f"output/{task_id}_detailed.docx")

# --- Cleanup System Tests ---
from services.db_service import register_document, get_task_documents, touch_task, execute_query
from services.cleanup_service import safe_delete_file, cleanup_task, run_cleanup_job, mark_task_active, mark_task_inactive
from datetime import datetime, timedelta

def test_cleanup_register_and_touch():
    task_id = "test_cleanup_task"
    register_document("doc_c1", task_id, "Doc", "pdf")
    docs = get_task_documents(task_id)
    assert "doc_c1" in docs
    
    # Check expires_at
    row = execute_query("SELECT expires_at FROM documents WHERE document_id='doc_c1'", fetch=True)
    assert row is not None
    
    touch_task(task_id)
    row2 = execute_query("SELECT expires_at FROM documents WHERE document_id='doc_c1'", fetch=True)
    assert row[0] < row2[0]  # expires_at pushed forward

@patch('services.cleanup_service.delete_document')
def test_cleanup_job(mock_del_doc):
    task_id = "test_expired_task"
    register_document("doc_exp", task_id, "Doc", "pdf")
    
    # Manually expire it
    past = (datetime.utcnow() - timedelta(hours=50)).isoformat()
    execute_query("UPDATE documents SET expires_at=? WHERE task_id=?", (past, task_id))
    
    # Create fake temp file
    os.makedirs("temp", exist_ok=True)
    temp_file = f"temp/{task_id}_fake.txt"
    with open(temp_file, "w") as f: f.write("fake")
        
    asyncio.run(run_cleanup_job())
    
    # Should be deleted
    assert not os.path.exists(temp_file)
    mock_del_doc.assert_called_with("doc_exp")
    
    # Metadata should be gone
    docs = get_task_documents(task_id)
    assert len(docs) == 0

@patch('services.cleanup_service.delete_document')
def test_cleanup_active_task_protection(mock_del_doc):
    task_id = "test_active_task"
    register_document("doc_act", task_id, "Doc", "pdf")
    
    # Manually expire it
    past = (datetime.utcnow() - timedelta(hours=50)).isoformat()
    execute_query("UPDATE documents SET expires_at=? WHERE task_id=?", (past, task_id))
    
    mark_task_active(task_id)
    asyncio.run(run_cleanup_job())
    
    # Should NOT be deleted because it is active
    docs = get_task_documents(task_id)
    assert len(docs) == 1
    assert not mock_del_doc.called
    mark_task_inactive(task_id)

def test_safe_delete_file_path_traversal():
    import tempfile
    
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"sensitive")
        external_file = f.name
        
    # Attempt path traversal
    safe_delete_file(f"temp/../../../../../../../../{external_file}")
    
    # Should STILL exist because it's outside temp/output
    assert os.path.exists(external_file)
    os.remove(external_file)
