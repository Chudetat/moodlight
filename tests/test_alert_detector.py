"""Tests for alert_detector.py — _make_alert, mood shift, mention surge, crisis, empathy_label."""

import json
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# _make_alert
# ---------------------------------------------------------------------------

class TestMakeAlert:
    def test_basic_structure(self):
        from alert_detector import _make_alert
        alert = _make_alert("test_type", "warning", "Test Title", "Test summary", {"key": "val"})
        assert alert["alert_type"] == "test_type"
        assert alert["severity"] == "warning"
        assert alert["title"] == "Test Title"
        assert alert["summary"] == "Test summary"
        assert alert["brand"] is None
        assert alert["username"] is None
        # data should be JSON string
        data = json.loads(alert["data"])
        assert data["key"] == "val"

    def test_with_brand_and_username(self):
        from alert_detector import _make_alert
        alert = _make_alert("t", "critical", "T", "S", {}, brand="Nike", username="user1")
        assert alert["brand"] == "Nike"
        assert alert["username"] == "user1"

    def test_numpy_bool_serialized(self):
        from alert_detector import _make_alert
        alert = _make_alert("t", "w", "T", "S", {"flag": np.bool_(True)})
        data = json.loads(alert["data"])
        assert data["flag"] == 1
        assert isinstance(data["flag"], int)

    def test_numpy_int64_serialized(self):
        from alert_detector import _make_alert
        alert = _make_alert("t", "w", "T", "S", {"count": np.int64(42)})
        data = json.loads(alert["data"])
        assert data["count"] == 42

    def test_numpy_float64_serialized(self):
        from alert_detector import _make_alert
        alert = _make_alert("t", "w", "T", "S", {"score": np.float64(3.14)})
        data = json.loads(alert["data"])
        assert abs(data["score"] - 3.14) < 0.001

    def test_numpy_array_serialized(self):
        from alert_detector import _make_alert
        alert = _make_alert("t", "w", "T", "S", {"arr": np.array([1, 2, 3])})
        data = json.loads(alert["data"])
        assert data["arr"] == [1, 2, 3]

    def test_string_data_passes_through(self):
        from alert_detector import _make_alert
        alert = _make_alert("t", "w", "T", "S", "raw string data")
        assert alert["data"] == "raw string data"


# ---------------------------------------------------------------------------
# detect_mood_shift
# ---------------------------------------------------------------------------

class TestDetectMoodShift:
    def test_large_drop_fires_alert(self, dates_3d):
        from alert_detector import detect_mood_shift
        d0, d1, d2 = dates_3d
        # Day 1: avg 0.8, Day 2: avg 0.5 => shift = -30pts
        df = pd.DataFrame({
            "created_at": [d1, d1, d2, d2],
            "empathy_score": [0.8, 0.8, 0.5, 0.5],
        })
        alerts = detect_mood_shift(df, pd.DataFrame())
        assert len(alerts) >= 1
        assert alerts[0]["alert_type"] == "mood_shift"
        assert "dropped" in alerts[0]["title"]

    def test_large_surge_fires_alert(self, dates_3d):
        from alert_detector import detect_mood_shift
        d0, d1, d2 = dates_3d
        df = pd.DataFrame({
            "created_at": [d1, d1, d2, d2],
            "empathy_score": [0.3, 0.3, 0.6, 0.6],
        })
        alerts = detect_mood_shift(df, pd.DataFrame())
        assert len(alerts) >= 1
        assert "surged" in alerts[0]["title"]

    def test_small_change_no_alert(self, dates_3d):
        from alert_detector import detect_mood_shift
        d0, d1, d2 = dates_3d
        # Day 1: 0.50, Day 2: 0.52 => shift = +2pts (below 15 threshold)
        df = pd.DataFrame({
            "created_at": [d1, d1, d2, d2],
            "empathy_score": [0.50, 0.50, 0.52, 0.52],
        })
        alerts = detect_mood_shift(df, pd.DataFrame())
        assert len(alerts) == 0

    def test_empty_df_no_alert(self):
        from alert_detector import detect_mood_shift
        alerts = detect_mood_shift(pd.DataFrame(), pd.DataFrame())
        assert alerts == []

    def test_critical_severity_on_large_shift(self, dates_3d):
        from alert_detector import detect_mood_shift
        d0, d1, d2 = dates_3d
        # shift = -40pts (above 25 critical threshold)
        df = pd.DataFrame({
            "created_at": [d1, d1, d2, d2],
            "empathy_score": [0.9, 0.9, 0.5, 0.5],
        })
        alerts = detect_mood_shift(df, pd.DataFrame())
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "critical"


# ---------------------------------------------------------------------------
# detect_brand_mention_surge
# ---------------------------------------------------------------------------

class TestDetectBrandMentionSurge:
    def test_surge_fires_at_multiplier(self, dates_3d):
        from alert_detector import detect_brand_mention_surge
        d0, d1, d2 = dates_3d
        # Baseline: 2/day, Today: 10 => 5x (above 3x default)
        df_news = pd.DataFrame({
            "id": range(14),
            "text": ["Nike shoes are great"] * 14,
            "title": ["Nike Launch"] * 14,
            "created_at": [d0] * 2 + [d1] * 2 + [d2] * 10,
            "source": ["Reuters"] * 14,
        })
        alerts = detect_brand_mention_surge(df_news, pd.DataFrame(), "Nike", "user1")
        assert len(alerts) >= 1
        assert alerts[0]["alert_type"] == "brand_news_surge"

    def test_no_surge_below_threshold(self, dates_3d):
        from alert_detector import detect_brand_mention_surge
        d0, d1, d2 = dates_3d
        # Baseline: 3/day, Today: 4 => 1.3x (below 3x)
        df_news = pd.DataFrame({
            "id": range(10),
            "text": ["Nike shoes are great"] * 10,
            "title": ["Nike Launch"] * 10,
            "created_at": [d0] * 3 + [d1] * 3 + [d2] * 4,
            "source": ["Reuters"] * 10,
        })
        alerts = detect_brand_mention_surge(df_news, pd.DataFrame(), "Nike", "user1")
        assert len(alerts) == 0

    def test_empty_data_no_alert(self):
        from alert_detector import detect_brand_mention_surge
        alerts = detect_brand_mention_surge(pd.DataFrame(), pd.DataFrame(), "Nike", "user1")
        assert alerts == []


# ---------------------------------------------------------------------------
# detect_brand_crisis
# ---------------------------------------------------------------------------

class TestDetectBrandCrisis:
    def test_crisis_fires_all_conditions(self, dates_3d):
        from alert_detector import detect_brand_crisis
        d0, d1, d2 = dates_3d
        n = 20
        # Volume surge: baseline 2/day, today 20 => 10x
        # Low empathy: avg < 0.15
        # Negative dominant: >50% anger/disgust
        df = pd.DataFrame({
            "id": range(n + 4),
            "text": ["Nike scandal horrible disaster"] * (n + 4),
            "title": ["Nike Crisis"] * (n + 4),
            "created_at": [d0] * 2 + [d1] * 2 + [d2] * n,
            "empathy_score": [0.1] * (n + 4),
            "emotion_top_1": ["anger"] * (n + 4),
            "source": ["Reuters"] * (n + 4),
        })
        alerts = detect_brand_crisis(df, pd.DataFrame(), "Nike", "user1")
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "brand_crisis"
        assert alerts[0]["severity"] == "critical"

    def test_no_crisis_when_empathy_high(self, dates_3d):
        from alert_detector import detect_brand_crisis
        d0, d1, d2 = dates_3d
        n = 20
        df = pd.DataFrame({
            "id": range(n + 4),
            "text": ["Nike celebration success"] * (n + 4),
            "title": ["Nike Win"] * (n + 4),
            "created_at": [d0] * 2 + [d1] * 2 + [d2] * n,
            "empathy_score": [0.8] * (n + 4),  # High empathy
            "emotion_top_1": ["anger"] * (n + 4),
            "source": ["Reuters"] * (n + 4),
        })
        alerts = detect_brand_crisis(df, pd.DataFrame(), "Nike", "user1")
        assert len(alerts) == 0

    def test_no_crisis_when_no_volume_surge(self, dates_3d):
        from alert_detector import detect_brand_crisis
        d0, d1, d2 = dates_3d
        # Same volume each day — no surge
        df = pd.DataFrame({
            "id": range(9),
            "text": ["Nike scandal"] * 9,
            "title": ["Nike Crisis"] * 9,
            "created_at": [d0] * 3 + [d1] * 3 + [d2] * 3,
            "empathy_score": [0.05] * 9,
            "emotion_top_1": ["anger"] * 9,
            "source": ["Reuters"] * 9,
        })
        alerts = detect_brand_crisis(df, pd.DataFrame(), "Nike", "user1")
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# empathy_label (from score_empathy.py)
# ---------------------------------------------------------------------------

class TestEmpathyLabel:
    def test_boundaries(self):
        from score_empathy import empathy_label
        assert empathy_label(0.0) == "Cold / Hostile"
        assert empathy_label(0.24) == "Cold / Hostile"
        assert empathy_label(0.25) == "Detached / Neutral"
        assert empathy_label(0.49) == "Detached / Neutral"
        assert empathy_label(0.5) == "Warm / Supportive"
        assert empathy_label(0.74) == "Warm / Supportive"
        assert empathy_label(0.75) == "Highly Empathetic"
        assert empathy_label(1.0) == "Highly Empathetic"

    def test_none_returns_neutral(self):
        from score_empathy import empathy_label
        assert empathy_label(None) == "Detached / Neutral"

    def test_nan_returns_neutral(self):
        import math
        from score_empathy import empathy_label
        assert empathy_label(float("nan")) == "Detached / Neutral"

    def test_clamps_above_one(self):
        from score_empathy import empathy_label
        assert empathy_label(1.5) == "Highly Empathetic"

    def test_clamps_below_zero(self):
        from score_empathy import empathy_label
        assert empathy_label(-0.5) == "Cold / Hostile"
