#!/usr/bin/env python
"""
score_empathy.py
Scores social.csv (X + news) with empathy, emotion, and labels.
Writes social_scored.csv (and news_scored.csv when called with news.csv).

NOW SUPPORTS INCREMENTAL SCORING:

- Only scores NEW entries (not already in output file)
- Preserves previously scored data
- Much faster for repeated runs!

Uses: https://huggingface.co/bhadresh-savani/bert-base-uncased-emotion
"""

import os
import sys
import csv
import math
from typing import List, Dict, Any, Set
from datetime import datetime, timezone

import pandas as pd
from pandas.errors import EmptyDataError
from transformers import pipeline, Pipeline
import torch

# -------------------------------
# Default paths
# -------------------------------
DEFAULT_INPUT_CSV = "social.csv"
DEFAULT_OUTPUT_CSV = "social_scored.csv"

# -------------------------------
# Empathy labeling
# -------------------------------
EMPATHY_LEVELS = [
    "Cold / Hostile",
    "Detached / Neutral",
    "Warm / Supportive",
    "Highly Empathetic",
]

def empathy_label(score: float) -> str:
    """Convert empathy score to human-readable label"""
    if score is None or math.isnan(score):
        return EMPATHY_LEVELS[1]
    score = max(0.0, min(1.0, float(score)))
    if score < 0.25:
        return EMPATHY_LEVELS[0]
    if score < 0.5:
        return EMPATHY_LEVELS[1]
    if score < 0.75:
        return EMPATHY_LEVELS[2]
    return EMPATHY_LEVELS[3]

# -------------------------------
# Prosocial emotions (GoEmotions)
# -------------------------------
PROSOCIAL = {
    "admiration", "approval", "caring", "gratitude", "love",
    "optimism", "pride", "relief", "joy", "amusement", "excitement"
}

# Correct model (exists and is fast)
MODEL_NAME = "bhadresh-savani/bert-base-uncased-emotion"

# -------------------------------
# Load existing scored data
# -------------------------------
def load_existing_scores(output_csv: str) -> tuple[pd.DataFrame, Set[str]]:
    """Load previously scored data to avoid re-scoring"""
    try:
        df = pd.read_csv(output_csv)
        print(f"Loaded {len(df)} previously scored entries from {output_csv}")

        # Get set of already-scored IDs
        scored_ids = set(df["id"].astype(str))
        
        return df, scored_ids
    except FileNotFoundError:
        print(f"No existing scored data found (will create {output_csv})")
        return pd.DataFrame(), set()
    except Exception as e:
        print(f"Error loading existing scores: {str(e)[:100]}")
        return pd.DataFrame(), set()

# -------------------------------
# Emotion pipeline (with fallbacks)
# -------------------------------
def build_emotion_pipeline() -> Pipeline:
    """Build the emotion classification pipeline"""
    print("Loading emotion model (bhadresh-savani/bert-base-uncased-emotion)...")

    device = 0 if torch.cuda.is_available() else -1
    print(f"   Using {'GPU' if device == 0 else 'CPU'}")

    try:
        clf = pipeline(
            "text-classification",
            model=MODEL_NAME,
            tokenizer=MODEL_NAME,
            top_k=None,
            device=device,
            truncation=True,
            max_length=512,
            batch_size=16,
        )
        print("   Model loaded successfully")
        return clf
    except Exception as e:
        print(f"   Failed to load model: {e}")
        print("   Falling back to neutral stub")

        def dummy(texts):
            return [[{"label": "neutral", "score": 1.0}] for _ in texts]
        return dummy

# -------------------------------
# Data loading
# -------------------------------
def load_data(input_csv: str) -> pd.DataFrame:
    """Load input CSV with validation"""
    print(f"Loading {input_csv}...")

    if not os.path.exists(input_csv):
        print(f"   File not found: {input_csv}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(input_csv)
    except EmptyDataError:
        print("   CSV is empty")
        return pd.DataFrame()
    except Exception as e:
        print(f"   Error reading CSV: {e}")
        return pd.DataFrame()

    if df.empty:
        print("   No rows in CSV")
        return pd.DataFrame()

    # Validate required columns
    required = ["text"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    # Ensure ID column exists
    if "id" not in df.columns:
        print("   No 'id' column, generating IDs")
        df["id"] = [f"row_{i}" for i in range(len(df))]

    # Convert IDs to strings for consistency
    df["id"] = df["id"].astype(str)

    # Normalize created_at
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)

    # Ensure engagement column
    if "engagement" not in df.columns:
        df["engagement"] = 0
    else:
        df["engagement"] = pd.to_numeric(df["engagement"], errors="coerce").fillna(0)

    # Preserve source
    if "source" not in df.columns:
        df["source"] = "unknown"

    print(f"   Loaded {len(df)} rows")
    return df

# -------------------------------
# Scoring (with progress)
# -------------------------------
def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Score empathy and emotions for all rows in dataframe"""
    if df.empty:
        return df

    clf = build_emotion_pipeline()
    texts = df["text"].astype(str).tolist()

    print(f"\nScoring {len(texts)} items...")

    # Score in batches with progress
    batch_size = 100
    all_results = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_results = clf(batch)
        all_results.extend(batch_results)
        
        if len(texts) > batch_size:
            progress = min(100, int((i + batch_size) / len(texts) * 100))
            print(f"   Progress: {progress}% ({i + len(batch)}/{len(texts)})")

    print(f"   Scoring complete")

    # Process results
    empathy_scores = []
    empathy_labels = []
    emotion_top_1 = []
    emotion_top_2 = []
    emotion_top_3 = []

    for dist in all_results:
        if not dist or not isinstance(dist, list):
            # Fallback for empty/invalid results
            pos_sum = 0.5
            top1 = top2 = top3 = "neutral"
        else:
            # Sort emotions by score
            sorted_em = sorted(dist, key=lambda x: x["score"], reverse=True)
            top1 = sorted_em[0]["label"]
            top2 = sorted_em[1]["label"] if len(sorted_em) > 1 else ""
            top3 = sorted_em[2]["label"] if len(sorted_em) > 2 else ""

            # Calculate empathy score (sum of prosocial emotions)
            pos_sum = sum(item["score"] for item in sorted_em if item["label"] in PROSOCIAL)
            pos_sum = max(0.0, min(1.0, float(pos_sum)))

        label = empathy_label(pos_sum)

        empathy_scores.append(pos_sum)
        empathy_labels.append(label)
        emotion_top_1.append(top1)
        emotion_top_2.append(top2)
        emotion_top_3.append(top3)

    # Add scores to dataframe
    df["empathy_score"] = empathy_scores
    df["empathy_label"] = empathy_labels
    df["emotion_top_1"] = emotion_top_1
    df["emotion_top_2"] = emotion_top_2
    df["emotion_top_3"] = emotion_top_3

    return df

# -------------------------------
# Main
# -------------------------------
def main():
    print("=" * 60)
    print("EMPATHY & EMOTION SCORING")
    print("=" * 60)

    # CLI: python score_empathy.py [input.csv] [output.csv]
    input_csv = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT_CSV
    output_csv = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT_CSV

    print(f"Input:  {input_csv}")
    print(f"Output: {output_csv}")
    print()

    # Load input data
    df_input = load_data(input_csv)

    if df_input.empty:
        print("\nNo data to score. Writing empty output with full schema.")

        # Full schema expected by app.py
        cols = [
            "id", "text", "created_at", "author_id", "like_count", "reply_count",
            "repost_count", "quote_count", "engagement", "topic", "source",
            "empathy_score", "empathy_label", "emotion_top_1", "emotion_top_2", "emotion_top_3"
        ]
        empty_df = pd.DataFrame(columns=cols)
        empty_df.to_csv(output_csv, index=False, quoting=csv.QUOTE_MINIMAL)
        print(f"Empty {output_csv} written")
        return

    # Load existing scored data (for incremental scoring)
    df_existing, scored_ids = load_existing_scores(output_csv)

    # Filter to only NEW entries that need scoring
    df_to_score = df_input[~df_input["id"].isin(scored_ids)].copy()

    if df_to_score.empty:
        print("\nAll entries already scored! Nothing new to process.")
        print(f"   Total scored entries: {len(df_existing)}")
        return

    print(f"\nSummary:")
    print(f"   Total input entries: {len(df_input)}")
    print(f"   Already scored: {len(scored_ids)}")
    print(f"   New to score: {len(df_to_score)}")

    # Score only new entries
    df_newly_scored = score_dataframe(df_to_score)

    # Combine with existing scores
    if not df_existing.empty:
        df_combined = pd.concat([df_existing, df_newly_scored], ignore_index=True)
        # Remove any duplicate IDs (keep newest)
        df_combined = df_combined.drop_duplicates(subset=["id"], keep="last")
    else:
        df_combined = df_newly_scored

    print(f"\nFinal totals:")
    print(f"   Newly scored: {len(df_newly_scored)}")
    print(f"   Total entries: {len(df_combined)}")

    # Merge ALL columns from input into combined
    # Get columns from input that aren't in combined yet
    input_extra_cols = [col for col in df_input.columns if col not in df_combined.columns]
    
    if input_extra_cols:
        # Merge these columns from df_input
        df_combined = df_combined.merge(
            df_input[['id'] + input_extra_cols],
            on='id',
            how='left',
            suffixes=('', '_input')
        )
    
    # Define final column order
    expected = [
        "id", "text", "created_at", "author_id", "like_count", "reply_count",
        "repost_count", "quote_count", "engagement", "topic", "source",
        "empathy_score", "empathy_label", "emotion_top_1", "emotion_top_2", "emotion_top_3"
    ]
    
    # Add any extra columns
    for col in df_combined.columns:
        if col not in expected:
            expected.append(col)
    
    # Ensure all columns exist
    for col in expected:
        if col not in df_combined.columns:
            df_combined[col] = None

    # Reorder columns
    df_combined = df_combined[expected]
    
    for col in expected:
        if col not in df_combined.columns:
            df_combined[col] = None

    # Reorder columns (keep extras at end)
    df_combined = df_combined[expected]

    # Sort by engagement (most engaging first)
    if "engagement" in df_combined.columns:
        df_combined = df_combined.sort_values("engagement", ascending=False)

    # Save
    df_combined.to_csv(output_csv, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"\nSaved {len(df_combined)} scored rows to {output_csv}")

    # Show empathy distribution
    if "empathy_label" in df_combined.columns:
        print(f"\nEmpathy distribution:")
        label_counts = df_combined["empathy_label"].value_counts()
        for label, count in label_counts.items():
            pct = count / len(df_combined) * 100
            print(f"   {label}: {count} ({pct:.1f}%)")

    # Show top emotions
    if "emotion_top_1" in df_combined.columns:
        print(f"\nTop emotions:")
        emotion_counts = df_combined["emotion_top_1"].value_counts().head(5)
        for emotion, count in emotion_counts.items():
            print(f"   {emotion}: {count}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)