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

import os, re, json, base64, tempfile, math, time
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
    """Convert visual facts to 0-100 score. Ceiling is 72 — no thumbnail
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

    r = _groq_call(client,
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

    r = _groq_call(client,
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


def analyze_uploaded_video(video_path: str) -> dict:
    client = _client()

    # ── Step 1: Watch the video — extract frames at key moments, detect cuts ──
    frames, duration_sec, cut_count = _extract_video_frames(video_path)

    # ── Step 2: Transcribe audio ──
    transcript = _extract_audio(video_path)
    sig = _audio_signals(transcript, duration_sec)

    # ── Step 3: Analyze each frame + audio-visual sync ──
    vision = _analyze_frame_sequence(frames, transcript, duration_sec, client)

    # ── Step 4: Score everything in Python ──
    hook_score   = _score_audio(sig)
    audio_score  = hook_score
    visual_score = vision["avg_visual"]
    pacing       = _pacing_score(cut_count, duration_sec, sig["wpm"])
    title_score  = 50
    seo_score    = 50

    content = _content_score(hook_score, audio_score, visual_score, title_score, seo_score)
    unproven_perf = 25
    final = max(2, min(98, round(unproven_perf * 0.60 + content * 0.40)))
    grade = _grade(final)

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

SCORES (do not change):
Hook:{hook_score} | Visual:{visual_score} | Pacing:{pacing} | Content:{content} | Final:{final} ({grade})

TRANSCRIPT (first 1200 chars):
{transcript[:1200] if transcript else "NO AUDIO DETECTED"}

Write a brutal, timestamped critique. Reference specific moments you observed.
Name the exact second things go wrong. Do not invent positives.

Return JSON only:
{{
  "virality_score": {final},
  "grade": "{grade}",
  "first_impression": "<what a cold viewer sees and hears in seconds 0-3 — be specific>",
  "breakdown": {{
    "hook_strength": {hook_score},
    "visual_quality": {visual_score},
    "engagement_signals": {unproven_perf},
    "pacing": {pacing},
    "content_depth": {content}
  }},
  "video_watch_report": {{
    "worst_moment": "{vision['worst_segment']}",
    "av_sync_verdict": "{vision['av_sync_verdict']}",
    "edit_pacing_verdict": "<{cuts_per_min} cuts/min — engaging or boring — what to change>",
    "retention_curve": "<predict exact moments viewers drop off and why, based on what was observed>",
    "segment_verdicts": [{{"label": "...", "problem": "..."}}]
  }},
  "audio_analysis": {{
    "verdict": "<professional or amateurish — name specific problems heard>",
    "transcript_summary": "<what was said in first 30 seconds>",
    "filler_word_problem": "<{sig['filler_pct']}% fillers — exact impact on credibility>",
    "pacing_verdict": "<{sig['wpm']} wpm — effect on retention>",
    "audio_visual_sync": "<full sync verdict with specific broken moments named>",
    "script_quality": "<tight/rambling — what lines to cut>"
  }},
  "hook_analysis": {{
    "verdict": "<did the first 3 seconds earn attention — be harsh>",
    "what_top_creators_do_instead": "<how a top creator would open this video>",
    "rewritten_opening": "<word-for-word replacement script for first 20 seconds>"
  }},
  "production_issues": ["<timestamped specific issue>", "<another>", "<another>"],
  "optimization_tips": ["<fix 1>", "<fix 2>", "<fix 3>", "<fix 4>", "<fix 5>"],
  "viral_potential": "<Low/Medium/High/Very High>",
  "estimated_improvement": "<realistic view count if all fixes applied — and why>"
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
        r = _groq_call(client, model=model, messages=messages, max_tokens=2400, temperature=0.15)
        result = _parse_json(r.choices[0].message.content)
    except Exception:
        result = {}

    result["virality_score"] = final
    result["grade"] = grade
    result["breakdown"] = {
        "hook_strength":      hook_score,
        "visual_quality":     visual_score,
        "engagement_signals": unproven_perf,
        "pacing":             pacing,
        "content_depth":      content,
    }
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
            "verdict":          "Audio analysis unavailable",
            "transcript_summary": transcript[:200] if transcript else "No audio detected",
            "filler_word_problem": f"{sig['filler_pct']}% filler words",
            "pacing_verdict":   f"{sig['wpm']} wpm",
            "audio_visual_sync": vision["av_sync_verdict"],
            "script_quality":   "Cannot assess",
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
