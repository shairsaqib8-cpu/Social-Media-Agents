"""
Virality Analyzer — unified scoring for URL and video upload.

SCORING SYSTEM (training document):
  10 dimensions, each scored /10 by Python. Total = sum = /100.
  1.  Hook      /10
  2.  Story     /10
  3.  Script    /10
  4.  Audio     /10
  5.  Visual    /10  (frame analysis, capped at 72, converted by /7.2)
  6.  Editing   /10
  7.  Retention /10  (real engagement for URL, predicted for upload)
  8.  Thumbnail /10
  9.  Title     /10
  10. Virality  /10

  Final score = sum of all 10 (clamped 1-100).
"""

import os, re, json, base64, tempfile, math, time
from pathlib import Path
from groq import Groq

TEXT_MODEL   = "llama-3.1-8b-instant"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

CRITIC_SYSTEM = """You are a multi-role YouTube performance system. You think simultaneously as:
(1) YouTube algorithm — what signals drive ranking, recommendation, and session watch time
(2) Professional video editor — what production choices hurt or help retention at each cut
(3) Marketing strategist — what drives CTR, conversion, and brand authority
(4) Audience psychology expert — what triggers curiosity, emotion, trust, and decision-making

You evaluate every video across 15 mandatory layers:
CONTENT IDENTITY · AUDIENCE INTELLIGENCE · CONTENT PURPOSE · HOOK PERFORMANCE ·
SCRIPT QUALITY · STORYTELLING · VISUAL PRODUCTION · EDITING & PACING · AUDIO QUALITY ·
SEO & DISCOVERABILITY · THUMBNAIL & CTR · ENGAGEMENT & RETENTION · ALGORITHM COMPATIBILITY ·
MONETIZATION & RISK · PSYCHOLOGICAL IMPACT

EXECUTION RULES — never break these:
1. Be analytical, not descriptive. Every statement must lead to a performance insight.
2. Be pixel-level specific. Name the exact second, word, or visual element that fails or succeeds.
3. Never use hedging language. Say "change this to X", "cut this line", "reshoot this scene".
4. Never invent positives. If something fails, say it fails and say exactly what to replace it with.
5. Every optimization tip must state: WHAT to change, EXACTLY what the replacement is, WHY it improves retention or CTR.
6. For every script problem: BAD: 'exact creator words' → GOOD: 'your exact replacement'. No vague advice.
7. Write a full 60-second rewritten script with [visual direction] markers. Make it hook-first, punchy, specific.
8. CUT RECOMMENDATIONS — CRITICAL: Every cut suggestion must include exact timestamp range (e.g. 00:14–00:28), reason it hurts retention, and what to replace it with. No cut without a timestamp.
9. LANGUAGE RULE — CRITICAL: Write ONLY in clear simple English. No Hindi, Urdu, Roman Urdu, or any non-English words. "Matlab", "bilkul", "bhai", "yaar" are NOT allowed.
10. Detect psychological triggers: curiosity gaps, Zeigarnik open loops, social proof signals, authority cues, fear/aspiration/amusement/outrage emotional drivers.
11. Think about global audience: language simplicity, accent neutrality, cultural universality, international scalability.
12. Evaluate monetization risk: flag any language, topic, or visual that risks demonetization, age restriction, or copyright strike.
13. Assess algorithm compatibility: recommendation friendliness, search ranking strength, session watch time contribution, Shorts feed potential.
14. Prioritize growth impact over theory. Think about what will actually move the numbers for THIS specific video and niche.
15. The scores have been computed from hard data. Your job is to EXPLAIN them and provide EXACT FIXES."""


# ─── helpers ──────────────────────────────────────────────────────────────────

def _client() -> Groq:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY not set in .env")
    return Groq(api_key=key)


def _groq_call(client: Groq, **kwargs):
    """Groq chat completion with automatic retry on rate-limit (429)."""
    for attempt in range(3):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                wait = 20 * (attempt + 1)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Groq rate limit — please wait 60 seconds and try again.")


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
        repair = _groq_call(client,
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
    r = _groq_call(client,
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
    """Convert visual facts to 0-72 score. Ceiling is 72 — no thumbnail
    earns an A without proven CTR data."""
    s = 20  # start harsh — most thumbnails are mediocre
    if facts.get("has_face"):                 s += 10
    if facts.get("face_emotion_strong"):      s += 10
    if facts.get("has_text_overlay"):         s += 8
    if facts.get("text_readable_on_mobile"):  s += 8
    if facts.get("good_lighting"):            s += 7
    if facts.get("high_contrast"):            s += 6
    if facts.get("subject_in_focus"):         s += 5
    if facts.get("looks_professional"):       s += 7
    if facts.get("high_energy_visible"):      s += 8
    if facts.get("would_stop_scroll"):        s += 8
    if facts.get("background_clean"):         s += 3
    # Hard penalties — these are fatal for YouTube CTR
    if not facts.get("has_face"):             s -= 10  # faceless = no emotional hook
    if not facts.get("has_text_overlay"):     s -= 10  # no text = viewer has no context
    if not facts.get("good_lighting"):        s -= 12  # dark/muddy = instant skip
    if not facts.get("looks_professional"):   s -= 12  # amateur look = brand damage
    if not facts.get("high_contrast"):        s -= 6   # blends into feed
    if not facts.get("would_stop_scroll"):    s -= 8   # the only metric that matters
    return max(5, min(72, s))


def _score_title(title: str, tags: list, description: str) -> tuple[int, int]:
    """Return (title_score_0_100, seo_score_0_100) from metadata."""
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


# ─── new /10 scoring functions ────────────────────────────────────────────────

def _score_hook_10(sig: dict) -> int:
    """0-10: Hook quality from audio signals."""
    s = 5
    if sig["starts_generic"]: s -= 3
    if sig["has_hook_trigger"]: s += 2
    if not sig["transcript_present"]: return 2
    if sig["filler_pct"] > 15: s -= 2
    elif sig["filler_pct"] > 8: s -= 1
    return max(1, min(10, s))


def _score_story_10(transcript: str, sig: dict) -> int:
    """0-10: Narrative arc quality — detects Setup/Tension/Resolution + emotional peaks."""
    if not sig["transcript_present"]: return 2
    s = 4
    t = transcript.lower()
    # Story phases
    if any(w in t for w in ["problem","issue","struggle","before","challenge"]): s += 1  # Setup
    if any(w in t for w in ["but","however","then","until","discovered","suddenly"]): s += 1  # Tension
    if any(w in t for w in ["result","finally","outcome","learned","achieved","now"]): s += 1  # Resolution
    # Emotional peaks — high-engagement trigger words
    emotional_peaks = ["shocked","amazing","unbelievable","you won't believe","this changed",
                       "i couldn't believe","mind blown","incredible","game changer","life changing",
                       "nothing was the same","everything changed","blew my mind"]
    if any(ep in t for ep in emotional_peaks): s += 1
    if sig["has_hook_trigger"]: s += 1
    if sig["starts_generic"]: s -= 2
    if sig["word_count"] < 50: s -= 2
    return max(1, min(10, s))


def _score_script_10(sig: dict) -> int:
    """0-10: Script clarity and pacing."""
    if not sig["transcript_present"]: return 2
    s = 6
    if sig["starts_generic"]: s -= 2
    if sig["filler_pct"] > 15: s -= 3
    elif sig["filler_pct"] > 8: s -= 2
    elif sig["filler_pct"] > 4: s -= 1
    wpm = sig["wpm"]
    if wpm > 0:
        if wpm < 100 or wpm > 200: s -= 2
        elif 130 <= wpm <= 165: s += 2
    return max(1, min(10, s))


def _score_audio_10(sig: dict) -> int:
    """0-10: Audio quality (same signals as hook, slightly different weights)."""
    if not sig["transcript_present"]: return 2
    s = 6
    if sig["filler_pct"] > 15: s -= 3
    elif sig["filler_pct"] > 8: s -= 2
    elif sig["filler_pct"] > 4: s -= 1
    if sig["starts_generic"]: s -= 1
    wpm = sig["wpm"]
    if wpm > 0:
        if wpm < 100 or wpm > 210: s -= 2
        elif 130 <= wpm <= 165: s += 2
    return max(1, min(10, s))


def _score_visual_10(facts: dict) -> int:
    """0-10: Visual quality from frame facts (converts /72 to /10)."""
    raw = _score_visual(facts)
    return max(1, min(10, round(raw / 7.2)))


def _score_editing_10(cut_count: int, duration_sec: float, wpm: int) -> int:
    """0-10: Edit pacing quality."""
    raw = _pacing_score(cut_count, duration_sec, wpm)
    return max(1, min(10, round(raw / 9)))


def _score_retention_10(view_count: int, like_ratio: float, comment_ratio: float) -> int:
    """0-10: Audience retention from real engagement data."""
    raw = _performance_score(view_count, like_ratio, comment_ratio)
    return max(1, min(10, round(raw / 10)))


def _score_retention_predicted_10(hook_10: int, story_10: int, editing_10: int) -> int:
    """0-10: Predicted retention for upload mode (no real data)."""
    return max(1, min(10, round((hook_10*0.4 + story_10*0.3 + editing_10*0.3))))


def _score_thumbnail_10(facts: dict) -> int:
    """0-10: Thumbnail CTR potential."""
    return _score_visual_10(facts)


def _score_title_10(title: str, tags: list, description: str) -> tuple[int, int]:
    """Return (title_10, seo_10)."""
    ts, ss = _score_title(title, tags, description)
    return max(1, min(10, round(ts/10))), max(1, min(10, round(ss/10)))


def _score_virality_10(hook_10: int, story_10: int, visual_10: int, retention_10: int, editing_10: int) -> int:
    """0-10: Viral potential prediction."""
    weighted = (hook_10*0.30 + visual_10*0.25 + story_10*0.20 + retention_10*0.15 + editing_10*0.10)
    return max(1, min(10, round(weighted)))


# ─── extended framework scoring (6 new dimensions) ───────────────────────────

def _score_seo_standalone_10(tags: list, description: str) -> int:
    """0-10: SEO & discoverability (separate from title strength)."""
    s = 3
    if tags and len(tags) >= 10: s += 4
    elif tags and len(tags) >= 5: s += 2
    elif tags and len(tags) >= 2: s += 1
    if description and len(description) > 300: s += 3
    elif description and len(description) > 100: s += 2
    elif description and len(description) > 30:  s += 1
    # Hashtag detection
    if description and description.count("#") >= 3: s += 1
    # Timestamp chapters
    import re as _re
    if description and _re.search(r'\d+:\d{2}', description): s += 1
    return max(1, min(10, s))


def _score_audience_fit_10(title: str, tags: list, description: str) -> int:
    """0-10: How specifically the content is targeted to an audience."""
    s = 4
    t = (title + " " + " ".join(tags or []) + " " + (description or "")).lower()
    # Audience specificity markers
    specific_markers = ["beginners","advanced","how to","step by step","guide","for","if you",
                        "tutorial","explained","vs","compared","review","in minutes"]
    hits = sum(1 for m in specific_markers if m in t)
    s += min(4, hits)
    # Niche signals
    if any(n in t for n in ["corporate","b2b","business","professional","brand"]): s += 1
    if len(tags or []) >= 5: s += 1
    return max(1, min(10, s))


def _score_engagement_10(hook_10: int, story_10: int, retention_10: int) -> int:
    """0-10: Predicted engagement potential (comment/share/like likelihood)."""
    return max(1, min(10, round(hook_10*0.4 + story_10*0.35 + retention_10*0.25)))


def _score_branding_10(visual_10: int, title_10: int) -> int:
    """0-10: Brand identity & visual consistency."""
    return max(1, min(10, round((visual_10*0.6 + title_10*0.4))))


def _score_technical_quality_10(audio_10: int, visual_10: int) -> int:
    """0-10: Overall technical production quality."""
    return max(1, min(10, round((audio_10 + visual_10) / 2)))


def _score_algorithm_fit_10(tags: list, description: str, seo_10: int, thumbnail_10: int) -> int:
    """0-10: YouTube algorithm recommendation compatibility."""
    s = round((seo_10*0.4 + thumbnail_10*0.3) * 1.2)
    if tags and len(tags) >= 5: s += 1
    if description and len(description) > 200: s += 1
    return max(1, min(10, s))


def _score_monetization_10(title: str, description: str, transcript: str) -> int:
    """0-10: Ad suitability / monetization safety (higher = safer)."""
    combined = (title + " " + (description or "") + " " + (transcript or "")).lower()
    s = 9  # start safe
    # Yellow/red dollar sign risk words
    risky = ["gun","weapon","violence","war","death","suicide","drug","alcohol","sex","nude",
             "explicit","kill","blood","political","controversial","crisis","disaster","tragedy"]
    hits = sum(1 for w in risky if w in combined)
    s -= min(7, hits * 2)
    # Copyright risk
    if "music" in combined or "song" in combined or "soundtrack" in combined: s -= 1
    return max(1, min(10, s))


def _performance_tier(score: int) -> str:
    if score >= 85: return "Viral"
    if score >= 70: return "High Performing"
    if score >= 50: return "Average"
    if score >= 35: return "Weak"
    return "Needs Major Improvement"


# ─── pacing & frame helpers ───────────────────────────────────────────────────

def _pacing_score(cut_count: int, duration_sec: float, wpm: int) -> int:
    """Score edit pacing — YouTube rewards fast, energetic cutting."""
    s = 45
    if duration_sec > 0:
        cpm = cut_count / (duration_sec / 60)
        if cpm < 1:    s -= 20
        elif cpm < 3:  s -= 10
        elif cpm < 6:  s += 0
        elif cpm < 12: s += 12
        else:          s += 18
    if wpm > 0:
        if wpm < 100:            s -= 10
        elif wpm > 200:          s -= 8
        elif 130 <= wpm <= 170:  s += 10
    return max(5, min(90, s))


def _extract_video_frames(video_path: str) -> tuple[list[dict], float, int]:
    """Extract frames at key retention points. Returns (frames, duration_sec, cut_count)."""
    import cv2
    frames = []
    duration_sec = 0
    cut_count = 0
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total / fps if fps > 0 else 0

        # Sample at: hook, 3s, 15s, 30s, 40%, 70%, near-end
        sample_secs = [1, 3, 15, 30]
        if duration_sec > 60:   sample_secs.append(round(duration_sec * 0.40))
        if duration_sec > 120:  sample_secs.append(round(duration_sec * 0.70))
        sample_secs.append(max(1, round(duration_sec - 5)))
        sample_secs = sorted(set(s for s in sample_secs if 0 < s < duration_sec))

        label_map = {}
        if sample_secs:
            label_map[sample_secs[0]] = "Hook (opening)"
            if len(sample_secs) > 1: label_map[sample_secs[1]] = "3-second mark"
            if len(sample_secs) > 2: label_map[sample_secs[2]] = "15-second mark"
            if len(sample_secs) > 3: label_map[sample_secs[3]] = "30-second mark"
            if len(sample_secs) > 4: label_map[sample_secs[4]] = "Mid video"
            if len(sample_secs) > 5: label_map[sample_secs[5]] = "Late video"
            label_map[sample_secs[-1]] = "Video ending"

        prev_hist = None
        for ts in sample_secs:
            frame_no = min(int(ts * fps), total - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret:
                continue

            # Detect scene cuts via histogram comparison
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist)
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                if diff > 0.4:
                    cut_count += 1
            prev_hist = hist.copy()

            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
            tmp.close()
            b64_data = base64.standard_b64encode(open(tmp.name, "rb").read()).decode()
            try: os.unlink(tmp.name)
            except: pass

            frames.append({
                "timestamp_sec": ts,
                "label": label_map.get(ts, f"{ts}s"),
                "b64": b64_data,
                "mime": "image/jpeg",
            })
        cap.release()
    except Exception:
        pass
    return frames, duration_sec, cut_count


def _analyze_frame_sequence(frames: list[dict], transcript: str,
                             duration_sec: float, client: Groq) -> dict:
    """
    Watch the video at each key frame: assess visual quality AND whether
    visuals match what's being spoken at that exact moment.
    """
    if not frames:
        return {"avg_visual": 25, "segments": [], "worst_segment": "no frames",
                "av_sync_verdict": "No frames extracted", "high_risk_moments": [],
                "broken_sync_moments": []}

    words = transcript.split() if transcript else []
    total_words = len(words)
    segment_scores = []
    segments_report = []

    for frm in frames[:6]:  # cap at 6 to respect rate limits
        ts = frm["timestamp_sec"]
        label = frm["label"]

        # Approximate words spoken at this timestamp
        spoken_here = ""
        if total_words > 0 and duration_sec > 0:
            progress = ts / duration_sec
            start_w = max(0, int(progress * total_words) - 15)
            spoken_here = " ".join(words[start_w:start_w + 30])

        facts = _get_frame_facts(frm["b64"], frm["mime"], client)
        vscore = _score_visual(facts)
        segment_scores.append(vscore)

        sync_prompt = f"""You are reviewing a YouTube video at the {label} (timestamp {ts}s).

WHAT THE CAMERA SHOWS (visual facts):
{json.dumps(facts)}

WHAT IS BEING SAID RIGHT NOW:
"{spoken_here if spoken_here else 'NO AUDIO / SILENT at this point'}"

Answer with JSON only — no markdown:
{{
  "what_viewer_sees": "<one sentence: what is literally on screen>",
  "what_creator_says": "<one sentence: what is being said>",
  "sync_rating": "<Excellent/Good/Weak/Broken>",
  "sync_problem": "<null if sync good, else: exact mismatch and viewer impact>",
  "retention_risk": "<Low/Medium/High>"
}}"""

        try:
            r = _groq_call(client,
                model=VISION_MODEL,
                messages=[{"role":"user","content":[
                    {"type":"image_url","image_url":{"url":f"data:{frm['mime']};base64,{frm['b64']}"}},
                    {"type":"text","text":sync_prompt}
                ]}],
                max_tokens=300, temperature=0.05,
            )
            seg = _parse_json(r.choices[0].message.content)
        except Exception:
            seg = {"sync_rating": "Unknown", "retention_risk": "Unknown",
                   "what_viewer_sees": "Analysis failed", "what_creator_says": spoken_here[:60]}

        seg["timestamp"] = ts
        seg["label"] = label
        seg["visual_score"] = vscore
        segments_report.append(seg)

    avg_visual = round(sum(segment_scores) / len(segment_scores)) if segment_scores else 25
    worst = min(segments_report, key=lambda s: s.get("visual_score", 50))
    broken = [s for s in segments_report if s.get("sync_rating") in ("Weak", "Broken")]
    risky  = [s for s in segments_report if s.get("retention_risk") == "High"]

    if len(broken) >= max(1, len(segments_report) // 2):
        av_sync = "Poor — visuals frequently disconnect from what is being said"
    elif broken:
        av_sync = f"Inconsistent — {len(broken)} of {len(segments_report)} segments have sync problems"
    else:
        av_sync = "Good — visuals support the audio throughout"

    return {
        "avg_visual": avg_visual,
        "segments": segments_report,
        "worst_segment": f"{worst.get('label','?')} ({worst.get('visual_score','?')}/72)",
        "av_sync_verdict": av_sync,
        "high_risk_moments": [f"{s['label']} at {s['timestamp']}s" for s in risky],
        "broken_sync_moments": [
            f"{s['label']}: {s.get('sync_problem','mismatch')}" for s in broken
        ],
    }


# ─── public API ───────────────────────────────────────────────────────────────

def analyze_thumbnail(image_path: str) -> dict:
    client = _client()
    b64, mime = _b64(image_path)
    facts = _get_frame_facts(b64, mime, client)
    thumb_10 = _score_thumbnail_10(facts)
    visual_raw = _score_visual(facts)
    grade = _grade(thumb_10 * 10)

    r = _groq_call(client,
        model=TEXT_MODEL,
        messages=[
            {"role":"system","content":CRITIC_SYSTEM},
            {"role":"user","content":f"""This YouTube thumbnail scored {thumb_10}/10 ({grade}).

Detected facts: {json.dumps(facts)}

Write a specific brutal critique. Explain WHY the score is {thumb_10}/10. Be pixel-level specific.

Return JSON only:
{{
  "score": {thumb_10},
  "grade": "{grade}",
  "ctr_prediction": "<one sentence: will this get clicked in a competitive feed — be direct>",
  "what_viewer_sees_in_03_seconds": "<exactly what registers in 0.3 seconds of scrolling>",
  "strengths": ["<only real strengths, max 2, omit if none>"],
  "weaknesses": ["<exact element that fails and why>", "<another>", "<another>"],
  "improvements": ["<exact fix — size, color, position, expression>", "<fix 2>", "<fix 3>"],
  "elements": {json.dumps(facts)},
  "ctr_potential": "<Low/Medium/High/Very High>",
  "five_thumbnail_concepts": [
    "<concept 1: what to show, text overlay, colors, layout>",
    "<concept 2>",
    "<concept 3>",
    "<concept 4>",
    "<concept 5>"
  ],
  "content_team_checklist": [
    "[ ] <checkbox item for production team>",
    "[ ] <another>",
    "[ ] <another>"
  ]
}}"""}
        ],
        max_tokens=1200, temperature=0.2,
    )
    result = _parse_json(r.choices[0].message.content)
    result["score"] = thumb_10   # enforce computed score
    result["grade"] = grade
    result["ctr_prediction"] = result.get("ctr_prediction", result.get("ctr_verdict", ""))
    return result


def analyze_video_content(title, description, tags, transcript, stats, duration) -> dict:
    client = _client()

    view_count    = stats.get("view_count", 0)
    like_count    = stats.get("like_count", 0)
    comment_count = stats.get("comment_count", 0)
    like_ratio    = round(like_count / view_count * 100, 2) if view_count > 0 else 0
    comment_ratio = round(comment_count / view_count * 100, 2) if view_count > 0 else 0

    # Compute all /10 scores in Python
    sig         = _audio_signals(transcript or "", duration or 0)
    hook_10     = _score_hook_10(sig)
    story_10    = _score_story_10(transcript or "", sig)
    script_10   = _score_script_10(sig)
    audio_10    = _score_audio_10(sig)
    # No video frames in URL mode — use neutral visual
    visual_facts: dict = {}
    visual_10   = 5  # neutral when no frame available
    editing_10  = 5  # neutral when no video file
    retention_10 = _score_retention_10(view_count, like_ratio, comment_ratio)
    thumbnail_10 = 5  # no thumbnail image provided
    title_10, seo_10 = _score_title_10(title, tags or [], description or "")
    # title dimension = average of title strength and SEO
    title_dim_10 = max(1, min(10, round((title_10 + seo_10) / 2)))
    virality_10  = _score_virality_10(hook_10, story_10, visual_10, retention_10, editing_10)

    final_score = hook_10 + story_10 + script_10 + audio_10 + visual_10 + editing_10 + retention_10 + thumbnail_10 + title_dim_10 + virality_10
    final_score = max(1, min(100, final_score))
    grade = _grade(final_score)

    # Extended framework scoring (6 new dimensions — Python computed)
    seo_10           = _score_seo_standalone_10(tags or [], description or "")
    audience_fit_10  = _score_audience_fit_10(title, tags or [], description or "")
    engagement_10    = _score_engagement_10(hook_10, story_10, retention_10)
    branding_10      = _score_branding_10(visual_10, title_dim_10)
    technical_10     = _score_technical_quality_10(audio_10, visual_10)
    algorithm_fit_10 = _score_algorithm_fit_10(tags or [], description or "", seo_10, thumbnail_10)
    monetization_10  = _score_monetization_10(title, description or "", transcript or "")
    tier             = _performance_tier(final_score)

    prompt = f"""YouTube video — 15-layer full audit. Score: {final_score}/100 | Tier: {tier}

CORE SCORES (Python-computed — do NOT change):
Hook:{hook_10}/10 | Story:{story_10}/10 | Script:{script_10}/10 | Audio:{audio_10}/10
Visual:{visual_10}/10 | Editing:{editing_10}/10 | Retention:{retention_10}/10
Thumbnail:{thumbnail_10}/10 | Title:{title_dim_10}/10 | Virality:{virality_10}/10

EXTENDED SCORES (Python-computed — do NOT change):
SEO:{seo_10}/10 | AudienceFit:{audience_fit_10}/10 | Engagement:{engagement_10}/10
Branding:{branding_10}/10 | TechnicalQuality:{technical_10}/10
AlgorithmFit:{algorithm_fit_10}/10 | MonetizationSafety:{monetization_10}/10

DATA:
Title: {title}
Tags ({len(tags or [])}): {', '.join((tags or [])[:12]) or 'NONE'}
Description: {(description or 'EMPTY')[:400]}
Stats: {view_count:,} views | {like_ratio}% likes | {comment_ratio}% comments
Transcript: {(transcript or 'NONE')[:1500]}

Apply all 15 analysis layers. Be ruthlessly specific. Reference exact timestamps, words, and data.
Return JSON only — every field is mandatory:
{{
  "overall_score": {final_score},
  "grade": "{grade}",
  "performance_tier": "{tier}",
  "confidence_level": "<High/Medium/Low>",
  "executive_summary": "<2-3 sentence honest summary — include the single biggest weakness and single biggest opportunity>",
  "audience_breakdown": {{
    "target_audience": "<who this is made for — age, type, skill level>",
    "content_purpose": "<Education/Entertainment/Sales/Brand Awareness/Community/Lead Gen/Authority>",
    "audience_intent": "<Learn/Entertain/Buy/Engage/Share>",
    "global_relevance": "<High/Medium/Low — with reason>",
    "language_simplicity": "<score 1-10 — is the language globally accessible?>",
    "cultural_universality": "<universal or region-specific — explain>"
  }},
  "psychological_analysis": {{
    "curiosity_gaps": ["<specific curiosity gap found or missing>"],
    "emotional_triggers": ["<trigger type and where it appears or is missing>"],
    "social_proof_signals": "<what social proof exists or is absent>",
    "authority_cues": "<what makes the creator credible — or what is missing>",
    "decision_influence": "<how does this video influence viewer action or fail to>"
  }},
  "scores": {{
    "hook": {hook_10},
    "story": {story_10},
    "script": {script_10},
    "audio": {audio_10},
    "visual": {visual_10},
    "editing": {editing_10},
    "retention": {retention_10},
    "thumbnail": {thumbnail_10},
    "title": {title_dim_10},
    "virality": {virality_10}
  }},
  "extended_scores": {{
    "seo": {seo_10},
    "audience_fit": {audience_fit_10},
    "engagement": {engagement_10},
    "branding": {branding_10},
    "technical_quality": {technical_10},
    "algorithm_fit": {algorithm_fit_10},
    "monetization_safety": {monetization_10}
  }},
  "strengths": ["<real strength with evidence — max 3>"],
  "weaknesses": ["<weakness with specific data evidence>", "<another>", "<another>"],
  "critical_issues": [
    {{"issue":"<specific problem>","timestamp":"<HH:MM:SS or null>","why_it_hurts":"<retention/CTR impact>","fix":"<exact instruction>","expected_impact":"<realistic estimate>"}}
  ],
  "timestamped_observations": [
    {{"time":"<HH:MM:SS>","observation":"<what happens>","severity":"<critical/warning/ok>"}}
  ],
  "retention_analysis": {{
    "predicted_drop_off_points": ["<timestamp + reason for drop-off>", "<another>"],
    "avg_view_duration_estimate": "<specific time estimate>",
    "replay_potential": "<Low/Medium/High — with reason>",
    "engagement_flow": "<how audience engagement rises and falls through the video>"
  }},
  "seo_ctr_audit": {{
    "title_seo_strength": "<specific keyword analysis>",
    "description_optimization": "<what is missing or wrong>",
    "tags_audit": "<are tags relevant and complete?>",
    "search_intent_match": "<does this match what viewers are actually searching?>",
    "suggested_video_potential": "<will YouTube recommend this next to other videos?>"
  }},
  "algorithm_compatibility": {{
    "recommendation_score": "<High/Medium/Low>",
    "search_ranking_strength": "<strong/average/weak — why>",
    "session_contribution": "<will viewers watch another video after this?>",
    "shorts_potential": "<could any segment work as a Short? which one?>"
  }},
  "monetization_risk": {{
    "ad_suitability": "<Green/Yellow/Red>",
    "risk_factors": ["<specific risk if any>"],
    "copyright_flags": "<any music/clip/brand risks detected>",
    "policy_violations": "<any content policy concerns>",
    "recommendation": "<what to change to protect monetization>"
  }},
  "improvement_roadmap": {{
    "high_impact": ["<fix 1 — biggest ROI change, specific>", "<fix 2>", "<fix 3>"],
    "medium_impact": ["<fix 1 — good improvement, moderate effort>", "<fix 2>"],
    "low_impact": ["<fix 1 — minor polish>", "<fix 2>"]
  }},
  "quick_wins": ["<fix under 10 minutes>", "<another>"],
  "ten_improved_titles": ["<title 1>","<title 2>","<title 3>","<title 4>","<title 5>","<title 6>","<title 7>","<title 8>","<title 9>","<title 10>"],
  "five_thumbnail_concepts": ["<concept 1: what to show, text, colors, layout>","<concept 2>","<concept 3>","<concept 4>","<concept 5>"],
  "content_team_checklist": ["[ ] <item>","[ ] <item>","[ ] <item>","[ ] <item>"],
  "final_verdict": "<harsh, honest 3-sentence summary — no softening>",
  "rewritten_hook": "<word-for-word first 20 seconds script + [visual direction] brackets>",
  "script_line_by_line": [
    {{"original":"<exact creator line>","problem":"<what is wrong>","rewrite":"<exact replacement>"}}
  ],
  "full_60s_script": "<complete rewritten 60-second script with [visual direction] throughout — hook-first, punchy, specific>",
  "story_arc": {{
    "phase_1_setup": "<first 20% — specific>",
    "phase_2_tension": "<conflict/problem introduced — specific>",
    "phase_3_resolution": "<payoff or failure to resolve — specific>",
    "emotional_peaks": ["<moment 1>","<moment 2>"],
    "arc_verdict": "<Strong/Weak/Missing>",
    "storytelling_fix": "<exact scene, line, and placement instruction>"
  }},
  "upload_strategy": {{
    "best_days": ["<day1>","<day2>"],
    "best_time_utc": "<HH:MM UTC>",
    "reasoning": "<why — based on niche and audience>",
    "metadata_fixes": {{
      "title_rewrite": "<improved title>",
      "description_first_line": "<first 2 SEO-optimized sentences>",
      "must_add_tags": ["<tag1>","<tag2>","<tag3>","<tag4>","<tag5>"]
    }},
    "chapter_timestamps": ["00:00 - <chapter>","01:30 - <chapter>","03:00 - <chapter>"]
  }},
  "performance_prediction": {{
    "predicted_views_30_days": "<honest range — based on score {final_score}/100>",
    "predicted_avg_view_duration": "<specific time>",
    "predicted_watch_time_hours": "<estimate>",
    "predicted_new_subscribers": "<realistic number>",
    "ctr_estimate": "<percentage>",
    "confidence": "<High/Medium/Low>",
    "what_will_hurt_most": "<single biggest limiter — specific>",
    "what_could_boost_it": "<single highest-impact change — specific>"
  }}
}}"""

    r = _groq_call(client,
        model=TEXT_MODEL,
        messages=[{"role":"system","content":CRITIC_SYSTEM}, {"role":"user","content":prompt}],
        max_tokens=4500, temperature=0.15,
    )
    result = _parse_json(r.choices[0].message.content)

    # Enforce all Python-computed values — AI cannot override
    result["overall_score"]   = final_score
    result["virality_score"]  = final_score
    result["grade"]           = grade
    result["performance_tier"] = tier
    result["scores"] = {
        "hook": hook_10, "story": story_10, "script": script_10,
        "audio": audio_10, "visual": visual_10, "editing": editing_10,
        "retention": retention_10, "thumbnail": thumbnail_10,
        "title": title_dim_10, "virality": virality_10,
    }
    result["extended_scores"] = {
        "seo": seo_10, "audience_fit": audience_fit_10,
        "engagement": engagement_10, "branding": branding_10,
        "technical_quality": technical_10, "algorithm_fit": algorithm_fit_10,
        "monetization_safety": monetization_10,
    }
    result["breakdown"] = {**result["scores"], **result["extended_scores"]}
    return result


def analyze_uploaded_video(video_path: str) -> dict:
    client = _client()

    # ── Step 1: Watch the video — extract frames at key moments, detect cuts ──
    frames, duration_sec, cut_count = _extract_video_frames(video_path)

    # ── Step 2: Transcribe audio ──
    transcript = _extract_audio(video_path)
    sig = _audio_signals(transcript, duration_sec)

    # ── Step 3: Analyze each frame + audio-visual sync ──
    vision = _analyze_frame_sequence(frames, transcript, duration_sec, client)

    # ── Step 4: Score all 10 dimensions in Python ──
    hook_10     = _score_hook_10(sig)
    story_10    = _score_story_10(transcript or "", sig)
    script_10   = _score_script_10(sig)
    audio_10    = _score_audio_10(sig)

    # Visual from frame analysis (avg of sampled frames, converted /72 → /10)
    avg_raw_visual = vision["avg_visual"]  # already 0-72
    visual_10   = max(1, min(10, round(avg_raw_visual / 7.2)))

    editing_10  = _score_editing_10(cut_count, duration_sec, sig["wpm"])

    # Retention is predicted for upload mode (no real YouTube data)
    retention_10 = _score_retention_predicted_10(hook_10, story_10, editing_10)

    # Thumbnail — no thumbnail uploaded, scored N/A (excluded from total)
    thumbnail_10 = None  # N/A — user uploaded a video, not a thumbnail

    # Title/SEO — not available for upload, use neutral
    title_dim_10 = 5
    virality_10  = _score_virality_10(hook_10, story_10, visual_10, retention_10, editing_10)

    # Score 9 dimensions (thumbnail excluded) scaled to /100
    nine_dims = hook_10 + story_10 + script_10 + audio_10 + visual_10 + editing_10 + retention_10 + title_dim_10 + virality_10
    final_score = max(1, min(100, round(nine_dims * 100 / 90)))
    grade = _grade(final_score)

    cuts_per_min = round(cut_count / (duration_sec / 60), 1) if duration_sec > 0 else 0

    # ── Step 5: Build critique with everything the agent observed ──
    segs_text = ""
    for s in vision["segments"]:
        segs_text += (f"\n  [{s['label']} @ {s['timestamp']}s] "
                      f"Visual:{s.get('visual_score','?')}/72 | "
                      f"Sync:{s.get('sync_rating','?')} | Risk:{s.get('retention_risk','?')}")
        if s.get("sync_problem"):
            segs_text += f"\n    → {s['sync_problem']}"

    critique = f"""I watched this video at {len(frames)} key moments. This is what I observed.

DURATION: {round(duration_sec)}s | SCENE CUTS: {cut_count} ({cuts_per_min}/min)

AUDIO:
- Starts with generic opener: {sig['starts_generic']}
- Strong hook trigger in first 30s: {sig['has_hook_trigger']}
- Filler words: {sig['filler_pct']}% | Speed: {sig['wpm']} wpm

VISUAL + SYNC REVIEW (what I saw at each moment):{segs_text}

OVERALL A/V SYNC: {vision['av_sync_verdict']}
HIGH DROP-OFF RISK MOMENTS: {vision['high_risk_moments'] or 'None detected'}
SYNC FAILURES: {vision['broken_sync_moments'] or 'None'}

10 DIMENSION SCORES (do not change these):
- Hook:      {hook_10}/10
- Story:     {story_10}/10
- Script:    {script_10}/10
- Audio:     {audio_10}/10
- Visual:    {visual_10}/10
- Editing:   {editing_10}/10
- Retention: {retention_10}/10 (predicted)
- Thumbnail: N/A (no thumbnail uploaded — excluded from score)
- Title:     {title_dim_10}/10
- Virality:  {virality_10}/10
TOTAL: {final_score}/100 ({grade}) [9 dimensions scored, thumbnail excluded]

TRANSCRIPT (first 1200 chars):
{transcript[:1200] if transcript else "NO AUDIO DETECTED"}

Write a brutal, timestamped critique. Reference specific moments you observed.
Name the exact second things go wrong. Do not invent positives.
Every criticism must include: evidence, timestamp, why it hurts, fix, expected impact.

Return JSON only — include ALL fields:
{{
  "overall_score": {final_score},
  "grade": "{grade}",
  "confidence_level": "<High/Medium/Low>",
  "executive_summary": "<2-3 sentence honest summary>",
  "scores": {{
    "hook": {hook_10},
    "story": {story_10},
    "script": {script_10},
    "audio": {audio_10},
    "visual": {visual_10},
    "editing": {editing_10},
    "retention": {retention_10},
    "thumbnail": null,
    "title": {title_dim_10},
    "virality": {virality_10}
  }},
  "strengths": ["<only real strength, max 3>"],
  "weaknesses": ["<weakness with specific evidence>"],
  "critical_issues": [
    {{
      "issue": "<specific problem>",
      "timestamp": "<HH:MM:SS or null>",
      "why_it_hurts": "<impact>",
      "fix": "<exact instruction>",
      "expected_impact": "<realistic estimate>"
    }}
  ],
  "timestamped_observations": [
    {{"time": "<HH:MM:SS>", "observation": "<what happens>", "severity": "<critical/warning/ok>"}}
  ],
  "ctr_prediction": "<will this get clicked — direct>",
  "retention_prediction": "<predicted average view duration>",
  "virality_prediction": "<realistic viral ceiling>",
  "quick_wins": ["<easy fix under 10 minutes>", "<another>"],
  "high_priority_fixes": [
    "<EXACT visual/audio/script instruction>",
    "<another>",
    "<another>"
  ],
  "ten_improved_titles": [
    "<title 1>","<title 2>","<title 3>","<title 4>","<title 5>",
    "<title 6>","<title 7>","<title 8>","<title 9>","<title 10>"
  ],
  "five_thumbnail_concepts": [
    "<concept 1: what to show, text, colors, layout>",
    "<concept 2>","<concept 3>","<concept 4>","<concept 5>"
  ],
  "content_team_checklist": [
    "[ ] <checkbox item>","[ ] <another>","[ ] <another>","[ ] <another>"
  ],
  "final_verdict": "<harsh 2-3 sentence summary>",
  "rewritten_hook": "<word-for-word first 20 seconds script + visual direction in brackets>",
  "script_line_by_line": [
    {{"original": "<exact line the creator said>", "problem": "<what is wrong>", "rewrite": "<exact replacement>"}},
    {{"original": "<exact line>", "problem": "<problem>", "rewrite": "<replacement>"}},
    {{"original": "<exact line>", "problem": "<problem>", "rewrite": "<replacement>"}}
  ],
  "full_60s_script": "<complete rewritten 60-second script with [visual direction] markers throughout — make it punchy, hook-first, specific>",
  "story_arc": {{
    "phase_1_setup": "<what the video establishes in the first 20% — be specific>",
    "phase_2_tension": "<what conflict or problem is introduced — be specific>",
    "phase_3_resolution": "<how it resolves or fails to — be specific>",
    "emotional_peaks": ["<moment 1 where emotion is highest>", "<moment 2>"],
    "arc_verdict": "<Strong/Weak/Missing>",
    "storytelling_fix": "<exact instruction: what scene to add, what line to say, where to put it>"
  }},
  "upload_strategy": {{
    "best_days": ["<day1>", "<day2>"],
    "best_time_utc": "<HH:MM UTC>",
    "reasoning": "<why these times based on content niche and audience>",
    "metadata_fixes": {{
      "title_rewrite": "<improved title>",
      "description_first_line": "<first 2 sentences of description — most important for SEO>",
      "must_add_tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"]
    }},
    "chapter_timestamps": ["00:00 - <chapter name>", "01:30 - <chapter name>", "03:00 - <chapter name>"]
  }},
  "video_watch_report": {{
    "worst_moment": "{vision['worst_segment']}",
    "av_sync_verdict": "{vision['av_sync_verdict']}",
    "edit_pacing_verdict": "<{cuts_per_min} cuts/min — engaging or boring>",
    "retention_curve": "<predict exact drop-off moments and why>"
  }},
  "audio_analysis": {{
    "verdict": "<professional or amateurish — specific>",
    "filler_word_problem": "<{sig['filler_pct']}% fillers — exact impact>",
    "pacing_verdict": "<{sig['wpm']} wpm — effect on retention>",
    "audio_visual_sync": "<full sync verdict>",
    "script_quality": "<tight/rambling — what lines to cut>"
  }},
  "performance_prediction": {{
    "predicted_views_30_days": "<honest number range like 500-1,200 — based on score {final_score}/100 and content quality>",
    "predicted_avg_view_duration": "<time like 1:10 — based on hook score {hook_10}/10, retention {retention_10}/10, script quality>",
    "predicted_watch_time_hours": "<total hours estimate for first 30 days>",
    "predicted_new_subscribers": "<realistic number like 1-5 — based on content quality score>",
    "ctr_estimate": "<percentage like 1.8% — based on visual score {visual_10}/10>",
    "confidence": "Medium",
    "what_will_hurt_most": "<the single biggest thing limiting reach — be very specific>",
    "what_could_boost_it": "<the single change that would most improve performance — be very specific>"
  }}
}}"""

    hook_frame = frames[0] if frames else None
    if hook_frame:
        messages = [
            {"role":"system","content":CRITIC_SYSTEM},
            {"role":"user","content":[
                {"type":"image_url","image_url":{"url":f"data:{hook_frame['mime']};base64,{hook_frame['b64']}"}},
                {"type":"text","text":critique}
            ]}
        ]
        model = VISION_MODEL
    else:
        messages = [{"role":"system","content":CRITIC_SYSTEM},
                    {"role":"user","content":critique}]
        model = TEXT_MODEL

    try:
        r = _groq_call(client, model=model, messages=messages, max_tokens=4500, temperature=0.15)
        result = _parse_json(r.choices[0].message.content)
    except Exception:
        result = {}

    # Extended scores for upload mode
    seo_10           = _score_seo_standalone_10([], "")
    audience_fit_10  = _score_audience_fit_10("", [], "")
    engagement_10    = _score_engagement_10(hook_10, story_10, retention_10)
    branding_10      = _score_branding_10(visual_10, title_dim_10)
    technical_10     = _score_technical_quality_10(audio_10, visual_10)
    algorithm_fit_10 = _score_algorithm_fit_10([], "", seo_10, 5)
    monetization_10  = _score_monetization_10("", "", transcript or "")
    tier             = _performance_tier(final_score)

    # Enforce all Python-computed values
    result["overall_score"]    = final_score
    result["virality_score"]   = final_score
    result["grade"]            = grade
    result["performance_tier"] = tier
    result["scores"] = {
        "hook": hook_10, "story": story_10, "script": script_10,
        "audio": audio_10, "visual": visual_10, "editing": editing_10,
        "retention": retention_10, "thumbnail": None,
        "title": title_dim_10, "virality": virality_10,
    }
    result["extended_scores"] = {
        "seo": seo_10, "audience_fit": audience_fit_10,
        "engagement": engagement_10, "branding": branding_10,
        "technical_quality": technical_10, "algorithm_fit": algorithm_fit_10,
        "monetization_safety": monetization_10,
    }
    result["breakdown"] = {**result["scores"], **result["extended_scores"]}
    result["video_stats"] = {
        "duration_sec":    round(duration_sec),
        "frames_analyzed": len(frames),
        "scene_cuts":      cut_count,
        "cuts_per_min":    cuts_per_min,
        "av_sync":         vision["av_sync_verdict"],
        "high_risk_moments": vision["high_risk_moments"],
    }
    if "audio_analysis" not in result:
        result["audio_analysis"] = {
            "verdict":             "Audio analysis unavailable",
            "filler_word_problem": f"{sig['filler_pct']}% filler words",
            "pacing_verdict":      f"{sig['wpm']} wpm",
            "audio_visual_sync":   vision["av_sync_verdict"],
            "script_quality":      "Cannot assess",
        }
    return result


def analyze_post_timing(image_path: str) -> dict:
    """Read a YouTube Analytics screenshot and return concrete posting schedule recommendations."""
    client = _client()
    try:
        b64, mime = _b64(image_path)
    except Exception as e:
        raise ValueError(f"Could not read image: {e}")

    prompt = """You are reading a YouTube Analytics screenshot. Identify: audience activity heatmap times, best performing days, audience demographics if visible. Give concrete posting schedule recommendations.

Look at the image carefully for:
- "When your viewers are on YouTube" heatmap (days of week + hours)
- Any audience retention or demographics data visible
- Any performance trends visible

Return JSON only — no markdown:
{
  "best_days": ["<day1>", "<day2>"],
  "best_times_utc": ["<HH:MM>", "<HH:MM>"],
  "audience_peak_hours": "<what the screenshot shows about peak activity — be specific>",
  "reasoning": "<plain English explanation of why these times — reference what you saw in the screenshot>",
  "title_tips": "<based on what content niche this appears to be — give 2-3 title improvement tips>",
  "description_tips": "<2-3 SEO tips for description based on the channel niche you can infer>",
  "tag_suggestions": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
  "posting_plan": "<week-by-week posting schedule recommendation — be specific with days and times>"
}"""

    try:
        r = _groq_call(client,
            model=VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt}
            ]}],
            max_tokens=900, temperature=0.1,
        )
        result = _parse_json(r.choices[0].message.content)
    except Exception as e:
        # Sensible defaults if vision model fails
        result = {
            "best_days": ["Saturday", "Sunday"],
            "best_times_utc": ["14:00", "18:00"],
            "audience_peak_hours": "Could not read the screenshot clearly.",
            "reasoning": f"Analysis failed: {str(e)[:100]}. Defaults shown are general YouTube best practices.",
            "title_tips": "Use numbers, power words, and a clear benefit in your title.",
            "description_tips": "Put your main keyword in the first sentence of your description.",
            "tag_suggestions": ["youtube", "viral", "tutorial", "tips", "howto"],
            "posting_plan": "Post 2-3 times per week, focusing on Saturday and Sunday afternoons.",
        }
    return result


def compare_competitors(main_title: str, competitors: list[dict]) -> dict:
    if not competitors:
        return {"summary":"No competitor data.", "insights":[]}
    client = _client()
    lines = "\n".join(f'{i+1}. "{c["title"]}" by {c["channel"]}' for i,c in enumerate(competitors))
    r = _groq_call(client,
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
