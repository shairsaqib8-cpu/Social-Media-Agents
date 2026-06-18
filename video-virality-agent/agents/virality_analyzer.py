import os
import re
import json
import base64
import tempfile
import math
from pathlib import Path
from groq import Groq


TEXT_MODEL = "llama-3.1-8b-instant"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

SYSTEM_BRUTAL = """You are Alex Chen, a ruthless YouTube performance auditor. You have killed more creator careers with honest feedback than built them — and that is why brands pay you. You have zero tolerance for mediocrity.

NON-NEGOTIABLE RULES:
1. Never soften feedback. If it is bad, say it is bad, say exactly why, and tell them what to do instead.
2. Every piece of feedback must be SPECIFIC — name the exact second, the exact word, the exact visual failure.
3. Do not say "consider", "might", "could". Say "change this", "cut this", "redo this".
4. Do not list strengths unless they genuinely exist and are worth mentioning.
5. Your output will be shared with a production team who needs to act on it immediately.
6. The score you receive is already computed from real data. Do not override it. Write your analysis to MATCH and EXPLAIN that score — not to justify a higher one."""

SYSTEM_VISION = """You are Alex Chen, YouTube thumbnail and hook frame specialist. You have split-tested 10,000+ thumbnails and know exactly what gets 8%+ CTR vs what dies at 1%.

RULES:
1. Judge every frame as a cold viewer scrolling at speed — you have 0.3 seconds.
2. Compare to MrBeast, MKBHD, top creators in this niche. Name the gap.
3. Be pixel-level specific: "the subject's face is underexposed, emotion is unreadable on mobile" not "improve lighting".
4. The score is pre-computed. Write your analysis to explain and match it."""


# ─── Hard score computation (Python, not AI) ─────────────────────────────────

def _compute_content_score(view_count: int, like_ratio: float, comment_ratio: float,
                            has_transcript: bool, tag_count: int, has_description: bool) -> int:
    """Compute a hard virality score anchored entirely to real data."""
    # Base from views
    if view_count < 500:
        base = 5
    elif view_count < 1000:
        base = 12
    elif view_count < 3000:
        base = 18
    elif view_count < 5000:
        base = 24
    elif view_count < 10000:
        base = 32
    elif view_count < 25000:
        base = 40
    elif view_count < 50000:
        base = 50
    elif view_count < 100000:
        base = 60
    elif view_count < 250000:
        base = 70
    elif view_count < 500000:
        base = 78
    elif view_count < 1000000:
        base = 85
    else:
        base = 92

    # Like ratio adjustments (industry average viral = 5-8%)
    if like_ratio == 0:
        base -= 12
    elif like_ratio < 1:
        base -= 10
    elif like_ratio < 2:
        base -= 7
    elif like_ratio < 3:
        base -= 3
    elif like_ratio >= 5:
        base += 3

    # Comment ratio adjustments
    if comment_ratio == 0:
        base -= 8
    elif comment_ratio < 0.05:
        base -= 6
    elif comment_ratio < 0.1:
        base -= 3
    elif comment_ratio >= 0.5:
        base += 2

    # SEO penalties
    if tag_count == 0:
        base -= 5
    if not has_description:
        base -= 4
    if not has_transcript:
        base -= 3

    score = max(3, min(100, base))

    # Grade
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 50:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    return score, grade


def _compute_frame_score(frame_data: dict) -> tuple[int, str]:
    """Enforce hard caps on vision analysis scores based on what AI found."""
    has_face = frame_data.get("has_face", False)
    has_text_overlay = frame_data.get("has_text_overlay", False)
    good_lighting = frame_data.get("good_lighting", False)
    high_energy = frame_data.get("high_energy", False)
    professional_setup = frame_data.get("professional_setup", False)
    visible_emotion = frame_data.get("visible_emotion", False)

    score = 55  # Start from average
    if not has_face:
        score -= 15
    if not has_text_overlay:
        score -= 10
    if not good_lighting:
        score -= 12
    if not high_energy:
        score -= 10
    if not professional_setup:
        score -= 8
    if not visible_emotion:
        score -= 8
    if has_face and good_lighting and high_energy and visible_emotion:
        score += 15  # Only reward if truly earns it

    score = max(5, min(95, score))
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D" if score >= 35 else "F"
    return score, grade


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


def _transcribe_audio(video_path: str, client: Groq) -> str:
    """Extract and transcribe audio from video using Groq Whisper."""
    try:
        import subprocess
        tmp_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_audio.close()
        result = subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1",
             "-b:a", "64k", tmp_audio.name, "-y", "-loglevel", "quiet"],
            timeout=60, capture_output=True
        )
        if result.returncode != 0:
            return ""
        with open(tmp_audio.name, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(Path(tmp_audio.name).name, f.read()),
                model="whisper-large-v3-turbo",
                response_format="text",
            )
        os.unlink(tmp_audio.name)
        return str(transcription)[:3000]
    except Exception:
        return ""


def _analyze_audio_quality(transcript: str, duration_sec: float) -> dict:
    """Derive audio quality signals from transcript content."""
    if not transcript:
        return {"wpm": 0, "filler_count": 0, "filler_ratio": 0, "has_hook_in_first_30": False, "starts_with_generic": True}

    words = transcript.split()
    word_count = len(words)
    wpm = round((word_count / duration_sec) * 60) if duration_sec > 0 else 0

    filler_words = ["um", "uh", "like", "you know", "basically", "literally", "right", "so", "anyway"]
    filler_count = sum(transcript.lower().count(f) for f in filler_words)
    filler_ratio = round(filler_count / max(word_count, 1) * 100, 1)

    generic_openers = ["hey guys", "hey everyone", "welcome back", "what's up guys", "hello everyone",
                       "hey what's up", "so today", "in this video", "hi guys", "hi everyone"]
    first_50 = transcript[:200].lower()
    starts_with_generic = any(opener in first_50 for opener in generic_openers)

    hook_triggers = ["secret", "never", "mistake", "shocking", "truth", "nobody tells you",
                     "i tried", "i tested", "what if", "why", "how i", "changed my", "worst", "best"]
    first_30_words = " ".join(words[:40]).lower()
    has_hook_in_first_30 = any(t in first_30_words for t in hook_triggers)

    return {
        "wpm": wpm,
        "filler_count": filler_count,
        "filler_ratio": filler_ratio,
        "has_hook_in_first_30": has_hook_in_first_30,
        "starts_with_generic": starts_with_generic,
        "word_count": word_count,
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def analyze_thumbnail(image_path: str) -> dict:
    client = _client()
    b64, mime = _image_b64(image_path)

    # Step 1: Get factual data from vision model
    fact_prompt = """Look at this YouTube thumbnail. Answer ONLY with valid JSON, no markdown:
{
  "has_face": <true/false>,
  "face_shows_strong_emotion": <true/false>,
  "has_text": <true/false>,
  "text_is_readable_on_mobile": <true/false>,
  "contrast_is_strong": <true/false>,
  "image_is_bright_and_clear": <true/false>,
  "has_clear_focal_point": <true/false>,
  "looks_professional": <true/false>,
  "background_is_clean": <true/false>,
  "would_stop_scroll": <true/false>
}"""

    fact_resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            {"type": "text", "text": fact_prompt},
        ]}],
        max_tokens=300, temperature=0.1,
    )
    try:
        facts = _parse_json(fact_resp.choices[0].message.content)
    except Exception:
        facts = {}

    # Step 2: Compute score from facts (not from AI opinion)
    score = 40
    if facts.get("has_face"): score += 10
    if facts.get("face_shows_strong_emotion"): score += 8
    if facts.get("has_text"): score += 5
    if facts.get("text_is_readable_on_mobile"): score += 7
    if facts.get("contrast_is_strong"): score += 5
    if facts.get("image_is_bright_and_clear"): score += 5
    if facts.get("has_clear_focal_point"): score += 5
    if facts.get("looks_professional"): score += 8
    if facts.get("background_is_clean"): score += 5
    if facts.get("would_stop_scroll"): score += 7

    # Hard penalties
    if not facts.get("has_face"): score -= 12
    if not facts.get("contrast_is_strong"): score -= 10
    if not facts.get("text_is_readable_on_mobile") and facts.get("has_text"): score -= 12
    if not facts.get("looks_professional"): score -= 10

    score = max(5, min(95, score))
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D" if score >= 35 else "F"

    # Step 3: Get specific written critique
    critique_prompt = f"""This YouTube thumbnail scored {score}/100 ({grade}) based on objective analysis.

Detected facts: {json.dumps(facts, indent=2)}

Now write the brutal, specific critique. Be precise — name exact visual elements, colors, placement, what a competitor thumbnail would do differently.

Return valid JSON only:
{{
  "score": {score},
  "grade": "{grade}",
  "ctr_verdict": "<one direct sentence: will this thumbnail get clicked in a competitive YouTube feed and why>",
  "what_viewer_sees_in_03_seconds": "<exactly what registers in a viewer brain at first glance — be visual and specific>",
  "strengths": ["<only list genuine strengths, max 2, skip entirely if none>"],
  "weaknesses": [
    "<specific failure 1 — name the exact element>",
    "<specific failure 2>",
    "<specific failure 3>"
  ],
  "improvements": [
    "<exact change: colors, layout, font size, expression — actionable today>",
    "<exact change 2>",
    "<exact change 3>"
  ],
  "audio_visual_alignment": "N/A — thumbnail only",
  "ctr_potential": "<Low/Medium/High/Very High>",
  "elements": {json.dumps(facts)}
}}"""

    critique_resp = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_BRUTAL},
            {"role": "user", "content": critique_prompt},
        ],
        max_tokens=900, temperature=0.2,
    )
    result = _parse_json(critique_resp.choices[0].message.content)
    # Always enforce computed score
    result["score"] = score
    result["grade"] = grade
    return result


def _client() -> Groq:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY not set in .env")
    return Groq(api_key=key)


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
    has_transcript = bool(transcript and len(transcript) > 50)
    has_description = bool(description and len(description) > 30)
    tag_count = len(tags) if tags else 0

    # Compute score in Python — AI cannot override this
    score, grade = _compute_content_score(
        view_count, like_ratio, comment_ratio,
        has_transcript, tag_count, has_description
    )

    audio = _analyze_audio_quality(transcript or "", 0)
    transcript_excerpt = (transcript or "NO TRANSCRIPT AVAILABLE")[:2000]

    # Additional audio penalties applied to score
    if audio["starts_with_generic"]:
        score = max(3, score - 6)
    if audio["filler_ratio"] > 10:
        score = max(3, score - 5)
    if not audio["has_hook_in_first_30"] and has_transcript:
        score = max(3, score - 4)

    # Recompute grade after audio penalties
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D" if score >= 35 else "F"

    prompt = f"""You are auditing a YouTube video. The score has already been computed from real data: {score}/100 ({grade}).
Your job is to EXPLAIN why this score is correct with specific, brutal analysis. Do NOT suggest a different score.

═══════════ REAL PERFORMANCE DATA ═══════════
Title: {title}
Views: {view_count:,}
Like ratio: {like_ratio}% (viral average: 5-8% — below 2% means audience rejected content)
Comment ratio: {comment_ratio}% (below 0.1% = zero conversation sparked)
Tags: {tag_count} tags — {', '.join((tags or [])[:10]) or 'NONE'}
Description: {'Present' if has_description else 'MISSING — critical SEO failure'}

═══════════ AUDIO / SCRIPT ANALYSIS ═══════════
Starts with generic opener (kills retention): {audio['starts_with_generic']}
Has hook trigger in first 30 seconds: {audio['has_hook_in_first_30']}
Filler words detected: {audio['filler_count']} ({audio['filler_ratio']}% of words) — above 8% is unprofessional
Words per minute: {audio['wpm']} (ideal: 130-160 wpm for YouTube)
Transcript excerpt:
{transcript_excerpt}

═══════════ YOUR TASK ═══════════
1. Title: Is every word earning its place? Does it create a specific curiosity gap or emotion?
2. Hook (first 30s): Based on transcript, did the creator EARN the viewer's attention immediately or waste it?
3. Audio-Visual alignment: Does the script match what a viewer would expect to see? Is there coherence?
4. SEO: Are the tags and description working or invisible?
5. What is the #1 change that would double performance?

Return valid JSON only — no markdown:
{{
  "virality_score": {score},
  "grade": "{grade}",
  "performance_verdict": "<one brutal sentence — why this video got the views it got, no sugarcoating>",
  "biggest_mistake": "<the single most damaging thing in this video — be specific, not generic>",
  "breakdown": {{
    "hook_strength": <0-100, must be low if starts_with_generic=true or no hook trigger>,
    "title_power": <0-100, penalize if no number/emotion/curiosity gap in title>,
    "seo_strength": <0-100, penalize for missing tags or empty description>,
    "engagement_signals": <0-100, anchor directly to {like_ratio}% like ratio>,
    "content_depth": <0-100, based on transcript quality>
  }},
  "audio_analysis": {{
    "verdict": "<is the audio clear, confident, and professionally paced, or does it sound amateur?>",
    "filler_word_problem": "<are filler words ruining credibility? how many is too many?>",
    "pacing_verdict": "<too fast, too slow, or right? what is the effect on retention?>",
    "audio_visual_sync": "<does the narration match what a viewer would see on screen? is there coherence between what is said and what is shown?>",
    "script_quality": "<is the script tight and purposeful or meandering and unfocused?>"
  }},
  "title_analysis": {{
    "verdict": "<strong or weak? specifically why>",
    "issues": ["<exact issue — e.g. no number, no emotion word, too generic>", "<issue 2>"],
    "alternative_titles": [
      "<rewritten title 1 — specific, curiosity-driven, power words>",
      "<rewritten title 2 — different angle>",
      "<rewritten title 3 — number/data driven>"
    ]
  }},
  "hook_analysis": {{
    "what_creator_actually_said": "<exact quote or close paraphrase of first 30 seconds>",
    "verdict": "<did this hook earn the viewer's next 30 seconds? be harsh>",
    "why_viewers_left": "<specific moment and reason viewers clicked away>",
    "rewritten_hook": "<exact word-for-word replacement script for first 30 seconds>"
  }},
  "seo_analysis": {{
    "tag_verdict": "<are these tags helping or useless?>",
    "suggested_tags": ["<high-volume tag>", "<long-tail tag>", "<niche tag>", "<trending tag>", "<competitor tag>"],
    "description_verdict": "<is the description optimized or wasted?>",
    "description_rewrite": "<rewritten first 150 chars of description — keyword-rich>"
  }},
  "optimization_tips": [
    "<tip 1 — specific, actionable, not generic>",
    "<tip 2>",
    "<tip 3>",
    "<tip 4>",
    "<tip 5>"
  ],
  "viral_potential": "<Low/Medium/High/Very High>",
  "if_reshot_today": "<realistic view count they could hit if ALL fixes are applied, and exactly why>"
}}"""

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_BRUTAL},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2000,
        temperature=0.15,
    )
    result = _parse_json(response.choices[0].message.content)
    # Always enforce Python-computed score — AI cannot override
    result["virality_score"] = score
    result["grade"] = grade
    return result


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

    # Transcribe audio
    transcript = _transcribe_audio(video_path, client)
    audio = _analyze_audio_quality(transcript, duration_sec)

    try:
        if frame_path:
            b64, mime = _image_b64(frame_path)

            # Step 1: Get objective facts from frame
            fact_prompt = """Analyze this YouTube video frame (captured at 3-second mark). Return JSON only:
{
  "has_face": <true/false>,
  "good_lighting": <true/false>,
  "visible_emotion": <true/false>,
  "high_energy": <true/false>,
  "professional_setup": <true/false>,
  "has_text_overlay": <true/false>,
  "background_is_clean": <true/false>,
  "camera_is_stable": <true/false>,
  "subject_fills_frame": <true/false>,
  "would_make_viewer_curious": <true/false>
}"""
            fact_resp = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": fact_prompt},
                ]}],
                max_tokens=250, temperature=0.1,
            )
            try:
                facts = _parse_json(fact_resp.choices[0].message.content)
            except Exception:
                facts = {}

            # Step 2: Compute score from facts
            score, grade = _compute_frame_score(facts)

            # Apply audio penalties
            if audio["starts_with_generic"]:
                score = max(3, score - 8)
            if audio["filler_ratio"] > 10:
                score = max(3, score - 6)
            if not audio["has_hook_in_first_30"]:
                score = max(3, score - 5)
            grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D" if score >= 35 else "F"

            critique_prompt = f"""This video frame (at 3-second hook mark) scored {score}/100 ({grade}).

Frame facts: {json.dumps(facts, indent=2)}

Audio/script facts:
- Starts with generic opener: {audio['starts_with_generic']}
- Has hook trigger in first 30s: {audio['has_hook_in_first_30']}
- Filler word ratio: {audio['filler_ratio']}%
- Words per minute: {audio['wpm']}
- Transcript (first 500 chars): {transcript[:500] if transcript else 'NO AUDIO TRANSCRIBED'}

Write a brutal specific audit. The score is {score}/{grade} — do not change it, explain it.

Return valid JSON only:
{{
  "virality_score": {score},
  "grade": "{grade}",
  "first_impression": "<what does a cold viewer think/feel in 0.3 seconds at this frame — be visual and specific>",
  "breakdown": {{
    "hook_strength": <0-100, heavily penalize if no text overlay or generic opener>,
    "visual_quality": <0-100, based on lighting/setup facts>,
    "engagement_signals": <0-100, based on emotion/energy facts>,
    "pacing": <0-100, based on wpm and transcript quality>,
    "content_depth": <0-100>
  }},
  "audio_analysis": {{
    "verdict": "<is the audio quality professional or amateurish? be specific>",
    "filler_word_problem": "<{audio['filler_count']} filler words — is this killing credibility?>",
    "pacing_verdict": "<{audio['wpm']} wpm — too fast/slow/right? effect on retention?>",
    "audio_visual_sync": "<does what is being SAID match what is SHOWN on screen? is there coherence or disconnect?>",
    "script_quality": "<tight and purposeful or rambling? what should be cut?>"
  }},
  "hook_analysis": {{
    "verdict": "<exactly why this 3-second frame earns or loses the viewer — be specific to the frame>",
    "what_top_creators_do_instead": "<specific: how would MrBeast or a top creator in this niche open this same video?>",
    "rewritten_opening": "<exact description of what should happen visually + script in first 15 seconds>"
  }},
  "production_issues": ["<exact production problem from the facts>", "<another>", "<another>"],
  "optimization_tips": [
    "<specific fix 1 — frame, audio, or script>",
    "<specific fix 2>",
    "<specific fix 3>",
    "<specific fix 4>",
    "<specific fix 5>"
  ],
  "viral_potential": "<Low/Medium/High/Very High>",
  "estimated_improvement": "<realistic view count change if ALL issues fixed>"
}}"""

            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_BRUTAL},
                    {"role": "user", "content": critique_prompt},
                ],
                max_tokens=1500, temperature=0.15,
            )
        else:
            score, grade = 15, "F"
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_BRUTAL},
                    {"role": "user", "content": f"""Video frame extraction failed. Audio transcript: {transcript[:500] if transcript else 'None'}.
Audio stats: {json.dumps(audio)}. Score: {score}/{grade}.
Return default failure JSON with these exact values for virality_score and grade."""},
                ],
                max_tokens=600, temperature=0.15,
            )

        result = _parse_json(response.choices[0].message.content)
        result["virality_score"] = score
        result["grade"] = grade
        return result
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

    prompt = f"""Competitor title battle. Every title below appeared in the same YouTube search results. A viewer clicks ONE. Tell me which wins and why my title loses or wins.

MY VIDEO: "{main_title}"

COMPETING TITLES:
{comp_lines}

Be direct. If my title is the weakest in the list, say it outright.

Return valid JSON only:
{{
  "head_to_head_verdict": "<does my title win or lose? rank it — e.g. 'Your title ranks #4 of 5 — here is why'>",
  "click_winner": "<which title in the list would get clicked FIRST by a cold viewer, and the exact psychological reason>",
  "summary": "<2-sentence honest assessment of where my title stands competitively>",
  "insights": [
    "<specific insight: what psychological trigger competitors use that mine lacks>",
    "<specific SEO/keyword advantage competitors have>",
    "<specific format or angle that is outperforming mine>"
  ],
  "title_edge": "<any genuine advantage my title has — say 'none' if there is none>",
  "what_competitors_do_better": ["<specific tactic>", "<another tactic>"],
  "gaps_to_exploit": [
    "<real uncovered angle in this niche>",
    "<another gap>"
  ],
  "positioning_advice": "<exact rewritten title that would rank #1 in this competitive set and why>"
}}"""

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_BRUTAL},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1000, temperature=0.15,
    )
    return _parse_json(response.choices[0].message.content)
