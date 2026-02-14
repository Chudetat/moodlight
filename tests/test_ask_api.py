"""Tests for Ask Moodlight API."""

import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        from ask_moodlight_api import app
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "ask-moodlight"


class TestRateLimiting:
    def test_check_rate_limit_under_limit(self):
        from ask_moodlight_api import _check_rate_limit, _rate_store
        _rate_store.clear()
        assert _check_rate_limit("192.168.1.1") is True

    def test_check_rate_limit_at_limit(self):
        from ask_moodlight_api import _check_rate_limit, _record_request, _rate_store, RATE_LIMIT
        _rate_store.clear()
        for _ in range(RATE_LIMIT):
            _record_request("10.0.0.1")
        assert _check_rate_limit("10.0.0.1") is False

    def test_rate_limit_resets_after_24h(self):
        from ask_moodlight_api import _check_rate_limit, _rate_store, _hash_ip, RATE_LIMIT
        _rate_store.clear()
        h = _hash_ip("10.0.0.2")
        # Add old entries (25 hours ago)
        old_time = time.time() - 90000
        _rate_store[h] = [old_time] * RATE_LIMIT
        assert _check_rate_limit("10.0.0.2") is True


class TestAskEndpoint:
    def test_empty_question_rejected(self):
        from ask_moodlight_api import app
        client = TestClient(app)
        resp = client.post("/api/ask", json={"question": "  "})
        assert resp.status_code == 400

    def test_long_question_rejected(self):
        from ask_moodlight_api import app
        client = TestClient(app)
        resp = client.post("/api/ask", json={"question": "x" * 501})
        assert resp.status_code == 400


class TestBuildVerifiedData:
    def test_empty_dataframe(self):
        import pandas as pd
        from ask_moodlight_api import build_verified_data
        result = build_verified_data(pd.DataFrame())
        assert "[VERIFIED DASHBOARD DATA]" in result
        assert "No dashboard data currently available" in result

    def test_with_data(self):
        import pandas as pd
        from ask_moodlight_api import build_verified_data
        df = pd.DataFrame({
            "text": ["test headline 1", "test headline 2"],
            "topic": ["Technology", "Technology"],
            "empathy_score": [55.0, 65.0],
            "empathy_label": ["warm", "warm"],
            "created_at": pd.to_datetime(["2025-01-01", "2025-01-02"]),
        })
        result = build_verified_data(df)
        assert "Total Posts Analyzed: 2" in result
        assert "Technology" in result


class TestDetectSearchTopic:
    def test_returns_dict_on_failure(self):
        from ask_moodlight_api import detect_search_topic
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("no key")
        result = detect_search_topic("test", mock_client)
        assert isinstance(result, dict)
        assert result["brand"] is None
        assert result["needs_web"] is False
