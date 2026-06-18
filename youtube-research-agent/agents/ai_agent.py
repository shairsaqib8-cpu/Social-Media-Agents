import os
import anthropic


class AIAgent:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"

    def generate_content_ideas(
        self,
        niche: str,
        trending_videos: list[dict],
        trending_searches: list[str],
        keywords: list[str],
        competitor_data: list[dict] | None = None,
    ) -> dict:
        """Generate 20 content ideas based on research data."""
        competitor_section = ""
        if competitor_data:
            competitor_section = "\n\nCOMPETITOR TOP VIDEOS:\n"
            for comp in competitor_data:
                channel = comp.get("channel", "Unknown")
                top = comp.get("top_videos", [])[:3]
                competitor_section += f"\nChannel: {channel}\n"
                for v in top:
                    competitor_section += f"  - {v['title']} ({v['view_count']:,} views)\n"

        trending_titles = [v["title"] for v in trending_videos[:10]]

        prompt = f"""You are a YouTube content strategist specializing in the niche: **{niche}**.

RESEARCH DATA:

TRENDING YOUTUBE VIDEOS (this week):
{chr(10).join(f'- {t}' for t in trending_titles)}

TRENDING GOOGLE SEARCHES:
{chr(10).join(f'- {s}' for s in trending_searches[:15])}

POPULAR KEYWORDS FROM TOP VIDEOS:
{', '.join(keywords[:30])}
{competitor_section}

Based on this data, generate exactly 20 YouTube video content ideas for the niche "{niche}".

For each idea, provide:
1. **Title** — compelling, SEO-optimized YouTube title
2. **Hook** — one sentence explaining why viewers will click
3. **Target keyword** — primary keyword to optimize for
4. **Estimated search volume** — Low / Medium / High (based on trends data)
5. **Content gap** — what competitors are missing that this video fills

Format each idea clearly numbered 1-20. Be specific and actionable."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "ideas": message.content[0].text,
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        }

    def analyze_content_gaps(
        self,
        niche: str,
        competitor_videos: list[dict],
        trending_searches: list[str],
    ) -> str:
        """Identify content gaps — topics trending but not covered by competitors."""
        competitor_titles = []
        for comp in competitor_videos:
            for v in comp.get("top_videos", []):
                competitor_titles.append(v["title"])

        prompt = f"""You are a YouTube content strategist. Analyze these data sets for the niche: **{niche}**.

COMPETITOR VIDEO TITLES (what's already covered):
{chr(10).join(f'- {t}' for t in competitor_titles[:30])}

TRENDING SEARCHES (what people want):
{chr(10).join(f'- {s}' for s in trending_searches[:20])}

Identify the top 10 CONTENT GAPS — topics that are trending in searches but NOT well covered by competitors.
For each gap, explain:
- The topic/keyword
- Why it's a gap
- Recommended video angle to dominate this gap"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def analyze_competitor_strategy(self, competitor_data: dict) -> str:
        """Generate a strategic analysis of a competitor channel."""
        channel = competitor_data.get("channel", "Unknown")
        videos = competitor_data.get("top_videos", [])[:10]
        tags = competitor_data.get("common_tags", [])

        video_list = "\n".join(
            f"- {v['title']} ({v['view_count']:,} views)" for v in videos
        )

        prompt = f"""Analyze this YouTube competitor channel: **{channel}**

TOP PERFORMING VIDEOS:
{video_list}

COMMON TAGS USED: {', '.join(tags[:20])}

Provide a strategic analysis covering:
1. What content formula is working for them
2. Their posting patterns and topic themes
3. Weaknesses and blind spots in their content
4. 5 specific ways to outperform them
5. Keywords they rank for that you should target"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
