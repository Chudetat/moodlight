"""Tests for tier_helper.py — feature access, tier limits, brief credits."""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# has_feature_access
# ---------------------------------------------------------------------------

class TestHasFeatureAccess:
    @pytest.mark.parametrize("tier", ["monthly", "annually", "professional", "enterprise"])
    def test_active_tier_has_all_features(self, tier):
        with patch("tier_helper.get_user_tier", return_value={"tier": tier, "brief_credits": 0}):
            from tier_helper import has_feature_access
            assert has_feature_access("testuser", "competitive_war_room") is True
            assert has_feature_access("testuser", "intelligence_reports") is True
            assert has_feature_access("testuser", "ask_moodlight") is True
            assert has_feature_access("testuser", "prediction_markets") is True

    def test_cancelled_tier_no_access(self):
        with patch("tier_helper.get_user_tier", return_value={"tier": "cancelled", "brief_credits": 0}):
            from tier_helper import has_feature_access
            assert has_feature_access("testuser", "competitive_war_room") is False
            assert has_feature_access("testuser", "intelligence_reports") is False

    def test_unknown_tier_no_access(self):
        with patch("tier_helper.get_user_tier", return_value={"tier": "unknown", "brief_credits": 0}):
            from tier_helper import has_feature_access
            assert has_feature_access("testuser", "ask_moodlight") is False

    def test_unknown_feature_defaults_to_active_tiers(self):
        with patch("tier_helper.get_user_tier", return_value={"tier": "monthly", "brief_credits": 0}):
            from tier_helper import has_feature_access
            assert has_feature_access("testuser", "nonexistent_feature") is True

        with patch("tier_helper.get_user_tier", return_value={"tier": "cancelled", "brief_credits": 0}):
            from tier_helper import has_feature_access
            assert has_feature_access("testuser", "nonexistent_feature") is False


# ---------------------------------------------------------------------------
# get_tier_limit
# ---------------------------------------------------------------------------

class TestGetTierLimit:
    @pytest.mark.parametrize("tier", ["monthly", "annually", "professional", "enterprise"])
    def test_brand_watchlist_max(self, tier):
        with patch("tier_helper.get_user_tier", return_value={"tier": tier, "brief_credits": 0}):
            from tier_helper import get_tier_limit
            assert get_tier_limit("testuser", "brand_watchlist_max") == 5

    @pytest.mark.parametrize("tier", ["monthly", "annually", "professional", "enterprise"])
    def test_topic_watchlist_max(self, tier):
        with patch("tier_helper.get_user_tier", return_value={"tier": tier, "brief_credits": 0}):
            from tier_helper import get_tier_limit
            assert get_tier_limit("testuser", "topic_watchlist_max") == 10

    def test_cancelled_tier_gets_zero(self):
        with patch("tier_helper.get_user_tier", return_value={"tier": "cancelled", "brief_credits": 0}):
            from tier_helper import get_tier_limit
            assert get_tier_limit("testuser", "brand_watchlist_max") == 0

    def test_unknown_limit_returns_zero(self):
        with patch("tier_helper.get_user_tier", return_value={"tier": "monthly", "brief_credits": 0}):
            from tier_helper import get_tier_limit
            assert get_tier_limit("testuser", "nonexistent_limit") == 0


# ---------------------------------------------------------------------------
# can_generate_brief
# ---------------------------------------------------------------------------

class TestCanGenerateBrief:
    @pytest.mark.parametrize("tier", ["monthly", "annually", "professional", "enterprise"])
    def test_active_tier_can_generate(self, tier):
        with patch("tier_helper.get_user_tier", return_value={"tier": tier, "brief_credits": 0}):
            from tier_helper import can_generate_brief
            allowed, msg = can_generate_brief("testuser")
            assert allowed is True
            assert msg == ""

    def test_cancelled_tier_cannot_generate(self):
        with patch("tier_helper.get_user_tier", return_value={"tier": "cancelled", "brief_credits": 0}):
            from tier_helper import can_generate_brief
            allowed, msg = can_generate_brief("testuser")
            assert allowed is False
            assert "does not have access" in msg

    def test_unknown_tier_cannot_generate(self):
        with patch("tier_helper.get_user_tier", return_value={"tier": "", "brief_credits": 0}):
            from tier_helper import can_generate_brief
            allowed, msg = can_generate_brief("testuser")
            assert allowed is False


# ---------------------------------------------------------------------------
# get_brief_credits
# ---------------------------------------------------------------------------

class TestGetBriefCredits:
    @pytest.mark.parametrize("tier", ["monthly", "annually", "professional", "enterprise"])
    def test_active_tier_returns_unlimited(self, tier):
        with patch("tier_helper.get_user_tier", return_value={"tier": tier, "brief_credits": 5}):
            from tier_helper import get_brief_credits
            assert get_brief_credits("testuser") == -1  # unlimited

    def test_cancelled_tier_returns_credit_count(self):
        with patch("tier_helper.get_user_tier", return_value={"tier": "cancelled", "brief_credits": 3}):
            from tier_helper import get_brief_credits
            assert get_brief_credits("testuser") == 3


# ---------------------------------------------------------------------------
# ACTIVE_TIERS constant
# ---------------------------------------------------------------------------

class TestConstants:
    def test_active_tiers_contains_expected(self):
        from tier_helper import ACTIVE_TIERS
        assert "monthly" in ACTIVE_TIERS
        assert "annually" in ACTIVE_TIERS
        assert "professional" in ACTIVE_TIERS
        assert "enterprise" in ACTIVE_TIERS

    def test_active_tiers_excludes_cancelled(self):
        from tier_helper import ACTIVE_TIERS
        assert "cancelled" not in ACTIVE_TIERS
        assert "free" not in ACTIVE_TIERS
