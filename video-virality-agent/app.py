import os
import sys
import shutil
import uuid
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agents.youtube_fetcher import (
    extract_video_id,
    fetch_youtube_metadata,
    fetch_transcript,
    fetch_competitor_videos,
)
from agents.virality_analyzer import (
    analyze_thumbnail,
    analyze_video_content,
    analyze_uploaded_video,
    compare_competitors,
)

UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Video Virality Analyzer")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp"}


def _save_upload(file: UploadFile, allowed: set[str]) -> Path:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
    dest = UPLOADS_DIR / f"{uuid.uuid4().hex}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


# ── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── YouTube URL analysis ─────────────────────────────────────────────────────

@app.post("/api/analyze-url")
async def analyze_url(request: Request):
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Could not extract video ID from URL.")

    meta = fetch_youtube_metadata(video_id)
    if "error" in meta:
        raise HTTPException(status_code=400, detail=meta["error"])

    transcript = fetch_transcript(video_id)

    try:
        content_analysis = analyze_video_content(
            title=meta["title"],
            description=meta["description"],
            tags=meta["tags"],
            transcript=transcript,
            stats={
                "view_count": meta["view_count"],
                "like_count": meta["like_count"],
                "comment_count": meta["comment_count"],
            },
            duration=meta["duration"],
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Competitor comparison
    competitor_videos = fetch_competitor_videos(
        query=" ".join(meta["title"].split()[:5]),
        exclude_id=video_id,
    )
    competitor_analysis = compare_competitors(meta["title"], competitor_videos)

    return {
        "source": "youtube_url",
        "metadata": meta,
        "content_analysis": content_analysis,
        "competitor_analysis": competitor_analysis,
        "competitors": competitor_videos,
    }


# ── Thumbnail upload analysis ────────────────────────────────────────────────

@app.post("/api/analyze-thumbnail")
async def analyze_thumbnail_upload(file: UploadFile = File(...)):
    path = _save_upload(file, ALLOWED_IMAGE)
    try:
        result = analyze_thumbnail(str(path))
    except ValueError as e:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        path.unlink(missing_ok=True)
    return {"source": "thumbnail_upload", "thumbnail_analysis": result}


# ── Video file upload analysis ───────────────────────────────────────────────

@app.post("/api/analyze-video")
async def analyze_video_upload(file: UploadFile = File(...)):
    path = _save_upload(file, ALLOWED_VIDEO)
    try:
        result = analyze_uploaded_video(str(path))
    except ValueError as e:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        path.unlink(missing_ok=True)
    return {"source": "video_upload", "video_analysis": result}


# ── Combined: URL + thumbnail override ──────────────────────────────────────

@app.post("/api/analyze-full")
async def analyze_full(
    url: str = Form(default=""),
    thumbnail: UploadFile = File(default=None),
):
    result = {}

    if url.strip():
        video_id = extract_video_id(url.strip())
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL.")
        meta = fetch_youtube_metadata(video_id)
        if "error" in meta:
            raise HTTPException(status_code=400, detail=meta["error"])
        transcript = fetch_transcript(video_id)
        try:
            content_analysis = analyze_video_content(
                title=meta["title"],
                description=meta["description"],
                tags=meta["tags"],
                transcript=transcript,
                stats={
                    "view_count": meta["view_count"],
                    "like_count": meta["like_count"],
                    "comment_count": meta["comment_count"],
                },
                duration=meta["duration"],
            )
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e))
        competitor_videos = fetch_competitor_videos(
            query=" ".join(meta["title"].split()[:5]),
            exclude_id=video_id,
        )
        competitor_analysis = compare_competitors(meta["title"], competitor_videos)
        result.update({
            "metadata": meta,
            "content_analysis": content_analysis,
            "competitor_analysis": competitor_analysis,
            "competitors": competitor_videos,
        })

    if thumbnail and thumbnail.filename:
        path = _save_upload(thumbnail, ALLOWED_IMAGE)
        try:
            thumb_result = analyze_thumbnail(str(path))
            result["thumbnail_analysis"] = thumb_result
        finally:
            path.unlink(missing_ok=True)

    if not result:
        raise HTTPException(status_code=400, detail="Provide a YouTube URL or upload a file.")

    result["source"] = "full_analysis"
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8004, reload=False)
