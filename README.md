# Study Synthesizer 🧠

**Study Synthesizer** is a lightweight, high-performance desktop-first AI learning assistant. It transforms raw study materials—ranging from long YouTube lectures to complex PDFs—into interactive Deep Dive notes, mastery quizzes, flashcards, and a fully conversational "Ask AI" context window.

Powered by **Gemini 2.5 Flash**, a local **ChromaDB** RAG implementation, and a blazingly fast Next.js/FastAPI stack, Study Synthesizer is built to be bundled as an offline-capable standalone Electron application.

## ✨ Features

- **Multi-Modal Ingestion**: Effortlessly process YouTube URLs (with automatic timestamp mapping), public web articles, and local document uploads (`.PDF`, `.DOCX`, `.PPTX`).
- **AI Deep Dives & Quizzes**: Automatically synthesizes uploaded material into beautifully formatted Markdown Notes, 1-Line Highlights, Definitions, and Multiple-Choice Quizzes.
- **Interactive Flashcards**: Auto-generates a 3D-flipping flashcard deck for rote memorization of core concepts.
- **"Ask AI" (RAG System)**: Chat with your study materials! A built-in local Vector Database (ChromaDB) intelligently retrieves context to answer your questions, complete with precise source citations (e.g., `DBMS.pdf — Page 12` or `YouTube — 12:35–13:10`).
- **Automated 48-Hour Data Cleanup**: Designed for privacy and storage efficiency. An internal SQLite background service tracks document lifecycles and safely wipes temporary files, processed audio/video, and RAG vector chunks after 48 hours of inactivity.
- **DOCX Export**: Instantly export your generated notes and quizzes to neatly formatted Word documents.
- **Zero Bloat**: Stripped of heavy dependencies like OpenCV and Redis, relying on lightweight raw `ffmpeg` streams, local SQLite, and Python's native `asyncio`.

## 🏗️ Architecture

Study Synthesizer is designed as a modular monolith split into two decoupled processes, ideal for Electron packaging:

1. **Frontend (Next.js 16)**: A responsive, Tailwind-styled React application with Server-Sent Events (SSE) for real-time generation streaming.
2. **Backend (FastAPI)**: A Python 3 backend orchestrating `yt-dlp`, PyPDF2, BeautifulSoup, and the Gemini API. Packaged securely into a single executable via **PyInstaller**.
3. **Storage (Local)**: 
   - `stats.db` (SQLite) for task lifecycles and cleanup tracking.
   - `temp/chroma_db` for local semantic vector storage.

## 🚀 Getting Started (Development)

### Prerequisites
- Node.js (v18+)
- Python (3.12+)
- [FFmpeg](https://ffmpeg.org/) installed and available in your system PATH.

### 1. Backend Setup
```bash
cd backend
python -m venv venv
# Activate venv (Windows: venv\Scripts\activate, Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt

# Set your Gemini API Key in a .env file or export it:
# GEMINI_API_KEY=your_google_gemini_key

# Run the FastAPI server
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` to interact with the application.

## 📦 Building for Production

### Compile Backend (PyInstaller)
```bash
cd backend
pyinstaller backend_server.spec
```
*Outputs a standalone executable to `backend/dist/backend_server.exe`.*

### Compile Frontend (Next.js)
```bash
cd frontend
npm run build
```
*Outputs a standalone optimized React build.*

## 🔒 Privacy & Data Retention
Study Synthesizer does **not** rely on external cloud databases. All SQLite tracking and ChromaDB vector embeddings remain firmly on your local disk. 

The built-in **Cleanup Service** runs a background cron-job every hour. Any study session untouched for exactly 48 hours will have its raw extracted files, videos, and ChromaDB embeddings permanently wiped from the application's internal managed storage to prevent SSD bloat. (Files you explicitly exported to your `Downloads` folder remain untouched).

## 📄 License
MIT License.
