import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure paths resolve relative to this file regardless of working directory
BASE_DIR = Path(__file__).parent.resolve()
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agents.youtube_agent import YouTubeAgent
from agents.trends_agent import TrendsAgent

AI_ENABLED = False

app = FastAPI(title="YouTube Research Agent")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ── Request models ──────────────────────────────────────────────────────────

class TrendingRequest(BaseModel):
    region: str = "US"
    max_results: int = 20

class KeywordRequest(BaseModel):
    keyword: str
    max_results: int = 20

class CompetitorRequest(BaseModel):
    channel_name: str

class ContentIdeasRequest(BaseModel):
    niche: str
    region: str = "US"
    competitors: list[str] = []

class GapAnalysisRequest(BaseModel):
    niche: str
    competitors: list[str] = []

class TrendingForChannelRequest(BaseModel):
    channel_name: str
    max_results: int = 20


# ── Pages ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── API endpoints ────────────────────────────────────────────────────────────

@app.post("/api/trending")
async def get_trending(req: TrendingRequest):
    """Fetch trending YouTube videos."""
    try:
        yt = YouTubeAgent()
        videos = yt.get_trending_videos(region_code=req.region, max_results=req.max_results)
        keywords = yt.extract_keywords_from_videos(videos)
        return {"videos": videos, "keywords": keywords}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search_videos(req: KeywordRequest):
    """Search YouTube for a keyword and return top videos."""
    try:
        yt = YouTubeAgent()
        videos = yt.search_videos(req.keyword, max_results=req.max_results)
        keywords = yt.extract_keywords_from_videos(videos)
        return {"videos": videos, "keywords": keywords}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/competitor")
async def analyze_competitor(req: CompetitorRequest):
    """Analyze a competitor YouTube channel (top videos only, AI disabled)."""
    try:
        yt = YouTubeAgent()
        data = yt.get_channel_top_videos(req.channel_name)
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        data["ai_analysis"] = "⚠️ AI analysis is disabled. Add an ANTHROPIC_API_KEY to your .env file to enable competitor strategy analysis."
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trending-for-channel")
async def trending_for_channel(req: TrendingForChannelRequest):
    """Find trending videos in the same niche/category as the given channel."""
    try:
        import re

        yt = YouTubeAgent()

        # Step 1: get full channel profile (description, keywords, topics, top videos)
        channel_data = yt.get_channel_top_videos(req.channel_name, max_results=10)
        if "error" in channel_data:
            raise HTTPException(status_code=404, detail=channel_data["error"])

        channel_id = channel_data["channel_id"]
        description = channel_data.get("description", "")
        ch_keywords = channel_data.get("channel_keywords", [])
        topic_labels = channel_data.get("topic_labels", [])
        common_tags = channel_data.get("common_tags", [])
        top_titles = [v["title"] for v in channel_data.get("top_videos", [])[:5]]
        channel_title = channel_data["channel"]

        # ── Build niche query (generic enough to find OTHER creators' content) ──
        # Words/phrases to NEVER include in search (would pull back own channel)
        channel_name_words = set(re.findall(r'\b\w+\b', channel_title.lower()))

        stop_words = {"this","that","with","from","your","have","will","been","they",
                      "their","also","about","which","when","what","more","than","into",
                      "over","video","part","full","episode","vlog","channel","subscribe",
                      "like","watch","official","new","best","top","hindi","urdu","pakistan",
                      "pakistan","latest","2024","2025","2026","ki","ka","ke","hai","aur"}
        stop_words |= channel_name_words  # exclude channel name words from query

        query_parts = []

        # Priority 1: YouTube topic labels (most reliable generic category signal)
        for label in topic_labels[:3]:
            if label.lower() not in stop_words:
                query_parts.append(label)

        # Priority 2: channel keywords set by creator (skip ones containing channel name)
        for kw in ch_keywords[:6]:
            words_in_kw = set(re.findall(r'\b\w+\b', kw.lower()))
            if not words_in_kw.intersection(channel_name_words):
                if kw.lower() not in stop_words:
                    query_parts.append(kw)

        # Priority 3: meaningful English words from description
        if description:
            desc_words = [w for w in re.findall(r'\b[A-Za-z]{4,}\b', description)
                          if w.lower() not in stop_words]
            freq = {}
            for w in desc_words:
                freq[w.lower()] = freq.get(w.lower(), 0) + 1
            query_parts.extend([w for w, _ in sorted(freq.items(), key=lambda x: -x[1])][:4])

        # Priority 4: English video tags (skip ones that match channel name)
        for tag in common_tags:
            if re.search(r'[A-Za-z]', tag):
                tag_words = set(re.findall(r'\b\w+\b', tag.lower()))
                if not tag_words.intersection(channel_name_words) and tag.lower() not in stop_words:
                    query_parts.append(tag)
                    if len(query_parts) >= 8:
                        break

        # Priority 5: title words excluding channel-specific terms
        for title in top_titles:
            for w in re.findall(r'\b[A-Za-z]{5,}\b', title):
                if w.lower() not in stop_words:
                    query_parts.append(w)

        # Deduplicate preserving order
        seen_q: set[str] = set()
        unique_parts: list[str] = []
        for p in query_parts:
            k = p.lower().strip()
            if k and k not in seen_q:
                seen_q.add(k)
                unique_parts.append(p.strip())

        search_query = " ".join(unique_parts[:4]) if unique_parts else "trending videos"

        # Step 3: search YouTube, EXCLUDING the channel's own videos
        trending_videos = yt.search_videos(
            search_query, max_results=req.max_results,
            exclude_channel_id=channel_id, order="viewCount"
        )

        # Step 4: fallback — try topic label alone if still empty
        if not trending_videos and topic_labels:
            search_query = topic_labels[0]
            trending_videos = yt.search_videos(
                search_query, max_results=req.max_results,
                exclude_channel_id=channel_id, order="viewCount"
            )

        # Step 5: last resort fallback to first keyword
        if not trending_videos and unique_parts:
            search_query = unique_parts[0]
            trending_videos = yt.search_videos(
                search_query, max_results=req.max_results,
                exclude_channel_id=channel_id
            )

        keywords = yt.extract_keywords_from_videos(trending_videos)

        return {
            "channel": channel_data["channel"],
            "niche_query": search_query,
            "description_used": description[:150] if description else "",
            "channel_keywords": ch_keywords,
            "topic_labels": topic_labels,
            "videos": trending_videos,
            "keywords": keywords,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trends")
async def get_google_trends(req: KeywordRequest):
    """Get Google Trends data for a keyword."""
    try:
        trends = TrendsAgent()
        related = trends.get_related_queries(req.keyword)
        trending_searches = trends.get_trending_searches()
        return {
            "keyword": req.keyword,
            "related_queries": related,
            "trending_searches": trending_searches,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/content-ideas")
async def generate_content_ideas(req: ContentIdeasRequest):
    """Return research data only — AI idea generation disabled."""
    try:
        yt = YouTubeAgent()
        trends = TrendsAgent()

        trending_videos = yt.get_trending_videos(region_code=req.region, max_results=20)
        search_videos = yt.search_videos(req.niche, max_results=15)
        all_videos = trending_videos + search_videos
        keywords = yt.extract_keywords_from_videos(all_videos)
        trending_searches = trends.get_trending_searches()

        return {
            "niche": req.niche,
            "ideas": "⚠️ AI idea generation is disabled. Add an ANTHROPIC_API_KEY to your .env file to generate 20 content ideas.\n\nHowever, here is your research data:\n\n📌 TOP KEYWORDS:\n" + "\n".join(f"• {k}" for k in keywords[:20]) + "\n\n🔥 TRENDING SEARCHES:\n" + "\n".join(f"• {s}" for s in trending_searches[:15]),
            "keywords_analyzed": keywords[:20],
            "trending_searches": trending_searches[:10],
            "tokens_used": 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gap-analysis")
async def gap_analysis(req: GapAnalysisRequest):
    """Return trending searches only — AI gap analysis disabled."""
    try:
        trends = TrendsAgent()
        trending_searches = trends.get_trending_searches()
        return {
            "niche": req.niche,
            "gaps": "⚠️ AI gap analysis is disabled. Add an ANTHROPIC_API_KEY to your .env file to enable this feature.\n\n🔥 TRENDING SEARCHES RIGHT NOW:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(trending_searches[:20])),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
