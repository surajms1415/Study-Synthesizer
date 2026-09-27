import os
import subprocess
import glob

def extract_frames(video_path: str, output_dir: str, interval_seconds: int = 10):
    """Extracts frames from a video at a specified interval using ffmpeg."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        # Heavily optimized frame extraction using ffmpeg to jump exactly to keyframes
        # -vf fps=1/interval downscales to 720p max while preserving aspect ratio
        out_pattern = os.path.join(output_dir, "frame_%04d.jpg")
        
        subprocess.run(
            [
                "ffmpeg", "-i", video_path, 
                "-vf", f"fps=1/{interval_seconds},scale='min(1280,iw)':'min(720,ih)'", 
                "-y", out_pattern
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        
        # Return list of generated frames
        saved_frames = sorted(glob.glob(os.path.join(output_dir, "frame_*.jpg")))
        return saved_frames
        
    except Exception as e:
        print(f"Error extracting frames with ffmpeg: {e}")
        return []
