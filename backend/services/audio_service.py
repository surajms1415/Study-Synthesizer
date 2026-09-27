import subprocess

def extract_audio(video_path: str, output_audio_path: str):
    """Extracts audio from a video file and saves it as an mp3 using ffmpeg."""
    try:
        # Heavily optimized fast audio extraction without re-encoding
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", "-y", output_audio_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return False
