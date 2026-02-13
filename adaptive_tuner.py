#!/usr/bin/env python
"""
Adaptive threshold tuner for Moodlight.
Uses feedback data (thumbs up/down, engagement rates) to automatically
adjust alert thresholds — making noisy alerts quieter and valued alerts
more sensitive.

Guardrails:
- Max 10% change per tuning cycle
- Never go beyond 0.5x–2x of original default
- Requires 10+ alerts of a type before adjusting
"""

from alert_thresholds import DEFAULT_THRESHOLDS, get_thresholds, update_threshold
from alert_feedback import get_feedback_summary


def run_adaptive_tuning(engine):
    """Run one cycle of adaptive threshold tuning.

    Logic per alert type (requires 10+ alerts in last 30 days):
    - thumbs_down rate > 0.5 OR engagement rate < 0.1 → raise threshold 10%
    - thumbs_up rate > 0.6 AND engagement rate > 0.5 → lower threshold 10%
    - Otherwise: no change

    Returns dict of changes made.
    """
    print("\n  Running adaptive threshold tuning...")
    summary = get_feedback_summary(engine, days=30)
    if not summary:
        print("    No feedback data — skipping tuning")
        return {}

    current = get_thresholds(engine)
    changes = {}

    for alert_type, stats in summary.items():
        total = stats.get("total_alerts", 0)
        if total < 10:
            continue

        engagement = stats.get("engagement_rate", 0)
        approval = stats.get("approval_rate", 0.5)
        thumbs_down_rate = 1 - approval

        # Determine direction
        if thumbs_down_rate > 0.5 or engagement < 0.1:
            direction = "raise"
            factor = 1.10  # +10%
            reason = (
                f"Low engagement ({engagement:.0%}) or high thumbs-down "
                f"({thumbs_down_rate:.0%}) over {total} alerts"
            )
        elif approval > 0.6 and engagement > 0.5:
            direction = "lower"
            factor = 0.90  # -10%
            reason = (
                f"High approval ({approval:.0%}) and engagement "
                f"({engagement:.0%}) over {total} alerts"
            )
        else:
            continue

        # Apply with guardrails
        curr = current.get(alert_type, {})
        defaults = DEFAULT_THRESHOLDS.get(alert_type, {})
        new_warning = _apply_guardrail(
            curr.get("warning"), defaults.get("warning"), factor
        )
        new_critical = _apply_guardrail(
            curr.get("critical"), defaults.get("critical"), factor
        )

        # Only update if something actually changed
        if new_warning != curr.get("warning") or new_critical != curr.get("critical"):
            update_threshold(
                engine, alert_type,
                new_warning=new_warning,
                new_critical=new_critical,
                reason=reason,
            )
            changes[alert_type] = {
                "direction": direction,
                "reason": reason,
                "old_warning": curr.get("warning"),
                "new_warning": new_warning,
                "old_critical": curr.get("critical"),
                "new_critical": new_critical,
            }
            print(f"    {direction.upper()} {alert_type}: {reason}")

    if not changes:
        print("    No threshold adjustments needed")
    else:
        print(f"    Adjusted {len(changes)} threshold(s)")

    return changes


def _apply_guardrail(current_val, default_val, factor):
    """Apply factor to a threshold value with guardrails.

    - Returns None if both current and default are None
    - Clamps result to [0.5x, 2x] of the default value
    - Max 10% change per cycle (enforced by the factor itself)
    """
    if current_val is None or default_val is None:
        return current_val  # Don't adjust None thresholds

    new_val = current_val * factor

    # Guardrail: never go beyond 0.5x–2x of the original default
    min_val = default_val * 0.5
    max_val = default_val * 2.0
    new_val = max(min_val, min(max_val, new_val))

    return round(new_val, 4)
