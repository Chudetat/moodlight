#!/usr/bin/env python
"""
trade_analyst.py
Moodlight's investment intelligence layer.
Pulls all real-time data (news sentiment, social momentum, markets,
Polymarket, economic indicators) and asks Claude for specific trade
recommendations with ticker, direction, conviction, and reasoning.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text as sql_text
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2000


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=300)


def _load_recent_news(engine, days=2, limit=50):
    """Load recent scored news headlines."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        df = pd.read_sql(
            sql_text("""
                SELECT text, source, topic, empathy_label, emotion_top_1,
                       created_at
                FROM news_scored
                WHERE created_at >= :cutoff
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            engine,
            params={"cutoff": cutoff, "limit": limit},
        )
        return df
    except Exception as e:
        print(f"  Failed to load news: {e}")
        return pd.DataFrame()


def _load_recent_social(engine, days=2, limit=50):
    """Load recent scored social posts."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        df = pd.read_sql(
            sql_text("""
                SELECT text, source, topic, empathy_label, emotion_top_1,
                       engagement, created_at
                FROM social_scored
                WHERE created_at >= :cutoff
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            engine,
            params={"cutoff": cutoff, "limit": limit},
        )
        return df
    except Exception as e:
        print(f"  Failed to load social: {e}")
        return pd.DataFrame()


def _load_market_data(engine):
    """Load latest market index data."""
    try:
        df = pd.read_sql(
            sql_text("""
                SELECT symbol, price, change_percent, latest_trading_day
                FROM markets
                WHERE timestamp::timestamptz >= NOW() - INTERVAL '7 days'
                ORDER BY timestamp DESC
            """),
            engine,
        )
        # Deduplicate to latest per symbol
        if not df.empty:
            df = df.drop_duplicates(subset=["symbol"], keep="first")
        return df
    except Exception as e:
        print(f"  Failed to load markets: {e}")
        return pd.DataFrame()


def _load_recent_alerts(engine, days=3, limit=20):
    """Load recent alerts for context."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        df = pd.read_sql(
            sql_text("""
                SELECT alert_type, severity, title, summary, brand, topic,
                       timestamp
                FROM alerts
                WHERE timestamp >= :cutoff
                ORDER BY timestamp DESC
                LIMIT :limit
            """),
            engine,
            params={"cutoff": cutoff, "limit": limit},
        )
        return df
    except Exception as e:
        print(f"  Failed to load alerts: {e}")
        return pd.DataFrame()


def _load_polymarket(limit=15):
    """Load prediction market data."""
    try:
        from polymarket_helper import fetch_polymarket_markets
        markets = fetch_polymarket_markets(limit=limit)
        return markets
    except Exception as e:
        print(f"  Failed to load Polymarket: {e}")
        return []


def _load_signal_log_performance(engine):
    """Load signal log hit rate for self-awareness."""
    try:
        df = pd.read_sql(
            sql_text("""
                SELECT
                    COUNT(*) as total_signals,
                    COUNT(spy_change_1d) as tracked,
                    AVG(spy_change_1d) as avg_1d,
                    AVG(spy_change_5d) as avg_5d,
                    COUNT(CASE WHEN spy_change_1d > 0 THEN 1 END) as positive_1d,
                    COUNT(CASE WHEN spy_change_5d > 0 THEN 1 END) as positive_5d
                FROM signal_log
                WHERE spy_change_1d IS NOT NULL
            """),
            engine,
        )
        if not df.empty:
            r = df.iloc[0]
            return {
                "total_tracked": int(r["tracked"]),
                "avg_1d_change": round(float(r["avg_1d"] or 0), 3),
                "avg_5d_change": round(float(r["avg_5d"] or 0), 3),
                "win_rate_1d": round(int(r["positive_1d"]) / max(int(r["tracked"]), 1) * 100, 1),
                "win_rate_5d": round(int(r["positive_5d"]) / max(int(r["tracked"]), 1) * 100, 1),
            }
    except Exception:
        pass
    return None


def _load_portfolio(engine):
    """Load current portfolio positions and cash."""
    try:
        df = pd.read_sql(
            sql_text("""
                SELECT * FROM trade_portfolio
                ORDER BY updated_at DESC
            """),
            engine,
        )
        return df
    except Exception:
        return pd.DataFrame()


def _format_news_for_prompt(df):
    if df.empty:
        return "No recent news data available."
    lines = []
    for _, row in df.head(30).iterrows():
        sentiment = row.get("empathy_label", "neutral")
        emotion = row.get("emotion_top_1", "")
        lines.append(f"- [{sentiment}/{emotion}] {row['text'][:200]} (source: {row.get('source', 'unknown')}, topic: {row.get('topic', 'general')})")
    return "\n".join(lines)


def _format_social_for_prompt(df):
    if df.empty:
        return "No recent social data available."
    lines = []
    for _, row in df.head(20).iterrows():
        sentiment = row.get("empathy_label", "neutral")
        engagement = row.get("engagement", 0)
        lines.append(f"- [{sentiment}, eng:{engagement}] {row['text'][:200]}")
    return "\n".join(lines)


def _format_markets_for_prompt(df):
    if df.empty:
        return "No market data available."
    lines = []
    for _, row in df.iterrows():
        try:
            price = float(row['price'])
            change = float(row['change_percent'])
            lines.append(f"- {row['symbol']}: ${price:.2f} ({change:+.2f}%) as of {row['latest_trading_day']}")
        except (ValueError, TypeError):
            lines.append(f"- {row['symbol']}: {row['price']} ({row['change_percent']}%) as of {row['latest_trading_day']}")
    return "\n".join(lines)


def _format_alerts_for_prompt(df):
    if df.empty:
        return "No recent alerts."
    lines = []
    for _, row in df.head(15).iterrows():
        lines.append(f"- [{row['severity']}] {row['title']} ({row['alert_type']})")
    return "\n".join(lines)


def _format_polymarket_for_prompt(markets):
    if not markets:
        return "No prediction market data available."
    lines = []
    for m in markets[:10]:
        lines.append(f"- {m['question']} — YES: {m['yes_odds']}%, NO: {m['no_odds']}% (vol: ${m['volume']:,.0f})")
    return "\n".join(lines)


def _format_portfolio_for_prompt(df):
    if df.empty:
        return "No current positions. Full cash: $1,000."
    lines = []
    for _, row in df.iterrows():
        lines.append(f"- {row.get('symbol', '?')}: {row.get('qty', 0)} shares @ ${row.get('avg_entry', 0):.2f}")
    return "\n".join(lines)


def generate_trade_recommendations(engine):
    """Pull all data and generate trade recommendations via Claude."""
    print("  Loading data sources...")

    df_news = _load_recent_news(engine)
    print(f"    News: {len(df_news)} articles")

    df_social = _load_recent_social(engine)
    print(f"    Social: {len(df_social)} posts")

    df_markets = _load_market_data(engine)
    print(f"    Markets: {len(df_markets)} indices")

    df_alerts = _load_recent_alerts(engine)
    print(f"    Alerts: {len(df_alerts)} recent")

    polymarket = _load_polymarket()
    print(f"    Polymarket: {len(polymarket)} markets")

    signal_perf = _load_signal_log_performance(engine)
    df_portfolio = _load_portfolio(engine)

    # Build prompt
    perf_context = ""
    if signal_perf:
        perf_context = f"""
HISTORICAL SIGNAL PERFORMANCE (for self-calibration):
- {signal_perf['total_tracked']} signals tracked
- 1-day win rate: {signal_perf['win_rate_1d']}% (avg change: {signal_perf['avg_1d_change']}%)
- 5-day win rate: {signal_perf['win_rate_5d']}% (avg change: {signal_perf['avg_5d_change']}%)
- NOTE: Past signals have been better at detecting events than predicting direction.
  Be cautious and focus on high-conviction setups only.
"""

    prompt = f"""You are Moodlight's Trade Analyst — an AI investment advisor managing a $1,000 paper trading portfolio.

Your job: analyze all real-time intelligence below and recommend specific trades for today.

RULES:
1. You manage a $1,000 portfolio. Never recommend risking more than 20% on a single position.
2. Recommend 0-3 trades per day. If nothing looks compelling, say HOLD and explain why.
3. For each trade, provide: TICKER, ACTION (BUY/SELL), AMOUNT ($), CONVICTION (1-10), REASONING.
4. Consider both long and short-term plays (1-5 day holds).
5. Set a STOP LOSS for every trade (max 5% loss per position).
6. Set a TAKE PROFIT target for every trade.
7. Factor in the overall market direction before individual picks.
8. Be honest about uncertainty. Only recommend trades with conviction >= 7.
9. If the data is stale or insufficient, say so and recommend HOLD.

CURRENT PORTFOLIO:
{_format_portfolio_for_prompt(df_portfolio)}

{perf_context}

=== REAL-TIME INTELLIGENCE ===

NEWS SENTIMENT (last 48 hours):
{_format_news_for_prompt(df_news)}

SOCIAL MOMENTUM:
{_format_social_for_prompt(df_social)}

MARKET INDICES:
{_format_markets_for_prompt(df_markets)}

MOODLIGHT ALERTS (last 72 hours):
{_format_alerts_for_prompt(df_alerts)}

PREDICTION MARKETS (Polymarket):
{_format_polymarket_for_prompt(polymarket)}

=== END INTELLIGENCE ===

Respond in this EXACT JSON format:
{{
  "market_assessment": "2-3 sentence overall market read",
  "trades": [
    {{
      "ticker": "SYMBOL",
      "action": "BUY" or "SELL",
      "amount_usd": 200,
      "conviction": 8,
      "stop_loss_pct": 3.0,
      "take_profit_pct": 6.0,
      "hold_days": 3,
      "reasoning": "Why this trade based on the intelligence"
    }}
  ],
  "hold_reason": "If no trades, explain why",
  "risk_warnings": ["Any key risks to watch today"]
}}

If recommending zero trades, return an empty trades array and fill hold_reason."""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ERROR: ANTHROPIC_API_KEY not set")
        return None

    client = Anthropic(api_key=api_key)

    print("  Asking Claude for trade recommendations...")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Parse JSON from response (handle markdown code blocks)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)
        print(f"  Received {len(result.get('trades', []))} trade recommendation(s)")
        return result

    except json.JSONDecodeError as e:
        print(f"  Failed to parse Claude response as JSON: {e}")
        print(f"  Raw response: {raw[:500]}")
        return None
    except Exception as e:
        print(f"  Claude API error: {e}")
        return None


def main():
    print("=" * 60)
    print("MOODLIGHT TRADE ANALYST")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    engine = _get_engine()

    result = generate_trade_recommendations(engine)

    if not result:
        print("\nNo recommendations generated.")
        sys.exit(1)

    print(f"\n  Market Assessment: {result.get('market_assessment', 'N/A')}")

    trades = result.get("trades", [])
    if trades:
        for i, t in enumerate(trades, 1):
            print(f"\n  Trade #{i}:")
            print(f"    {t['action']} {t['ticker']} — ${t['amount_usd']}")
            print(f"    Conviction: {t['conviction']}/10")
            print(f"    Stop Loss: {t['stop_loss_pct']}% | Take Profit: {t['take_profit_pct']}%")
            print(f"    Hold: {t['hold_days']} days")
            print(f"    Reasoning: {t['reasoning']}")
    else:
        print(f"\n  HOLD — {result.get('hold_reason', 'No compelling setups')}")

    warnings = result.get("risk_warnings", [])
    if warnings:
        print(f"\n  Risk Warnings:")
        for w in warnings:
            print(f"    ⚠ {w}")

    # Return for use by trade_executor
    return result


if __name__ == "__main__":
    main()
