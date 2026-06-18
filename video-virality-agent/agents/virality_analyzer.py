import os
import re
import json
import base64
import tempfile
from pathlib import Path
from groq import Groq


TEXT_MODEL = "llama-3.3-70b-versatile"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _client() -> Groq:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY not set in .env")
    return Groq(api_key=key)


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _image_b64(path: str) -> tuple[str, str]:
    suffix = Path(path).suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(suffix, "image/jpeg")
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode(), mime


def analyze_thumbnail(image_path: str) -> dict:
    client = _client()
    b64, mime = _image_b64(image_path)

    prompt = """You are a YouTube thumbnail expert. Analyze this thumbnail and respond with valid JSON only — no markdown, no explanation.

Return exactly this structure:
{
  "score": <0-100 integer>,
  "grade": "<A/B/C/D/F>",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "improvements": ["...", "..."],
  "elements": {
    "has_face": <true/false>,
    "has_text": <true/false>,
    "text_readable": <true/false>,
    "contrast_strong": <true/false>,
    "emotion_visible": <true/false>,
    "brand_consistent": <true/false>
  },
  "ctr_potential": "<Low/Medium/High/Very High>"
}"""

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=800,
    )
    return _parse_json(response.choices[0].message.content)


def analyze_video_content(
    title: str,
    description: str,
    tags: list[str],
    transcript: str,
    stats: dict,
    duration: str,
) -> dict:
    client = _client()

    stats_block = (
        f"Views: {stats.get('view_count', 'N/A')}, "
        f"Likes: {stats.get('like_count', 'N/A')}, "
        f"Comments: {stats.get('comment_count', 'N/A')}"
    )
    transcript_excerpt = transcript[:1500] if transcript else "No transcript available."

    prompt = f"""You are a YouTube virality expert. Analyze this video and return valid JSON only — no markdown.

Title: {title}
Description: {description[:500]}
Tags: {', '.join(tags[:20])}
Duration: {duration}
Stats: {stats_block}
Transcript excerpt: {transcript_excerpt}

Return exactly this structure:
{{
  "virality_score": <0-100 integer>,
  "grade": "<A/B/C/D/F>",
  "breakdown": {{
    "hook_strength": <0-100>,
    "title_power": <0-100>,
    "seo_strength": <0-100>,
    "engagement_signals": <0-100>,
    "content_depth": <0-100>
  }},
  "title_analysis": {{
    "issues": ["..."],
    "alternative_titles": ["...", "...", "..."]
  }},
  "hook_analysis": {{
    "first_line": "...",
    "verdict": "...",
    "rewrite": "..."
  }},
  "seo_recommendations": {{
    "suggested_tags": ["...", "...", "..."],
    "description_tips": ["..."],
    "chapter_suggestion": ["00:00 - Intro", "..."]
  }},
  "optimization_tips": ["...", "...", "...", "...", "..."],
  "viral_potential": "<Low/Medium/High/Very High>",
  "estimated_improvement": "<percentage range if tips applied>"
}}"""

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )
    return _parse_json(response.choices[0].message.content)


def analyze_uploaded_video(video_path: str) -> dict:
    client = _client()

    frame_path = None
    duration_sec = 0
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duration_sec = total / fps if fps else 0

        target = min(int(3 * fps), max(0, total - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ret, frame = cap.read()
        cap.release()

        if ret:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, frame)
            tmp.close()
            frame_path = tmp.name
    except Exception:
        pass

    try:
        if frame_path:
            b64, mime = _image_b64(frame_path)
            prompt = """You are a YouTube video virality expert analyzing a video frame (from the 3-second hook moment).
Assess hook strength, visual quality, on-screen elements, pacing feel, and return valid JSON only.

Return exactly:
{
  "virality_score": <0-100>,
  "grade": "<A/B/C/D/F>",
  "breakdown": {
    "hook_strength": <0-100>,
    "visual_quality": <0-100>,
    "engagement_signals": <0-100>,
    "pacing": <0-100>,
    "content_depth": <0-100>
  },
  "hook_analysis": {"verdict": "...", "rewrite": "..."},
  "optimization_tips": ["...", "...", "...", "...", "..."],
  "viral_potential": "<Low/Medium/High/Very High>",
  "estimated_improvement": "<range if tips applied>"
}"""
            response = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                max_tokens=1000,
            )
        else:
            prompt = f"""A video file was uploaded (duration ~{int(duration_sec)}s). Without visual frames available, provide a general virality framework analysis.
Return valid JSON only matching this structure:
{{
  "virality_score": 50,
  "grade": "C",
  "breakdown": {{"hook_strength": 50, "visual_quality": 50, "engagement_signals": 50, "pacing": 50, "content_depth": 50}},
  "hook_analysis": {{"verdict": "Unable to extract frames for analysis", "rewrite": "Ensure your first 3 seconds have a bold visual hook"}},
  "optimization_tips": ["Add strong visual hook in first 3 seconds", "Use text overlays for key points", "Include face/reaction shots", "Keep pacing tight — cut dead air", "Add background music"],
  "viral_potential": "Medium",
  "estimated_improvement": "20-40% with hook optimization"
}}"""
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
            )

        return _parse_json(response.choices[0].message.content)
    finally:
        if frame_path:
            try:
                os.unlink(frame_path)
            except Exception:
                pass


def compare_competitors(main_title: str, competitors: list[dict]) -> dict:
    if not competitors:
        return {"summary": "No competitor data available.", "insights": []}
    client = _client()

    comp_lines = "\n".join(
        f"{i+1}. \"{c['title']}\" by {c['channel']}"
        for i, c in enumerate(competitors)
    )
    prompt = f"""Compare this video against its competitors and return valid JSON only.

My Video: "{main_title}"

Top Competitor Videos:
{comp_lines}

Return:
{{
  "summary": "...",
  "insights": ["...", "...", "..."],
  "title_edge": "...",
  "gaps_to_exploit": ["...", "..."],
  "positioning_advice": "..."
}}"""

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
    )
    return _parse_json(response.choices[0].message.content)
