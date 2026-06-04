import PyInstaller.__main__
import os

if __name__ == "__main__":
    PyInstaller.__main__.run([
        'main.py',
        '--name=backend_server',
        '--onefile',
        '--hidden-import=uvicorn',
        '--hidden-import=uvicorn.logging',
        '--hidden-import=uvicorn.loops',
        '--hidden-import=uvicorn.loops.auto',
        '--hidden-import=uvicorn.protocols',
        '--hidden-import=uvicorn.protocols.http',
        '--hidden-import=uvicorn.protocols.http.auto',
        '--hidden-import=uvicorn.protocols.websockets',
        '--hidden-import=uvicorn.protocols.websockets.auto',
        '--hidden-import=uvicorn.lifespan',
        '--hidden-import=uvicorn.lifespan.on',
        '--hidden-import=fastapi',
        '--hidden-import=pydantic',
        '--hidden-import=moviepy',
        '--hidden-import=python-docx',
        '--hidden-import=python-pptx',
        '--hidden-import=google.genai',
        '--hidden-import=yt_dlp',
        '--hidden-import=cv2',
        '--hidden-import=youtube_transcript_api',
        '--collect-all=moviepy',
        '--collect-all=google.genai',
        '--collect-all=docx',
        '--collect-all=pptx',
        '--collect-all=yt_dlp',
        '--copy-metadata=imageio',
        '--copy-metadata=tqdm',
        '--copy-metadata=moviepy',
        '--noconfirm'
    ])
