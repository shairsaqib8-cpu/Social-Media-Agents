import time
from pytrends.request import TrendReq


class TrendsAgent:
    def __init__(self):
        self.pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))

    def get_trending_searches(self, geo: str = "US") -> list[str]:
        """Get today's trending searches."""
        try:
            trending = self.pytrends.trending_searches(pn=geo)
            return trending[0].tolist()[:20]
        except Exception as e:
            return [f"Error fetching trends: {str(e)}"]

    def get_interest_over_time(self, keywords: list[str], timeframe: str = "today 3-m") -> dict:
        """Get interest over time for a list of keywords (max 5 at a time)."""
        # Google Trends allows max 5 keywords per request
        keywords = keywords[:5]
        try:
            self.pytrends.build_payload(keywords, timeframe=timeframe, geo="US")
            time.sleep(1)  # Avoid rate limiting
            data = self.pytrends.interest_over_time()
            if data.empty:
                return {}
            data = data.drop(columns=["isPartial"], errors="ignore")
            return data.tail(12).to_dict()  # Last 12 weeks
        except Exception as e:
            return {"error": str(e)}

    def get_related_queries(self, keyword: str) -> dict:
        """Get related queries (rising and top) for a keyword."""
        try:
            self.pytrends.build_payload([keyword], timeframe="today 3-m", geo="US")
            time.sleep(1)
            related = self.pytrends.related_queries()
            result = {}
            kw_data = related.get(keyword, {})
            if kw_data.get("top") is not None:
                result["top"] = kw_data["top"]["query"].tolist()[:10]
            if kw_data.get("rising") is not None:
                result["rising"] = kw_data["rising"]["query"].tolist()[:10]
            return result
        except Exception as e:
            return {"error": str(e)}

    def compare_keywords(self, keywords: list[str]) -> dict:
        """Compare search interest of multiple keywords."""
        keywords = keywords[:5]
        try:
            self.pytrends.build_payload(keywords, timeframe="today 3-m", geo="US")
            time.sleep(1)
            data = self.pytrends.interest_over_time()
            if data.empty:
                return {}
            data = data.drop(columns=["isPartial"], errors="ignore")
            averages = data.mean().to_dict()
            return {kw: round(float(avg), 1) for kw, avg in averages.items()}
        except Exception as e:
            return {"error": str(e)}
