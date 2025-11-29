import streamlit as st

def check_password():
    """Returns True if user has entered correct password."""
    
    def password_entered():
        """Checks whether password entered is correct."""
        if st.session_state["password"] == "Moodlight2026!":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:

        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.write("*Please contact admin for access*")
        return False
    elif not st.session_state["password_correct"]:

        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:

        return True

if not check_password():
    st.stop()

import math
import subprocess

import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
import altair as alt
from startup import fetch_data_if_needed
fetch_data_if_needed()

st.set_page_config(
    page_title="Moodlight",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# -------------------------------
# Streamlit page config
# -------------------------------

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

def clean_source_name(source: str) -> str:
    """Convert source codes to readable names"""
    if source == "x":
        return "X (Twitter)"
    elif source == "news":
        return "NewsAPI"
    elif "reddit" in source.lower():
        parts = source.replace("reddit_", "").replace("_", " ")
        return f"Reddit: {parts.title()}"
    else:
        # Convert bbc_world to BBC World, etc.
        return source.replace("_", " ").title()

# -------------------------------
# Data loading
# -------------------------------
@st.cache_data(ttl=10)
def load_data() -> pd.DataFrame:
    sources = [
        ("social_scored.csv", None),
        ("news_scored.csv", "None"),
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
                
            if src:  # Only overwrite if src is provided
                df["source"] = src
            elif path == "social_scored.csv":
                # For social_scored.csv, mark posts without a source as 'x'
                df.loc[df["source"].isna() | (df["source"] == ""), "source"] = "x"
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

    # Process timestamps
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        before_drop = len(df)
        df = df.dropna(subset=["created_at"])
        # Silently drop invalid dates - no need to warn users

    if "engagement" in df.columns:
        df["engagement"] = pd.to_numeric(df["engagement"], errors="coerce").fillna(0)

    # Add readable source names
    if "source" in df.columns:
        df["source_display"] = df["source"].apply(clean_source_name)

    return df

@st.cache_data(ttl=10)
def load_market_data() -> pd.DataFrame:
    """Load market sentiment data"""
    try:
        df = pd.read_csv("markets.csv")
        if df.empty:
            return pd.DataFrame()
        return df
    except FileNotFoundError:
        return pd.DataFrame()
    except Exception as e:
        st.warning(f"Error loading market data: {str(e)[:100]}")
        return pd.DataFrame()

def run_fetch_and_score(custom_query: str | None = None) -> tuple[bool, str]:
    msg_parts = []
    has_error = False

    # Prepare environment with API keys
    import os
    env = os.environ.copy()
    try:
        env["X_BEARER_TOKEN"] = st.secrets.get("X_BEARER_TOKEN", "")
        env["NEWSAPI_KEY"] = st.secrets.get("NEWSAPI_KEY", "")
    except:
        pass
    
    # Fetch X posts
    cmd_x = [sys.executable, "fetch_posts.py"]
    
    if custom_query:
        cmd_x += ["--query", custom_query.strip()]

    try:
        x_proc = subprocess.run(cmd_x, capture_output=True, text=True, timeout=300, check=False, env=env)
        
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
                [sys.executable, "score_empathy.py", "social.csv", "social_scored.csv"],
                capture_output=True, text=True, timeout=300, check=False, env=env
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
            [sys.executable, "fetch_news_rss.py"], 
            capture_output=True, text=True, timeout=300, check=False, env=env
        )
        
        if news_proc.returncode != 0:
            has_error = True
            error_msg = news_proc.stderr[:100] if news_proc.stderr else "Unknown error"
            msg_parts.append(f"News fetch failed: {error_msg}")
        else:
            msg_parts.append("News fetched")
            
            # Score news data
            score_n = subprocess.run(
                [sys.executable, "score_empathy.py", "news.csv", "news_scored.csv"],
                capture_output=True, text=True, timeout=300, check=False, env=env
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
st.title("Moodlight")
st.caption("Real-time global news and culture analysis, prediction, and actionable intelligence")

with st.sidebar:
    st.header("Controls")
    custom_query = st.text_input(
        "Search for a topic",
        placeholder='e.g. "student loans"',
        help="Leave empty for default.",
    )
    brand_focus = st.checkbox(
    "Brand Focus Mode",
    value=False,
    help="When enabled, shows only posts matching your search query"
    )

    if st.button("Refresh"):
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

if brand_focus and custom_query.strip():
    search_term = custom_query.strip().lower()
    df_all = df_all[df_all["text"].str.lower().str.contains(search_term, na=False)]
    if len(df_all) == 0:
        st.warning(f"No posts found matching '{custom_query}'. Try refreshing data or a different search term.")
        st.stop()
    st.info(f"🎯 Brand Focus Mode: Showing {len(df_all)} posts about '{custom_query}'")
    
    if df_all.empty:
        st.error("No data available. Click 'Refresh' to fetch data.")
        st.stop()

# Create 48-hour filtered dataset
if "created_at" in df_all.columns:
    df_all["created_at"] = pd.to_datetime(df_all["created_at"], errors="coerce", utc=True)
    df_all = df_all.dropna(subset=["created_at"])
    cutoff_48h = datetime.now(timezone.utc) - timedelta(days=30)
    df_48h = df_all[df_all["created_at"] >= cutoff_48h].copy()
else:
    df_48h = df_all.copy()

# Compute world mood
world_score, world_label, world_emoji = compute_world_mood(df_48h)

# ==========================================
# INTELLIGENCE VISUALIZATIONS
# ==========================================

def create_intensity_gauge(df: pd.DataFrame, avg_intensity: float):
    """Create vertical thermometer showing global threat intensity"""
    import altair as alt
    import streamlit as st
    
    try:
        # Ensure it's a valid float
        avg_intensity = float(avg_intensity) if not pd.isna(avg_intensity) else 0.0
        
        # Create zones dataframe
        zones = pd.DataFrame({
            'zone': ['Low', 'Moderate', 'Elevated', 'Critical'],
            'min': [0.0, 1.5, 2.5, 3.5],
            'max': [1.5, 2.5, 3.5, 5.0],
            'color': ['#90EE90', '#FFFF00', '#FFA500', '#FF0000']
        })
        
        # Determine current zone
        if avg_intensity < 1.5:
            current_zone = 'Low'
        elif avg_intensity < 2.5:
            current_zone = 'Moderate'
        elif avg_intensity < 3.5:
            current_zone = 'Elevated'
        else:
            current_zone = 'Critical'
        
        # Create vertical bar with zones
        base = alt.Chart(zones).mark_bar(size=80).encode(
            y=alt.Y('min:Q', title='Threat Level (0-5)', scale=alt.Scale(domain=[0, 5])),
            y2='max:Q',
            color=alt.Color('color:N', scale=None, legend=None),
            tooltip=['zone:N']
        )
        
        # Add current level marker
        current_data = pd.DataFrame({'value': [float(avg_intensity)]})
        marker = alt.Chart(current_data).mark_rule(
                color='black',
                strokeWidth=2  # Change from 4 to 2
            ).encode(
                y='value:Q',
                tooltip=[alt.Tooltip('value:Q', title='Current Level', format='.2f')]
            )
        
        # Add text label
        text = alt.Chart(current_data).mark_text(
            align='left',
            dx=45,
            dy=-10,  # ADD THIS - moves text UP 10 pixels
            fontSize=16,
            fontWeight='bold',
            color='black'
        ).encode(
            y='value:Q',
            text=alt.Text('value:Q', format='.2f')
        )
        
        chart = (base + marker + text).properties(
            title=f'Global Threat Level: {avg_intensity:.2f} ({current_zone})',
            width=150,
            height=400
        )
        
        return chart
        
    except Exception as e:
        st.error(f"Chart error: {str(e)}")
        # Return simple text display as fallback
        st.markdown(f"### {avg_intensity:.2f} / 5.0")
        return None

def create_ic_topic_breakdown(df: pd.DataFrame):
    """Create breakdown of IC-level intelligence topics"""
    import altair as alt
    
    cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7)
    recent = df[df['created_at'] >= cutoff].copy()
    
    topic_counts = recent['topic'].value_counts().head(20).reset_index()
    topic_counts.columns = ['topic', 'count']
    
def create_geographic_hotspot_map(df: pd.DataFrame):
    """Create map showing countries by threat intensity"""
    import altair as alt
    
    cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(hours=48)
    recent = df[df['created_at'] >= cutoff].copy()
    
    country_stats = recent.groupby('country').agg({
        'intensity': 'mean',
        'id': 'count'
    }).reset_index()
    country_stats.columns = ['country', 'avg_intensity', 'article_count']
    
    country_stats = country_stats[
        (country_stats['country'] != 'Unknown') & 
        (country_stats['article_count'] >= 3)
    ].sort_values('avg_intensity', ascending=False).head(15)
    
    chart = (
        alt.Chart(country_stats)
        .mark_bar()
        .encode(
            y=alt.Y('country:N', sort='-x', title='Country'),
            x=alt.X('avg_intensity:Q', title='Average Threat Intensity (1-5)', scale=alt.Scale(domain=[0, 5])),
            color=alt.Color('avg_intensity:Q', scale=alt.Scale(scheme='reds'), legend=None),
            tooltip=[
                alt.Tooltip('country:N', title='Country'),
                alt.Tooltip('avg_intensity:Q', title='Avg Intensity', format='.2f'),
                alt.Tooltip('article_count:Q', title='Articles')
            ]
        )
        .properties(title='Geographic Hotspots (Last 48h)', height=500)
    )
    
    return chart

def create_ic_topic_breakdown(df: pd.DataFrame):
    """Create breakdown of IC-level intelligence topics"""
    import altair as alt
    
    cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7)
    recent = df[df['created_at'] >= cutoff].copy()
    
    topic_counts = recent['topic'].value_counts().head(20).reset_index()
    topic_counts.columns = ['topic', 'count']
    
    chart = (
        alt.Chart(topic_counts)
        .mark_bar()
        .encode(
            y=alt.Y('topic:N', sort='-x', title='Intelligence Category'),
            x=alt.X('count:Q', title='Article Count'),
            color=alt.value('#1f77b4'),
            tooltip=[
                alt.Tooltip('topic:N', title='Topic'),
                alt.Tooltip('count:Q', title='Articles')
            ]
        )
        .properties(title='Intelligence Topic Distribution (Last 7 Days)', height=600)
    )
    
    return chart

def create_trend_indicators(df: pd.DataFrame):
    """Show which topics are trending up/down"""
    import altair as alt
    from collections import Counter
    
    now = pd.Timestamp.now(tz='UTC')
    recent_start = now - pd.Timedelta(hours=24)
    prev_start = now - pd.Timedelta(hours=48)
    
    recent_df = df[df['created_at'] >= recent_start]
    prev_df = df[(df['created_at'] >= prev_start) & (df['created_at'] < recent_start)]
    
    if len(recent_df) == 0:
        recent_start = now - pd.Timedelta(days=3)
        prev_start = now - pd.Timedelta(days=7)
        recent_df = df[df['created_at'] >= recent_start]
        prev_df = df[(df['created_at'] >= prev_start) & (df['created_at'] < recent_start)]
    
    recent_topics = Counter(recent_df['topic'])
    prev_topics = Counter(prev_df['topic'])
    
    trends = []
    for topic in recent_topics:
        recent_count = recent_topics[topic]
        prev_count = prev_topics.get(topic, 1)
        change_pct = ((recent_count - prev_count) / prev_count) * 100
        
        trends.append({
            'topic': topic,
            'change_pct': round(change_pct, 1),
            'recent': recent_count
        })
    
    trends_df = pd.DataFrame(sorted(trends, key=lambda x: abs(x['change_pct']), reverse=True)[:15])
    
    chart = (
        alt.Chart(trends_df)
        .mark_bar()
        .encode(
            y=alt.Y('topic:N', sort='-x', title='Topic'),
            x=alt.X('change_pct:Q', title='% Change'),
            color=alt.condition(
                alt.datum.change_pct > 0,
                alt.value('green'),
                alt.value('red')
            ),
            tooltip=[
                alt.Tooltip('topic:N', title='Topic'),
                alt.Tooltip('change_pct:Q', title='Change %', format='+.1f'),
                alt.Tooltip('recent:Q', title='Recent Count')
            ]
        )
        .properties(title='Topic Trends (24h % change)', height=500)
    )
    
    return chart

    chart = (
        alt.Chart(topic_counts)
        .mark_bar()
        .encode(
            y=alt.Y('topic:N', sort='-x', title='Intelligence Category'),
            x=alt.X('count:Q', title='Article Count'),
            color=alt.value('#1f77b4'),
            tooltip=[
                alt.Tooltip('topic:N', title='Topic'),
                alt.Tooltip('count:Q', title='Articles')
            ]
        )
        .properties(title='Intelligence Topic Distribution (Last 7 Days)', height=600)
    )
    
    return chart

def create_trend_indicators(df: pd.DataFrame):
    """Show which topics are trending up/down"""
    import altair as alt
    from collections import Counter
    
    now = pd.Timestamp.now(tz='UTC')
    recent_start = now - pd.Timedelta(hours=24)
    prev_start = now - pd.Timedelta(hours=48)
    
    recent_df = df[df['created_at'] >= recent_start]
    prev_df = df[(df['created_at'] >= prev_start) & (df['created_at'] < recent_start)]
    
    if len(recent_df) == 0:
        recent_start = now - pd.Timedelta(days=3)
        prev_start = now - pd.Timedelta(days=7)
        recent_df = df[df['created_at'] >= recent_start]
        prev_df = df[(df['created_at'] >= prev_start) & (df['created_at'] < recent_start)]
    
    recent_topics = Counter(recent_df['topic'])
    prev_topics = Counter(prev_df['topic'])
    
    trends = []
    for topic in recent_topics:
        recent_count = recent_topics[topic]
        prev_count = prev_topics.get(topic, 1)
        change_pct = ((recent_count - prev_count) / prev_count) * 100
        
        trends.append({
            'topic': topic,
            'change_pct': round(change_pct, 1),
            'recent': recent_count
        })
    
    trends_df = pd.DataFrame(sorted(trends, key=lambda x: abs(x['change_pct']), reverse=True)[:15])
    
    chart = (
        alt.Chart(trends_df)
        .mark_bar()
        .encode(
            y=alt.Y('topic:N', sort='-x', title='Topic'),
            x=alt.X('change_pct:Q', title='% Change'),
            color=alt.condition(
                alt.datum.change_pct > 0,
                alt.value('green'),
                alt.value('red')
            ),
            tooltip=[
                alt.Tooltip('topic:N', title='Topic'),
                alt.Tooltip('change_pct:Q', title='Change %', format='+.1f'),
                alt.Tooltip('recent:Q', title='Recent Count')
            ]
        )
        .properties(title='Topic Trends (24h % change)', height=500)
    )
    
    return chart

# Date header
current_date = datetime.now().strftime("%B %d, %Y")
st.markdown(f"## {current_date}")

# Social & News Sentiment Section
st.markdown("### Social & News Sentiment")

if world_score is None or len(df_48h) == 0:
    st.warning("Not enough data from the last 48 hours yet. Try refreshing.")
else:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Global Mood Score", world_score)
    with c2:
        st.markdown(f"**{world_emoji} {world_label}**  \n*Based on {len(df_48h)} posts*")

st.caption(f"X query: *{custom_query.strip() or '[default timeline]'}*")

# ========================================
# MARKET MOOD
# ========================================
st.markdown("### Market Sentiment")

df_markets = load_market_data()

if not df_markets.empty and "market_sentiment" in df_markets.columns:
    market_score = df_markets["market_sentiment"].iloc[0]
    market_pct = int(round(market_score * 100))
    
    if market_pct < 40:
        market_label = "Bearish 🐻"
        market_color = "#DC143C"
    elif market_pct < 60:
        market_label = "Neutral ⚖️"
        market_color = "#808080"
    else:
        market_label = "Bullish 🐂"
        market_color = "#2E7D32"
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Market Sentiment", market_pct)
    with col2:
        st.markdown(f"**{market_label}**")
        st.caption(f"Based on {len(df_markets)} global indices")
    
    # Show individual indices
    st.markdown("#### Global Markets")
    cols = st.columns(4)
    for idx, (_, row) in enumerate(df_markets.iterrows()):
        with cols[idx % 4]:
            change = float(row['change_percent'])
            emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
            st.caption(f"{emoji} **{row['name']}**")
            st.caption(f"{change:+.2f}%")
else:
    st.info("Market data not available. Run fetch_markets.py to fetch.")

st.markdown("---")

# ========================================
# MOOD VS MARKET COMPARISON
# ========================================
st.markdown("## Mood vs Market: Leading Indicators")
st.caption("Track how social sentiment compares to market performance over time")

# Check if we have enough historical data
if "created_at" in df_all.columns and "empathy_score" in df_all.columns and not df_markets.empty:
    # Calculate daily social mood for last 7 days
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    
    df_hist = df_all[["created_at", "empathy_score"]].copy()
    df_hist = df_hist.dropna()
    df_hist = df_hist[df_hist["created_at"] >= seven_days_ago]
    
    if len(df_hist) > 0:
        df_hist["date"] = df_hist["created_at"].dt.date
        
        # Daily average social mood
        daily_social = (
            df_hist.groupby("date")["empathy_score"]
            .mean()
            .reset_index()
        )
        daily_social = daily_social.rename(columns={'empathy_score': 'social_mood'})
        daily_social["social_mood"] = (daily_social["social_mood"] * 100).round().astype(int)
        daily_social["type"] = "Social Mood"
        
        # Get market sentiment (currently just today's value, will build history over time)
        market_value = int(round(df_markets["market_sentiment"].iloc[0] * 100))
        
    # Create market reference line (horizontal)
        market_line = pd.DataFrame({
            "date": daily_social["date"].tolist(),
            "score": [market_value] * len(daily_social),
            "metric": ["Market Mood"] * len(daily_social)
        })

        # Combine data
        combined = pd.concat([
            daily_social.rename(columns={'social_mood': 'score'}).assign(metric='Social Mood'),
            market_line
        ])

        # Create comparison chart
        comparison_chart = (
            alt.Chart(combined)
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x=alt.X("date:T", title="Date", axis=alt.Axis(format='%b %d', values=combined['date'].unique().tolist())),
                y=alt.Y("score:Q", title="Sentiment Score (0-100)", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("metric:N", 
                              title="Sentiment Type",
                              scale=alt.Scale(domain=['Social Mood', 'Market Mood'],
                                            range=['#1f77b4', '#2E7D32'])),
                tooltip=[
                    alt.Tooltip("date:T", format="%B %d, %Y"),
                    alt.Tooltip("metric:N", title="Type"),
                    alt.Tooltip("score:Q", title="Score")
                ]
            )
            .properties(height=300)
            .interactive()
        )
        
        st.altair_chart(comparison_chart, use_container_width=True)
        
        # Show divergence analysis
        col1, col2, col3 = st.columns(3)
        
        with col1:
            latest_social = daily_social["social_mood"].iloc[-1] if len(daily_social) > 0 else 50
            st.metric("Latest Social Mood", latest_social)
        
        with col2:
            st.metric("Latest Market Mood", market_value)
        
        with col3:
            divergence = abs(latest_social - market_value)
            if divergence > 20:
                status = "⚠️ High Divergence"
                color = "🔴"
            elif divergence > 10:
                status = "⚡ Moderate Divergence"
                color = "🟡"
            else:
                status = "✅ Aligned"
                color = "🟢"
            
            st.metric("Alignment", status)
            st.caption(f"{color} {divergence} point difference")
    else:
        st.info("Building historical data... Check back after a few days for trend comparison")
else:
    st.info("Insufficient data for comparison. Run data fetch to populate.")

st.markdown("---")

# ========================================
# SECTION 2: DETAILED ANALYSIS
# ========================================
st.markdown("## Detailed Analysis (Last 48 Hours)")

df_filtered = df_48h.copy()

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
st.markdown(f"**Filtered posts:** {len(df_filtered)}")

if "empathy_score" in df_filtered.columns and len(df_filtered):
    avg = df_filtered["empathy_score"].mean()
    st.metric("Average empathy (filtered)", empathy_label_from_score(avg) or "N/A", f"{avg:.3f}")

# Average Empathy by Topic
if "topic" in df_filtered.columns and "empathy_score" in df_filtered.columns and len(df_filtered):
    st.markdown("### Average Empathy by Topic")
    topic_avg = (
        df_filtered.groupby("topic")["empathy_score"]
        .agg(['mean', 'count'])
        .reset_index()
        .rename(columns={'mean': 'avg_empathy'})
    )
    topic_avg = topic_avg[topic_avg['count'] >= 2]
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
                              labelExpr='["🥶 Cold","😐 Neutral","🙂 Warm","❤️ Empathetic"][datum.value]')),
        color=alt.Color("label:N", 
                      scale=alt.Scale(domain=EMPATHY_LEVELS),
                      legend=alt.Legend(
                          symbolType="square",
                          labelExpr='{"Cold / Hostile": "🥶 Cold / Hostile", "Detached / Neutral": "😐 Detached / Neutral", "Warm / Supportive": "🙂 Warm / Supportive", "Highly Empathetic": "❤️ Highly Empathetic"}[datum.label]'
                      )),
        tooltip=[
            "topic", 
            "label", 
            alt.Tooltip("avg_empathy", format=".3f", title="Score"),
            alt.Tooltip("count", title="Posts")
        ]
    )
)
        st.altair_chart(chart, use_container_width=True)
    # Show topic insights
    st.markdown("#### Topic Insights")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🔥 Most Empathetic Topics**")
        top_empathetic = topic_avg.nlargest(3, 'avg_empathy')
        for _, row in top_empathetic.iterrows():
            st.caption(f"• **{row['topic']}** - {row['label']} ({row['avg_empathy']:.2f})")

    with col2:
        st.markdown("**🥶 Coldest/Most Hostile Topics**")
        bottom_empathetic = topic_avg.nsmallest(3, 'avg_empathy')
        for _, row in bottom_empathetic.iterrows():
            st.caption(f"• **{row['topic']}** - {row['label']} ({row['avg_empathy']:.2f})")

    st.markdown("---")

# ========================================
# EMOTIONAL BREAKDOWN
# ========================================
if "emotion_top_1" in df_filtered.columns and len(df_filtered):
    st.markdown("### Emotional Breakdown")
    st.caption("Dominant emotions detected across all posts")
    
    emotion_counts = df_filtered["emotion_top_1"].value_counts()
    
    if len(emotion_counts) > 0:
        chart_df = emotion_counts.reset_index()
        chart_df.columns = ["emotion", "posts"]
        
        # Define emotion colors
        emotion_colors = {
            "joy": "#FFD700",
            "sadness": "#4682B4", 
            "anger": "#DC143C",
            "fear": "#8B008B",
            "surprise": "#FF8C00",
            "disgust": "#556B2F",
            "neutral": "#808080"
        }
        
        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                x=alt.X("posts:Q", title="Number of Posts"),
                y=alt.Y("emotion:N", sort="-x", title="Emotion"),
                color=alt.Color("emotion:N", 
                              scale=alt.Scale(domain=list(emotion_colors.keys()),
                                            range=list(emotion_colors.values())),
                              legend=None),
                tooltip=["emotion", "posts"]
            )
        )
        st.altair_chart(chart, use_container_width=True)
        
        # Show percentages
        col1, col2, col3 = st.columns(3)
        total = emotion_counts.sum()
        top3 = emotion_counts.head(3)
        
        for idx, (col, (emotion, count)) in enumerate(zip([col1, col2, col3], top3.items())):
            with col:
                pct = (count / total * 100)
                st.metric(f"{emotion.title()}", f"{pct:.1f}%", f"{count} posts")
                        
        st.markdown("---")

# ========================================
# SECTION 3: EMPATHY DISTRIBUTION
# ========================================
if "empathy_label" in df_filtered.columns and len(df_filtered):
    st.markdown("### Empathy Distribution")
    st.caption("How empathetically people are communicating (tone and approach)")
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

    # Show percentages for top 3 empathy levels
    col1, col2, col3 = st.columns(3)
    total = counts.sum()
    top3 = counts.nlargest(3)
    
    for col, (label, count) in zip([col1, col2, col3], top3.items()):
        if count > 0:
            with col:
                pct = (count / total * 100)
                st.metric(label, f"{pct:.1f}%", f"{count} posts")

    st.markdown("---")

# ========================================
# SECTION 4: TOPIC DISTRIBUTION
# ========================================
if "topic" in df_filtered.columns and len(df_filtered):
    st.markdown("### Topic Distribution")
    counts = df_filtered["topic"].value_counts().head(15)
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
    
    # Show top topics
    if len(counts) > 0:
        st.markdown("#### Top Discussed Topics")
        col1, col2, col3 = st.columns(3)
        top3 = counts.head(3)
        
        for idx, (col, (topic, count)) in enumerate(zip([col1, col2, col3], top3.items())):
            with col:
                rank = ["🥇", "🥈", "🥉"][idx]
                pct = (count / counts.sum() * 100)
                st.metric(f"{rank} {topic}", f"{pct:.1f}%", f"{count} posts")

    st.markdown("---")

# ========================================
# SECTION 5: TRENDING HEADLINES
# ========================================
st.markdown("### Trending Headlines")
st.caption("Posts with highest engagement plotted by empathy vs. time")

if "created_at" in df_all.columns and "engagement" in df_all.columns and len(df_all) > 0:
    df_trending = df_all.nlargest(30, "engagement").copy()
    now = datetime.now(timezone.utc)
    three_days_ago = now - timedelta(days=3)
    df_trending = df_all[df_all["created_at"] >= three_days_ago].nlargest(30, "engagement").copy()
    df_trending["hours_ago"] = (now - df_trending["created_at"]).dt.total_seconds() / 3600

    trending_chart = (
        alt.Chart(df_trending)
        .mark_circle(size=100, opacity=0.7)
        .encode(
            x=alt.X("hours_ago:Q", title="Hours Ago", scale=alt.Scale(reverse=True)),
            y=alt.Y("empathy_score:Q", title="Empathy Score", scale=alt.Scale(domain=[0, 1])),
            size=alt.Size("engagement:Q", title="Engagement", scale=alt.Scale(range=[100, 2000])),
            color=alt.Color("source_display:N", title="Source"),
            tooltip=[
                alt.Tooltip("text:N", title="Headline"),
                alt.Tooltip("source_display:N", title="Source"),
                alt.Tooltip("engagement:Q", title="Engagement", format=","),
                alt.Tooltip("empathy_score:Q", title="Empathy", format=".2f"),
                alt.Tooltip("created_at:T", title="Posted", format="%b %d, %H:%M")
            ]
        )
        .properties(height=400)
        .interactive()
    )
    st.altair_chart(trending_chart, use_container_width=True)
    
   # Show headline insights
    st.markdown("#### Headline Insights")
    
    if not df_trending.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**📈 Highest Engagement**")
            top_post = df_trending.nlargest(1, 'engagement').iloc[0]
            st.caption(f"**{top_post['source_display']}** ({top_post['engagement']:,.0f} engagements)")
            st.caption(f"_{top_post['text'][:100]}..._")
        
        with col2:
            st.markdown("**❤️ Most Empathetic Viral Post**")
            top_empathy = df_trending.nlargest(1, 'empathy_score').iloc[0]
            st.caption(f"**{top_empathy['source_display']}** (Score: {top_empathy['empathy_score']:.2f})")
            st.caption(f"_{top_empathy['text'][:100]}..._")
        
        with col3:
            st.markdown("**🥶 Least Empathetic Viral Post**")
            bottom_empathy = df_trending.nsmallest(1, 'empathy_score').iloc[0]
            st.caption(f"**{bottom_empathy['source_display']}** (Score: {bottom_empathy['empathy_score']:.2f})")
            st.caption(f"_{bottom_empathy['text'][:100]}..._")
    else:
        st.info("No headline insights available yet.")

st.markdown("---")

# ========================================
# SECTION 6: VIRALITY × EMPATHY
# ========================================
st.markdown("### Virality × Empathy: Posts with Viral Potential")
st.caption("High-engagement posts from last 3 days - bigger bubbles = higher engagement")

if "engagement" in df_all.columns and "created_at" in df_all.columns and len(df_all) > 0:
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    vdf = df_all[df_all["created_at"] >= three_days_ago].copy()
    
    now = datetime.now(timezone.utc)
    vdf["age_hours"] = (now - vdf["created_at"]).dt.total_seconds() / 3600
    vdf["age_hours"] = vdf["age_hours"].replace(0, 0.1)
    vdf["virality"] = vdf["engagement"] / vdf["age_hours"]
    
    if len(vdf) > 10:
        virality_threshold = vdf["virality"].quantile(0.3)  # Top 70%
        engagement_threshold = vdf["engagement"].quantile(0.3)  # Top 70%
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
                color=alt.Color("source_display:N", title="Source"),
                tooltip=[
                    alt.Tooltip("text:N", title="Post"),
                    alt.Tooltip("source_display:N", title="Source"),
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
        
        # Show virality insights
        st.markdown("#### Virality Insights")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🚀 Fastest Rising**")
            fastest = vdf_high.nlargest(1, 'virality').iloc[0]
            st.caption(f"**{fastest['source_display']}** ({fastest['virality']:.1f} eng/hr)")
            st.caption(f"_{fastest['text'][:100]}..._")
        
        with col2:
            st.markdown("**❤️ Most Engaging Empathetic**")
            # Filter for empathetic posts (score > 0.6)
            empathetic = vdf_high[vdf_high['empathy_score'] > 0.6]
            if len(empathetic) > 0:
                top_emp = empathetic.nlargest(1, 'engagement').iloc[0]
                st.caption(f"**{top_emp['source_display']}** ({top_emp['engagement']:,.0f} eng)")
                st.caption(f"_{top_emp['text'][:100]}..._")
            else:
                st.caption("No highly empathetic viral posts")
        
        with col3:
            st.markdown("**🥶 Most Engaging Hostile**")
            # Filter for hostile posts (score < 0.4)
            hostile = vdf_high[vdf_high['empathy_score'] < 0.4]
            if len(hostile) > 0:
                top_host = hostile.nlargest(1, 'engagement').iloc[0]
                st.caption(f"**{top_host['source_display']}** ({top_host['engagement']:,.0f} eng)")
                st.caption(f"_{top_host['text'][:100]}..._")
            else:
                st.caption("No hostile viral posts")

        source_counts = vdf_high["source"].value_counts()
        st.caption(f"Source breakdown: {dict(source_counts)}")
    else:
        st.info("No high-virality posts in last 3 days yet.")
else:
    st.info("No engagement data available.")

st.markdown("---")

# ========================================
# NEW SECTION: VELOCITY × LONGEVITY
# ========================================
st.markdown("### Velocity × Longevity: Topic Strategic Value")
st.caption("Understand which topics are lasting movements vs. fleeting trends")

# Load longevity data
try:
    longevity_df = pd.read_csv('topic_longevity.csv')
    
    # Normalize velocity for better visualization (log scale)
    longevity_df['velocity_norm'] = longevity_df['velocity_score'] / longevity_df['velocity_score'].max()
    
    # Create quadrants
    velocity_median = longevity_df['velocity_norm'].median()
    longevity_median = longevity_df['longevity_score'].median()
    
    def get_quadrant(row):
        if row['velocity_norm'] >= velocity_median and row['longevity_score'] >= longevity_median:
            return "Lasting Movement 🚀"
        elif row['velocity_norm'] >= velocity_median and row['longevity_score'] < longevity_median:
            return "Flash Trend ⚡"
        elif row['velocity_norm'] < velocity_median and row['longevity_score'] >= longevity_median:
            return "Evergreen Topic 🌲"
        else:
            return "Fading Out 💨"
    
    longevity_df['quadrant'] = longevity_df.apply(get_quadrant, axis=1)
    
    # Create chart
    quad_chart = (
        alt.Chart(longevity_df)
        .mark_circle(size=200, opacity=0.7)
        .encode(
            x=alt.X("velocity_norm:Q", title="Velocity (Normalized)", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("longevity_score:Q", title="Longevity Score", scale=alt.Scale(domain=[0, 1])),
            size=alt.Size("post_count:Q", title="Post Volume", scale=alt.Scale(range=[100, 1000])),
            color=alt.Color("quadrant:N", title="Strategic Value",
                          scale=alt.Scale(domain=["Lasting Movement 🚀", "Flash Trend ⚡", 
                                                "Evergreen Topic 🌲", "Fading Out 💨"],
                                        range=["#2E7D32", "#FFA726", "#5C6BC0", "#9E9E9E"])),
            tooltip=[
                alt.Tooltip("topic:N", title="Topic"),
                alt.Tooltip("quadrant:N", title="Category"),
                alt.Tooltip("longevity_score:Q", title="Longevity", format=".2f"),
                alt.Tooltip("velocity_norm:Q", title="Velocity", format=".2f"),
                alt.Tooltip("post_count:Q", title="Posts"),
                alt.Tooltip("source_count:Q", title="Sources")
            ]
        )
        .properties(height=500)
        .interactive()
    )
    
    st.altair_chart(quad_chart, use_container_width=True)
    
    # Show quadrant breakdown
    st.markdown("#### Strategic Breakdown:")
    cols = st.columns(4)
    for i, (quad, emoji) in enumerate([
        ("Lasting Movement 🚀", "High velocity + High longevity"),
        ("Flash Trend ⚡", "High velocity + Low longevity"),
        ("Evergreen Topic 🌲", "Low velocity + High longevity"),
        ("Fading Out 💨", "Low velocity + Low longevity")
    ]):
        with cols[i]:
            count = len(longevity_df[longevity_df['quadrant'] == quad])
            st.metric(quad.split()[0], count)
            st.caption(emoji.split(' + ')[1])
            
except FileNotFoundError:
    st.info("Run calculate_longevity.py first to generate topic analysis")

st.markdown("---")

# ========================================
# DENSITY ANALYSIS
# ========================================
st.markdown("### Density: Where Conversations Are Concentrated")
st.caption("Understand geographic, platform, and conversation depth")

try:
    density_df = pd.read_csv('topic_density.csv')
    
    # Create density visualization
    density_chart = (
        alt.Chart(density_df)
        .mark_bar()
        .encode(
            y=alt.Y("topic:N", sort="-x", title="Topic"),
            x=alt.X("density_score:Q", title="Density Score (0-1)", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("density_score:Q", 
                          scale=alt.Scale(scheme='viridis'),
                          legend=None),
            tooltip=[
                alt.Tooltip("topic:N", title="Topic"),
                alt.Tooltip("density_score:Q", title="Density", format=".2f"),
                alt.Tooltip("primary_region:N", title="Primary Region"),
                alt.Tooltip("primary_platform:N", title="Primary Platform"),
                alt.Tooltip("conversation_depth:N", title="Conversation Depth"),
                alt.Tooltip("post_count:Q", title="Posts")
            ]
        )
        .properties(height=500)
    )
    
    st.altair_chart(density_chart, use_container_width=True)
    
    # Show density insights
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🎯 Most Concentrated**")
        top3 = density_df.nlargest(3, 'density_score')
        for _, row in top3.iterrows():
            st.caption(f"{row['topic']}: {row['density_score']:.2f}")
    
    with col2:
        st.markdown("**🌍 Geographic Spread**")
        geo_diversity = density_df.nlargest(3, 'geo_diversity')
        for _, row in geo_diversity.iterrows():
            st.caption(f"{row['topic']}: {row['primary_region']}")
    
    with col3:
        st.markdown("**💬 Deepest Discussions**")
        deep = density_df[density_df['conversation_depth'] == 'Deep (active debate)'].head(3)
        for _, row in deep.iterrows():
            st.caption(f"{row['topic']}")
            
except FileNotFoundError:
    st.info("Run calculate_density.py to generate density analysis")

st.markdown("---")

# ========================================
# SCARCITY ANALYSIS
# ========================================
st.markdown("### Scarcity: Topic Opportunity Gaps")
st.caption("Discover underserved topics where brands can establish thought leadership")

try:
    scarcity_df = pd.read_csv('topic_scarcity.csv')
    
    # Create scarcity chart
    scarcity_chart = (
        alt.Chart(scarcity_df)
        .mark_bar()
        .encode(
            y=alt.Y("topic:N", sort="-x", title="Topic"),
            x=alt.X("scarcity_score:Q", title="Scarcity Score (1.0 = Zero Coverage)", 
                   scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("opportunity:N", 
                          scale=alt.Scale(domain=['HIGH', 'MEDIUM', 'LOW'],
                                        range=['#2E7D32', '#FFA726', '#9E9E9E']),
                          title="Opportunity Level"),
            tooltip=[
                alt.Tooltip("topic:N", title="Topic"),
                alt.Tooltip("scarcity_score:Q", title="Scarcity", format=".2f"),
                alt.Tooltip("mention_count:Q", title="Current Mentions"),
                alt.Tooltip("coverage_level:N", title="Coverage"),
                alt.Tooltip("opportunity:N", title="Opportunity")
            ]
        )
        .properties(height=500)
    )
    
    st.altair_chart(scarcity_chart, use_container_width=True)
    
    # Strategic insights
    st.markdown("#### Strategic Opportunities")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**HIGH OPPORTUNITY** (First-mover advantage)")
        high_opp = scarcity_df[scarcity_df['opportunity'] == 'HIGH'].head(5)
        for _, row in high_opp.iterrows():
            st.caption(f"• **{row['topic']}** ({row['mention_count']} mentions)")
    
    with col2:
        st.markdown("**SATURATED** (High competition)")
        saturated = scarcity_df[scarcity_df['scarcity_score'] < 0.3].head(3)
        if len(saturated) > 0:
            for _, row in saturated.iterrows():
                st.caption(f"• {row['topic']} ({row['mention_count']} mentions)")
        else:
            st.caption("No saturated topics found")
    
    # Key insight
    st.info(f"Insight: {len(scarcity_df[scarcity_df['opportunity'] == 'HIGH'])} topics have HIGH scarcity - white space opportunities for thought leadership.")

except FileNotFoundError:
    st.info("Run calculate_scarcity.py to generate scarcity analysis")

st.markdown("---")

# ========================================
# SECTION 7: 7-DAY MOOD HISTORY
# ========================================
st.markdown("### 7-Day Mood History")

if "created_at" in df_all.columns and "empathy_score" in df_all.columns:
    df_hist = df_all[["created_at", "empathy_score"]].copy()
    df_hist = df_hist.dropna()
    
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    df_week = df_hist[df_hist["created_at"] >= seven_days_ago].copy()
    
    if len(df_week) > 0:
        df_week["date"] = df_week["created_at"].dt.date
        
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
        
        st.caption(f"Showing {len(daily)} days with data (posts per day: {daily['count'].min()}-{daily['count'].max()})")
        
        mood_chart = (
            alt.Chart(daily)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("date:T", title="Date", axis=alt.Axis(format='%b %d', values=daily['date'].unique().tolist())),
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
        st.info(f"No data in the last 7 days.")
else:
    st.info("No historical data available.")

# ========================================
# SECTION 8: WORLD VIEW
# ========================================
st.markdown("### World View")
st.caption("All posts from the last 3 days - scroll to explore")

cols = [c for c in ["text", "source", "topic", "empathy_label", "emotion_top_1", "engagement", "created_at"] if c in df_filtered.columns]
if len(df_filtered):
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

st.markdown("---")

# ========================================
# INTELLIGENCE DASHBOARD
# ========================================
st.markdown("### 🎯 Intelligence Dashboard")
st.caption("IC-level threat analysis with geographic hotspots and trend detection")

# Check if intensity and country columns exist
if 'intensity' in df_all.columns and 'country' in df_all.columns:
    
    # Row 1: Threat gauge + IC topics
    col1, col2 = st.columns([1, 2])
    
    with col1:
        avg_int = df_all['intensity'].mean()
        
        chart = create_intensity_gauge(df_all, avg_int)
        if chart is not None:
            st.altair_chart(chart, use_container_width=True)
    
    with col2:
        st.altair_chart(create_ic_topic_breakdown(df_all), use_container_width=True)
    
    # Row 2: Geographic hotspots + Trends
    col1, col2 = st.columns(2)
    
    with col1:
        st.altair_chart(create_geographic_hotspot_map(df_all), use_container_width=True)
    
    with col2:
        st.altair_chart(create_trend_indicators(df_all), use_container_width=True)

        # Quick Trends Section
        st.markdown("#### 📈 Quick Trends (24h)")

        from collections import Counter

        now = pd.Timestamp.now(tz='UTC')
        recent_start = now - pd.Timedelta(hours=24)
        prev_start = now - pd.Timedelta(hours=48)

        recent_df = df_all[df_all['created_at'] >= recent_start]
        prev_df = df_all[(df_all['created_at'] >= prev_start) & (df_all['created_at'] < recent_start)]

        if len(recent_df) == 0:
            recent_start = now - pd.Timedelta(days=3)
            prev_start = now - pd.Timedelta(days=7)
            recent_df = df_all[df_all['created_at'] >= recent_start]
            prev_df = df_all[(df_all['created_at'] >= prev_start) & (df_all['created_at'] < recent_start)]

        recent_topics = Counter(recent_df['topic'])
        prev_topics = Counter(prev_df['topic'])

        trends = []
        for topic in recent_topics:
            recent_count = recent_topics[topic]
            prev_count = prev_topics.get(topic, 1)
            change_pct = ((recent_count - prev_count) / prev_count) * 100
            trends.append({'topic': topic, 'change': change_pct})

        trends = sorted(trends, key=lambda x: abs(x['change']), reverse=True)[:20]

        for t in trends:
            arrow = "🟢" if t['change'] > 0 else "🔴"
            st.markdown(f"{arrow} **{t['topic']}**: {t['change']:+.0f}%")

else:
    st.info("Intelligence features require updated data. Run fetch_posts.py to enable geographic and intensity analysis.")