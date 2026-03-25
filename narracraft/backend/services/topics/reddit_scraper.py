"""Scrape top posts from franchise subreddits for topic ideas."""

from dataclasses import dataclass, field

import httpx

# Map franchise IDs to their subreddits
FRANCHISE_SUBREDDITS: dict[str, list[str]] = {
    "resident_evil": ["residentevil"],
    "soulsborne": ["darksouls", "Eldenring", "bloodborne"],
    "zelda": ["zelda", "Breath_of_the_Wild", "tearsofthekingdom"],
    "one_piece": ["OnePiece"],
    "attack_on_titan": ["ShingekiNoKyojin", "attackontitan"],
    "naruto": ["Naruto"],
    "jujutsu_kaisen": ["JuJutsuKaisen"],
}

REDDIT_JSON_HEADERS = {
    "User-Agent": "NarraCraft/0.1 (YouTube Shorts Automation; research only)"
}


@dataclass
class RedditPost:
    title: str
    url: str
    subreddit: str
    score: int = 0
    num_comments: int = 0
    selftext: str = ""
    flair: str = ""
    created_utc: float = 0


async def scrape_subreddit(
    subreddit: str,
    sort: str = "top",
    timeframe: str = "month",
    limit: int = 25,
) -> list[RedditPost]:
    """Scrape top posts from a subreddit using Reddit's public JSON API."""
    posts: list[RedditPost] = []

    async with httpx.AsyncClient(
        timeout=15.0,
        headers=REDDIT_JSON_HEADERS,
        follow_redirects=True,
    ) as client:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
            resp = await client.get(url, params={
                "t": timeframe,
                "limit": str(limit),
            })
            resp.raise_for_status()
            data = resp.json()

            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                # Filter for text/discussion posts (not just images/memes)
                if post.get("is_self") or post.get("num_comments", 0) > 10:
                    posts.append(RedditPost(
                        title=post.get("title", ""),
                        url=f"https://reddit.com{post.get('permalink', '')}",
                        subreddit=subreddit,
                        score=post.get("score", 0),
                        num_comments=post.get("num_comments", 0),
                        selftext=(post.get("selftext", "") or "")[:1000],
                        flair=post.get("link_flair_text", "") or "",
                        created_utc=post.get("created_utc", 0),
                    ))

        except (httpx.HTTPError, ValueError):
            pass

    return posts


async def scrape_franchise_subreddits(
    franchise_id: str,
    sort: str = "top",
    timeframe: str = "month",
    limit_per_sub: int = 25,
) -> list[RedditPost]:
    """Scrape all subreddits associated with a franchise."""
    subreddits = FRANCHISE_SUBREDDITS.get(franchise_id, [])
    all_posts: list[RedditPost] = []

    for sub in subreddits:
        posts = await scrape_subreddit(sub, sort, timeframe, limit_per_sub)
        all_posts.extend(posts)

    # Sort by score (highest first)
    all_posts.sort(key=lambda p: p.score, reverse=True)
    return all_posts


def filter_lore_posts(posts: list[RedditPost]) -> list[RedditPost]:
    """Filter posts that are likely lore/trivia discussions (not memes or art)."""
    lore_keywords = [
        "did you know", "theory", "lore", "fact", "detail", "noticed",
        "hidden", "easter egg", "foreshadow", "secret", "never knew",
        "trivia", "interesting", "explain", "meaning", "connection",
        "reference", "symbolism", "hint", "clue", "originally",
        "cut content", "scrapped", "beta", "unused", "developer",
    ]

    filtered = []
    for post in posts:
        title_lower = post.title.lower()
        text_lower = post.selftext.lower()
        combined = title_lower + " " + text_lower

        if any(kw in combined for kw in lore_keywords):
            filtered.append(post)

    return filtered
