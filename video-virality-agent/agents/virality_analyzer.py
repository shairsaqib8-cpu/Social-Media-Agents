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

    prompt = """You are a brutal YouTube thumbnail critic hired to tell creators the truth. Your job is to identify exactly why a thumbnail will or will not get clicks in a crowded feed. Be specific — name colors, text placement, facial expressions, contrast issues. Do NOT be encouraging if the thumbnail is bad.

SCORING RULES:
- Score based on real CTR potential in a competitive YouTube feed
- A thumbnail without a face scores max 60 unless it has exceptional visual hook
- Unreadable or no text on thumbnail: penalize title_power hard
- Low contrast or dark/muddy image: penalize heavily
- Generic or stock-looking image: F grade territory
- Grade: A=85+, B=70-84, C=50-69, D=35-49, F=below 35

Respond with valid JSON only — no markdown:
{
  "score": <0-100 integer>,
  "grade": "<A/B/C/D/F>",
  "ctr_verdict": "<one honest sentence on whether this thumbnail will get clicked in a real feed>",
  "strengths": ["<specific strength with detail>"],
  "weaknesses": ["<specific weakness with exact detail — color, placement, text, etc>"],
  "improvements": ["<exact actionable fix>", "<another fix>", "<another fix>"],
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

    view_count = stats.get('view_count', 0)
    like_count = stats.get('like_count', 0)
    comment_count = stats.get('comment_count', 0)
    like_ratio = round((like_count / view_count * 100), 2) if view_count > 0 else 0
    comment_ratio = round((comment_count / view_count * 100), 2) if view_count > 0 else 0

    prompt = f"""You are a brutally honest YouTube performance analyst hired by a content team to audit their videos. Your job is NOT to encourage — it is to diagnose WHY a video failed or succeeded and give actionable fixes. Do not sugarcoat. Be specific, harsh where warranted, and data-driven.

SCORING RULES (follow strictly):
- The virality_score MUST be anchored to REAL performance data first:
  * Under 1,000 views: score cannot exceed 35 regardless of content quality
  * 1,000–10,000 views: score range 25–55
  * 10,000–100,000 views: score range 45–75
  * 100,000–1M views: score range 65–90
  * 1M+ views: score range 80–100
- A like ratio below 2% is a failure signal — penalize heavily
- A comment ratio below 0.1% means the content did not spark conversation — penalize
- If transcript is weak/missing, penalize hook_strength and content_depth hard
- Grade MUST match score: A=85+, B=70-84, C=50-69, D=35-49, F=below 35

VIDEO DATA:
Title: {title}
Description: {description[:500]}
Tags: {', '.join(tags[:20]) if tags else 'None'}
Duration: {duration}
Views: {view_count:,}
Likes: {like_count:,} ({like_ratio}% like ratio)
Comments: {comment_count:,} ({comment_ratio}% comment ratio)
Transcript excerpt: {transcript_excerpt}

Be direct. If the title is weak, say exactly why. If the hook fails, explain what a viewer sees in the first 5 seconds and why they click away. Name the specific problems, not generic advice.

Return valid JSON only — no markdown:
{{
  "virality_score": <0-100 integer, strictly anchored to performance data above>,
  "grade": "<A/B/C/D/F>",
  "performance_verdict": "<one brutal honest sentence on why this video performed the way it did>",
  "breakdown": {{
    "hook_strength": <0-100>,
    "title_power": <0-100>,
    "seo_strength": <0-100>,
    "engagement_signals": <0-100>,
    "content_depth": <0-100>
  }},
  "title_analysis": {{
    "issues": ["<specific issue 1>", "<specific issue 2>"],
    "alternative_titles": ["<better title 1>", "<better title 2>", "<better title 3>"]
  }},
  "hook_analysis": {{
    "first_line": "<what happens in first 5 seconds based on transcript>",
    "verdict": "<harsh honest verdict>",
    "rewrite": "<exact rewritten hook script, first 15 seconds>"
  }},
  "seo_recommendations": {{
    "suggested_tags": ["...", "...", "..."],
    "description_tips": ["<specific tip>"],
    "chapter_suggestion": ["00:00 - Intro", "..."]
  }},
  "optimization_tips": ["<specific fix 1>", "<specific fix 2>", "<specific fix 3>", "<specific fix 4>", "<specific fix 5>"],
  "viral_potential": "<Low/Medium/High/Very High — based on niche competition and content quality>",
  "estimated_improvement": "<realistic range if ALL tips applied>"
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
            prompt = """You are a brutal YouTube video analyst reviewing a frame captured at the 3-second mark — the most critical moment that determines if a viewer stays or leaves. Be honest and specific. If this frame looks boring, amateurish, or fails to create curiosity, say so directly.

SCORING RULES:
- If the frame has no clear subject/face/action visible: hook_strength max 30
- Static, talking-head with no graphics/text overlay: penalize pacing hard
- Poor lighting, shaky cam, or low resolution: penalize visual_quality severely
- No visible emotion or energy: engagement_signals should be low
- Grade: A=85+, B=70-84, C=50-69, D=35-49, F=below 35

Return valid JSON only:
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
  "hook_analysis": {
    "verdict": "<specific honest verdict on what a viewer sees at 3 seconds and why they stay or leave>",
    "rewrite": "<exactly what should happen in first 15 seconds to maximize retention>"
  },
  "optimization_tips": ["<specific fix>", "<specific fix>", "<specific fix>", "<specific fix>", "<specific fix>"],
  "viral_potential": "<Low/Medium/High/Very High>",
  "estimated_improvement": "<realistic range if tips applied>"
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
    prompt = f"""You are a competitive intelligence analyst. Compare this video's title against top-performing competitor videos in the same niche. Be brutally honest about where this video loses to competitors — in title psychology, keyword targeting, or positioning. Do not be diplomatic.

My Video: "{main_title}"

Top Competing Videos (ranked by views):
{comp_lines}

Identify specifically:
- What the competitors do in their titles that this video does not
- Whether this video's title is weaker, generic, or fails to compete
- What angle or gap exists that competitors have NOT covered

Return valid JSON only:
{{
  "summary": "<honest 2-sentence verdict on how this video competes>",
  "insights": ["<specific insight 1>", "<specific insight 2>", "<specific insight 3>"],
  "title_edge": "<does this title beat competitors or lose? why specifically?>",
  "gaps_to_exploit": ["<real gap competitors missed>", "<another real gap>"],
  "positioning_advice": "<exact repositioning strategy to beat the top competitor>"
}}"""

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
    )
    return _parse_json(response.choices[0].message.content)
