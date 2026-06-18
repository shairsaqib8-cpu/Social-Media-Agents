import os
import json
import urllib.request
import urllib.error


class GEOAgent:
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
            "max_tokens": 4096,
            "temperature": 0.4
        }).encode()
        req = urllib.request.Request(
            self.url, data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}", "User-Agent": "python-requests/2.31.0"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()

    def analyze(self, topic: str, content: str = "", language: str = "English") -> dict:
        content_section = f"\n\nEXISTING CONTENT TO OPTIMIZE:\n{content}" if content.strip() else ""

        prompt = f"""You are a Generative Engine Optimization (GEO) expert. Your job is to help content rank and get cited by AI systems like ChatGPT, Claude, Perplexity, and Google AI Overviews.

TOPIC: {topic}
LANGUAGE: {language}{content_section}

Analyze the topic and return a JSON object with EXACTLY this structure (no markdown, pure JSON):

{{
  "main_topic": "concise topic title",
  "topic_summary": "2-3 sentence clear answer that AI systems can directly quote",
  "entities": [
    {{"name": "entity name", "type": "Concept|Person|Place|Organization|Tool", "relevance": "why this entity matters to the topic"}}
  ],
  "semantic_keywords": {{
    "primary": ["keyword1", "keyword2"],
    "secondary": ["keyword3", "keyword4"],
    "lsi": ["related term 1", "related term 2"]
  }},
  "related_questions": [
    {{"question": "the question", "answer": "direct 1-2 sentence answer AI can cite"}}
  ],
  "content_structure": {{
    "recommended_sections": ["section title 1", "section title 2"],
    "ideal_format": "Article|Guide|Listicle|FAQ|Comparison",
    "word_count_target": 1500,
    "schema_markup": "Article|HowTo|FAQ|BreadcrumbList"
  }},
  "authority_building": [
    {{"tactic": "tactic name", "description": "how to implement it"}}
  ],
  "geo_score": {{
    "clarity": 0,
    "structure": 0,
    "entity_coverage": 0,
    "faq_depth": 0,
    "overall": 0,
    "notes": "what to improve"
  }},
  "optimized_description": "160-char SEO meta description with clear answer",
  "faq_section": [
    {{"q": "question", "a": "answer (2-4 sentences, citable by AI)"}}
  ]
}}

Rules:
- entities: 5-8 items
- semantic_keywords.primary: 3-5, secondary: 5-8, lsi: 5-10
- related_questions: 5-7 items
- content_structure.recommended_sections: 5-7 items
- authority_building: 4-6 tactics
- geo_score fields (clarity, structure, entity_coverage, faq_depth, overall): integers 0-100
- faq_section: 5-6 Q&A pairs
- If existing content was provided, score it and base recommendations on it. Otherwise build from scratch.
- Write in {language}.
- Return ONLY the JSON. No explanation, no markdown fences."""

        raw = self._call(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
