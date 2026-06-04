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

app = FastAPI(title="Video Insight Extractor API")

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

async def handle_document_saving(docs, task_id):
    doc_paths = []
    for d in docs:
        if d.filename:
            path = f"temp/{task_id}_doc_{d.filename}"
            with open(path, "wb") as buf:
                buf.write(await d.read())
            
            ext = os.path.splitext(d.filename)[1].lower()
            if ext in ['.pptx', '.ppt']:
                try:
                    text_content = extract_text_from_pptx(path)
                    text_path = path + ".txt"
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write(text_content)
                    doc_paths.append(text_path)
                except Exception as e:
                    print(f"Failed to extract pptx text: {e}")
                    doc_paths.append(path)
            elif ext in ['.docx', '.doc']:
                try:
                    text_content = extract_text_from_docx(path)
                    text_path = path + ".txt"
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write(text_content)
                    doc_paths.append(text_path)
                except Exception as e:
                    print(f"Failed to extract docx text: {e}")
                    doc_paths.append(path)
            else:
                doc_paths.append(path)
    return doc_paths

async def process_task_pipeline(task_id, temp_video_path, doc_paths, web_url, focus_topic, api_key, yt_url=None):
    queue = stream_queues.get(task_id)
    loop = asyncio.get_running_loop()
    
    def emit_cb(data):
        asyncio.run_coroutine_threadsafe(queue.put(data), loop)
        
    try:
        audio_path = None
        frame_paths = []
        transcript_fetched = False
        video_download_failed = False
        
        # Youtube Logic
        if yt_url:
            emit_cb({"type": "status", "message": "Fetching YouTube Details..."})
            try:
                import re
                from youtube_transcript_api import YouTubeTranscriptApi
                match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:\?|&|$)", yt_url)
                if not match: match = re.search(r"youtu\.be\/([0-9A-Za-z_-]{11})(?:\?|&|$)", yt_url)
                video_id = match.group(1) if match else None
                
                if video_id:
                    transcript_list = await asyncio.to_thread(YouTubeTranscriptApi.get_transcript, video_id)
                    transcript_text = " ".join([t['text'] for t in transcript_list])
                    
                    transcript_path = f"temp/{task_id}_yt_transcript.txt"
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        f.write(transcript_text)
                    doc_paths.append(transcript_path)
                    transcript_fetched = True
            except Exception as e:
                print(f"No yt transcript: {e}")

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
            scraped_text = await asyncio.to_thread(scrape_article, web_url)
            if scraped_text:
                path = f"temp/{task_id}_web.txt"
                with open(path, "w", encoding="utf-8") as f:
                    f.write(scraped_text)
                doc_paths.append(path)
                
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
        
        emit_cb({"type": "complete", "result": {"docx_urls": docx_urls}})
        
    except Exception as e:
        error_msg = str(e).lower()
        if "api_key_invalid" in error_msg or "400" in error_msg:
            emit_cb({"type": "error", "message": "Invalid API Key!"})
        else:
            emit_cb({"type": "error", "message": f"Processing Failed: {str(e)}"})
    finally:
        for path in doc_paths:
            try: os.remove(path)
            except: pass
        if frame_paths:
            for path in frame_paths:
                try: os.remove(path)
                except: pass
        if temp_video_path:
            try: os.remove(temp_video_path)
            except: pass
        if audio_path:
            try: os.remove(audio_path)
            except: pass

@app.post("/api/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    docs: list[UploadFile] = File(default=[]),
    focus_topic: Optional[str] = Form(None),
    web_url: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None)
):
    if not file and not docs and not web_url:
        raise HTTPException(status_code=400, detail="Must provide at least a video, a document, or a web link")
    
    task_id = str(uuid.uuid4())
    temp_video_path = None
    
    if file and file.filename:
        if not file.filename.endswith(('.mp4', '.mkv', '.avi', '.mov')):
            raise HTTPException(status_code=400, detail="Invalid video format")
            
        temp_video_path = f"temp/{task_id}_video{os.path.splitext(file.filename)[1]}"
        with open(temp_video_path, "wb") as buffer:
            buffer.write(await file.read())
            
    doc_paths = await handle_document_saving(docs, task_id)
    
    stream_queues[task_id] = asyncio.Queue()
    background_tasks.add_task(process_task_pipeline, task_id, temp_video_path, doc_paths, web_url, focus_topic, api_key, None)
    
    return {"status": "processing", "task_id": task_id}

@app.post("/api/process-link")
async def process_link(
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
    doc_paths = await handle_document_saving(docs, task_id)
    
    stream_queues[task_id] = asyncio.Queue()
    background_tasks.add_task(process_task_pipeline, task_id, None, doc_paths, web_url, focus_topic, api_key, url)
    
    return {"status": "processing", "task_id": task_id}

@app.get("/api/stream/{task_id}")
async def stream_task_events(task_id: str):
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
