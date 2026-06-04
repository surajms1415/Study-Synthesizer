import os
import uuid
import yt_dlp

def download_video_from_url(url: str, output_dir: str = "temp") -> str:
    """Downloads a video from a URL using yt-dlp and returns the saved file path."""
    os.makedirs(output_dir, exist_ok=True)
    task_id = str(uuid.uuid4())
    
    # Configure yt-dlp to download max 720p to drastically reduce download and processing time
    # Added extractor_args to spoof Android/iOS clients to bypass YouTube's datacenter Bot Protection
    ydl_opts = {
        'format': 'best[height<=720]/best',
        'outtmpl': os.path.join(output_dir, f'{task_id}_video.%(ext)s'),
        'quiet': False,
        'no_warnings': True,
        'socket_timeout': 300,
        'retries': 10,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'mweb']
            }
        }
    }
    
    try_opts = [
        ydl_opts, # Try completely unauthenticated first with Android spoof
    ]
    
    # Define browser fallback options to combat IP blocks when running locally
    browsers = ['edge', 'chrome', 'firefox', 'brave', 'safari', 'opera']
    for browser in browsers:
        opt_copy = ydl_opts.copy()
        opt_copy['cookiesfrombrowser'] = (browser,)
        try_opts.append(opt_copy)

    last_err = None
    
    for current_opts in try_opts:
        try:
            with yt_dlp.YoutubeDL(current_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                # Find the properly downloaded file by prefix
                for file in os.listdir(output_dir):
                    if file.startswith(f"{task_id}_video"):
                        return os.path.join(output_dir, file)
                        
                # Fallback if no file is found (unlikely)
                return os.path.join(output_dir, f'{task_id}_video.mp4')
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            last_err = e
            # If the error is an anti-bot block or cookies error, continue to the next browser option
            if "sign in to confirm" in error_msg or "bot" in error_msg or "cookie" in error_msg or "permission denied" in error_msg:
                continue 
            # If it's a completely different error (like video unavailable), break and raise immediately
            break
        except Exception as e:
            # For database lock errors or missing browser errors, just skip to the next
            last_err = e
            continue

    # If it exhausts all options (or broke early) and still failed
    if last_err:
        err_msg = str(last_err).lower()
        if "sign in to confirm" in err_msg or "bot" in err_msg:
             raise ValueError("YouTube Anti-Bot Protection triggered! YouTube is currently blocking download requests for this video. Please try a different video link, or upload the video/transcript manually.")
        raise ValueError(f"Failed to download video: {str(last_err)}")
        
    raise ValueError("Failed to download video due to unknown error.")
