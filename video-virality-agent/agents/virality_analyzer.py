"""
Virality Analyzer — unified scoring for URL and video upload.

SCORING PHILOSOPHY:
  Two separate scores always shown:
    1. content_score  (0-100): pure quality of hook, audio, script, visuals, title/SEO
    2. performance_score (0-100): anchored to real YouTube metrics (only for URL mode)

  The final virality_score returned to the frontend is:
    - URL mode:   weighted blend  (content 40% + performance 60%)
    - Upload mode: content_score only  (no YouTube data available)

  This means the same video analysed via URL and via upload will score
  similarly on content quality, while URL additionally reflects real performance.
"""

import os, re, json, base64, tempfile, math
from pathlib import Path
from groq import Groq

TEXT_MODEL   = "llama-3.1-8b-instant"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

CRITIC_SYSTEM = """You are a ruthless YouTube performance analyst. Real brands pay you to kill bad content before it ships.

RULES — never break them:
- Be specific. Name the exact second, word, or visual that fails.
- Do NOT use hedging language ("could", "might", "consider"). Say "change this", "cut this", "redo this".
- Do NOT invent positives. If something is bad, say it is bad.
- Your output goes directly to a production team who will act on it today.
- The score has been computed from hard data. Your job is to EXPLAIN it — not to argue for a different number."""


# ─── helpers ──────────────────────────────────────────────────────────────────

def _client() -> Groq:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY not set in .env")
    return Groq(api_key=key)


def _parse_json(text: str) -> dict:
    """Parse JSON from AI response, with multiple fallback strategies."""
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract first {...} block
    try:
        start = text.index("{")
        # Find matching closing brace
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i+1])
    except (ValueError, json.JSONDecodeError):
        pass

    # Strategy 3: fix common AI mistakes — trailing commas, unescaped newlines
    try:
        fixed = re.sub(r",\s*([\]}])", r"\1", text)          # trailing commas
        fixed = re.sub(r"\n", " ", fixed)                     # newlines in strings
        fixed = re.sub(r"(?<!\\)'", '"', fixed)               # single → double quotes
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Strategy 4: ask AI to fix its own broken JSON using a cheap model call
    try:
        client = _client()
        repair = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content":
                f"Fix this broken JSON so it is valid. Return ONLY the fixed JSON, nothing else:\n{text[:3000]}"}],
            max_tokens=2000, temperature=0,
        )
        return json.loads(repair.choices[0].message.content.strip())
    except Exception:
        pass

    raise ValueError(f"Could not parse JSON from AI response. First 200 chars: {text[:200]}")


def _b64(path: str) -> tuple[str, str]:
    ext = Path(path).suffix.lower().lstrip(".")
    mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}.get(ext,"image/jpeg")
    return base64.standard_b64encode(open(path,"rb").read()).decode(), mime


def _grade(score: int) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 50: return "C"
    if score >= 35: return "D"
    return "F"


# ─── score computers (all Python, AI cannot override) ─────────────────────────

def _performance_score(view_count: int, like_ratio: float, comment_ratio: float) -> int:
    """0-100 score based purely on real YouTube metrics."""
    if   view_count < 500:     base = 4
    elif view_count < 1_000:   base = 10
    elif view_count < 3_000:   base = 16
    elif view_count < 5_000:   base = 22
    elif view_count < 10_000:  base = 30
    elif view_count < 25_000:  base = 40
    elif view_count < 50_000:  base = 50
    elif view_count < 100_000: base = 60
    elif view_count < 250_000: base = 70
    elif view_count < 500_000: base = 78
    elif view_count < 1_000_000: base = 85
    else:                        base = 93

    # like ratio vs 5% viral average
    if   like_ratio == 0:  base -= 15
    elif like_ratio < 1:   base -= 12
    elif like_ratio < 2:   base -= 7
    elif like_ratio < 3:   base -= 3
    elif like_ratio >= 6:  base += 4

    # comment ratio
    if   comment_ratio == 0:    base -= 8
    elif comment_ratio < 0.05:  base -= 5
    elif comment_ratio < 0.1:   base -= 2
    elif comment_ratio >= 0.5:  base += 3

    return max(2, min(98, base))


def _content_score(hook_score: int, audio_score: int, visual_score: int,
                   title_score: int, seo_score: int) -> int:
    """Weighted content quality score — same formula for URL and upload."""
    raw = (hook_score   * 0.30 +
           audio_score  * 0.20 +
           visual_score * 0.20 +
           title_score  * 0.15 +
           seo_score    * 0.15)
    return max(2, min(98, round(raw)))


# ─── audio extraction & analysis ─────────────────────────────────────────────

def _extract_audio(video_path: str) -> str:
    """Extract audio and transcribe via Groq Whisper. Returns transcript string."""
    tmp = None
    try:
        import imageio_ffmpeg, subprocess
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        r = subprocess.run(
            [ffmpeg, "-i", video_path, "-vn", "-ar", "16000", "-ac", "1",
             "-b:a", "64k", tmp.name, "-y"],
            capture_output=True, timeout=120
        )
        if r.returncode != 0 or os.path.getsize(tmp.name) < 500:
            return ""
        client = _client()
        with open(tmp.name, "rb") as f:
            tx = client.audio.transcriptions.create(
                file=(Path(tmp.name).name, f.read()),
                model="whisper-large-v3-turbo",
                response_format="text",
            )
        return str(tx)[:3000]
    except Exception:
        return ""
    finally:
        if tmp and os.path.exists(tmp.name):
            try: os.unlink(tmp.name)
            except: pass


def _audio_signals(transcript: str, duration_sec: float = 0) -> dict:
    """Derive numeric quality signals from transcript text."""
    if not transcript:
        return dict(wpm=0, filler_pct=0, starts_generic=True,
                    has_hook_trigger=False, word_count=0, transcript_present=False)
    words = transcript.split()
    wc = len(words)
    wpm = round(wc / duration_sec * 60) if duration_sec > 0 else 0
    fillers = ["um","uh","like","you know","basically","literally","right","so","anyway","kind of","sort of"]
    fc = sum(transcript.lower().count(f) for f in fillers)
    filler_pct = round(fc / max(wc, 1) * 100, 1)
    generic = ["hey guys","hey everyone","welcome back","what's up guys","hello everyone",
               "hi guys","so today","in this video","hi everyone","hey what's up"]
    starts_generic = any(g in transcript[:150].lower() for g in generic)
    triggers = ["secret","never","mistake","shocking","truth","nobody tells","i tried",
                "i tested","what if","why","how i","changed","worst","best","you won't","actually"]
    has_trigger = any(t in " ".join(words[:40]).lower() for t in triggers)
    return dict(wpm=wpm, filler_pct=filler_pct, starts_generic=starts_generic,
                has_hook_trigger=has_trigger, word_count=wc, transcript_present=True)


def _score_audio(sig: dict) -> int:
    """Convert audio signals to 0-100 score."""
    if not sig["transcript_present"]: return 15  # no speech detected
    s = 65  # start average
    if sig["starts_generic"]:    s -= 25  # "hey guys welcome back" kills retention
    if sig["has_hook_trigger"]:  s += 15
    if sig["filler_pct"] > 15:   s -= 20
    elif sig["filler_pct"] > 8:  s -= 12
    elif sig["filler_pct"] > 4:  s -= 5
    wpm = sig["wpm"]
    if wpm > 0:
        if wpm < 100 or wpm > 200: s -= 10   # too slow or too fast
        elif 130 <= wpm <= 160:    s += 5    # ideal YouTube pacing
    return max(5, min(95, s))


# ─── vision analysis ─────────────────────────────────────────────────────────

def _get_frame_facts(b64_img: str, mime: str, client: Groq) -> dict:
    """Ask vision model for objective yes/no facts only (temperature 0.05)."""
    r = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{"role":"user","content":[
            {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64_img}"}},
            {"type":"text","text":"""Look at this image and answer with JSON only, no markdown:
{
  "has_face": <true/false>,
  "face_emotion_strong": <true/false>,
  "has_text_overlay": <true/false>,
  "text_readable_on_mobile": <true/false>,
  "good_lighting": <true/false>,
  "high_contrast": <true/false>,
  "subject_in_focus": <true/false>,
  "background_clean": <true/false>,
  "looks_professional": <true/false>,
  "high_energy_visible": <true/false>,
  "would_stop_scroll": <true/false>
}"""}
        ]}],
        max_tokens=250, temperature=0.05,
    )
    try:    return _parse_json(r.choices[0].message.content)
    except: return {}


def _score_visual(facts: dict) -> int:
    """Convert visual facts to 0-100 score."""
    s = 30  # start low — earn it
    if facts.get("has_face"):             s += 12
    if facts.get("face_emotion_strong"):  s += 10
    if facts.get("has_text_overlay"):     s += 6
    if facts.get("text_readable_on_mobile"): s += 6
    if facts.get("good_lighting"):        s += 8
    if facts.get("high_contrast"):        s += 5
    if facts.get("subject_in_focus"):     s += 5
    if facts.get("background_clean"):     s += 5
    if facts.get("looks_professional"):   s += 8
    if facts.get("high_energy_visible"):  s += 8
    if facts.get("would_stop_scroll"):    s += 7
    # Hard penalties
    if not facts.get("has_face"):            s -= 8
    if not facts.get("good_lighting"):       s -= 10
    if not facts.get("looks_professional"):  s -= 8
    return max(5, min(95, s))


def _score_title(title: str, tags: list, description: str) -> tuple[int, int]:
    """Return (title_score, seo_score) from metadata."""
    # title scoring
    ts = 40
    import re as _re
    if any(c.isdigit() for c in title):           ts += 10  # numbers build trust
    power = ["secret","never","mistake","how to","why","best","worst","truth","revealed",
             "shocking","tested","actually","you need","stop","avoid","mistake"]
    if any(w in title.lower() for w in power):    ts += 12
    if len(title) < 40:                           ts -= 8   # too short = vague
    if len(title) > 70:                           ts -= 5   # too long = truncated
    question_or_number = bool(_re.search(r'\d|how|why|what|when|does|can|will', title.lower()))
    if question_or_number:                        ts += 8

    # seo scoring
    ss = 30
    if tags and len(tags) >= 5:   ss += 20
    elif tags and len(tags) >= 2: ss += 10
    else:                         ss -= 10   # no tags = invisible
    if description and len(description) > 100: ss += 20
    elif description and len(description) > 30: ss += 10
    else:                                       ss -= 15   # no description = no SEO

    return max(5, min(95, ts)), max(5, min(95, ss))


# ─── public API ───────────────────────────────────────────────────────────────

def analyze_thumbnail(image_path: str) -> dict:
    client = _client()
    b64, mime = _b64(image_path)
    facts = _get_frame_facts(b64, mime, client)
    visual = _score_visual(facts)
    grade  = _grade(visual)

    r = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role":"system","content":CRITIC_SYSTEM},
            {"role":"user","content":f"""This YouTube thumbnail scored {visual}/100 ({grade}).

Detected facts: {json.dumps(facts)}

Write a specific brutal critique. Explain WHY the score is {visual}. Be pixel-level specific.

Return JSON only:
{{
  "score": {visual},
  "grade": "{grade}",
  "ctr_verdict": "<one sentence: will this get clicked in a competitive feed — be direct>",
  "what_viewer_sees_in_03_seconds": "<exactly what registers in 0.3 seconds of scrolling>",
  "strengths": ["<only real strengths, max 2, omit if none>"],
  "weaknesses": ["<exact element that fails and why>", "<another>", "<another>"],
  "improvements": ["<exact fix — size, color, position, expression>", "<fix 2>", "<fix 3>"],
  "elements": {json.dumps(facts)},
  "ctr_potential": "<Low/Medium/High/Very High>"
}}"""}
        ],
        max_tokens=900, temperature=0.2,
    )
    result = _parse_json(r.choices[0].message.content)
    result["score"] = visual   # enforce computed score
    result["grade"] = grade
    return result


def analyze_video_content(title, description, tags, transcript, stats, duration) -> dict:
    client = _client()

    view_count    = stats.get("view_count", 0)
    like_count    = stats.get("like_count", 0)
    comment_count = stats.get("comment_count", 0)
    like_ratio    = round(like_count / view_count * 100, 2) if view_count > 0 else 0
    comment_ratio = round(comment_count / view_count * 100, 2) if view_count > 0 else 0

    # Compute all sub-scores in Python
    perf_score = _performance_score(view_count, like_ratio, comment_ratio)
    sig        = _audio_signals(transcript or "")
    hook_score = _score_audio(sig)
    title_score, seo_score = _score_title(title, tags or [], description or "")
    visual_score = 50   # no frame available for URL-only mode

    content = _content_score(hook_score, hook_score, visual_score, title_score, seo_score)

    # Weighted blend: 60% real performance + 40% content quality
    final = round(perf_score * 0.60 + content * 0.40)
    final = max(2, min(98, final))
    grade = _grade(final)

    prompt = f"""YouTube video audit. Final score: {final}/100 ({grade}).

How this score was computed (DO NOT change these numbers):
- Performance score (real YouTube data): {perf_score}/100
  * Views: {view_count:,}
  * Like ratio: {like_ratio}% (viral average = 5-8%)
  * Comment ratio: {comment_ratio}%
- Content quality score: {content}/100
  * Hook/audio: {hook_score}/100 — generic opener: {sig['starts_generic']}, hook trigger: {sig['has_hook_trigger']}, filler words: {sig['filler_pct']}%
  * Title strength: {title_score}/100
  * SEO strength: {seo_score}/100

Title: {title}
Tags: {', '.join((tags or [])[:12]) or 'NONE — zero SEO effort'}
Description: {(description or 'EMPTY')[:300]}
Transcript excerpt: {(transcript or 'NONE')[:1500]}

Write the audit. Explain exactly why each sub-score is what it is. Be specific and harsh.

Return JSON only:
{{
  "virality_score": {final},
  "grade": "{grade}",
  "performance_verdict": "<one sentence: why this video got the exact views it got — name the real reason>",
  "biggest_mistake": "<the single most damaging issue — be specific, not generic>",
  "breakdown": {{
    "hook_strength": {hook_score},
    "title_power": {title_score},
    "seo_strength": {seo_score},
    "engagement_signals": {perf_score},
    "content_depth": {content}
  }},
  "audio_analysis": {{
    "verdict": "<is the audio confident and professional, or amateurish? specific>",
    "filler_word_problem": "<{sig['filler_pct']}% filler words — what is the exact impact on credibility?>",
    "pacing_verdict": "<{sig['wpm']} wpm — ideal is 130-160 — what is the effect on viewer retention?>",
    "audio_visual_sync": "<does what is SAID match what a viewer would expect to SEE? is there coherence or disconnect?>",
    "script_quality": "<tight and punchy or rambling? what specific lines should be cut?>"
  }},
  "title_analysis": {{
    "verdict": "<strong or weak — specifically why>",
    "issues": ["<exact issue with this title>", "<another>"],
    "alternative_titles": ["<rewritten title 1 — more specific, curiosity-driven>", "<title 2>", "<title 3>"]
  }},
  "hook_analysis": {{
    "what_creator_actually_said": "<quote or paraphrase the actual first 30 seconds from transcript>",
    "verdict": "<did the hook earn the viewer or waste them — be harsh and specific>",
    "why_viewers_left": "<the exact moment and reason retention dropped>",
    "rewritten_hook": "<word-for-word replacement script for first 30 seconds>"
  }},
  "seo_analysis": {{
    "tag_verdict": "<are these tags hitting real search queries or useless?>",
    "suggested_tags": ["<high-volume tag>", "<long-tail tag>", "<niche tag>", "<trending tag>", "<competitor tag>"],
    "description_verdict": "<is the description doing SEO work or wasted space?>",
    "description_rewrite": "<rewritten first 150 chars — keyword rich>"
  }},
  "optimization_tips": ["<specific actionable fix>", "<fix 2>", "<fix 3>", "<fix 4>", "<fix 5>"],
  "viral_potential": "<Low/Medium/High/Very High>",
  "if_reshot_today": "<realistic view count if ALL fixes applied — and exactly why>"
}}"""

    r = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role":"system","content":CRITIC_SYSTEM}, {"role":"user","content":prompt}],
        max_tokens=2000, temperature=0.15,
    )
    result = _parse_json(r.choices[0].message.content)
    # Enforce Python-computed values
    result["virality_score"] = final
    result["grade"] = grade
    result["breakdown"] = {
        "hook_strength":      hook_score,
        "title_power":        title_score,
        "seo_strength":       seo_score,
        "engagement_signals": perf_score,
        "content_depth":      content,
    }
    return result


def analyze_uploaded_video(video_path: str) -> dict:
    client = _client()

    # Extract frame at 3s
    frame_path = None
    duration_sec = 0
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total / fps
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(int(3*fps), max(0, total-1)))
        ret, frame = cap.read()
        cap.release()
        if ret:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, frame)
            tmp.close()
            frame_path = tmp.name
    except Exception:
        pass

    # Extract and transcribe audio
    transcript = _extract_audio(video_path)
    sig = _audio_signals(transcript, duration_sec)

    # Compute all sub-scores in Python
    hook_score   = _score_audio(sig)
    audio_score  = hook_score

    facts = {}
    visual_score = 30   # default: penalise if no frame
    if frame_path:
        b64, mime = _b64(frame_path)
        facts = _get_frame_facts(b64, mime, client)
        visual_score = _score_visual(facts)

    # No title/SEO for raw upload — use neutral 50
    title_score = 50
    seo_score   = 50

    content = _content_score(hook_score, audio_score, visual_score, title_score, seo_score)
    grade   = _grade(content)

    # Build critique prompt
    frame_facts_str = json.dumps(facts) if facts else "Frame extraction failed"
    b64_content = []
    if frame_path:
        b64i, mimei = _b64(frame_path)
        b64_content = [{"type":"image_url","image_url":{"url":f"data:{mimei};base64,{b64i}"}}]

    critique = f"""Video upload analysis. Score: {content}/100 ({grade}).

HOW SCORE WAS COMPUTED (do not change these):
- Hook/audio score: {hook_score}/100
  * Transcript present: {sig['transcript_present']}
  * Starts with generic opener ("hey guys / welcome back"): {sig['starts_generic']}
  * Has strong hook trigger in first 30s: {sig['has_hook_trigger']}
  * Filler word percentage: {sig['filler_pct']}%
  * Words per minute: {sig['wpm']} (ideal: 130-160)
- Visual score: {visual_score}/100
  * Frame facts: {frame_facts_str}
- Overall content quality: {content}/100

Transcript (first 800 chars): {transcript[:800] if transcript else "NO AUDIO DETECTED — video may be silent or audio extraction failed"}

Write a brutal, specific audit explaining exactly why each number is what it is.
If no transcript: explain what that means for viewer retention and what to fix.
If frame shows no face/bad lighting/no energy: say it directly.

Return JSON only:
{{
  "virality_score": {content},
  "grade": "{grade}",
  "first_impression": "<what a cold viewer sees and hears in first 3 seconds — be specific>",
  "breakdown": {{
    "hook_strength": {hook_score},
    "visual_quality": {visual_score},
    "engagement_signals": {min(hook_score, visual_score)},
    "pacing": {audio_score},
    "content_depth": {content}
  }},
  "audio_analysis": {{
    "verdict": "<is the audio professional or amateurish — name specific problems>",
    "transcript_summary": "<what was actually said in first 30 seconds>",
    "filler_word_problem": "<{sig['filler_pct']}% filler words — specific impact>",
    "pacing_verdict": "<{sig['wpm']} wpm — too fast/slow/right — effect on retention>",
    "audio_visual_sync": "<does what is SAID match what is SHOWN on screen — is there alignment or disconnect?>",
    "script_quality": "<tight and valuable or rambling — what exact lines should be cut>"
  }},
  "hook_analysis": {{
    "verdict": "<did the opening earn viewer attention or lose it — why exactly>",
    "what_top_creators_do_instead": "<how a top creator in this niche would open this same video>",
    "rewritten_opening": "<exact word-for-word script + visual description for first 20 seconds>"
  }},
  "production_issues": ["<specific production problem from facts>", "<another>", "<another>"],
  "optimization_tips": ["<specific fix — audio, visual, or script>", "<fix 2>", "<fix 3>", "<fix 4>", "<fix 5>"],
  "viral_potential": "<Low/Medium/High/Very High>",
  "estimated_improvement": "<realistic score and view count change if all issues fixed>"
}}"""

    messages = [{"role":"system","content":CRITIC_SYSTEM}]
    if b64_content:
        messages.append({"role":"user","content": b64_content + [{"type":"text","text":critique}]})
        model = VISION_MODEL
    else:
        messages.append({"role":"user","content": critique})
        model = TEXT_MODEL

    try:
        r = client.chat.completions.create(model=model, messages=messages, max_tokens=1800, temperature=0.15)
        result = _parse_json(r.choices[0].message.content)
    except Exception:
        result = {}

    # Always enforce Python-computed values
    result["virality_score"] = content
    result["grade"] = grade
    result["breakdown"] = {
        "hook_strength":      hook_score,
        "visual_quality":     visual_score,
        "engagement_signals": min(hook_score, visual_score),
        "pacing":             audio_score,
        "content_depth":      content,
    }
    if "audio_analysis" not in result:
        result["audio_analysis"] = {
            "verdict": "Audio analysis failed — check video encoding",
            "transcript_summary": transcript[:200] if transcript else "No audio detected",
            "filler_word_problem": f"{sig['filler_pct']}% filler words",
            "pacing_verdict": f"{sig['wpm']} words per minute",
            "audio_visual_sync": "Cannot assess without audio transcript",
            "script_quality": "Cannot assess without audio transcript",
        }
    if frame_path:
        try: os.unlink(frame_path)
        except: pass
    return result


def compare_competitors(main_title: str, competitors: list[dict]) -> dict:
    if not competitors:
        return {"summary":"No competitor data.", "insights":[]}
    client = _client()
    lines = "\n".join(f'{i+1}. "{c["title"]}" by {c["channel"]}' for i,c in enumerate(competitors))
    r = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role":"system","content":CRITIC_SYSTEM},
            {"role":"user","content":f"""Title battle. These all appear in the same YouTube search results. A viewer clicks ONE.

MY VIDEO: "{main_title}"
COMPETITORS:
{lines}

If my title is the weakest, say so outright. Rank it.

Return JSON only:
{{
  "head_to_head_verdict": "<rank my title — e.g. ranks 4th of 5 — exact reason>",
  "click_winner": "<which title wins the click and the exact psychological reason>",
  "summary": "<2-sentence honest competitive assessment>",
  "insights": ["<psychological trigger competitors use that mine lacks>", "<SEO advantage competitors have>", "<format/angle beating mine>"],
  "title_edge": "<any genuine advantage — say none if there is none>",
  "what_competitors_do_better": ["<specific tactic>", "<another>"],
  "gaps_to_exploit": ["<real uncovered angle in niche>", "<another>"],
  "positioning_advice": "<exact rewritten title that would rank #1 in this set — and why>"
}}"""}
        ],
        max_tokens=900, temperature=0.15,
    )
    return _parse_json(r.choices[0].message.content)
