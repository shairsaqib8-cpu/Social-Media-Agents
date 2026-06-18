import os
import re
import requests
from urllib.parse import urlparse, parse_qs


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def fetch_youtube_metadata(video_id: str) -> dict:
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        return {"error": "YOUTUBE_API_KEY not set in .env"}

    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=snippet,statistics,contentDetails"
        f"&id={video_id}&key={api_key}"
    )
    r = requests.get(url, timeout=10)
    if r.status_code == 400:
        return {"error": "Invalid YouTube API key or bad request. Please set a valid YOUTUBE_API_KEY in your .env file."}
    if r.status_code == 403:
        return {"error": "YouTube API quota exceeded or API key not authorized. Check your YOUTUBE_API_KEY."}
    if not r.ok:
        return {"error": f"YouTube API error {r.status_code}: {r.text[:200]}"}
    data = r.json()
    if not data.get("items"):
        return {"error": "Video not found"}

    item = data["items"][0]
    snippet = item["snippet"]
    stats = item.get("statistics", {})
    content = item.get("contentDetails", {})

    thumbnails = snippet.get("thumbnails", {})
    thumb_url = (
        thumbnails.get("maxres", thumbnails.get("high", thumbnails.get("default", {}))).get("url", "")
    )

    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "channel": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "tags": snippet.get("tags", []),
        "category_id": snippet.get("categoryId", ""),
        "duration": content.get("duration", ""),
        "view_count": int(stats.get("viewCount", 0)),
        "like_count": int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
        "thumbnail_url": thumb_url,
    }


def fetch_transcript(video_id: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(t["text"] for t in transcript_list[:80])
    except Exception:
        return ""


def fetch_competitor_videos(query: str, exclude_id: str = "", max_results: int = 5) -> list[dict]:
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        return []
    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&q={requests.utils.quote(query)}"
        f"&maxResults=10&order=viewCount&key={api_key}"
    )
    r = requests.get(url, timeout=10)
    if not r.ok:
        return []
    items = r.json().get("items", [])
    results = []
    for item in items:
        vid_id = item["id"].get("videoId", "")
        if vid_id == exclude_id:
            continue
        results.append({
            "video_id": vid_id,
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "thumbnail": item["snippet"]["thumbnails"].get("high", {}).get("url", ""),
        })
        if len(results) >= max_results:
            break
    return results
