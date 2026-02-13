"""Shared fixtures for Moodlight tests."""

import sys
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub heavy ML modules that aren't installed in test/CI environments
# ---------------------------------------------------------------------------
for _mod in ("transformers", "torch"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


@pytest.fixture
def dates_3d():
    """Three consecutive dates for time-series tests."""
    now = datetime.now(timezone.utc)
    return [now - timedelta(days=2), now - timedelta(days=1), now]


@pytest.fixture
def df_news_basic(dates_3d):
    """Minimal news DataFrame with empathy_score, topic, intensity."""
    d0, d1, d2 = dates_3d
    return pd.DataFrame({
        "id": [f"n{i}" for i in range(9)],
        "text": [f"News article {i}" for i in range(9)],
        "title": [f"Title {i}" for i in range(9)],
        "created_at": [d0, d0, d0, d1, d1, d1, d2, d2, d2],
        "empathy_score": [0.5, 0.6, 0.4, 0.5, 0.5, 0.5, 0.2, 0.1, 0.15],
        "topic": ["economics"] * 3 + ["technology"] * 3 + ["economics"] * 3,
        "intensity": [3.0, 2.5, 3.5, 3.0, 3.0, 3.0, 4.0, 4.5, 4.2],
        "source": ["Reuters", "AP", "BBC"] * 3,
    })


@pytest.fixture
def df_social_basic(dates_3d):
    """Minimal social DataFrame."""
    d0, d1, d2 = dates_3d
    return pd.DataFrame({
        "id": [f"s{i}" for i in range(6)],
        "text": [f"Social post {i}" for i in range(6)],
        "created_at": [d0, d0, d1, d1, d2, d2],
        "empathy_score": [0.6, 0.5, 0.55, 0.45, 0.3, 0.25],
        "topic": ["economics", "technology"] * 3,
        "intensity": [2.0, 3.0, 2.5, 3.5, 4.0, 4.5],
        "source": ["twitter"] * 6,
    })


@pytest.fixture
def df_empty():
    """Empty DataFrame."""
    return pd.DataFrame()


@pytest.fixture
def mock_db_engine():
    """Mock SQLAlchemy engine that returns configurable results."""
    engine = MagicMock()
    return engine


def make_mock_user_row(tier="monthly", brief_credits=0):
    """Helper: create a mock DB result row for get_user_tier."""
    row = MagicMock()
    row.__getitem__ = lambda self, i: (tier, brief_credits)[i]
    return row
