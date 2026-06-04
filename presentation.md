# Project Report: Study Synthesizer (Desktop & Web Application)

---

## Abstract
**Study Synthesizer** (formerly Video Insight Extractor) is an advanced AI-powered educational tool designed to transform raw multimedia content into structured, interactive study materials. By leveraging Google's Gemini AI, the application processes video lectures, YouTube links, and presentation slides (PPTX, PDF, DOCX) to generate comprehensive notes, key highlights, definitions, quizzes, and interactive flashcards. Originally built as a full-stack web application, it has been successfully packaged into a standalone desktop application to bypass external API limitations (like YouTube anti-bot mechanisms) and provide a seamless, localized user experience.

---

## 1. Introduction

### 1.1 Problem Statement
Students, professionals, and lifelong learners often spend countless hours manually summarizing long video lectures, webinars, and dense presentation slides. Furthermore, existing online summarization tools struggle to effectively handle multiple modalities simultaneously (e.g., combining insights from a video with the accompanying PowerPoint slides) or are blocked by platform restrictions such as YouTube's anti-bot protections.

### 1.2 Objectives
* **Automated Synthesis:** Automatically generate detailed notes, glossaries, and flashcards from diverse educational inputs.
* **Multimodal Support:** Process video, audio, text, and presentation formats simultaneously.
* **Local Execution:** Package the application as a standalone desktop executable to ensure reliable processing (e.g., native `yt-dlp` execution) without relying on restricted cloud scraping APIs.
* **Interactive UX:** Provide a rich, responsive interface with features like 3D interactive flashcards and direct export to Microsoft Word (`.docx`).

---

## 2. System Architecture & Technology Stack

The project utilizes a decoupled client-server architecture, which operates seamlessly both on the web and locally on a desktop.

### 2.1 Backend (Server-Side)
* **Framework:** FastAPI (Python) - *Chosen for its high performance and asynchronous execution.*
* **AI Engine:** Google GenAI SDK (Gemini 2.5 Flash) - *Utilized for rapid, multimodal reasoning and structured JSON output generation.*
* **Media Processing:** 
  * `yt-dlp` & `youtube_transcript_api` for robust YouTube extraction.
  * `moviepy` and `OpenCV` (cv2) for local video frame sampling and audio extraction.
* **Document Parsing:** `python-docx` (for Word manipulation/export), `python-pptx` (for PowerPoint), and `PyPDF2`/`pdfplumber` (for PDFs).
* **Packaging:** `PyInstaller` - *Bundles the entire Python FastAPI backend into a single executable for the desktop app.*

### 2.2 Frontend (Client-Side)
* **Framework:** Next.js 14+ (React)
* **Styling:** Tailwind CSS with a cohesive Dark Mode design system.
* **Components:** Custom interactive 3D flashcards, animated loaders, and Markdown rendering (`react-markdown` with `remark-gfm`).
* **Packaging:** `Electron` - *Wraps the Next.js static export into a native desktop window, managing the lifecycle of the bundled Python backend executable.*

---

## 3. Key Features & Modules

### 3.1 Intelligent Ingestion Pipeline
* **YouTube Processing:** Users can paste any YouTube URL. The backend fetches transcripts and metadata, explicitly handling errors through retry logic to bypass temporary blocks.
* **Local File Uploads:** Supports direct upload of video files, extracting audio tracks and taking visual snapshots to feed into the multimodal AI.
* **Document Supplementation:** Users can upload accompanying `.pptx`, `.pdf`, or `.docx` files. The system unpacks the text and feeds it alongside the video context, allowing the AI to bridge the gap between spoken words and visual slides.

### 3.2 AI Synthesis Capabilities
* **Deep Dive Notes:** Generates structured, academically rigorous Markdown notes, actively suppressing irrelevant math noise and focusing on core concepts.
* **1-Line Highlights:** Condenses hours of material into a rapid-fire list of bullet points.
* **Glossary & Definitions:** Extracts technical terminology and constructs a structured dictionary.
* **Mastery Quizzes:** Formulates multiple-choice questions to test comprehension.
* **Interactive Flashcards:** Generates Q&A pairs rendered as flip-able 3D UI components.

### 3.3 Seamless Exporting
* The platform dynamically compiles the AI's synthesized Markdown notes, quizzes, and definitions into a beautifully styled, downloadable Microsoft Word document using programmatic templates.

---

## 4. Desktop Application Integration (Electron + PyInstaller)

To solve deployment issues related to YouTube's strict scraping policies, the application was transitioned into a standalone desktop application.

### 4.1 Backend Compilation
The FastAPI server was packaged using PyInstaller. Extensive configuration was applied to ensure that all implicit dependencies (such as `yt-dlp` executables, OpenCV binaries, and document parsers) were correctly bundled into the `dist/` directory.

### 4.2 Frontend Desktop Wrapping
An Electron main process (`main.js`) was configured to:
1. Spawns the bundled PyInstaller backend executable upon app launch.
2. Waits for the backend to bind to `localhost:8000`.
3. Loads the locally exported Next.js frontend (`out/index.html`) into a native OS window.
4. Gracefully terminates the backend process when the user closes the application, preventing orphaned background processes.

---

## 5. Challenges & Solutions

| Challenge | Solution Implemented |
| :--- | :--- |
| **YouTube Anti-Bot Blocking** | Cloud deployments were frequently blocked. The solution was packaging the app for the Desktop, utilizing local user IP addresses and `yt-dlp`'s advanced extraction to bypass blocks naturally. |
| **Handling Huge Files** | Video and audio files can be massive. Implemented efficient local processing: extracting low-bitrate audio and sampling visual frames every 10 seconds rather than sending raw video to the AI. |
| **Desktop App Lifecycle Management** | The Electron app left the Python server running in the background after closing. Implemented strict `child_process.spawn` controls and process termination listening on `window-all-closed`. |
| **Gemini API Unreliability** | API rate limits and 503 errors during file uploads. Implemented robust `retry` logic with exponential backoff inside the `backend/services/ai_service.py` to ensure stable processing. |

---

## 6. Conclusion & Future Work

**Study Synthesizer** successfully demonstrates how modern web technologies, tightly integrated with multimodal LLMs, can be packaged into highly capable local desktop applications. By shifting the processing to the user's machine, the architecture solves significant obstacles related to bot-protection APIs and large file transfer bottlenecks.

### Future Enhancements
* **Local Open-Source AI:** Integrating lightweight local models (e.g., Llama 3 or Mistral via Ollama) to allow completely offline synthesis without needing a Gemini API key.
* **Spaced Repetition Integration:** Exporting flashcards directly into Anki (`.apkg` format).
* **Direct Cloud Sync:** Allow users to save their generated notes directly to Google Drive or Notion.
