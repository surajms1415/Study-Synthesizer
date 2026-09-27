from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import os
import uuid
import asyncio
import json
from dotenv import load_dotenv

load_dotenv()

from services.audio_service import extract_audio
from services.video_service import extract_frames
from services.ai_service import analyze_video_content
from services.doc_service import create_docx_from_markdown, extract_text_from_docx, extract_text_from_pptx
from services.download_service import download_video_from_url
from services.web_service import scrape_article
from services import db_service
from pydantic import BaseModel
import requests
from rag.api import router as rag_router

app = FastAPI(title="Video Insight Extractor API")
app.include_router(rag_router)

# Initialize database
db_service.init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp", exist_ok=True)
os.makedirs("output", exist_ok=True)

# Global dicts for streaming
stream_queues = {} # { task_id : queue }

@app.get("/")
def read_root():
    return {"message": "Video Insight Extractor API is running! (Streaming Enabled)"}

from services.ingestion_service import ingest_document

from services.db_service import init_db, register_document, touch_task
from services.cleanup_service import start_cleanup_service, mark_task_active, mark_task_inactive

@app.on_event("startup")
async def startup_event():
    init_db()
    start_cleanup_service()

async def handle_document_ingestion(docs, task_id) -> list:
    all_content = []
    for d in docs:
        if d.filename:
            content_list = await ingest_document(d)
            for c in content_list:
                register_document(c.document_id, task_id, c.document_name, c.source_type)
            all_content.extend(content_list)
    return all_content

from services.ingestion_service import ingest_youtube_transcript, scrape_article
from models import DocumentContent

async def process_task_pipeline(task_id, temp_video_path, doc_contents: list, web_url, focus_topic, api_key, yt_url=None):
    queue = stream_queues.get(task_id)
    loop = asyncio.get_running_loop()
    
    def emit_cb(data):
        asyncio.run_coroutine_threadsafe(queue.put(data), loop)
        
    try:
        mark_task_active(task_id)
        audio_path = None
        frame_paths = []
        transcript_fetched = False
        video_download_failed = False
        all_documents: list[DocumentContent] = list(doc_contents)
        emit_cb({"type": "rag_status", "step": "EXTRACTING"})
        
        # Youtube Logic
        if yt_url:
            emit_cb({"type": "status", "message": "Fetching YouTube Details..."})
            yt_docs = await ingest_youtube_transcript(yt_url)
            if yt_docs:
                for d in yt_docs:
                    register_document(d.document_id, task_id, d.document_name, d.source_type, yt_url)
                all_documents.extend(yt_docs)
                transcript_fetched = True
                
            emit_cb({"type": "status", "message": f"Downloading video from link..."})
            try:
                temp_video_path = await asyncio.to_thread(download_video_from_url, yt_url, "temp")
                if not temp_video_path or not os.path.exists(temp_video_path):
                    raise ValueError("Failed to download video limits.")
            except Exception as e:
                video_download_failed = True
                if not transcript_fetched:
                    raise Exception("YouTube Anti-Bot Protection triggered and no transcript is available! Please upload manually.")
                else:
                    emit_cb({"type": "status", "message": "Video blocked but transcript found. Continuing text-only analysis..."})

        # Feature extraction
        if temp_video_path and not video_download_failed:
            if not transcript_fetched:
                audio_path = f"temp/{task_id}_audio.mp3"
                emit_cb({"type": "status", "message": "Extracting audio map..."})
                await asyncio.to_thread(extract_audio, temp_video_path, audio_path)
                
            emit_cb({"type": "status", "message": "Extracting video keyframes..."})
            frames_dir = f"temp/{task_id}_frames"
            try:
                frame_paths = await asyncio.to_thread(extract_frames, temp_video_path, frames_dir, 10)
            except Exception as e:
                print(f"Failed to extract frames: {e}")
                
        if web_url:
            emit_cb({"type": "status", "message": "Scraping web article..."})
            scraped_docs = await asyncio.to_thread(scrape_article, web_url)
            if scraped_docs:
                for d in scraped_docs:
                    register_document(d.document_id, task_id, d.document_name, d.source_type, web_url)
                all_documents.extend(scraped_docs)
                
        # Aggregate normalized DocumentContent representations into a single context file
        context_path = f"temp/{task_id}_context.txt"
        with open(context_path, "w", encoding="utf-8") as f:
            for d in all_documents:
                f.write(f"--- Document: {d.document_name} ({d.source_type}) ---\n")
                if d.metadata:
                    f.write(f"Metadata: {d.metadata}\n")
                f.write(f"{d.text}\n\n")
                
        doc_paths = [context_path] if all_documents else []
        
        if all_documents:
            emit_cb({"type": "rag_status", "step": "INDEXING_STARTED"})
            emit_cb({"type": "status", "message": "Indexing content for RAG search..."})
            from rag.retrieval import index_documents
            try:
                await asyncio.to_thread(index_documents, all_documents, api_key, emit_cb)
            except Exception as e:
                emit_cb({"type": "rag_status", "step": "INDEXING_FAILED"})
                print(f"RAG indexing failed: {e}")
                # We do not fail the main pipeline if RAG indexing fails
                
        emit_cb({"type": "status", "message": "Pumping payload to Gemini AI..."})
        
        # Heavy generative AI stream
        ai_result = await asyncio.to_thread(
            analyze_video_content, 
            audio_path, frame_paths, doc_paths, focus_topic, api_key, emit_cb
        )
        
        if "error" in ai_result and ai_result["error"]:
            raise Exception("AI synthesis pipeline failed. Please verify API key and quota.")

        emit_cb({"type": "status", "message": "Generating Microsoft Word Exports..."})
        await asyncio.to_thread(create_docx_from_markdown, ai_result["detailed_notes"], f"output/{task_id}_detailed.docx")
        await asyncio.to_thread(create_docx_from_markdown, ai_result["one_line_points"], f"output/{task_id}_points.docx")
        await asyncio.to_thread(create_docx_from_markdown, ai_result.get("definitions", ""), f"output/{task_id}_definitions.docx")
        await asyncio.to_thread(create_docx_from_markdown, ai_result["quiz"], f"output/{task_id}_quiz.docx")
        
        docx_urls = {
            "detailed": f"/api/download/{task_id}/detailed",
            "points": f"/api/download/{task_id}/points",
            "definitions": f"/api/download/{task_id}/definitions",
            "quiz": f"/api/download/{task_id}/quiz"
        }
        
        # Index generated notes into RAG
        if "detailed_notes" in ai_result and ai_result["detailed_notes"]:
            emit_cb({"type": "status", "message": "Indexing generated notes for RAG search..."})
            try:
                from models import DocumentContent
                from rag.retrieval import index_documents
                
                import re
                clean_notes = ai_result["detailed_notes"]
                clean_notes = re.sub(r'#+\s', '', clean_notes) # Remove headers
                clean_notes = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_notes) # Remove bold
                clean_notes = re.sub(r'\*(.*?)\*', r'\1', clean_notes) # Remove italics
                clean_notes = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean_notes) # Remove links
                clean_notes = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', clean_notes, flags=re.DOTALL) # Remove code blocks
                
                source_ids = ",".join([d.document_id for d in all_documents]) if all_documents else ""
                notes_doc = DocumentContent(
                    document_id=f"notes_{task_id}",
                    document_name="AI Generated Deep Dive Notes",
                    source_type="generated_notes",
                    text=clean_notes,
                    metadata={
                        "associated_task": task_id,
                        "source_documents": source_ids
                    }
                )
                register_document(notes_doc.document_id, task_id, notes_doc.document_name, notes_doc.source_type)
                emit_cb({"type": "rag_status", "step": "INDEXING_STARTED"})
                await asyncio.to_thread(index_documents, [notes_doc], api_key, emit_cb)
            except Exception as e:
                emit_cb({"type": "rag_status", "step": "INDEXING_FAILED"})
                print(f"Notes RAG indexing failed: {e}")
                
        emit_cb({"type": "complete", "result": {"docx_urls": docx_urls}})
        
    except Exception as e:
        error_msg = str(e).lower()
        if "api_key_invalid" in error_msg or "400" in error_msg:
            emit_cb({"type": "error", "message": "Invalid API Key!"})
        else:
            emit_cb({"type": "error", "message": f"Processing Failed: {str(e)}"})
    finally:
        mark_task_inactive(task_id)
        for path in doc_paths:
            try: os.remove(path)
            except: pass
        if frame_paths:
            import shutil
            frames_dir = os.path.dirname(frame_paths[0])
            try: shutil.rmtree(frames_dir)
            except: pass
        if temp_video_path:
            try: os.remove(temp_video_path)
            except: pass
        if audio_path:
            try: os.remove(audio_path)
            except: pass

@app.post("/api/process")
async def process_content(
    background_tasks: BackgroundTasks,
    url: str = Form(""),
    docs: list[UploadFile] = File(default=[]),
    focus_topic: Optional[str] = Form(None),
    web_url: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None)
):
    if not url and not docs and not web_url:
        raise HTTPException(status_code=400, detail="Must provide at least a video link, a document, or a web link")
        
    task_id = str(uuid.uuid4())
    doc_contents = await handle_document_ingestion(docs, task_id)
    
    stream_queues[task_id] = asyncio.Queue()
    
    yt_url = None
    final_web_url = web_url
    if url:
        import re
        if re.search(r"(?:youtube\.com|youtu\.be)", url.lower()):
            yt_url = url
        else:
            final_web_url = url

    background_tasks.add_task(process_task_pipeline, task_id, None, doc_contents, final_web_url, focus_topic, api_key, yt_url)
    
    return {"status": "processing", "task_id": task_id}

@app.get("/api/stream/{task_id}")
async def stream_task_events(task_id: str):
    touch_task(task_id)
    queue = stream_queues.get(task_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
        
    async def event_generator():
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in ["complete", "error"]:
                    break
        finally:
            if task_id in stream_queues:
                del stream_queues[task_id]
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/download/{task_id}/{doc_type}")
async def download_docx(task_id: str, doc_type: str):
    touch_task(task_id)
    valid_types = ["detailed", "points", "definitions", "quiz"]
    if doc_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid document type")
        
    file_path = f"output/{task_id}_{doc_type}.docx"
    filenames = {
        "detailed": "detailed_notes.docx",
        "points": "1_line_highlights.docx",
        "definitions": "definitions.docx",
        "quiz": "topic_quiz.docx"
    }
    
    if os.path.exists(file_path):
        return FileResponse(
            file_path, 
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
            filename=filenames[doc_type]
        )
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/api/stats/download")
async def record_download():
    db_service.increment_download()
    return {"status": "success"}

class FeedbackModel(BaseModel):
    rating: str
    comment: Optional[str] = None

@app.post("/api/feedback")
async def record_feedback(feedback: FeedbackModel):
    db_service.add_feedback(feedback.rating, feedback.comment)
    
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if webhook_url:
        try:
            emoji = "👍" if feedback.rating == "up" else "👎"
            msg = f"**New Feedback!** Rating: {feedback.rating} {emoji}"
            if feedback.comment:
                msg += f"\n> {feedback.comment}"
            requests.post(webhook_url, json={"content": msg})
        except Exception as e:
            print(f"Discord webhook failed: {e}")
            
    return {"status": "success"}

@app.get("/api/stats/summary")
async def get_stats_summary():
    return db_service.get_stats()

ADMIN_SECRET = "1803ks1415ms"

@app.get("/api/admin/feedback")
async def admin_get_feedback(secret: str = None):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    return db_service.get_all_feedback()

@app.delete("/api/admin/feedback/{feedback_id}")
async def admin_delete_feedback(feedback_id: int, secret: str = None):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    db_service.delete_feedback(feedback_id)
    return {"status": "deleted"}

if __name__ == "__main__":
    import uvicorn
    import multiprocessing
    multiprocessing.freeze_support()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
