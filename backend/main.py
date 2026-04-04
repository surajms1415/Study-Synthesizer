from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import uuid
import asyncio

from services.audio_service import extract_audio
from services.video_service import extract_frames
from services.ai_service import analyze_video_content
from services.doc_service import create_docx_from_markdown
from services.download_service import download_video_from_url
from services.web_service import scrape_article
from pydantic import BaseModel
import json

app = FastAPI(title="Video Insight Extractor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow Vercel frontend to talk to Render backend
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp", exist_ok=True)
os.makedirs("output", exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "Video Insight Extractor API is running!"}

@app.post("/api/upload")
async def upload_video(
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
    audio_path = None
    frame_paths = []
    
    if file and file.filename:
        if not file.filename.endswith(('.mp4', '.mkv', '.avi', '.mov')):
            raise HTTPException(status_code=400, detail="Invalid video format")
            
        temp_video_path = f"temp/{task_id}_video{os.path.splitext(file.filename)[1]}"
        with open(temp_video_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
    doc_paths = []
    for d in docs:
        if d.filename:
            path = f"temp/{task_id}_doc_{d.filename}"
            with open(path, "wb") as buf:
                buf.write(await d.read())
            doc_paths.append(path)
            
    if web_url:
        print(f"Scraping {web_url}...")
        scraped_text = scrape_article(web_url)
        if scraped_text:
            path = f"temp/{task_id}_web.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write(scraped_text)
            doc_paths.append(path)
        
    try:
        if temp_video_path:
            # Step 1: Extract Audio
            audio_path = f"temp/{task_id}_audio.mp3"
            print("Extracting audio...")
            extract_audio(temp_video_path, audio_path)
            
            # Step 2: Extract Frames
            frames_dir = f"temp/{task_id}_frames"
            print("Extracting frames...")
            # Get frame every 10 seconds
            frame_paths = extract_frames(temp_video_path, frames_dir, interval_seconds=10)
        
        # Step 3: AI Processing
        print("Analyzing with Gemini...")
        ai_result = analyze_video_content(audio_path, frame_paths, doc_paths, focus_topic, api_key)
        
        # Step 4: Generate DOCX
        print("Generating DOCX files...")
        create_docx_from_markdown(ai_result["detailed_notes"], f"output/{task_id}_detailed.docx")
        create_docx_from_markdown(ai_result["one_line_points"], f"output/{task_id}_points.docx")
        create_docx_from_markdown(ai_result.get("definitions", ""), f"output/{task_id}_definitions.docx")
        create_docx_from_markdown(ai_result["quiz"], f"output/{task_id}_quiz.docx")
        

        
        return {
            "status": "success",
            "task_id": task_id,
            "detailed_notes": ai_result["detailed_notes"],
            "one_line_points": ai_result["one_line_points"],
            "definitions": ai_result.get("definitions", ""),
            "quiz": ai_result["quiz"],
            "flashcards": ai_result.get("flashcards", []),
            "docx_urls": {
                "detailed": f"/api/download/{task_id}/detailed",
                "points": f"/api/download/{task_id}/points",
                "definitions": f"/api/download/{task_id}/definitions",
                "quiz": f"/api/download/{task_id}/quiz"
            }
        }
        
    except Exception as e:
        print(f"Error during processing: {e}")
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
            raise HTTPException(status_code=429, detail="API Quota Exceeded! Your Gemini API key has run out of its free usage limit. Please click 'Get Key Here' above to generate a new FREE API key, paste it into the box, and try again.")
        if "400" in error_str or "api_key_invalid" in error_str or "api key not valid" in error_str:
            raise HTTPException(status_code=400, detail="Invalid API Key! Please double-check that you copied the key correctly from Google AI Studio without any extra spaces or missing characters.")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Guaranteed cleanup regardless of success or failure
        for path in doc_paths:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        for path in frame_paths:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        if temp_video_path and os.path.exists(temp_video_path):
            try: os.remove(temp_video_path)
            except: pass
        if audio_path and os.path.exists(audio_path):
            try: os.remove(audio_path)
            except: pass

class LinkRequest(BaseModel):
    url: str

@app.post("/api/process-link")
async def process_link(
    url: str = Form(""),
    docs: list[UploadFile] = File(default=[]),
    focus_topic: Optional[str] = Form(None),
    web_url: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None)
):
    if not url and not docs and not web_url:
        raise HTTPException(status_code=400, detail="Must provide at least a video link, a document, or a web tie")
        
    try:
        task_id = str(uuid.uuid4())
        audio_path = None
        frame_paths = []
        
        # Step 0: Download from link
        if url:
            print(f"Downloading video from {url}...")
            temp_video_path = download_video_from_url(url, "temp")
            
            # Verify the file was created
            if not temp_video_path or not os.path.exists(temp_video_path):
                raise HTTPException(status_code=400, detail="Failed to download video from the provided link.")
                
            # Step 1: Extract Audio or fetch Transcript directly (instant)
            audio_path = None
            transcript_fetched = False
            
            try:
                import re
                from youtube_transcript_api import YouTubeTranscriptApi
                
                match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:\?|&|$)", url)
                if not match:
                    match = re.search(r"youtu\.be\/([0-9A-Za-z_-]{11})(?:\?|&|$)", url)
                    
                video_id = match.group(1) if match else None
                
                if video_id:
                    print(f"Attempting to fetch YouTube transcript directly for {video_id}...")
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                    transcript_text = " ".join([t['text'] for t in transcript_list])
                    
                    transcript_path = f"temp/{task_id}_yt_transcript.txt"
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        f.write(transcript_text)
                    doc_paths.append(transcript_path)
                    transcript_fetched = True
                    print("Transcript fetched instantly! Skipping time-consuming MP3 audio rendering.")
                else:
                    raise Exception("Not a recognized YouTube ID")
            except Exception as e:
                print(f"Could not fetch transcript (maybe no captions), falling back to MP3 extraction: {e}")
                
            if not transcript_fetched:
                audio_path = f"temp/{task_id}_audio.mp3"
                print("Extracting audio map (fallback)...")
                extract_audio(temp_video_path, audio_path)
            
            # Step 2: Extract Frames
            frames_dir = f"temp/{task_id}_frames"
            print("Extracting frames...")
            # Get frame every 10 seconds
            frame_paths = extract_frames(temp_video_path, frames_dir, interval_seconds=10)
            
        doc_paths = []
        for d in docs:
            if d.filename:
                path = f"temp/{task_id}_doc_{d.filename}"
                with open(path, "wb") as buf:
                    buf.write(await d.read())
                doc_paths.append(path)
                
        if web_url:
            print(f"Scraping {web_url}...")
            scraped_text = scrape_article(web_url)
            if scraped_text:
                path = f"temp/{task_id}_web.txt"
                with open(path, "w", encoding="utf-8") as f:
                    f.write(scraped_text)
                doc_paths.append(path)
        
        # Step 3: AI Processing
        print("Analyzing with Gemini...")
        ai_result = analyze_video_content(audio_path, frame_paths, doc_paths, focus_topic, api_key)
        
        # Step 4: Generate DOCX
        print("Generating DOCX files...")
        create_docx_from_markdown(ai_result["detailed_notes"], f"output/{task_id}_detailed.docx")
        create_docx_from_markdown(ai_result["one_line_points"], f"output/{task_id}_points.docx")
        create_docx_from_markdown(ai_result.get("definitions", ""), f"output/{task_id}_definitions.docx")
        create_docx_from_markdown(ai_result["quiz"], f"output/{task_id}_quiz.docx")
        

        return {
            "status": "success",
            "task_id": task_id,
            "detailed_notes": ai_result["detailed_notes"],
            "one_line_points": ai_result["one_line_points"],
            "definitions": ai_result.get("definitions", ""),
            "quiz": ai_result["quiz"],
            "flashcards": ai_result.get("flashcards", []),
            "docx_urls": {
                "detailed": f"/api/download/{task_id}/detailed",
                "points": f"/api/download/{task_id}/points",
                "definitions": f"/api/download/{task_id}/definitions",
                "quiz": f"/api/download/{task_id}/quiz"
            }
        }
        
    except Exception as e:
        print(f"Error during processing link: {e}")
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
            raise HTTPException(status_code=429, detail="API Quota Exceeded! Your Gemini API key has run out of its free usage limit. Please click 'Get Key Here' above to generate a new FREE API key, paste it into the box, and try again.")
        if "400" in error_str or "api_key_invalid" in error_str or "api key not valid" in error_str:
            raise HTTPException(status_code=400, detail="Invalid API Key! Please double-check that you copied the key correctly from Google AI Studio without any extra spaces or missing characters.")
        raise HTTPException(status_code=500, detail=str(e))

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

