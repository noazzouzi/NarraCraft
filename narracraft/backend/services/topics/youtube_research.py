"""YouTube transcript research — search YT, get transcripts, extract facts.

Uses youtube-transcript-api for transcripts (no API key needed)
and httpx for YouTube search via Invidious public API.
"""

import re
from dataclasses import dataclass, field

import httpx

# Public Invidious instances for search (no API key needed)
INVIDIOUS_INSTANCES = [
    "https://vid.puffyan.us",
    "https://invidious.snopyta.org",
    "https://yewtu.be",
]


@dataclass
class YouTubeVideo:
    video_id: str
    title: str
    channel: str
    views: int = 0
    description: str = ""


@dataclass
class ExtractedFact:
    text: str
    video_id: str
    video_title: str
    timestamp_start: str = ""
    confidence: str = "medium"  # low, medium, high


async def search_youtube(query: str, limit: int = 10) -> list[YouTubeVideo]:
    """Search YouTube via Invidious API (no API key needed)."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for instance in INVIDIOUS_INSTANCES:
            try:
                resp = await client.get(
                    f"{instance}/api/v1/search",
                    params={"q": query, "type": "video", "sort_by": "relevance"},
                )
                resp.raise_for_status()
                data = resp.json()

                videos = []
                for item in data[:limit]:
                    if item.get("type") != "video":
                        continue
                    videos.append(YouTubeVideo(
                        video_id=item.get("videoId", ""),
                        title=item.get("title", ""),
                        channel=item.get("author", ""),
                        views=item.get("viewCount", 0),
                        description=(item.get("description", "") or "")[:500],
                    ))
                return videos
            except (httpx.HTTPError, ValueError):
                continue

    return []


async def get_transcript(video_id: str) -> str | None:
    """Fetch video transcript using youtube-transcript-api.

    Returns the full transcript text or None if unavailable.
    """
    try:
        # Use youtube-transcript-api if installed
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(entry["text"] for entry in transcript_list)
    except ImportError:
        # Fallback: try Invidious captions API
        return await _get_transcript_invidious(video_id)
    except Exception:
        return None


async def _get_transcript_invidious(video_id: str) -> str | None:
    """Fallback transcript fetch via Invidious."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for instance in INVIDIOUS_INSTANCES:
            try:
                resp = await client.get(f"{instance}/api/v1/captions/{video_id}")
                resp.raise_for_status()
                captions = resp.json()

                if not captions:
                    continue

                # Get English captions
                for cap in captions:
                    if cap.get("language_code", "").startswith("en"):
                        label = cap.get("label", "")
                        cap_resp = await client.get(
                            f"{instance}/api/v1/captions/{video_id}",
                            params={"label": label},
                        )
                        if cap_resp.status_code == 200:
                            return cap_resp.text

            except (httpx.HTTPError, ValueError):
                continue

    return None


def extract_facts_from_transcript(
    transcript: str,
    video: YouTubeVideo,
    franchise_name: str,
) -> list[ExtractedFact]:
    """Extract individual facts/claims from a video transcript.

    Looks for patterns that indicate interesting facts or trivia.
    """
    if not transcript:
        return []

    facts: list[ExtractedFact] = []

    # Split into sentences
    sentences = re.split(r"[.!?]+", transcript)

    # Fact indicator patterns
    fact_patterns = [
        r"did you know",
        r"fun fact",
        r"interesting(?:ly)?",
        r"originally",
        r"was supposed to",
        r"was meant to",
        r"scrapped|cut from",
        r"easter egg",
        r"hidden (?:detail|secret|reference)",
        r"based on|inspired by",
        r"designed to|intended to",
        r"most people don't (?:know|realize)",
        r"actually",
        r"secret",
        r"theory",
        r"developer(?:s)? (?:said|revealed|confirmed|intended)",
        r"beta|prototype|early version",
    ]

    compiled = [re.compile(p, re.IGNORECASE) for p in fact_patterns]

    i = 0
    while i < len(sentences):
        sentence = sentences[i].strip()
        if len(sentence) < 20:
            i += 1
            continue

        matched = any(p.search(sentence) for p in compiled)
        if matched:
            # Grab this sentence and the next 1-2 for context
            fact_text = sentence
            for j in range(1, 3):
                if i + j < len(sentences) and len(sentences[i + j].strip()) > 10:
                    fact_text += ". " + sentences[i + j].strip()

            facts.append(ExtractedFact(
                text=fact_text[:500],
                video_id=video.video_id,
                video_title=video.title,
                confidence="medium",
            ))
            i += 3  # Skip ahead to avoid duplicates
        else:
            i += 1

    return facts


async def research_franchise_youtube(
    franchise_name: str,
    search_queries: list[str] | None = None,
) -> list[ExtractedFact]:
    """Research a franchise via YouTube transcripts.

    Searches for lore/trivia videos, fetches transcripts, extracts facts.
    """
    if not search_queries:
        search_queries = [
            f"{franchise_name} did you know",
            f"{franchise_name} facts trivia",
            f"{franchise_name} hidden details easter eggs",
            f"{franchise_name} lore explained",
        ]

    all_facts: list[ExtractedFact] = []
    seen_videos: set[str] = set()

    for query in search_queries:
        videos = await search_youtube(query, limit=5)
        for video in videos:
            if video.video_id in seen_videos:
                continue
            seen_videos.add(video.video_id)

            transcript = await get_transcript(video.video_id)
            if transcript:
                facts = extract_facts_from_transcript(transcript, video, franchise_name)
                all_facts.extend(facts)

    return all_facts
