import os
import json
import time
import random
from typing import List, Dict, Optional

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import yt_dlp


# ==========================
# CONFIGURATION
# ==========================

# TODO: change this to your playlist URL
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLXrRC--1DgPab9DaC_WSUsrMEeMa3uhD7"

# Output folder for saved transcripts
OUTPUT_DIR = "transcripts"

# Delay between processing videos (in seconds)
MIN_DELAY_SECONDS = 5
MAX_DELAY_SECONDS = 20

# Batch settings: after this many videos, take a longer rest
BATCH_SIZE = 100
BATCH_REST_SECONDS = 5 * 60  # 5 minutes

# Preferred transcript languages (in order)
# Add more if needed, for example ["tr", "en"] for Turkish + English.
PREFERRED_LANGUAGES = ["tr", "en"]


# ==========================
# PLAYLIST HANDLING (yt-dlp)
# ==========================

def get_videos_from_playlist(playlist_url: str) -> List[Dict[str, str]]:
    """
    Use yt-dlp to extract basic info (id, title) for each video
    in the playlist (or single video URL).
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",  # do not resolve each video in full
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    videos: List[Dict[str, str]] = []

    # If it's a playlist, "entries" will be present.
    if "entries" in info:
        for entry in info["entries"]:
            if not entry:
                continue
            video_id = entry.get("id")
            title = entry.get("title") or ""
            if video_id:
                videos.append({"id": video_id, "title": title})
    else:
        # Single video URL
        video_id = info.get("id")
        title = info.get("title") or ""
        if video_id:
            videos.append({"id": video_id, "title": title})

    return videos


# ==========================
# TRANSCRIPT HANDLING
# ==========================

def fetch_transcript_for_video(
    video_id: str,
    languages: Optional[List[str]] = None,
) -> Optional[List[Dict]]:
    """
    Fetch transcript segments for a video using youtube-transcript-api.
    Uses the instance-based API (YouTubeTranscriptApi().fetch),
    which works with both manually created and auto-generated subtitles.

    Returns a list of segments like:
        [{"text": "...", "start": 0.0, "duration": 3.2}, ...]
    or None if not available.
    """
    if languages is None:
        languages = PREFERRED_LANGUAGES

    try:
        print(f"  Trying to fetch transcript for {video_id} with languages: {languages}")
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages)
        segments = fetched.to_raw_data()
        print(f"  Got {len(segments)} transcript snippets")
        return segments
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        print(f"  Transcript not available for {video_id}: {e}")
        return None
    except Exception as e:
        print(f"  Unexpected error fetching transcript for {video_id}: {e}")
        return None


def sanitize_filename(name: str) -> str:
    """
    Make a safe filename from a video title.
    """
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    # Remove very long names
    return name.strip()[:150] or "untitled"


def build_transcript_filepath(
    video: Dict[str, str],
    output_dir: str = OUTPUT_DIR,
) -> str:
    """
    Build the output filepath for a video's transcript JSON.
    """
    os.makedirs(output_dir, exist_ok=True)

    video_id = video.get("id", "")
    title = video.get("title", "")
    safe_title = sanitize_filename(title)

    filename = f"{safe_title}__{video_id}.json"
    return os.path.join(output_dir, filename)


def save_transcript(
    video: Dict[str, str],
    segments: List[Dict],
    output_dir: str = OUTPUT_DIR,
) -> None:
    """
    Save transcript as JSON, including video id, title, and segments.
    """
    filepath = build_transcript_filepath(video, output_dir=output_dir)

    data = {
        "video_id": video.get("id", ""),
        "title": video.get("title", ""),
        "segments": segments,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  Saved transcript to: {filepath}")


# ==========================
# MAIN SCRIPT
# ==========================

def main() -> None:
    if "PASTE_YOUR_PLAYLIST_ID_HERE" in PLAYLIST_URL:
        print("Please edit PLAYLIST_URL in main.py and put your real playlist URL.")
        return

    print("Fetching playlist information...")
    videos = get_videos_from_playlist(PLAYLIST_URL)
    total = len(videos)
    print(f"Found {total} video(s) in playlist.")

    if total == 0:
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for index, video in enumerate(videos, start=1):
        video_id = video["id"]
        title = video.get("title", "")

        print(f"\n[{index}/{total}] Processing video:")
        print(f"  ID: {video_id}")
        print(f"  Title: {title}")

        # Simple resume system: skip videos that already have a saved transcript file
        existing_path = build_transcript_filepath(video, output_dir=OUTPUT_DIR)
        if os.path.exists(existing_path):
            print(f"  Transcript already exists at: {existing_path}")
            # Still sleep a bit before moving to the next video
            delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            print(f"  Sleeping for {delay:.1f} seconds before next video...")
            time.sleep(delay)
            continue

        segments = fetch_transcript_for_video(video_id)

        if not segments:
            print("  No transcript, skipping save.")
        else:
            save_transcript(video, segments)

        # Random delay between videos to be gentle with YouTube
        delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        print(f"  Sleeping for {delay:.1f} seconds...")
        time.sleep(delay)

        # Long cool-down after each batch of BATCH_SIZE videos (except after the last one)
        if index % BATCH_SIZE == 0 and index < total:
            print(
                f"\nProcessed {index} videos, taking a long rest of "
                f"{BATCH_REST_SECONDS} seconds..."
            )
            time.sleep(BATCH_REST_SECONDS)

    print("\nDone processing all videos.")


if __name__ == "__main__":
    main()


