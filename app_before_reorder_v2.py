import math
import subprocess
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
import altair as alt

# -------------------------------
# Streamlit page config
# -------------------------------
st.set_page_config(page_title="World Mood Score", layout="wide")

# -------------------------------
# Global constants
# -------------------------------
EMPATHY_LEVELS = [
    "Cold / Hostile",
    "Detached / Neutral",
    "Warm / Supportive",
    "Highly Empathetic",
]

TOPIC_CATEGORIES = [
    "politics", "government", "economics", "education", "culture & identity",
    "branding & advertising", "creative & design", "technology & ai",
    "climate & environment", "healthcare & wellbeing", "immigration",
    "crime & safety", "war & foreign policy", "media & journalism",
    "race & ethnicity", "gender & sexuality", "business & corporate",
    "labor & work", "housing", "religion & values", "sports",
    "entertainment", "other",
]

# -------------------------------
# Helper functions
# -------------------------------
def empathy_label_from_score(score: float) -> str | None:
    if score is None or math.isnan(score):
        return None
    score = max(0.0, min(1.0, float(score)))
    if score < 0.25:
        return EMPATHY_LEVELS[0]
    if score < 0.5:
        return EMPATHY_LEVELS[1]
    if score < 0.75:
        return EMPATHY_LEVELS[2]
    return EMPATHY_LEVELS[3]

def empathy_index_from_label(label: str | None) -> int | None:
    return EMPATHY_LEVELS.index(label) if label in EMPATHY_LEVELS else None

# -------------------------------
# Data loading
# -------------------------------
@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    sources = [
        ("social_scored.csv", "x"),
        ("news_scored.csv", "news"),
    ]
    frames = []

    for path, src in sources:
        try:
            df = pd.read_csv(path)
            if df.empty:
                continue
            
            # Validate required columns
            required_cols = ["empathy_score", "created_at", "text"]
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                st.warning(f"Warning: {path} missing columns: {missing}")
                continue
                
            df["source"] = src
            frames.append(df)
        except FileNotFoundError:
            st.warning(f"Warning: {path} not found - click Refresh to fetch data")
            continue
        except pd.errors.EmptyDataError:
            st.warning(f"Warning: {path} is empty")
            continue
        except Exception as e:
            st.error(f"Error loading {path}: {str(e)[:200]}")
            continue

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # Process empathy scores
    if "empathy_score" in df.columns:
        df["empathy_score"] = pd.to_numeric(df["empathy_score"], errors="coerce")
        df["empathy_label"] = df["empathy_score"].apply(empathy_label_from_score)

    # Process timestamps - CRITICAL FIX
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        # Drop rows with invalid dates
        before_drop = len(df)
        df = df.dropna(subset=["created_at"])
        if len(df) < before_drop:
            st.warning(f"Dropped {before_drop - len(df)} rows with invalid dates")

    if "engagement" in df.columns:
        df["engagement"] = pd.to_numeric(df["engagement"], errors="coerce").fillna(0)

    return df

def run_fetch_and_score(custom_query: str | None = None) -> tuple[bool, str]:
    msg_parts = []
    has_error = False

    # Fetch X posts
    cmd_x = ["python3", "fetch_posts.py"]
    if custom_query:
        cmd_x += ["--query", custom_query.strip()]

    try:
        x_proc = subprocess.run(cmd_x, capture_output=True, text=True, timeout=300, check=False)
        
        if x_proc.returncode == 2:
            msg_parts.append("X quota hit - kept previous data")
        elif x_proc.returncode != 0:
            has_error = True
            error_msg = x_proc.stderr[:100] if x_proc.stderr else "Unknown error"
            msg_parts.append(f"X fetch failed: {error_msg}")
        else:
            msg_parts.append("X fetched")
            
            # Score X data
            score_x = subprocess.run(
                ["python3", "score_empathy.py", "social.csv", "social_scored.csv"],
                capture_output=True, text=True, timeout=300, check=False
            )
            if score_x.returncode == 0:
                msg_parts.append("X scored")
            else:
                has_error = True
                error_msg = score_x.stderr[:100] if score_x.stderr else "Unknown error"
                msg_parts.append(f"X scoring failed: {error_msg}")
                
    except subprocess.TimeoutExpired:
        has_error = True
        msg_parts.append("X fetch timed out")
    except Exception as e:
        has_error = True
        msg_parts.append(f"X exception: {str(e)[:100]}")

    # Fetch news
    try:
        news_proc = subprocess.run(
            ["python3", "fetch_news_rss.py"], 
            capture_output=True, text=True, timeout=300, check=False
        )
        
        if news_proc.returncode != 0:
            has_error = True
            error_msg = news_proc.stderr[:100] if news_proc.stderr else "Unknown error"
            msg_parts.append(f"News fetch failed: {error_msg}")
        else:
            msg_parts.append("News fetched")
            
            # Score news data
            score_n = subprocess.run(
                ["python3", "score_empathy.py", "news.csv", "news_scored.csv"],
                capture_output=True, text=True, timeout=300, check=False
            )
            if score_n.returncode == 0:
                msg_parts.append("News scored")
            else:
                has_error = True
                error_msg = score_n.stderr[:100] if score_n.stderr else "Unknown error"
                msg_parts.append(f"News scoring failed: {error_msg}")
                
    except subprocess.TimeoutExpired:
        has_error = True
        msg_parts.append("News fetch timed out")
    except Exception as e:
        has_error = True
        msg_parts.append(f"News exception: {str(e)[:100]}")

    return not has_error, " | ".join(msg_parts)

# -------------------------------
# World Mood Score
# -------------------------------
def compute_world_mood(df: pd.DataFrame) -> tuple[int | None, str | None, str]:
    if "empathy_score" not in df.columns or df["empathy_score"].isna().all():
        return None, None, ""
    avg = df["empathy_score"].mean()
    score = int(round(avg * 100))
    if score < 25:
        label = "Very Cold / Hostile"
        emoji = "🥶"
    elif score < 50:
        label = "Detached / Neutral"
        emoji = "😐"
    elif score < 75:
        label = "Warm / Supportive"
        emoji = "🙂"
    else:
        label = "Highly Empathetic"
        emoji = "❤️"
    return score, label, emoji

# -------------------------------
# UI
# -------------------------------
st.title("World Mood Score")

with st.sidebar:
    st.header("Controls")
    custom_query = st.text_input(
        "Search X for a topic",
        placeholder='e.g. "student loans"',
        help="Leave empty for default.",
    )

    if st.button("Refresh from X + News now"):
        with st.spinner("Fetching & scoring..."):
            ok, msg = run_fetch_and_score(custom_query.strip() or None)
            st.cache_data.clear()
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        st.rerun()

# Load all data once
df_all = load_data()

if df_all.empty:
    st.error("No data available. Click 'Refresh from X + News now' to fetch data.")
    st.stop()

# Create 48-hour filtered dataset for "current mood"
# --- 48h data (FIXED: Safe datetime conversion) ---
if "created_at" in df_all.columns:
    # Convert to datetime safely
    df_all["created_at"] = pd.to_datetime(df_all["created_at"], errors="coerce", utc=True)
    df_all = df_all.dropna(subset=["created_at"])  # Drop invalid dates

    cutoff_48h = datetime.now(timezone.utc) - timedelta(hours=48)
    df_48h = df_all[df_all["created_at"] >= cutoff_48h].copy()
else:
    df_48h = df_all.copy()

# Compute world mood from 48h data
world_score, world_label, world_emoji = compute_world_mood(df_48h)

current_date = datetime.now().strftime("%B %d, %Y")
st.markdown(f"## World Mood Score (last 48 hours) — {current_date}")

if world_score is None or len(df_48h) == 0:
    st.warning("Not enough data from the last 48 hours yet. Try refreshing.")
else:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.metric("Mood (0-100)", world_score)
    with c2:
        st.markdown(f"**{world_emoji} {world_label}**  \n*Based on {len(df_48h)} posts*")
    with c3:
        latest = df_48h["created_at"].max()
        st.caption(f"Latest: {latest.strftime('%b %d, %H:%M UTC')}")

st.caption(f"X query: *{custom_query.strip() or '[default timeline]'}*")

# — FIX #2: 7-DAY MOOD HISTORY —
st.markdown("### 7-Day Mood History")

if "created_at" in df_all.columns and "empathy_score" in df_all.columns:
    df_hist = df_all[["created_at", "empathy_score"]].copy()
    df_hist = df_hist.dropna()

    # Get date range
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    # Filter to last 7 days
    df_week = df_hist[df_hist["created_at"] >= seven_days_ago].copy()

    if len(df_week) > 0:
        # Create date column (date only, no time)
        df_week["date"] = df_week["created_at"].dt.date
        
        # Group by date and compute average
        daily = (
            df_week.groupby("date")["empathy_score"]
            .agg(['mean', 'count'])
            .reset_index()
        )
        daily = daily.rename(columns={'mean': 'mood_score'})
        daily["mood_score"] = (daily["mood_score"] * 100).round().astype(int)
        daily["label"] = daily["mood_score"].apply(
            lambda x: "Very Cold / Hostile" if x < 25 else
                      "Detached / Neutral" if x < 50 else
                      "Warm / Supportive" if x < 75 else
                      "Highly Empathetic"
        )
        
        # Show data summary
        st.caption(f"Showing {len(daily)} days with data (posts per day: {daily['count'].min()}-{daily['count'].max()})")
        
        # Chart with line and points
        mood_chart = (
            alt.Chart(daily)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("date:T", title="Date", axis=alt.Axis(format='%b %d')),
                y=alt.Y("mood_score:Q", title="Mood Score (0-100)", scale=alt.Scale(domain=[0, 100])),
                color=alt.value("#1f77b4"),
                tooltip=[
                    alt.Tooltip("date:T", format="%B %d, %Y"),
                    alt.Tooltip("mood_score:Q", title="Score"),
                    alt.Tooltip("label:N", title="Mood"),
                    alt.Tooltip("count:Q", title="Posts")
                ]
            )
            .properties(height=250)
        )
        st.altair_chart(mood_chart, use_container_width=True)
    else:
        st.info(f"No data in the last 7 days. Oldest post: {df_hist['created_at'].min().strftime('%Y-%m-%d')}")
else:
    st.info("No historical data available.")

# — FIX #4: TRENDING HEADLINES (X-Y GRAPH) —
st.markdown("### Trending Headlines")
st.caption("Posts with highest engagement plotted by empathy vs. time")

if "created_at" in df_all.columns and "engagement" in df_all.columns and len(df_all) > 0:
    # Get top 30 most engaged posts
    df_trending = df_all.nlargest(30, "engagement").copy()

    # Calculate hours ago
    now = datetime.now(timezone.utc)
    df_trending["hours_ago"] = (now - df_trending["created_at"]).dt.total_seconds() / 3600

    # Create scatter plot
    trending_chart = (
        alt.Chart(df_trending)
        .mark_circle(size=100, opacity=0.7)
        .encode(
            x=alt.X("hours_ago:Q", title="Hours Ago", scale=alt.Scale(reverse=True)),
            y=alt.Y("empathy_score:Q", title="Empathy Score", scale=alt.Scale(domain=[0, 1])),
            size=alt.Size("engagement:Q", title="Engagement", scale=alt.Scale(range=[100, 2000])),
            color=alt.Color("source:N", title="Source", scale=alt.Scale(scheme='category10')),
            tooltip=[
                alt.Tooltip("text:N", title="Headline"),
                alt.Tooltip("source:N", title="Source"),
                alt.Tooltip("engagement:Q", title="Engagement", format=","),
                alt.Tooltip("empathy_score:Q", title="Empathy", format=".2f"),
                alt.Tooltip("created_at:T", title="Posted", format="%b %d, %H:%M")
            ]
        )
        .properties(height=400)
        .interactive()
    )
    st.altair_chart(trending_chart, use_container_width=True)
else:
    st.info("No engagement data available yet.")

# — FIX #3: VIRALITY × EMPATHY (EXPANDED TIME WINDOW) —
st.markdown("### Virality × Empathy: Posts with Viral Potential")
st.caption("High-engagement posts from last 7 days (not just 48h) - bigger bubbles = higher engagement")

if "engagement" in df_all.columns and "created_at" in df_all.columns and len(df_all) > 0:
    # Use last 7 days instead of 48h to get more data
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    vdf = df_all[df_all["created_at"] >= seven_days_ago].copy()

    now = datetime.now(timezone.utc)
    vdf["age_hours"] = (now - vdf["created_at"]).dt.total_seconds() / 3600
    vdf["age_hours"] = vdf["age_hours"].replace(0, 0.1)  # Avoid division by zero
    vdf["virality"] = vdf["engagement"] / vdf["age_hours"]

    # Show posts above 70th percentile in virality OR top engagement
    if len(vdf) > 10:
        virality_threshold = vdf["virality"].quantile(0.7)
        engagement_threshold = vdf["engagement"].quantile(0.8)
        vdf_high = vdf[(vdf["virality"] > virality_threshold) | (vdf["engagement"] > engagement_threshold)]
    else:
        vdf_high = vdf

    if len(vdf_high) > 0:
        st.caption(f"Showing {len(vdf_high)} high-potential posts (X: {len(vdf_high[vdf_high['source']=='x'])}, News: {len(vdf_high[vdf_high['source']=='news'])})")
        
        virality_chart = (
            alt.Chart(vdf_high)
            .mark_circle(opacity=0.6)
            .encode(
                x=alt.X("virality:Q", title="Virality (Engagement/Hour)", scale=alt.Scale(type='log')),
                y=alt.Y("empathy_score:Q", title="Empathy Score", scale=alt.Scale(domain=[0, 1])),
                size=alt.Size("engagement:Q", title="Total Engagement", scale=alt.Scale(range=[200, 2000])),
                color=alt.Color("source:N", title="Source", scale=alt.Scale(scheme='set1')),
                tooltip=[
                    alt.Tooltip("text:N", title="Post"),
                    alt.Tooltip("source:N", title="Source"),
                    alt.Tooltip("virality:Q", title="Virality", format=".1f"),
                    alt.Tooltip("engagement:Q", title="Engagement", format=","),
                    alt.Tooltip("empathy_score:Q", title="Empathy", format=".2f"),
                    alt.Tooltip("age_hours:Q", title="Hours Old", format=".1f")
                ]
            )
            .properties(height=400)
            .interactive()
        )
        st.altair_chart(virality_chart, use_container_width=True)
        
        # Show breakdown by source
        source_counts = vdf_high["source"].value_counts()
        st.caption(f"Source breakdown: {dict(source_counts)}")
    else:
        st.info("No high-virality posts in last 7 days yet. Try refreshing to get more data.")
else:
    st.info("No engagement data available.")

# Apply filters to 48h data for remaining sections
df_filtered = df_48h.copy()

st.markdown("---")
st.markdown("## Detailed Analysis (Last 48 Hours)")

# Filters
if "topic" in df_filtered.columns:
    topics = sorted(df_filtered["topic"].dropna().unique())
    sel_topics = st.sidebar.multiselect("Filter by topic", topics, default=topics)
    if sel_topics:
        df_filtered = df_filtered[df_filtered["topic"].isin(sel_topics)]

if "emotion_top_1" in df_filtered.columns:
    emotions = sorted(df_filtered["emotion_top_1"].dropna().unique())
    sel_emo = st.sidebar.multiselect("Filter by dominant emotion", emotions, default=emotions)
    if sel_emo:
        df_filtered = df_filtered[df_filtered["emotion_top_1"].isin(sel_emo)]

search = st.sidebar.text_input("Search in text")
if search:
    df_filtered = df_filtered[df_filtered["text"].str.contains(search, case=False, na=False)]

# Show source breakdown
if len(df_filtered) > 0:
    source_breakdown = df_filtered["source"].value_counts()
    st.markdown(f"**Filtered posts:** {len(df_filtered)} (X: {source_breakdown.get('x', 0)}, News: {source_breakdown.get('news', 0)})")
else:
    st.markdown(f"**Filtered posts:** 0")

if "empathy_score" in df_filtered.columns and len(df_filtered):
    avg = df_filtered["empathy_score"].mean()
    st.metric("Average empathy (filtered)", empathy_label_from_score(avg) or "N/A", f"{avg:.3f}")

# — Average Empathy by Topic —
if "topic" in df_filtered.columns and "empathy_score" in df_filtered.columns and len(df_filtered):
    st.markdown("### Average Empathy by Topic")
    topic_avg = (
        df_filtered.groupby("topic")["empathy_score"]
        .agg(['mean', 'count'])
        .reset_index()
        .rename(columns={'mean': 'avg_empathy'})
    )
    topic_avg = topic_avg[topic_avg['count'] >= 2]  # Only show topics with 2+ posts
    topic_avg["label"] = topic_avg["avg_empathy"].apply(empathy_label_from_score)
    topic_avg["idx"] = topic_avg["label"].apply(empathy_index_from_label)
    topic_avg = topic_avg.dropna(subset=["idx"])

    if len(topic_avg):
        chart = (
            alt.Chart(topic_avg)
            .mark_bar()
            .encode(
                y=alt.Y("topic:N", sort="-x", title="Topic"),
                x=alt.X("idx:Q", title="Empathy Level", scale=alt.Scale(domain=[0, 3]),
                        axis=alt.Axis(values=[0,1,2,3],
                                      labelExpr='["Cold","Neutral","Warm","Empathetic"][datum.value]')),
                color=alt.Color("label:N", scale=alt.Scale(domain=EMPATHY_LEVELS)),
                tooltip=[
                    "topic", 
                    "label", 
                    alt.Tooltip("avg_empathy", format=".3f", title="Score"),
                    alt.Tooltip("count", title="Posts")
                ]
            )
        )
        st.altair_chart(chart, use_container_width=True)

# — Empathy Distribution —
if "empathy_label" in df_filtered.columns and len(df_filtered):
    st.markdown("### Empathy Distribution")
    counts = df_filtered["empathy_label"].value_counts().reindex(EMPATHY_LEVELS, fill_value=0)
    chart_df = counts.reset_index()
    chart_df.columns = ["label", "posts"]
    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("posts:Q", title="Number of Posts"),
            y=alt.Y("label:N", sort=EMPATHY_LEVELS, title="Empathy Level"),
            tooltip=["label", "posts"],
            color=alt.Color("label:N", scale=alt.Scale(domain=EMPATHY_LEVELS), legend=None)
        )
    )
    st.altair_chart(chart, use_container_width=True)

# — Topic Distribution —
if "topic" in df_filtered.columns and len(df_filtered):
    st.markdown("### Topic Distribution")
    counts = df_filtered["topic"].value_counts().head(15)  # Top 15 topics
    chart_df = counts.reset_index()
    chart_df.columns = ["topic", "posts"]
    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            y=alt.Y("topic:N", sort="-x", title="Topic"),
            x=alt.X("posts:Q", title="Number of Posts"),
            tooltip=["topic", "posts"],
            color=alt.value("#1f77b4")
        )
    )
    st.altair_chart(chart, use_container_width=True)

# — FIX #5: WORLD VIEW (SCROLLABLE LIST) —
st.markdown("### World View")
st.caption("All posts from the last 48 hours - scroll to explore")

cols = [c for c in ["text", "source", "topic", "empathy_label", "emotion_top_1", "engagement", "created_at"] if c in df_filtered.columns]
if len(df_filtered):
    # Format the dataframe for better display
    display_df = df_filtered[cols].copy()
    if "created_at" in display_df.columns:
        display_df["created_at"] = display_df["created_at"].dt.strftime("%b %d, %H:%M")

    st.dataframe(
        display_df.head(100),
        use_container_width=True,
        column_config={
            "text": st.column_config.TextColumn("Post", width="large"),
            "source": st.column_config.TextColumn("Source", width="small"),
            "engagement": st.column_config.NumberColumn("Engagement", format="%d"),
            "empathy_label": st.column_config.TextColumn("Empathy"),
            "created_at": st.column_config.TextColumn("Posted")
        },
        height=600
    )
else:
    st.info("No posts match your filters.")