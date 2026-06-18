import os
import base64
import math
import re
from pathlib import Path
import anthropic


def _claude_client() -> anthropic.Anthropic:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")
    return anthropic.Anthropic(api_key=key)


def _image_to_b64(path: str) -> tuple[str, str]:
    suffix = Path(path).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif"}.get(suffix.lstrip("."), "image/jpeg")
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode(), mime


def analyze_thumbnail(image_path: str) -> dict:
    client = _claude_client()
    b64, mime = _image_to_b64(image_path)

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

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    import json
    text = msg.content[0].text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def analyze_video_content(
    title: str,
    description: str,
    tags: list[str],
    transcript: str,
    stats: dict,
    duration: str,
) -> dict:
    client = _claude_client()

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

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    import json
    text = msg.content[0].text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def analyze_uploaded_video(video_path: str) -> dict:
    """Extract frames and analyze a locally uploaded video file."""
    client = _claude_client()

    # Try to extract a frame using cv2; fall back to text-only analysis
    frame_b64 = None
    frame_mime = "image/jpeg"
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duration_sec = total / fps if fps else 0

        # Grab frame at 3-second mark (hook frame)
        target = min(int(3 * fps), max(0, total - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ret, frame = cap.read()
        cap.release()

        if ret:
            import cv2
            import tempfile, os as _os
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, frame)
            tmp.close()
            with open(tmp.name, "rb") as f:
                frame_b64 = base64.standard_b64encode(f.read()).decode()
            _os.unlink(tmp.name)
    except Exception:
        duration_sec = 0

    import json

    if frame_b64:
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
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": frame_mime, "data": frame_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
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
  "estimated_improvement": "20–40% with hook optimization"
}}"""
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

    text = msg.content[0].text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def compare_competitors(main_title: str, competitors: list[dict]) -> dict:
    if not competitors:
        return {"summary": "No competitor data available.", "insights": []}
    client = _claude_client()

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

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    import json
    text = msg.content[0].text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text)
