"""Tests for score_empathy.py — empathy_label boundaries and constants."""

import pytest
import math


class TestEmpathyLevels:
    def test_four_levels_defined(self):
        from score_empathy import EMPATHY_LEVELS
        assert len(EMPATHY_LEVELS) == 4

    def test_level_names(self):
        from score_empathy import EMPATHY_LEVELS
        assert "Cold / Hostile" in EMPATHY_LEVELS
        assert "Detached / Neutral" in EMPATHY_LEVELS
        assert "Warm / Supportive" in EMPATHY_LEVELS
        assert "Highly Empathetic" in EMPATHY_LEVELS


class TestProsocialEmotions:
    def test_prosocial_set_exists(self):
        from score_empathy import PROSOCIAL
        assert isinstance(PROSOCIAL, set)
        assert len(PROSOCIAL) > 0

    def test_key_emotions_included(self):
        from score_empathy import PROSOCIAL
        for emotion in ["admiration", "caring", "gratitude", "joy", "love", "optimism"]:
            assert emotion in PROSOCIAL

    def test_negative_emotions_excluded(self):
        from score_empathy import PROSOCIAL
        for emotion in ["anger", "disgust", "fear", "sadness"]:
            assert emotion not in PROSOCIAL


class TestEmpathyLabelDetailed:
    """Detailed boundary testing for empathy_label."""

    def test_exact_quarter_boundaries(self):
        from score_empathy import empathy_label
        # At each boundary, the score should fall into the higher bucket
        assert empathy_label(0.25) == "Detached / Neutral"
        assert empathy_label(0.50) == "Warm / Supportive"
        assert empathy_label(0.75) == "Highly Empathetic"

    def test_just_below_boundaries(self):
        from score_empathy import empathy_label
        assert empathy_label(0.249) == "Cold / Hostile"
        assert empathy_label(0.499) == "Detached / Neutral"
        assert empathy_label(0.749) == "Warm / Supportive"

    def test_extremes(self):
        from score_empathy import empathy_label
        assert empathy_label(0.0) == "Cold / Hostile"
        assert empathy_label(1.0) == "Highly Empathetic"

    def test_midpoints(self):
        from score_empathy import empathy_label
        assert empathy_label(0.125) == "Cold / Hostile"
        assert empathy_label(0.375) == "Detached / Neutral"
        assert empathy_label(0.625) == "Warm / Supportive"
        assert empathy_label(0.875) == "Highly Empathetic"

    def test_nan_handling(self):
        from score_empathy import empathy_label
        assert empathy_label(float("nan")) == "Detached / Neutral"
        assert empathy_label(None) == "Detached / Neutral"

    def test_out_of_range_clamped(self):
        from score_empathy import empathy_label
        # Values outside [0,1] should be clamped
        assert empathy_label(-1.0) == "Cold / Hostile"
        assert empathy_label(2.0) == "Highly Empathetic"
