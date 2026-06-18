import os
import re
import json
import base64
import tempfile
from pathlib import Path
from groq import Groq


TEXT_MODEL = "llama-3.1-8b-instant"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

SYSTEM_BRUTAL = """You are Alex Chen, a no-bullshit YouTube growth strategist with 10 years auditing viral content for major brands. You have reviewed 50,000+ videos and you have seen every mistake creators make.

YOUR RULES — NEVER BREAK THEM:
1. You do NOT encourage bad work. Praise is only given when genuinely earned.
2. You diagnose EXACTLY why content fails — specific, named reasons, not vague advice.
3. You speak to the creator as if their career depends on fixing these issues RIGHT NOW.
4. You never say things like "good start", "potential", "with some tweaks". Either it works or it doesn't.
5. Your feedback must be specific enough that a content team can act on it TODAY — rewrite the title, change the hook script, reshoot the opening.
6. You compare against top-performing videos in the niche, not against the creator's own past work.
7. A video that failed on YouTube (low views, low engagement) is a FAILED video. Score it as such.

Your scoring must reflect TRUTH, not kindness."""

SYSTEM_VISION = """You are Alex Chen, a YouTube thumbnail and video hook specialist. You have split-tested 10,000+ thumbnails and you know exactly what gets clicks and what gets scrolled past.

YOUR RULES:
1. Look at every pixel critically — lighting, composition, emotion, text readability, contrast.
2. Compare this thumbnail/frame against what MrBeast, MKBHD, and top creators in the same niche produce.
3. Be specific: "the text is too small and placed over a busy background making it unreadable on mobile" beats "improve text placement".
4. If it's bad, say it's bad. Don't soften it.
5. Score it as a real viewer would judge it in 0.3 seconds while scrolling YouTube."""


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

    prompt = """Audit this YouTube thumbnail. A real viewer has 0.3 seconds to notice it while scrolling. Tell me if this thumbnail survives that test.

HARD SCORING RULES — DO NOT DEVIATE:
- No human face: maximum score 55 (faces drive clicks, no exceptions)
- Text present but unreadable on a phone screen: deduct 20 points immediately
- Dark, muddy, or low-contrast image: maximum score 45
- Generic/stock-photo feel with no personality: maximum score 40, grade D or F
- No clear focal point or emotion: maximum score 50
- Cluttered with too many elements competing: deduct 15 points
- If this thumbnail looks like it was made in 10 minutes with no strategy: say so directly
- Grade: A=85+, B=70-84, C=50-69, D=35-49, F=below 35

Be specific. Name exact visual elements. Tell them what a top YouTuber in this niche does differently.

Return valid JSON only — no markdown, no explanation outside JSON:
{
  "score": <0-100 integer, follow scoring rules strictly>,
  "grade": "<A/B/C/D/F>",
  "ctr_verdict": "<one direct sentence: will this get clicked or scrolled past, and why exactly>",
  "what_viewer_sees_in_03_seconds": "<exactly what registers in a viewer's brain at first glance>",
  "strengths": ["<only list genuine strengths, skip if none>"],
  "weaknesses": [
    "<specific weakness 1 — name the exact element and why it fails>",
    "<specific weakness 2>",
    "<specific weakness 3>"
  ],
  "improvements": [
    "<exact change to make — be specific about colors, fonts, layout, face position>",
    "<exact change 2>",
    "<exact change 3>"
  ],
  "competitor_comparison": "<how does this compare to top thumbnails in this niche? what are they doing that this thumbnail is missing?>",
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
        messages=[
            {"role": "system", "content": SYSTEM_VISION},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            },
        ],
        max_tokens=1000,
        temperature=0.3,
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

    view_count = stats.get('view_count', 0)
    like_count = stats.get('like_count', 0)
    comment_count = stats.get('comment_count', 0)
    like_ratio = round((like_count / view_count * 100), 2) if view_count > 0 else 0
    comment_ratio = round((comment_count / view_count * 100), 2) if view_count > 0 else 0
    transcript_excerpt = transcript[:2000] if transcript else "NO TRANSCRIPT — creator did not speak clearly or video is silent."

    # Determine score ceiling based on real performance
    if view_count < 500:
        score_ceiling = 20
        performance_tier = "DEAD ON ARRIVAL — under 500 views is a complete failure"
    elif view_count < 1000:
        score_ceiling = 28
        performance_tier = "FAILED — under 1,000 views means the algorithm rejected this content"
    elif view_count < 5000:
        score_ceiling = 38
        performance_tier = "POOR — under 5k views means very limited reach"
    elif view_count < 10000:
        score_ceiling = 48
        performance_tier = "BELOW AVERAGE — 5k-10k views is not viral by any standard"
    elif view_count < 50000:
        score_ceiling = 62
        performance_tier = "MEDIOCRE — reached some people but far from viral"
    elif view_count < 100000:
        score_ceiling = 72
        performance_tier = "DECENT — approaching 100k but still not breaking out"
    elif view_count < 500000:
        score_ceiling = 83
        performance_tier = "GOOD — solid performance but not viral"
    elif view_count < 1000000:
        score_ceiling = 91
        performance_tier = "STRONG — approaching 1M, real traction"
    else:
        score_ceiling = 100
        performance_tier = "VIRAL — 1M+ views, algorithm loved this"

    # Additional penalties
    like_penalty = 15 if like_ratio < 1 else (10 if like_ratio < 2 else (5 if like_ratio < 3 else 0))
    comment_penalty = 10 if comment_ratio < 0.05 else (5 if comment_ratio < 0.1 else 0)

    prompt = f"""You are auditing this YouTube video for a content team. Their goal is to go viral. Give them the truth they need to improve, not comfort.

═══════════════════════════════════════
REAL PERFORMANCE DATA (this is what happened):
═══════════════════════════════════════
Title: {title}
Views: {view_count:,}
Performance Tier: {performance_tier}
Like ratio: {like_ratio}% — Industry average for viral content is 4-8%. Below 2% means viewers did not connect.
Comment ratio: {comment_ratio}% — Below 0.1% means zero conversation was sparked.
Duration: {duration}
Tags used: {', '.join(tags[:15]) if tags else 'NONE — major SEO failure'}
Description (first 500 chars): {description[:500] if description else 'EMPTY — no SEO effort at all'}
Transcript (first 2000 chars): {transcript_excerpt}

═══════════════════════════════════════
MANDATORY SCORING CONSTRAINTS:
═══════════════════════════════════════
- virality_score HARD CEILING: {score_ceiling}/100 (based on actual view count)
- Additional deductions already calculated: -{like_penalty} for like ratio, -{comment_penalty} for comment ratio
- Final score cannot exceed {max(5, score_ceiling - like_penalty - comment_penalty)}
- DO NOT give a score higher than {max(5, score_ceiling - like_penalty - comment_penalty)}
- Grade MUST match: A=85+, B=70-84, C=50-69, D=35-49, F=below 35

═══════════════════════════════════════
YOUR AUDIT TASKS:
═══════════════════════════════════════
1. TITLE: Is it specific, curiosity-driven, emotionally charged? Or is it generic and forgettable?
   Compare it to top titles in this niche. Name exactly what words or structure make it weak.

2. HOOK (first 30 seconds): Based on the transcript, what does the viewer hear first?
   Does it start with a strong promise, a shocking statement, or a relatable problem?
   Or does it start with "Hey guys welcome back"? (That kills retention instantly.)

3. SEO: Are the tags relevant, specific, and keyword-targeted? Is the description optimized?

4. ENGAGEMENT: Given the like/comment ratio, did this content create any emotional reaction?

5. VERDICT: What is the single biggest reason this video did not perform?

Return valid JSON only — no markdown:
{{
  "virality_score": <integer, MUST NOT exceed {max(5, score_ceiling - like_penalty - comment_penalty)}>,
  "grade": "<A/B/C/D/F matching the score strictly>",
  "performance_verdict": "<one brutal sentence naming the SINGLE biggest reason this video succeeded or failed — be specific>",
  "biggest_mistake": "<the #1 thing that killed this video's performance — be direct>",
  "breakdown": {{
    "hook_strength": <0-100, heavily penalize if transcript starts with generic welcome>,
    "title_power": <0-100, penalize if title is vague, lacks numbers/emotion/curiosity gap>,
    "seo_strength": <0-100, penalize if no tags or empty description>,
    "engagement_signals": <0-100, anchor to actual like/comment ratios>,
    "content_depth": <0-100, based on transcript quality and topic coverage>
  }},
  "title_analysis": {{
    "verdict": "<is the title strong or weak? exactly why?>",
    "issues": [
      "<specific issue — e.g. 'Title has no numbers, no curiosity gap, and no emotional trigger'>",
      "<specific issue 2>",
      "<specific issue 3>"
    ],
    "alternative_titles": [
      "<rewritten title 1 — more specific, curiosity-driven, with power words>",
      "<rewritten title 2 — different angle>",
      "<rewritten title 3 — numbers/data driven>"
    ]
  }},
  "hook_analysis": {{
    "what_creator_actually_said": "<exact quote or summary of first 30 seconds from transcript>",
    "verdict": "<harsh verdict: did the hook earn the viewer's next 30 seconds or not?>",
    "why_viewers_left": "<specific reason retention dropped — based on what you see in transcript>",
    "rewritten_hook": "<exact script rewrite for first 30 seconds — word for word what they should say>"
  }},
  "seo_analysis": {{
    "tag_verdict": "<are these tags killing or helping reach?>",
    "suggested_tags": ["<high-volume specific tag>", "<long-tail tag>", "<niche tag>", "<trending tag>", "<competitor tag>"],
    "description_verdict": "<is the description SEO-optimized or wasted space?>",
    "description_first_line": "<rewritten first line of description — keyword rich, 150 chars>",
    "chapter_suggestion": ["00:00 - Hook", "01:30 - ...", "..."]
  }},
  "optimization_tips": [
    "<tip 1 — specific and actionable, not generic>",
    "<tip 2>",
    "<tip 3>",
    "<tip 4>",
    "<tip 5>"
  ],
  "viral_potential": "<Low/Medium/High/Very High — honest assessment of this niche and content format>",
  "if_reshot_today": "<if they reshoot this video with all fixes applied, what realistic view count could they hit and why>"
}}"""

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_BRUTAL},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2000,
        temperature=0.2,
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
            prompt = f"""This is the frame at the 3-second mark of a YouTube video — the exact moment the algorithm decides if a viewer stays or clicks away. Average viewer retention drop happens in the first 5 seconds. This frame must EARN the viewer's attention.

Video duration: ~{int(duration_sec)} seconds

Judge this frame the way a cold viewer would — someone who never heard of this creator, seeing this recommended on their feed.

HARD SCORING RULES:
- Static talking head, no graphics, no text overlay, no movement: hook_strength max 25
- Poor/flat lighting that makes the subject look unprofessional: visual_quality max 40
- No visible emotion or energy on subject's face: engagement_signals max 30
- Background is messy, distracting, or looks like a bedroom with no setup: penalize 15 points
- No text overlay showing what the video is about: hook_strength max 35
- Looks like it was filmed on a phone with no production thought: visual_quality max 45
- Grade: A=85+, B=70-84, C=50-69, D=35-49, F=below 35

Compare to how top creators in any niche open their videos. Be specific.

Return valid JSON only:
{{
  "virality_score": <0-100, follow rules strictly>,
  "grade": "<A/B/C/D/F>",
  "first_impression": "<what does a cold viewer think in 0.3 seconds seeing this frame?>",
  "breakdown": {{
    "hook_strength": <0-100>,
    "visual_quality": <0-100>,
    "engagement_signals": <0-100>,
    "pacing": <0-100>,
    "content_depth": <0-100>
  }},
  "hook_analysis": {{
    "verdict": "<exactly what works or fails at the 3-second mark and why>",
    "what_top_creators_do_instead": "<specific example of how a top YouTuber would open this same video>",
    "rewritten_opening": "<exact description of what should happen in first 15 seconds: visuals, audio, text overlays, energy>"
  }},
  "production_issues": ["<specific production problem>", "<another>"],
  "optimization_tips": [
    "<specific fix 1 — actionable today>",
    "<specific fix 2>",
    "<specific fix 3>",
    "<specific fix 4>",
    "<specific fix 5>"
  ],
  "viral_potential": "<Low/Medium/High/Very High>",
  "estimated_improvement": "<realistic view count change if opening is reworked>"
}}"""
            response = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_VISION},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                            {"type": "text", "text": prompt},
                        ],
                    },
                ],
                max_tokens=1200,
                temperature=0.2,
            )
        else:
            prompt = f"""A video was uploaded but no frame could be extracted (duration ~{int(duration_sec)}s). Give a general framework audit.
Return valid JSON:
{{
  "virality_score": 25,
  "grade": "D",
  "first_impression": "Frame extraction failed — cannot assess visual hook",
  "breakdown": {{"hook_strength": 25, "visual_quality": 25, "engagement_signals": 25, "pacing": 25, "content_depth": 25}},
  "hook_analysis": {{
    "verdict": "Cannot assess without visual — but statistically 70% of low-performing videos fail in the first 5 seconds",
    "what_top_creators_do_instead": "Strong visual hook with text overlay, high energy, immediate value statement in first 3 seconds",
    "rewritten_opening": "Open with the most shocking/surprising moment of the video. Show result first, explain later. Add text overlay with the core promise."
  }},
  "production_issues": ["Frame extraction failed — check video encoding", "Ensure video is not corrupted"],
  "optimization_tips": [
    "Start with your most compelling moment — not an intro",
    "Add bold text overlay in first 3 seconds stating exactly what viewer will learn/see",
    "Show your face with high emotion in the opening frame",
    "Cut all 'hey guys welcome back' type intros — they kill retention",
    "Match your thumbnail exactly to your opening frame for continuity"
  ],
  "viral_potential": "Unknown — visual analysis failed",
  "estimated_improvement": "Fixing the hook alone typically improves average view duration by 40-60%"
}}"""
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_BRUTAL},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
                temperature=0.2,
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

    prompt = f"""You are doing a competitor title analysis. Your job is to tell the creator exactly how their title stacks up in a real YouTube search results page where all these videos appear side by side.

A viewer sees all these titles at once. They will click the one that creates the most curiosity, promises the most value, or triggers the strongest emotion.

MY VIDEO TITLE: "{main_title}"

COMPETING TITLES IN THIS NICHE:
{comp_lines}

ANALYZE:
1. If a viewer sees all these titles at once, which do they click FIRST and why?
2. Does my title use stronger or weaker psychological triggers than competitors?
3. What specific words, structures, or angles are working in competitor titles that mine lacks?
4. What unique angle do competitors NOT cover that I could own?
5. Is my title generic, derivative, or does it stand out?

Be direct. If my title loses to competitors, say it loses and exactly why.

Return valid JSON only:
{{
  "head_to_head_verdict": "<does my title win or lose against these competitors, and specifically why>",
  "rank_in_feed": "<if all these titles appeared side by side, where would mine rank by click likelihood — be honest>",
  "summary": "<2-sentence honest assessment of competitive position>",
  "insights": [
    "<specific insight about what competitors do better psychologically>",
    "<specific insight about keyword/SEO advantage competitors have>",
    "<specific insight about angle or format that is working for competitors>"
  ],
  "title_edge": "<does my title have any genuine advantage? if none, say none>",
  "what_competitors_do_better": ["<specific tactic competitor uses>", "<another>"],
  "gaps_to_exploit": [
    "<specific angle no competitor covers that could dominate this niche>",
    "<another gap>"
  ],
  "positioning_advice": "<exact strategy to reposition this content to beat the top competitor — include a specific rewritten title that would win>"
}}"""

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_BRUTAL},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1000,
        temperature=0.2,
    )
    return _parse_json(response.choices[0].message.content)
