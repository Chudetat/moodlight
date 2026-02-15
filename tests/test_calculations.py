"""Tests for calculate_longevity, calculate_density, calculate_scarcity."""

import math
import pandas as pd
import pytest
from datetime import datetime, timezone, timedelta


# ── Longevity tests ──

class TestCalculateVelocity:
    """Test volume-based velocity calculation."""

    def test_no_data_returns_zero(self):
        from calculate_longevity import calculate_velocity
        df = pd.DataFrame({"created_at": []})
        assert calculate_velocity(df) == 0.0

    def test_single_row_returns_zero(self):
        from calculate_longevity import calculate_velocity
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({"created_at": [now]})
        assert calculate_velocity(df) == 0.0

    def test_only_recent_posts_max_velocity(self):
        from calculate_longevity import calculate_velocity
        now = datetime.now(timezone.utc)
        # All posts in last 48h, none older
        dates = [now - timedelta(hours=i) for i in range(5)]
        df = pd.DataFrame({"created_at": pd.to_datetime(dates, utc=True)})
        assert calculate_velocity(df) == 1.0

    def test_only_older_posts_zero_velocity(self):
        from calculate_longevity import calculate_velocity
        now = datetime.now(timezone.utc)
        # All posts 3-7 days ago, none recent
        dates = [now - timedelta(days=d) for d in [3, 4, 5, 6]]
        df = pd.DataFrame({"created_at": pd.to_datetime(dates, utc=True)})
        assert calculate_velocity(df) == 0.0

    def test_balanced_posts_moderate_velocity(self):
        from calculate_longevity import calculate_velocity
        now = datetime.now(timezone.utc)
        # Equal rate: 2 posts in 48h, 5 posts in prior 5 days
        recent = [now - timedelta(hours=i) for i in [1, 24]]
        older = [now - timedelta(days=d) for d in [3, 4, 5, 6, 7]]
        df = pd.DataFrame({"created_at": pd.to_datetime(recent + older, utc=True)})
        vel = calculate_velocity(df)
        assert 0.0 < vel < 1.0

    def test_missing_created_at(self):
        from calculate_longevity import calculate_velocity
        df = pd.DataFrame({"text": ["hello", "world"]})
        assert calculate_velocity(df) == 0.0


class TestCalculateLongevityScore:
    """Test overall longevity score."""

    def test_returns_float_in_range(self):
        from calculate_longevity import calculate_longevity_score
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({
            "source": ["bbc", "cnn", "reuters", "ap", "guardian"],
            "created_at": pd.to_datetime([now - timedelta(days=i) for i in range(5)], utc=True),
            "reply_count": [10, 20, 5, 15, 8],
            "like_count": [100, 200, 50, 150, 80],
        })
        score = calculate_longevity_score("economics", df)
        assert 0.0 <= score <= 1.0

    def test_more_sources_higher_longevity(self):
        from calculate_longevity import calculate_longevity_score
        now = datetime.now(timezone.utc)
        # 1 source
        df1 = pd.DataFrame({
            "source": ["bbc"] * 5,
            "created_at": pd.to_datetime([now] * 5, utc=True),
        })
        # 5 sources
        df5 = pd.DataFrame({
            "source": ["bbc", "cnn", "reuters", "ap", "guardian"],
            "created_at": pd.to_datetime([now] * 5, utc=True),
        })
        assert calculate_longevity_score("test", df5) > calculate_longevity_score("test", df1)


# ── Density tests ──

class TestGetGeographicDensity:
    """Test expanded geo mapping."""

    def test_bbc_maps_to_uk_europe(self):
        from calculate_density import get_geographic_density
        df = pd.DataFrame({"source": ["bbc_world", "bbc_news", "bbc_business"]})
        result = get_geographic_density(df)
        assert result["primary_region"] == "UK/Europe"

    def test_cnn_maps_to_north_america(self):
        from calculate_density import get_geographic_density
        df = pd.DataFrame({"source": ["cnn_top", "cnn_world"]})
        result = get_geographic_density(df)
        assert result["primary_region"] == "North America"

    def test_mixed_sources_increase_diversity(self):
        from calculate_density import get_geographic_density
        df = pd.DataFrame({"source": ["bbc_news", "cnn_top", "al_jazeera"]})
        result = get_geographic_density(df)
        assert result["diversity"] > 0.0

    def test_unknown_sources_dont_count_as_diversity(self):
        from calculate_density import get_geographic_density
        df = pd.DataFrame({"source": ["unknown_source_1", "unknown_source_2"]})
        result = get_geographic_density(df)
        assert result["diversity"] == 0
        assert result["primary_region"] == "Other"


class TestGetConversationDepth:
    """Test multi-signal depth calculation."""

    def test_news_only_uses_articles_per_source(self):
        from calculate_density import get_conversation_depth
        now = datetime.now(timezone.utc)
        # 6 articles from 2 sources = 3 per source = deep
        df = pd.DataFrame({
            "source": ["bbc"] * 3 + ["cnn"] * 3,
            "created_at": pd.to_datetime([now - timedelta(days=i) for i in range(6)], utc=True),
        })
        result = get_conversation_depth(df)
        assert result["depth_score"] > 0.5

    def test_empty_df_returns_low_default(self):
        from calculate_density import get_conversation_depth
        df = pd.DataFrame({"source": [], "created_at": []})
        result = get_conversation_depth(df)
        assert result["depth_score"] == 0.3


class TestCalculateDensityScore:
    """Test overall density score."""

    def test_returns_float_in_range(self):
        from calculate_density import calculate_density_score
        now = datetime.now(timezone.utc)
        df = pd.DataFrame({
            "source": ["bbc", "cnn", "reuters"] * 10,
            "created_at": pd.to_datetime([now - timedelta(hours=i) for i in range(30)], utc=True),
            "topic": ["economics"] * 30,
        })
        density, geo, platform, depth = calculate_density_score(df, 100)
        assert 0.0 <= density <= 1.0

    def test_higher_volume_higher_density(self):
        from calculate_density import calculate_density_score
        now = datetime.now(timezone.utc)
        small = pd.DataFrame({
            "source": ["bbc"] * 2,
            "created_at": pd.to_datetime([now] * 2, utc=True),
        })
        large = pd.DataFrame({
            "source": ["bbc"] * 50,
            "created_at": pd.to_datetime([now] * 50, utc=True),
        })
        d_small, _, _, _ = calculate_density_score(small, 100)
        d_large, _, _, _ = calculate_density_score(large, 100)
        assert d_large > d_small


# ── Scarcity tests ──

class TestScarcityScore:
    """Test continuous log-scaled scarcity scoring."""

    def test_zero_mentions_max_scarcity(self):
        from calculate_scarcity import _calculate_scarcity_score
        assert _calculate_scarcity_score(0, 1000) == 1.0

    def test_max_mentions_min_scarcity(self):
        from calculate_scarcity import _calculate_scarcity_score
        score = _calculate_scarcity_score(1000, 1000)
        assert score == 0.0

    def test_continuous_not_bucketed(self):
        from calculate_scarcity import _calculate_scarcity_score
        scores = [_calculate_scarcity_score(m, 1000) for m in [1, 5, 20, 50, 100, 500]]
        # All should be unique (continuous, not bucketed)
        assert len(set(scores)) == len(scores)
        # Should be monotonically decreasing
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1]

    def test_score_in_range(self):
        from calculate_scarcity import _calculate_scarcity_score
        for m in [0, 1, 10, 100, 1000, 5000]:
            score = _calculate_scarcity_score(m, 5000)
            assert 0.0 <= score <= 1.0


class TestCoverageLevel:
    """Test coverage level labels."""

    def test_high_scarcity_label(self):
        from calculate_scarcity import _coverage_level
        assert _coverage_level(0.95) == "Zero coverage"

    def test_low_scarcity_label(self):
        from calculate_scarcity import _coverage_level
        assert _coverage_level(0.05) == "Saturated"


class TestOpportunityLevel:
    """Test opportunity classification."""

    def test_high_opportunity(self):
        from calculate_scarcity import _opportunity_level
        assert _opportunity_level(0.8) == "HIGH"

    def test_medium_opportunity(self):
        from calculate_scarcity import _opportunity_level
        assert _opportunity_level(0.5) == "MEDIUM"

    def test_low_opportunity(self):
        from calculate_scarcity import _opportunity_level
        assert _opportunity_level(0.2) == "LOW"


class TestCheckTopicCoverage:
    """Test end-to-end scarcity analysis."""

    def test_returns_dataframe(self):
        from calculate_scarcity import check_topic_coverage
        df = pd.DataFrame({
            "text": ["AI regulation is important", "climate action needed", "remote work trends"],
            "topic": ["tech", "climate", "work"],
        })
        result = check_topic_coverage(df)
        assert isinstance(result, pd.DataFrame)
        assert "scarcity_score" in result.columns
        assert "opportunity" in result.columns

    def test_handles_nan_text(self):
        from calculate_scarcity import check_topic_coverage
        df = pd.DataFrame({
            "text": ["hello world", None, float("nan"), "test"],
            "topic": ["a", "b", "c", "d"],
        })
        # Should not crash
        result = check_topic_coverage(df)
        assert len(result) > 0
