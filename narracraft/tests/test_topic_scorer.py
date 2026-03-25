"""Unit tests for topic scoring algorithm."""

import pytest
from backend.services.topics.topic_scorer import score_topic, ScoringInput, WEIGHTS, CATEGORY_BONUSES


class TestScoreTopic:
    """Tests for the multi-signal topic scorer."""

    def test_empty_input_returns_baseline(self):
        """A topic with no signals should still get uniqueness + freshness baseline."""
        inp = ScoringInput(title="Test topic")
        result = score_topic(inp)
        assert result.total_score > 0
        assert result.tier in ("C", "D")
        assert "uniqueness" in result.breakdown
        assert "freshness" in result.breakdown

    def test_single_source_scores_lower_than_multiple(self):
        """More source diversity should yield higher scores."""
        single = ScoringInput(
            title="Test",
            sources=[{"type": "wiki", "score": 2.0}],
        )
        multi = ScoringInput(
            title="Test",
            sources=[
                {"type": "wiki", "score": 2.0},
                {"type": "reddit", "score": 3.0},
                {"type": "youtube", "score": 2.5},
            ],
        )
        r_single = score_topic(single)
        r_multi = score_topic(multi)
        assert r_multi.total_score > r_single.total_score

    def test_four_sources_max_diversity(self):
        """Four source types should hit maximum diversity score."""
        inp = ScoringInput(
            title="Test",
            sources=[
                {"type": "wiki"}, {"type": "reddit"},
                {"type": "youtube"}, {"type": "ai"},
            ],
        )
        result = score_topic(inp)
        expected_max = 5 * WEIGHTS["source_diversity"]
        assert result.breakdown["source_diversity"] == expected_max

    def test_reddit_engagement_log_scale(self):
        """Reddit score uses log scale — 100 upvotes < 10000 upvotes."""
        low = ScoringInput(title="T", reddit_score=50)
        high = ScoringInput(title="T", reddit_score=10000)
        assert score_topic(high).breakdown["reddit_engagement"] > score_topic(low).breakdown["reddit_engagement"]

    def test_reddit_comment_bonus(self):
        """Comments add a bonus on top of upvote score."""
        no_comments = ScoringInput(title="T", reddit_score=100, reddit_comments=0)
        with_comments = ScoringInput(title="T", reddit_score=100, reddit_comments=200)
        assert score_topic(with_comments).breakdown["reddit_engagement"] > score_topic(no_comments).breakdown["reddit_engagement"]

    def test_youtube_views_scoring(self):
        """YouTube views contribute to validation score."""
        no_views = ScoringInput(title="T", youtube_views=0)
        many_views = ScoringInput(title="T", youtube_views=100000)
        assert score_topic(no_views).breakdown["youtube_validation"] == 0
        assert score_topic(many_views).breakdown["youtube_validation"] > 0

    def test_wiki_presence_binary(self):
        """Wiki presence is a binary on/off signal."""
        no_wiki = ScoringInput(title="T", has_wiki_section=False)
        has_wiki = ScoringInput(title="T", has_wiki_section=True)
        assert score_topic(no_wiki).breakdown["wiki_presence"] == 0
        assert score_topic(has_wiki).breakdown["wiki_presence"] == 3.0 * WEIGHTS["wiki_presence"]

    def test_freshness_trending_bonus(self):
        """Trending topics get a higher freshness score than evergreen."""
        evergreen = ScoringInput(title="T", freshness="evergreen")
        trending = ScoringInput(title="T", freshness="trending")
        assert score_topic(trending).breakdown["freshness"] > score_topic(evergreen).breakdown["freshness"]

    def test_asset_readiness_scoring(self):
        """Ready assets score higher than blocked."""
        ready = ScoringInput(title="T", asset_readiness="ready")
        blocked = ScoringInput(title="T", asset_readiness="blocked")
        assert score_topic(ready).breakdown["asset_readiness"] > score_topic(blocked).breakdown["asset_readiness"]

    def test_category_bonus_multiplier(self):
        """Easter egg category should score higher than memes (1.3 vs 0.9)."""
        easter = ScoringInput(title="T", category="easter_egg", has_wiki_section=True)
        memes = ScoringInput(title="T", category="memes", has_wiki_section=True)
        assert score_topic(easter).total_score > score_topic(memes).total_score

    def test_tier_assignment_s(self):
        """High-scoring topic should get S tier (>=30)."""
        inp = ScoringInput(
            title="T",
            sources=[{"type": "wiki"}, {"type": "reddit"}, {"type": "youtube"}, {"type": "ai"}],
            reddit_score=5000,
            reddit_comments=300,
            youtube_views=500000,
            has_wiki_section=True,
            category="easter_egg",
            freshness="trending",
            asset_readiness="ready",
        )
        result = score_topic(inp)
        assert result.tier == "S"
        assert result.total_score >= 30

    def test_tier_assignment_d(self):
        """Minimal topic should get D tier (<8)."""
        inp = ScoringInput(title="T", category="memes", asset_readiness="blocked")
        result = score_topic(inp)
        assert result.tier in ("C", "D")

    def test_breakdown_keys_complete(self):
        """Breakdown should contain all 7 scoring dimensions."""
        result = score_topic(ScoringInput(title="T"))
        expected_keys = {"source_diversity", "reddit_engagement", "youtube_validation",
                         "wiki_presence", "uniqueness", "freshness", "asset_readiness"}
        assert set(result.breakdown.keys()) == expected_keys
