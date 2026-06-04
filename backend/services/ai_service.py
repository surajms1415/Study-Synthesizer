import os
import json
import time
import concurrent.futures
from google import genai

def analyze_video_content(audio_path=None, frame_paths=None, doc_paths=None, focus_topic=None, user_api_key=None, emit_cb=None):
    api_key = user_api_key or os.environ.get("GEMINI_API_KEY")
    if getattr(api_key, "strip", None):
        api_key = api_key.strip()
    
    if not api_key or api_key == "your_gemini_api_key_here":
        if emit_cb: emit_cb({"type": "error", "message": "Valid GEMINI_API_KEY is not set. Please set it in your browser settings or .env file."})
        return {"error": True}
        
    client = genai.Client(api_key=api_key)
    files_to_upload = []
    if audio_path: files_to_upload.append(audio_path)
    
    max_frames = 15
    if frame_paths:
        if len(frame_paths) > max_frames:
            step = len(frame_paths) // max_frames
            sampled_frames = frame_paths[::step][:max_frames]
        else:
            sampled_frames = frame_paths
        files_to_upload.extend(sampled_frames)
        
    if doc_paths:
        files_to_upload.extend(doc_paths)
        
    if emit_cb: emit_cb({"type": "status", "message": f"Uploading {len(files_to_upload)} files to Gemini (concurrently)..."})
    
    def upload_single_file(path_to_upload):
        max_upload_retries = 3
        for attempt in range(max_upload_retries):
            try:
                return client.files.upload(file=path_to_upload)
            except Exception as e:
                err_str = str(e).lower()
                if ("503" in err_str or "high demand" in err_str or "unavailable" in err_str) and attempt < max_upload_retries - 1:
                    time.sleep(2 ** attempt * 5)
                else:
                    raise

    uploaded_files = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for file_ref in executor.map(upload_single_file, files_to_upload):
            uploaded_files.append(file_ref)
            
    topic_instruction = ""
    if focus_topic:
        topic_instruction = f"""
    CRITICAL FOCUS INSTRUCTION: The user has specifically requested that you FOCUS YOUR ANALYSIS intensely on this topic: "{focus_topic}". 
    You must prioritize and expand immensely on information relating specifically to {focus_topic}.
    """
            
    prompt = f"""
    You are an expert tutor and examination preparer. 
    I have provided you with a video's audio track, keyframes (images) from the video, and possibly supplementary documents (PDFs, PPTs, Word, etc.). 
    CRITICAL RESTRICTION: You are ALLOWED and ENCOURAGED to use outside knowledge to explain topics and provide detailed context and examples, but DO NOT use too many equations or formulas. Keep explanations clear, text-based, and easy to understand. Do NOT output complex logic symbols or unreadable formats. Use your outside knowledge to make the Deep Dive notes thoroughly elaborate and deeply explanatory!
    {topic_instruction}
    
    Your task is to synthesize this multimodal information into five distinct, highly-structured examination-prep sections.
    
    IMPORTANT MUST-FOLLOW INSTRUCTIONS FOR OUTPUT FORMAT:
    You must output your response EXACTLY in five sections separated by the following identical marker lines:
    
    ===DETAILED_NOTES===
    [Intelligently extracted, elaborate explanations of IMPORTANT topics only]
    Do NOT include mundane details or everything from the files. Identify only the key concepts and provide thorough, detailed, and clear explanations strictly for these important topics using exam-ready text.
    Structure your notes perfectly using Markdown: use clear # Headings, bullet points, and bold text for emphasis. Do NOT use code blocks unless strictly necessary for context.
    
    ===ONE_LINE_POINTS===
    [Extract strictly the most important 1-line points from the content as a markdown bulleted list]
    Limit each point to a single concise sentence. Focus only on the absolute most valuable takeaways for a quick review.
    
    ===DEFINITIONS===
    [Extract all the important terminology, keywords, and their definitions]
    Present this strictly as a markdown bulleted list. Each term MUST be on its own line, starting with a dash, bolded term, and a clear explanation.
    
    ===QUIZ===
    [Generate exactly 5-10 highly relevant MCQs focused strictly on the important topics]
    Test the concepts deeply, even inferring related important knowledge beyond just the video's literal words.
    Present them format:
    ### Q1: [Question]
    - A) [Option A]
    - B) [Option B]
    - C) [Option C]
    - D) [Option D]
    
    **Answer:** [Correct Option]
    
    ===FLASHCARDS===
    [Generate exactly 10 flashcards in highly-structured JSON format]
    Output ONLY a valid JSON array of objects, containing "q" (question) and "a" (answer) keys. YOU MUST INCLUDE THIS SECTION AND THE JSON ARRAY WITHOUT FAIL. Do NOT wrap this in Markdown block ticks (no ```json). Look at the exact expected format:
    [
      {{ "q": "What is the primary function of the Mitochondria?", "a": "To generate most of the chemical energy needed to power the cell's biochemical reactions." }}
    ]
    """
    
    if emit_cb: emit_cb({"type": "status", "message": "Analyzing with Gemini (Streaming)..."})
    
    max_retries = 3
    response_stream = None
    for attempt in range(max_retries):
        try:
            response_stream = client.models.generate_content_stream(
                model='gemini-2.5-flash',
                contents=uploaded_files + [prompt]
            )
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt * 5)
            else:
                if emit_cb: emit_cb({"type": "error", "message": f"Gemini Error: {str(e)}"})
                return {"error": True}
                
    detailed_notes, one_line_points, definitions, quiz, flashcards_raw = "", "", "", "", ""
    current_section = "detailed_notes"
    
    buffer = ""
    for chunk in response_stream:
        text = chunk.text
        if not text: continue
        buffer += text
        
        while True:
            parts = buffer.split("===ONE_LINE_POINTS===")
            if len(parts) > 1:
                detailed_notes += parts[0]
                if emit_cb: emit_cb({"type": "chunk", "section": "detailed_notes", "text": parts[0]})
                current_section = "one_line_points"
                buffer = parts[1]
                continue
                
            parts = buffer.split("===DEFINITIONS===")
            if len(parts) > 1:
                if current_section == "detailed_notes": detailed_notes += parts[0]
                elif current_section == "one_line_points": one_line_points += parts[0]
                if emit_cb: emit_cb({"type": "chunk", "section": current_section, "text": parts[0]})
                current_section = "definitions"
                buffer = parts[1]
                continue
                
            parts = buffer.split("===QUIZ===")
            if len(parts) > 1:
                if current_section == "one_line_points": one_line_points += parts[0]
                elif current_section == "definitions": definitions += parts[0]
                if emit_cb: emit_cb({"type": "chunk", "section": current_section, "text": parts[0]})
                current_section = "quiz"
                buffer = parts[1]
                continue
                
            parts = buffer.split("===FLASHCARDS===")
            if len(parts) > 1:
                if current_section == "definitions": definitions += parts[0]
                elif current_section == "quiz": quiz += parts[0]
                if emit_cb: emit_cb({"type": "chunk", "section": current_section, "text": parts[0]})
                current_section = "flashcards"
                buffer = parts[1]
                continue
            break
            
        if len(buffer) > 40:
            safe_text = buffer[:-30]
            buffer = buffer[-30:]
            if current_section == "detailed_notes": 
                detailed_notes += safe_text
                if emit_cb: emit_cb({"type": "chunk", "section": "detailed_notes", "text": safe_text})
            elif current_section == "one_line_points":
                one_line_points += safe_text
                if emit_cb: emit_cb({"type": "chunk", "section": "one_line_points", "text": safe_text})
            elif current_section == "definitions":
                definitions += safe_text
                if emit_cb: emit_cb({"type": "chunk", "section": "definitions", "text": safe_text})
            elif current_section == "quiz":
                quiz += safe_text
                if emit_cb: emit_cb({"type": "chunk", "section": "quiz", "text": safe_text})
            elif current_section == "flashcards":
                flashcards_raw += safe_text
                    
    if buffer:
        safe_text = buffer
        if current_section == "detailed_notes": 
            detailed_notes += safe_text
            if emit_cb: emit_cb({"type": "chunk", "section": "detailed_notes", "text": safe_text})
        elif current_section == "one_line_points":
            one_line_points += safe_text
            if emit_cb: emit_cb({"type": "chunk", "section": "one_line_points", "text": safe_text})
        elif current_section == "definitions":
            definitions += safe_text
            if emit_cb: emit_cb({"type": "chunk", "section": "definitions", "text": safe_text})
        elif current_section == "quiz":
            quiz += safe_text
            if emit_cb: emit_cb({"type": "chunk", "section": "quiz", "text": safe_text})
        elif current_section == "flashcards":
            flashcards_raw += safe_text

    flashcards_parsed = []
    if flashcards_raw:
        try:
            cl = flashcards_raw.replace("```json", "").replace("```", "").strip()
            flashcards_parsed = json.loads(cl)
            if emit_cb: emit_cb({"type": "chunk", "section": "flashcards_update", "text": json.dumps(flashcards_parsed)})
        except Exception as e:
            print("Failed to parse flashcards JSON:", e)

    return {
        "detailed_notes": detailed_notes.strip() if detailed_notes else "Error generating notes.",
        "one_line_points": one_line_points.strip() if one_line_points else "Error generating key points.",
        "definitions": definitions.strip() if definitions else "Error generating definitions.",
        "quiz": quiz.strip() if quiz else "Error generating quiz.",
        "flashcards": flashcards_parsed
    }
