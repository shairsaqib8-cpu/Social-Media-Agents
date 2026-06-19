"""
Script Optimizer Agent — Core Analysis Engine
22-dimension scoring framework based on research-backed YouTube performance parameters.
"""
import os, re, json, time
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
MODEL = "llama-3.1-8b-instant"

# ── Retry wrapper ──────────────────────────────────────────────────────────────
def _call(messages, max_tokens=4000, temperature=0.4):
    for attempt in range(4):
        try:
            r = client.chat.completions.create(
                model=MODEL, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
                response_format={"type": "json_object"},
                timeout=60,
            )
            return r.choices[0].message.content
        except Exception as e:
            err = str(e)
            if ("429" in err or "rate_limit" in err) and attempt < 3:
                wait = [15, 30, 60][attempt]
                time.sleep(wait)
            elif "json_validate_failed" in err or "max completion" in err:
                # JSON truncated — return partial raw text for fallback parsing
                import re as _re
                m = _re.search(r"'failed_generation':\s*'(.*?)'", err, _re.DOTALL)
                return m.group(1) if m else "{}"
            else:
                raise

# ── Pure-Python scoring (AI cannot override these) ────────────────────────────
def _compute_scores(script: str) -> dict:
    words  = script.split()
    sents  = re.split(r'[.!?]+', script)
    sents  = [s.strip() for s in sents if len(s.strip()) > 3]
    n_sent = max(len(sents), 1)
    n_word = max(len(words), 1)

    # 1. Hook speed — how quickly the hook fires (first 50 words)
    first_50 = " ".join(words[:50]).lower()
    hook_triggers = ["you", "imagine", "what if", "did you", "here's", "stop",
                     "secret", "never", "always", "biggest", "mistake", "truth",
                     "warning", "most", "i was", "the real", "nobody", "this is"]
    hook_hits = sum(1 for t in hook_triggers if t in first_50)
    hook_speed_10 = min(10, round(2 + hook_hits * 1.2))

    # 2. Second-person dominance ("you/your" ratio)
    you_count = len(re.findall(r'\byou\b|\byour\b|\byourself\b', script, re.I))
    they_count = len(re.findall(r'\bthey\b|\bpeople\b|\bviewers\b|\beveryone\b', script, re.I))
    ratio = you_count / max(you_count + they_count, 1)
    second_person_10 = min(10, round(ratio * 12))

    # 3. Specificity — count concrete numbers, names, dates
    specifics = len(re.findall(r'\b\d[\d,\.%$]*\b|\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', script, re.I))
    specificity_10 = min(10, round(2 + specifics * 0.6))

    # 4. Sentence length variance — standard deviation of word counts
    sent_lengths = [len(s.split()) for s in sents]
    if len(sent_lengths) > 1:
        mean = sum(sent_lengths) / len(sent_lengths)
        variance = sum((x - mean)**2 for x in sent_lengths) / len(sent_lengths)
        std = variance ** 0.5
        variance_10 = min(10, round(std * 0.8))
    else:
        variance_10 = 1

    # 5. Active voice — passive indicators
    passive = len(re.findall(r'\b(is|are|was|were|be|been|being)\s+\w+ed\b', script, re.I))
    passive_ratio = passive / n_sent
    active_voice_10 = min(10, max(1, round(10 - passive_ratio * 15)))

    # 6. Pattern interrupt frequency — shift markers every ~45s (≈100 words)
    interrupts = len(re.findall(
        r'\b(but wait|however|actually|here\'s the thing|plot twist|now here\'s|'
        r'you might think|wrong|the truth|in fact|surprisingly|here\'s what|'
        r'stop|think about|imagine|picture this|look at|consider|real talk)\b',
        script, re.I))
    sections = max(1, n_word // 100)
    interrupt_density = interrupts / sections
    pattern_interrupt_10 = min(10, round(interrupt_density * 3.5 + 2))

    # 7. Open loop markers
    loops = len(re.findall(
        r'\b(more on that|i\'ll explain|you\'ll see|coming up|stay with|'
        r'but first|before i|we\'ll get to|in a moment|hold that thought|'
        r'keep watching|find out|reveal|later in|by the end)\b',
        script, re.I))
    open_loops_10 = min(10, round(2 + loops * 1.5))

    # 8. Power word density
    power = len(re.findall(
        r'\b(secret|never|always|ultimate|best|worst|biggest|most|least|'
        r'free|instant|proven|guaranteed|exclusive|shocking|incredible|'
        r'dangerous|warning|critical|essential|massive|huge|tiny|simple|easy|'
        r'fast|quick|exact|real|truth|myth|mistake|hack|trick|strategy)\b',
        script, re.I))
    power_density = power / max(n_word / 100, 1)
    power_word_10 = min(10, round(power_density * 2))

    # 9. Readability — avg words per sentence (target 15-20)
    avg_sent = n_word / n_sent
    if 12 <= avg_sent <= 22:
        readability_10 = 9
    elif 8 <= avg_sent < 12 or 22 < avg_sent <= 30:
        readability_10 = 6
    else:
        readability_10 = 3

    # 10. Callback markers
    callbacks = len(re.findall(
        r'\b(remember|earlier|i mentioned|like i said|as i said|back to|'
        r'going back|recall|that\'s why|which brings|that\'s the reason)\b',
        script, re.I))
    callbacks_10 = min(10, round(2 + callbacks * 1.8))

    # 11. CTA presence (soft metric)
    cta = len(re.findall(
        r'\b(subscribe|comment|like|share|click|watch|follow|join|download|'
        r'check out|let me know|tell me|drop a|hit the)\b',
        script, re.I))
    cta_10 = min(10, max(1, round(cta * 1.5 + 1)))

    # 12. Jargon penalty — unknown tech words (very rough heuristic)
    long_words = [w for w in words if len(w) > 12 and not re.match(r'\d', w)]
    jargon_ratio = len(long_words) / n_word
    clarity_10 = min(10, max(1, round(10 - jargon_ratio * 60)))

    scores = {
        "hook_speed":         hook_speed_10,
        "second_person":      second_person_10,
        "specificity":        specificity_10,
        "sentence_variance":  variance_10,
        "active_voice":       active_voice_10,
        "pattern_interrupts": pattern_interrupt_10,
        "open_loops":         open_loops_10,
        "power_words":        power_word_10,
        "readability":        readability_10,
        "callbacks":          callbacks_10,
        "cta_quality":        cta_10,
        "clarity":            clarity_10,
    }
    overall = round(sum(scores.values()) / len(scores) * 10)
    return scores, overall


# ── AI deep analysis ──────────────────────────────────────────────────────────
def analyze_script(script: str, title: str = "", audience: str = "", niche: str = "") -> dict:
    scores, overall = _compute_scores(script)

    word_count = len(script.split())
    est_duration_min = round(word_count / 140, 1)

    context = f"""
TITLE: {title or "(none provided)"}
NICHE/TOPIC: {niche or "(not specified)"}
TARGET AUDIENCE: {audience or "(not specified)"}
ESTIMATED VIDEO DURATION: ~{est_duration_min} minutes ({word_count} words)
PRE-COMPUTED SCORES: {json.dumps(scores)}

SCRIPT (first 1200 chars):
\"\"\"
{script[:1200]}
\"\"\"
"""

    prompt = f"""YouTube script coach. Analyze the script below and return ONLY a valid JSON object.

{context}

Return this exact JSON structure (English only, keep all values concise — 1 sentence max per field):
{{"hook_type":"<Bold Claim|Question|Result-First|Cold Open|Direct Promise|Scenario|Shocking Statistic|Controversy|None/Weak>","storytelling_framework":"<Three-Act|PAS|AIDA|BAB|Hero's Journey|StoryBrand|MrBeast Survival|None/Unclear>","content_purpose":"<Education|Entertainment|Sales|Brand Awareness|Community|Lead Generation|Authority Building>","audience_intelligence":{{"target_audience":"<who>","audience_intent":"<Learn|Entertain|Buy|Engage|Share>","skill_level":"<Beginner|Intermediate|Expert>","global_relevance":"<High|Medium|Low + reason>","language_simplicity_score":"<1-10>","cultural_issues":"<issues or none>"}},"psychological_analysis":{{"curiosity_gaps":["<gap>"],"emotional_triggers":["<trigger>"],"social_proof":"<present or absent>","authority_cues":"<present or absent>","decision_influence":"<1 sentence>","zeigarnik_loops":"<quote or NONE>"}},"hook_performance":{{"first_3s":"<captured or lost>","first_5s":"<yes/no interrupt>","first_10s":"<promise clear yes/no>","first_30s":"<keep watching reason>","retention_probability":"<Low|Medium|High>"}},"hook_verdict":"<1 sentence>","hook_alternatives":["<Bold Claim>","<Question>","<Scenario>","<Shocking Stat>","<Cold Open>"],"storytelling_verdict":"<2 sentences>","arc_breakdown":{{"setup":"<1 sentence>","tension":"<quote or MISSING>","resolution":"<1 sentence>","emotional_journey":"<emotion sequence>","arc_fix":"<1 sentence exact fix>"}},"connectivity_verdict":"<1-2 sentences>","weak_transitions":[{{"location":"<quote>","fix":"<replacement>"}}],"open_loops_found":["<quote>"],"missing_open_loop":"<exact line + where>","pattern_interrupts_found":["<quote>"],"missing_interrupt":"<exact line + where>","re_hook_exists":false,"re_hook_location":"<quote or MISSING>","re_hook_fix":"<exact line>","style_verdict":"<2 sentences>","style_issues":[{{"bad":"<exact quote>","good":"<rewrite>"}}],"pacing_verdict":"<1-2 sentences>","pacing_fixes":["<fix>"],"emotional_arc_score":"<Low|Medium|High>","emotional_arc_verdict":"<which of 6 drivers present, which missing>","stakes_clarity":"<Clear|Weak|Missing>","stakes_fix":"<exact line for first 30s>","specificity_issues":[{{"vague":"<phrase>","specific":"<with number/name/date>"}}],"power_words_used":["<word>"],"power_words_missing":["<word>","<word>","<word>"],"cta_verdict":"<1 sentence>","cta_fix":"<exact line + placement>","global_adaptation":{{"language_issues":["<issue>"],"simplification_suggestions":["<suggestion>"],"accent_neutrality":"<neutral or regional>","international_scalability":"<High|Medium|Low>"}},"improvement_roadmap":{{"high_impact":["<fix>","<fix>","<fix>"],"medium_impact":["<fix>","<fix>"],"low_impact":["<fix>"]}},"critical_issues":["<issue 1>","<issue 2>","<issue 3>"],"quick_wins":["<fix>","<fix>","<fix>"],"overall_verdict":"<2 sentences: performance tier + top fix>"}}

Rules: Quote ACTUAL script lines. English output only. Be specific not generic."""

    raw = _call([{"role": "user", "content": prompt}], max_tokens=3500)
    try:
        ai = json.loads(raw)
    except Exception:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        ai = json.loads(match.group()) if match else {}

    # ── Call 2: rewrites only (separate call keeps each request under 6k TPM) ──
    script_preview = script[:1500]
    prompt2 = f"""YouTube script coach. Rewrite and improve this script. Return ONLY valid JSON.

TITLE: {title or "(none)"}
NICHE: {niche or "(none)"}
SCRIPT:
\"\"\"{script_preview}\"\"\"

JSON (English only):
{{"hook_rewrite":"<Punchy 3-5 sentence hook rewrite with [visual cues]>","full_rewritten_script":"<Complete improved script min 200 words with [visual cues]. English only.>","title_suggestions":["<number/power word title>","<curiosity gap title>","<negative framing title>","<result-first title>","<controversy title>"]}}"""

    try:
        raw2 = _call([{"role": "user", "content": prompt2}], max_tokens=2500)
        try:
            ai2 = json.loads(raw2)
        except Exception:
            match = re.search(r'\{.*\}', raw2, re.DOTALL)
            ai2 = json.loads(match.group()) if match else {}
        ai.update(ai2)
    except Exception:
        # Call 2 failed — analysis still returned, rewrites will be empty
        pass

    return {
        "scores": scores,
        "overall": overall,
        "word_count": word_count,
        "est_duration_min": est_duration_min,
        "title": title,
        "audience": audience,
        "niche": niche,
        **ai
    }
