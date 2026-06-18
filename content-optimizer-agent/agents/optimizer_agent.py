import os
import json
import urllib.request
import urllib.error


class OptimizerAgent:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set in environment")
        self.model = "llama-3.3-70b-versatile"
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def _call(self, prompt: str) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 6000,
            "temperature": 0.5
        }).encode()
        req = urllib.request.Request(
            self.url, data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "python-requests/2.31.0"
            }
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()

    def optimize(
        self,
        title: str,
        description: str,
        tags: list[str],
        hashtags: list[str],
        modes: list[str],
        niche: str = "",
        language: str = "English"
    ) -> dict:

        modes_str = ", ".join(modes) if modes else "SEO, SXO, AEO, GEO"
        tags_str = ", ".join(tags)
        hashtags_str = " ".join(hashtags)
        niche_str = f"\nNICHE/TOPIC: {niche}" if niche else ""

        prompt = f"""You are a YouTube + Social Media Content Optimization expert who applies SEO, SXO, AEO, and GEO frameworks used by professional SEO tools.

CONTENT TO ANALYZE:
Title: {title}
Description: {description}
Tags: {tags_str}
Hashtags: {hashtags_str}{niche_str}
Language: {language}
Optimization Modes Requested: {modes_str}

SCORING FRAMEWORKS:

SEO (Search Engine Optimization):
- Title: 60-70 chars ideal, primary keyword in first 3 words, no clickbait
- Description: first 150 chars must hook (shown in search), keyword density 1-2%, call to action
- Tags: 10-15 tags, mix of broad+specific+long-tail, no keyword stuffing
- Hashtags: 3-5 relevant, no spam
- Score on: keyword placement, title length, description quality, tag diversity, CTR potential

SXO (Search Experience Optimization):
- Intent alignment: does content type match what users expect for this topic?
- User story clarity: can user immediately tell what they'll get?
- Page-type match: tutorial/review/list/comparison/vlog — is the format declared?
- CTA strength: is there a clear next action?
- Score on: intent match, content format clarity, user journey logic, CTA presence

AEO (Answer Engine Optimization):
- Direct answer in first 2 sentences of description
- Question-based signals: does title/description answer a specific question?
- Quotable facts/stats present?
- FAQ-style structure signals?
- Self-contained answer blocks (134-167 word passages for AI citation)
- Score on: directness, question targeting, factual density, quotability, AI snippet readiness

GEO (Generative Engine Optimization):
- AI citation readiness (brand mentions, YouTube has 0.737 correlation with AI citations)
- Entity presence: named entities (people, places, tools, brands) mentioned?
- Passage citability: are there self-contained, quotable 134-167 word blocks?
- Freshness signals: dates, version numbers, "2025/2026" signals?
- Brand signal diversity: cross-platform visibility signals?
- AI crawler friendliness: structured, semantic, entity-rich content?
- Score on: entity density, citability, brand signals, freshness, AI discoverability

Return ONLY a JSON object (no markdown, no explanation):

{{
  "scores": {{
    "seo": {{
      "score": 0,
      "wins": ["what is already good"],
      "issues": ["what needs fixing with specific reason"]
    }},
    "sxo": {{
      "score": 0,
      "wins": [],
      "issues": []
    }},
    "aeo": {{
      "score": 0,
      "wins": [],
      "issues": []
    }},
    "geo": {{
      "score": 0,
      "wins": [],
      "issues": []
    }},
    "overall": 0,
    "grade": "A/B/C/D/F",
    "summary": "2-sentence overall verdict"
  }},
  "optimized": {{
    "title": "optimized YouTube title (60-70 chars, keyword-first)",
    "title_char_count": 0,
    "description": "full optimized YouTube description (300-500 words): hook in first 150 chars, timestamps section, about section, keywords naturally woven in, CTA, links placeholders, hashtags at end)",
    "tags": ["tag1", "tag2"],
    "hashtags": ["#tag1", "#tag2"]
  }},
  "captions": {{
    "facebook": "Facebook caption (150-300 words, conversational, question hook, emoji, CTA to watch video, 2-3 hashtags)",
    "instagram": "Instagram caption (100-150 words, punchy opener, line breaks for readability, 10-15 hashtags at end, CTA)",
    "tiktok": "TikTok caption (50-80 words, trend-aware language, energetic, 3-5 hashtags, challenge or duet CTA if relevant)",
    "twitter": "X/Twitter caption (max 250 chars, punchy, thread hook or question, 1-2 hashtags, link CTA)",
    "linkedin": "LinkedIn caption (200-300 words, professional tone, insight-led hook, what you learned/takeaway, CTA to watch, 3 hashtags)"
  }},
  "improvements": {{
    "critical": ["urgent fixes that hurt visibility"],
    "high": ["important improvements"],
    "medium": ["good to have optimizations"],
    "quick_wins": ["easy changes with big impact"]
  }}
}}

Rules:
- All scores: integers 0-100
- overall = weighted average: SEO 30% + SXO 20% + AEO 25% + GEO 25%
- wins/issues: 2-4 items each, specific and actionable
- optimized.tags: 12-15 tags as a JSON array of strings
- optimized.hashtags: 5-6 hashtags as a JSON array starting with #
- Each caption must be platform-native in tone and format
- Write everything in {language}
- Return ONLY the JSON"""

        raw = self._call(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
