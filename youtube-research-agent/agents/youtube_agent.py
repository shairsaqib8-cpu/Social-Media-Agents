import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class YouTubeAgent:
    def __init__(self):
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY not set in environment")
        self.youtube = build("youtube", "v3", developerKey=api_key)

    def get_trending_videos(self, region_code: str = "US", max_results: int = 20) -> list[dict]:
        """Fetch trending videos from YouTube."""
        try:
            response = self.youtube.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode=region_code,
                maxResults=max_results,
            ).execute()

            videos = []
            for item in response.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                videos.append({
                    "id": item["id"],
                    "title": snippet["title"],
                    "channel": snippet["channelTitle"],
                    "published_at": snippet["publishedAt"],
                    "description": snippet.get("description", "")[:200],
                    "tags": snippet.get("tags", [])[:10],
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "thumbnail": snippet["thumbnails"].get("medium", {}).get("url", ""),
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                })
            return videos
        except HttpError as e:
            raise RuntimeError(f"YouTube API error: {e}")

    def search_videos(self, query: str, max_results: int = 20,
                      exclude_channel_id: str | None = None,
                      order: str = "viewCount") -> list[dict]:
        """Search YouTube videos for a keyword, optionally excluding a channel."""
        try:
            search_response = self.youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                order=order,
                maxResults=min(max_results + 10, 50),  # fetch extra to cover exclusions
            ).execute()

            items = search_response.get("items", [])

            # Exclude the target channel's own videos
            if exclude_channel_id:
                items = [i for i in items
                         if i["snippet"].get("channelId") != exclude_channel_id]

            video_ids = [item["id"]["videoId"] for item in items[:max_results]]
            if not video_ids:
                return []

            stats_response = self.youtube.videos().list(
                part="statistics,snippet",
                id=",".join(video_ids),
            ).execute()

            videos = []
            for item in stats_response.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                # Skip if this video belongs to the excluded channel
                if exclude_channel_id and snippet.get("channelId") == exclude_channel_id:
                    continue
                videos.append({
                    "id": item["id"],
                    "title": snippet["title"],
                    "channel": snippet["channelTitle"],
                    "published_at": snippet["publishedAt"],
                    "tags": snippet.get("tags", [])[:10],
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "thumbnail": snippet["thumbnails"].get("medium", {}).get("url", ""),
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                })
            return sorted(videos, key=lambda x: x["view_count"], reverse=True)
        except HttpError as e:
            raise RuntimeError(f"YouTube API error: {e}")

    def get_channel_profile(self, channel_name: str) -> dict:
        """Fetch full channel profile: description, keywords, category, subscriber count."""
        try:
            # Step 1: find channel ID
            search_response = self.youtube.search().list(
                part="snippet", q=channel_name, type="channel", maxResults=1,
            ).execute()
            if not search_response.get("items"):
                return {"error": f"Channel '{channel_name}' not found"}

            ch_item = search_response["items"][0]
            channel_id = ch_item["id"]["channelId"]
            channel_title = ch_item["snippet"]["title"]

            # Step 2: fetch full channel details including description & keywords
            ch_response = self.youtube.channels().list(
                part="snippet,brandingSettings,statistics,topicDetails",
                id=channel_id,
            ).execute()

            ch_data = ch_response.get("items", [{}])[0]
            snippet = ch_data.get("snippet", {})
            branding = ch_data.get("brandingSettings", {}).get("channel", {})
            stats = ch_data.get("statistics", {})
            topics = ch_data.get("topicDetails", {})

            description = snippet.get("description", "")
            keywords_raw = branding.get("keywords", "")  # space-separated string
            country = snippet.get("country", "")
            subscriber_count = int(stats.get("subscriberCount", 0))
            topic_categories = topics.get("topicCategories", [])  # Wikipedia URLs

            # Parse channel keywords (quoted phrases or single words)
            import re
            kw_list = re.findall(r'"([^"]+)"|(\S+)', keywords_raw)
            channel_keywords = [a or b for a, b in kw_list]

            # Extract topic labels from Wikipedia URLs (e.g. ".../Entertainment" → "Entertainment")
            topic_labels = [url.rstrip("/").split("/")[-1].replace("_", " ") for url in topic_categories]

            return {
                "channel": channel_title,
                "channel_id": channel_id,
                "description": description[:500],
                "channel_keywords": channel_keywords[:15],
                "topic_labels": topic_labels,
                "country": country,
                "subscriber_count": subscriber_count,
            }
        except HttpError as e:
            raise RuntimeError(f"YouTube API error: {e}")

    def get_channel_top_videos(self, channel_name: str, max_results: int = 10) -> dict:
        """Analyze a competitor channel's top videos."""
        try:
            # Search for the channel
            search_response = self.youtube.search().list(
                part="snippet", q=channel_name, type="channel", maxResults=1,
            ).execute()

            if not search_response.get("items"):
                return {"error": f"Channel '{channel_name}' not found"}

            channel_item = search_response["items"][0]
            channel_id = channel_item["id"]["channelId"]
            channel_title = channel_item["snippet"]["title"]

            # Fetch full channel details for description + keywords
            ch_response = self.youtube.channels().list(
                part="snippet,brandingSettings,topicDetails",
                id=channel_id,
            ).execute()
            ch_data = ch_response.get("items", [{}])[0]
            description = ch_data.get("snippet", {}).get("description", "")[:300]
            keywords_raw = ch_data.get("brandingSettings", {}).get("channel", {}).get("keywords", "")
            import re
            kw_list = re.findall(r'"([^"]+)"|(\S+)', keywords_raw)
            channel_keywords = [a or b for a, b in kw_list][:10]
            topic_urls = ch_data.get("topicDetails", {}).get("topicCategories", [])
            topic_labels = [u.rstrip("/").split("/")[-1].replace("_", " ") for u in topic_urls]

            # Get channel's top videos
            videos_response = self.youtube.search().list(
                part="snippet", channelId=channel_id,
                order="viewCount", type="video", maxResults=max_results,
            ).execute()

            video_ids = [item["id"]["videoId"] for item in videos_response.get("items", [])]
            if not video_ids:
                return {"channel": channel_title, "top_videos": [], "common_tags": [],
                        "description": description, "channel_keywords": channel_keywords, "topic_labels": topic_labels}

            stats_response = self.youtube.videos().list(
                part="statistics,snippet", id=",".join(video_ids),
            ).execute()

            videos = []
            all_tags = []
            for item in stats_response.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                tags = snippet.get("tags", [])[:10]
                all_tags.extend(tags)
                videos.append({
                    "title": snippet["title"],
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "tags": tags,
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                })

            return {
                "channel": channel_title,
                "channel_id": channel_id,
                "description": description,
                "channel_keywords": channel_keywords,
                "topic_labels": topic_labels,
                "top_videos": sorted(videos, key=lambda x: x["view_count"], reverse=True),
                "common_tags": list(set(all_tags))[:20],
            }
        except HttpError as e:
            raise RuntimeError(f"YouTube API error: {e}")

    def extract_keywords_from_videos(self, videos: list[dict]) -> list[str]:
        """Extract and deduplicate keywords/tags from a list of videos."""
        all_tags = []
        for video in videos:
            all_tags.extend(video.get("tags", []))
        # Count frequency
        tag_counts: dict[str, int] = {}
        for tag in all_tags:
            tag = tag.lower()
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        # Sort by frequency
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        return [tag for tag, _ in sorted_tags[:50]]
