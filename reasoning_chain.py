#!/usr/bin/env python
"""
Multi-step reasoning chains for Moodlight alert investigation.
Replaces single-turn investigation for complex alerts with a sequential
chain of Claude calls where each step's output feeds into the next.

Chain steps:
1. Situation Assessment — What is happening?
2. Historical Context — Has this happened before?
3. Causal Analysis — Why is this happening?
4. Strategic Implications — What should the user do?
5. Confidence Scoring — How confident are we?

Not every alert needs all 5 steps. Simple alerts get 2-3 steps,
complex/predictive alerts get the full chain.
"""

import os
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Chain configuration — which alert types get which steps
# ---------------------------------------------------------------------------

CHAIN_CONFIGS = {
    # Simple: 3 steps
    "brand_news_surge": ["situation", "causal", "confidence"],
    "brand_social_buzz": ["situation", "causal", "confidence"],
    "brand_sentiment_shift": ["situation", "historical", "confidence"],
    "mood_shift": ["situation", "causal", "confidence"],
    "intensity_cluster": ["situation", "causal", "confidence"],
    "brand_mention_surge": ["situation", "causal", "confidence"],

    # Medium: 4 steps
    "market_mood_divergence": ["situation", "historical", "causal", "confidence"],
    "topic_emergence": ["situation", "causal", "strategic", "confidence"],
    "brand_white_space": ["situation", "causal", "strategic", "confidence"],
    "brand_velocity_spike": ["situation", "historical", "strategic", "confidence"],
    "brand_narrative_fading": ["situation", "historical", "strategic", "confidence"],
    "brand_saturation": ["situation", "causal", "strategic", "confidence"],
    "competitor_momentum": ["situation", "historical", "causal", "confidence"],
    "share_of_voice_shift": ["situation", "historical", "strategic", "confidence"],
    "competitive_white_space": ["situation", "causal", "strategic", "confidence"],

    # Full 5 steps for predictive and compound
    "predictive_mood_shift": ["situation", "historical", "causal", "strategic", "confidence"],
    "predictive_intensity_cluster": ["situation", "historical", "causal", "strategic", "confidence"],
    "predictive_brand_velocity_spike": ["situation", "historical", "causal", "strategic", "confidence"],
    "predictive_brand_saturation": ["situation", "historical", "causal", "strategic", "confidence"],
    "predictive_brand_white_space": ["situation", "historical", "causal", "strategic", "confidence"],
    "predictive_market_mood_divergence": ["situation", "historical", "causal", "strategic", "confidence"],
    "predictive_compound_signal": ["situation", "historical", "causal", "strategic", "confidence"],
    # New alert types
    "brand_crisis": ["situation", "historical", "causal", "strategic", "confidence"],
    "regulatory_policy_spike": ["situation", "historical", "causal", "strategic", "confidence"],
    "breaking_signal": ["situation", "causal", "confidence"],
    "geopolitical_risk_escalation": ["situation", "historical", "causal", "strategic", "confidence"],
    # Situation reports (correlated alert clusters)
    "situation_report": ["situation", "historical", "causal", "strategic", "confidence"],
    # Topic watchlist detectors
    "topic_mention_surge": ["situation", "causal", "confidence"],
    "topic_sentiment_shift": ["situation", "historical", "confidence"],
    "topic_intensity_spike": ["situation", "causal", "confidence"],
    "topic_velocity_spike": ["situation", "historical", "strategic", "confidence"],
    "topic_saturation": ["situation", "causal", "strategic", "confidence"],
    "predictive_topic_velocity_spike": ["situation", "historical", "causal", "strategic", "confidence"],
    "predictive_topic_saturation": ["situation", "historical", "causal", "strategic", "confidence"],
    # Economic detectors
    "economic_stress": ["situation", "historical", "causal", "strategic", "confidence"],
    "economic_threshold_crossing": ["situation", "historical", "causal", "confidence"],
    # Commodity detector
    "commodity_spike": ["situation", "causal", "strategic", "confidence"],
    # Brand stock detector
    "brand_stock_divergence": ["situation", "historical", "causal", "strategic", "confidence"],
}

DEFAULT_CHAIN = ["situation", "causal", "confidence"]

STEP_DISPATCH = {}  # Populated after function definitions

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS_PER_STEP = 600


# ---------------------------------------------------------------------------
# Context building (adapted from alert_investigator._build_context)
# ---------------------------------------------------------------------------

def _build_context(alert, df_news=None, df_social=None, df_markets=None, engine=None):
    """Gather supporting data for the investigation prompt."""
    parts = []
    brand = alert.get("brand")

    if df_news is not None and not df_news.empty:
        sample = df_news
        if brand:
            brand_lower = brand.lower()
            for col in ["title", "text"]:
                if col in sample.columns:
                    mask = sample[col].str.contains(brand_lower, case=False, na=False)
                    filtered = sample[mask]
                    if not filtered.empty:
                        sample = filtered
                        break
        if "title" in sample.columns:
            headlines = sample["title"].dropna().head(10).tolist()
            parts.append("Recent headlines:\n" + "\n".join(f"- {h}" for h in headlines))

    if df_social is not None and not df_social.empty:
        sample = df_social
        if brand:
            brand_lower = brand.lower()
            for col in ["text", "title"]:
                if col in sample.columns:
                    mask = sample[col].str.contains(brand_lower, case=False, na=False)
                    filtered = sample[mask]
                    if not filtered.empty:
                        sample = filtered
                        break
        if "text" in sample.columns:
            posts = sample["text"].dropna().head(5).tolist()
            parts.append("Recent social posts:\n" + "\n".join(f"- {p[:200]}" for p in posts))

    if df_markets is not None and not df_markets.empty:
        if "market_sentiment" in df_markets.columns:
            avg_sentiment = df_markets["market_sentiment"].mean()
            parts.append(f"Current market sentiment: {avg_sentiment:.2f} (0=bearish, 1=bullish)")

    # Economic indicators context
    if engine:
        try:
            from sqlalchemy import text as _sql_text
            with engine.connect() as conn:
                result = conn.execute(_sql_text("""
                    SELECT metric_name, metric_value, snapshot_date
                    FROM metric_snapshots
                    WHERE scope = 'economic'
                      AND snapshot_date = (
                          SELECT MAX(snapshot_date) FROM metric_snapshots
                          WHERE scope = 'economic' AND metric_name = metric_snapshots.metric_name
                      )
                    ORDER BY metric_name
                """))
                rows = result.fetchall()
                if rows:
                    econ_lines = ["Economic indicators:"]
                    for name, value, date in rows:
                        label = name.replace("_", " ").title()
                        econ_lines.append(f"  - {label}: {value} (as of {date})")
                    parts.append("\n".join(econ_lines))
        except Exception:
            pass

    # Commodity prices context
    if engine:
        try:
            from sqlalchemy import text as _sql_text
            with engine.connect() as conn:
                result = conn.execute(_sql_text("""
                    SELECT scope_name, metric_name, metric_value
                    FROM metric_snapshots
                    WHERE scope = 'commodity'
                      AND snapshot_date = (
                          SELECT MAX(snapshot_date) FROM metric_snapshots
                          WHERE scope = 'commodity'
                      )
                    ORDER BY scope_name, metric_name
                """))
                rows = result.fetchall()
                if rows:
                    comm_lines = ["Commodity prices:"]
                    for scope_name, metric_name, value in rows:
                        if metric_name == "price":
                            comm_lines.append(f"  - {scope_name}: ${value:.2f}")
                        elif metric_name == "daily_change_pct":
                            comm_lines.append(f"    (daily change: {value:+.2f}%)")
                    parts.append("\n".join(comm_lines))
        except Exception:
            pass

    return "\n\n".join(parts) if parts else "No additional context available."


# ---------------------------------------------------------------------------
# Historical data loading
# ---------------------------------------------------------------------------

def _load_historical_alerts(engine, alert_type, brand=None, days=30):
    """Load past alerts of the same type for precedent analysis."""
    if not engine:
        return []

    from sqlalchemy import text

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        with engine.connect() as conn:
            if brand:
                result = conn.execute(
                    text("""
                        SELECT timestamp, title, summary
                        FROM alerts
                        WHERE alert_type = :atype AND brand = :brand
                          AND timestamp > :cutoff
                        ORDER BY timestamp DESC LIMIT 5
                    """),
                    {"atype": alert_type, "brand": brand, "cutoff": cutoff},
                )
            else:
                result = conn.execute(
                    text("""
                        SELECT timestamp, title, summary
                        FROM alerts
                        WHERE alert_type = :atype AND timestamp > :cutoff
                        ORDER BY timestamp DESC LIMIT 5
                    """),
                    {"atype": alert_type, "cutoff": cutoff},
                )
            rows = result.fetchall()
            return [
                {"timestamp": str(r[0]), "title": r[1], "summary": r[2]}
                for r in rows
            ]
    except Exception as e:
        print(f"WARNING: _load_historical_alerts failed: {e}")
        return []


def _load_metric_history(engine, scope, scope_name, metric_name, days=30):
    """Load metric snapshot history for trend context."""
    if not engine:
        return []

    from sqlalchemy import text

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    try:
        with engine.connect() as conn:
            if scope_name:
                result = conn.execute(
                    text("""
                        SELECT snapshot_date, metric_value FROM metric_snapshots
                        WHERE scope = :scope AND scope_name = :name
                          AND metric_name = :metric AND snapshot_date >= :cutoff
                        ORDER BY snapshot_date
                    """),
                    {"scope": scope, "name": scope_name, "metric": metric_name, "cutoff": cutoff},
                )
            else:
                result = conn.execute(
                    text("""
                        SELECT snapshot_date, metric_value FROM metric_snapshots
                        WHERE scope = :scope AND scope_name IS NULL
                          AND metric_name = :metric AND snapshot_date >= :cutoff
                        ORDER BY snapshot_date
                    """),
                    {"scope": scope, "metric": metric_name, "cutoff": cutoff},
                )
            return [(str(r[0]), float(r[1])) for r in result.fetchall()]
    except Exception as e:
        print(f"WARNING: _load_metric_history failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------

def _format_prior_steps(prior_steps):
    """Format prior step outputs as context for the next step."""
    if not prior_steps:
        return ""
    parts = []
    for step in prior_steps:
        title = step.get("title", step.get("step", ""))
        content = step.get("content", "")
        parts.append(f"[{title}]: {content}")
    return "\n\n".join(parts)


def _call_claude(client, prompt):
    """Make a single Claude API call. Returns text or None."""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_PER_STEP,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"    Chain step API call failed: {e}")
        return None


def _parse_confidence(text):
    """Extract a confidence float from step output text."""
    # Look for patterns like "confidence: 0.8" or "Confidence: 75%"
    import re
    # Try decimal (0-1)
    match = re.search(r'confidence[:\s]+([01]?\.\d+)', text, re.IGNORECASE)
    if match:
        return min(1.0, float(match.group(1)))
    # Try percentage
    match = re.search(r'confidence[:\s]+(\d{1,3})%', text, re.IGNORECASE)
    if match:
        return min(1.0, float(match.group(1)) / 100)
    return 0.5  # neutral default


def _step_situation(client, alert, context, prior_steps=None, **kwargs):
    """Step 1 — Situation Assessment: What is happening?"""
    brand_note = f" about {alert['brand']}" if alert.get("brand") else ""

    prompt = f"""You are Moodlight's intelligence analyst. Provide a concise SITUATION ASSESSMENT{brand_note}.

ALERT:
- Type: {alert.get('alert_type', 'unknown')}
- Severity: {alert.get('severity', 'unknown')}
- Title: {alert.get('title', '')}
- Summary: {alert.get('summary', '')}

DATA:
{context}

Provide exactly:
1. What is happening? (2-3 sentences describing the situation)
2. How significant are the numbers? (1 sentence)
3. Is this new or a continuation? (1 sentence)

End with: Confidence: [0.0-1.0]"""

    text = _call_claude(client, prompt)
    if not text:
        return None

    confidence = _parse_confidence(text)
    return {
        "step": "situation",
        "title": "Situation Assessment",
        "content": text,
        "confidence": confidence,
    }


def _step_historical(client, alert, context, prior_steps=None, **kwargs):
    """Step 2 — Historical Context: Has this happened before?"""
    engine = kwargs.get("engine")
    historical_alerts = _load_historical_alerts(
        engine, alert.get("alert_type"), alert.get("brand")
    )

    # Load metric history if this is a predictive alert with metric data
    metric_history = []
    alert_data = alert.get("data", "{}")
    if isinstance(alert_data, str):
        try:
            alert_data = json.loads(alert_data)
        except (json.JSONDecodeError, TypeError):
            alert_data = {}
    metric_name = alert_data.get("metric")
    if metric_name and engine:
        scope = "brand" if alert.get("brand") else "global"
        metric_history = _load_metric_history(
            engine, scope, alert.get("brand"), metric_name
        )

    prior_text = _format_prior_steps(prior_steps)

    hist_summary = "No similar alerts found in the past 30 days."
    if historical_alerts:
        hist_lines = [f"- [{a['timestamp'][:10]}] {a['title']}" for a in historical_alerts]
        hist_summary = f"Similar alerts in the past 30 days:\n" + "\n".join(hist_lines)

    metric_summary = ""
    if metric_history:
        metric_lines = [f"  {d}: {v:.4f}" for d, v in metric_history[-7:]]
        metric_summary = f"\nMetric trend ({metric_name}):\n" + "\n".join(metric_lines)

    prompt = f"""You are Moodlight's intelligence analyst. Provide HISTORICAL CONTEXT for this alert.

PRIOR ANALYSIS:
{prior_text}

HISTORICAL DATA:
{hist_summary}
{metric_summary}

Has this pattern occurred before? If so, what happened next?
Was the outcome significant or did it normalize?
Assess whether this follows precedent or represents something new.

End with: Confidence: [0.0-1.0]"""

    text = _call_claude(client, prompt)
    if not text:
        return None

    confidence = _parse_confidence(text)
    return {
        "step": "historical",
        "title": "Historical Context",
        "content": text,
        "confidence": confidence,
        "precedent_found": len(historical_alerts) > 0,
    }


def _step_causal(client, alert, context, prior_steps=None, **kwargs):
    """Step 3 — Causal Analysis: Why is this happening?"""
    prior_text = _format_prior_steps(prior_steps)

    prompt = f"""You are Moodlight's intelligence analyst. Provide CAUSAL ANALYSIS.

PRIOR ANALYSIS:
{prior_text}

SUPPORTING DATA:
{context}

Why is this happening? Cross-reference the news topics, social sentiment, and market data.
Identify 2-3 likely causes (be specific, cite data points).

Format:
1. Primary cause: [explanation]
2. Contributing factor: [explanation]
3. Additional context: [explanation]

End with: Confidence: [0.0-1.0]"""

    text = _call_claude(client, prompt)
    if not text:
        return None

    confidence = _parse_confidence(text)

    # Extract likely causes
    likely_causes = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and (stripped[0].isdigit() or stripped.startswith("-")):
            cause = stripped.lstrip("0123456789.-) ").strip()
            if cause and len(cause) > 10:
                likely_causes.append(cause[:200])

    return {
        "step": "causal",
        "title": "Causal Analysis",
        "content": text,
        "confidence": confidence,
        "likely_causes": likely_causes[:5],
    }


def _step_strategic(client, alert, context, prior_steps=None, **kwargs):
    """Step 4 — Strategic Implications: What should the user do?"""
    prior_text = _format_prior_steps(prior_steps)

    # Select relevant strategic frameworks
    framework_prompt = ""
    try:
        from strategic_frameworks import select_frameworks, get_framework_prompt
        user_need = alert.get("summary", "") + " " + alert.get("alert_type", "")
        frameworks = select_frameworks(user_need)
        framework_prompt = get_framework_prompt(frameworks)
    except Exception as e:
        print(f"WARNING: loading strategic frameworks failed: {e}")
        framework_prompt = "Apply relevant strategic frameworks to your analysis."

    prompt = f"""You are Moodlight's intelligence analyst. Provide STRATEGIC IMPLICATIONS.

PRIOR ANALYSIS:
{prior_text}

{framework_prompt}

Based on the situation, history, and causes identified:
1. What are the strategic implications? (2-3 sentences)
2. What specific actions should be taken? (2-3 bullet points)
3. What frameworks best apply and why? (1-2 sentences)

End with: Confidence: [0.0-1.0]"""

    text = _call_claude(client, prompt)
    if not text:
        return None

    confidence = _parse_confidence(text)

    # Extract recommended actions
    recommended_actions = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("-") or stripped.startswith("•"):
            action = stripped.lstrip("-•").strip()
            if action and len(action) > 10:
                recommended_actions.append(action[:200])

    # Extract framework names
    frameworks_applied = []
    try:
        frameworks_applied = frameworks[:3] if frameworks else []
    except NameError as e:
        print(f"WARNING: extracting framework names failed: {e}")

    return {
        "step": "strategic",
        "title": "Strategic Implications",
        "content": text,
        "confidence": confidence,
        "frameworks_applied": frameworks_applied,
        "recommended_actions": recommended_actions[:5],
    }


def _step_confidence(client, alert, context, prior_steps=None, **kwargs):
    """Step 5 — Confidence Scoring: How confident are we?"""
    prior_text = _format_prior_steps(prior_steps)

    # Gather step confidences for the prompt
    step_confs = []
    for step in (prior_steps or []):
        step_confs.append(f"- {step.get('title', '?')}: {step.get('confidence', 'N/A')}")

    prompt = f"""You are Moodlight's intelligence analyst. Provide a CONFIDENCE ASSESSMENT.

PRIOR ANALYSIS:
{prior_text}

Step confidences so far:
{chr(10).join(step_confs)}

Score your overall confidence 0-100 considering:
1. Data quality and sample size
2. Signal strength (how clear is the pattern?)
3. Historical precedent (was this confirmed before?)
4. Agreement across prior steps

Then recommend ONE action:
- ACT_NOW: High confidence, clear threat/opportunity requiring immediate action
- MONITOR: Moderate confidence, worth watching closely over next 24-48 hours
- INVESTIGATE_FURTHER: Low confidence, need more data before acting

Format:
Overall confidence: [0-100]
Recommendation: [ACT_NOW|MONITOR|INVESTIGATE_FURTHER]
Reasoning: [2-3 sentences explaining your assessment]"""

    text = _call_claude(client, prompt)
    if not text:
        return None

    # Parse overall confidence
    import re
    overall = 50
    match = re.search(r'overall\s+confidence[:\s]+(\d{1,3})', text, re.IGNORECASE)
    if match:
        overall = min(100, max(0, int(match.group(1))))

    # Parse recommendation
    recommendation = "monitor"
    text_lower = text.lower()
    if "act_now" in text_lower or "act now" in text_lower:
        recommendation = "act_now"
    elif "investigate_further" in text_lower or "investigate further" in text_lower:
        recommendation = "investigate_further"

    return {
        "step": "confidence",
        "title": "Confidence Assessment",
        "content": text,
        "confidence": overall / 100,
        "overall_confidence": overall,
        "recommendation": recommendation,
    }


# Register step dispatch
STEP_DISPATCH = {
    "situation": _step_situation,
    "historical": _step_historical,
    "causal": _step_causal,
    "strategic": _step_strategic,
    "confidence": _step_confidence,
}


# ---------------------------------------------------------------------------
# Chain orchestrator
# ---------------------------------------------------------------------------

def run_reasoning_chain(alert, engine=None, df_news=None, df_social=None,
                         df_markets=None):
    """Execute a multi-step reasoning chain for an alert.

    Returns a dict with chain steps + legacy compatibility fields,
    or None on complete failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("    ANTHROPIC_API_KEY not set — skipping reasoning chain")
        return None

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
    except Exception as e:
        print(f"    Could not initialize Anthropic client: {e}")
        return None

    # Determine which steps to run
    alert_type = alert.get("alert_type", "")
    steps_to_run = CHAIN_CONFIGS.get(alert_type, DEFAULT_CHAIN)

    # Build data context
    context = _build_context(alert, df_news, df_social, df_markets, engine=engine)

    # Execute chain
    completed_steps = []
    chain_status = "complete"

    for step_name in steps_to_run:
        step_fn = STEP_DISPATCH.get(step_name)
        if not step_fn:
            continue

        print(f"    Chain step: {step_name}...")
        step_result = step_fn(
            client, alert, context,
            prior_steps=completed_steps,
            engine=engine,
        )

        if step_result is None:
            print(f"    Step {step_name} failed — stopping chain")
            chain_status = "partial"
            break

        completed_steps.append(step_result)

        # Early bailout on very low confidence
        if step_result.get("confidence", 0.5) < 0.2:
            print(f"    Step {step_name} confidence too low ({step_result['confidence']:.2f}) — stopping chain")
            chain_status = "partial"
            break

    if not completed_steps:
        return None

    # Extract overall confidence and recommendation
    last_step = completed_steps[-1]
    overall_confidence = last_step.get("overall_confidence", 50)
    recommendation = last_step.get("recommendation", "monitor")

    # If the last step wasn't a confidence step, estimate from step confidences
    if last_step.get("step") != "confidence":
        avg_conf = sum(s.get("confidence", 0.5) for s in completed_steps) / len(completed_steps)
        overall_confidence = int(avg_conf * 100)
        recommendation = "monitor"

    # Build legacy compatibility fields
    analysis = ""
    implications = ""
    watch_items = ""

    for step in completed_steps:
        step_type = step.get("step")
        content = step.get("content", "")
        if step_type == "situation":
            analysis = content
        elif step_type in ("strategic", "causal"):
            if not implications:
                implications = content
        elif step_type == "confidence":
            watch_items = content

    # Build one-line summary
    summary = alert.get("title", "Alert detected")
    if recommendation == "act_now":
        summary += " — Immediate action recommended"
    elif recommendation == "investigate_further":
        summary += " — Further investigation needed"

    chain_type = f"{'full' if len(completed_steps) >= 5 else 'partial'}_{len(completed_steps)}_step"

    return {
        "chain_type": chain_type,
        "chain_status": chain_status,
        "steps": completed_steps,
        "overall_confidence": overall_confidence,
        "recommendation": recommendation,
        "summary": summary,
        # Legacy fields for backward compat
        "analysis": analysis,
        "implications": implications,
        "watch_items": watch_items,
    }
