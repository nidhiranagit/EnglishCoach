"""
Stats module — dashboard calculations with type-aware filtering.
"""

from datetime import date, timedelta
from collections import Counter


def calculate_stats(history: list[dict], entry_type: str = None) -> dict:
    """Calculate dashboard statistics. Optionally filter by entry type."""
    today = date.today()

    if entry_type:
        filtered = [e for e in history if e.get("type", "sentence") == entry_type]
    else:
        filtered = history

    # Sentence-specific stats (for backward compat)
    sentences = [e for e in history if e.get("type", "sentence") == "sentence"]

    total_sentences = len(sentences)
    total_reviewed = sum(1 for e in filtered if e.get("times_reviewed", 0) > 0)
    total_bookmarked = sum(1 for e in filtered if e.get("bookmarked", False))

    # Streak calculation (across all types)
    streak = _calculate_streak(history, today)

    # Score trends (sentences only for backward compat)
    this_week_scores = []
    last_week_scores = []
    for entry in sentences:
        entry_date = date.fromisoformat(entry["date"])
        days_ago = (today - entry_date).days
        score = entry.get("score", 0)
        if score > 0:
            if days_ago < 7:
                this_week_scores.append(score)
            elif days_ago < 14:
                last_week_scores.append(score)

    avg_this_week = round(sum(this_week_scores) / len(this_week_scores), 1) if this_week_scores else 0
    avg_last_week = round(sum(last_week_scores) / len(last_week_scores), 1) if last_week_scores else 0

    # Weakest rule (most repeated mistake)
    rules = [e["rule"] for e in sentences if e.get("verdict") in ("incorrect", "unnatural") and e.get("rule")]
    rule_counts = Counter(rules)
    weakest_rule = rule_counts.most_common(1)[0] if rule_counts else None

    # Verdict distribution (sentences only)
    verdicts = Counter(e.get("verdict", "unknown") for e in sentences)

    # Recent activity (last 7 days, all types)
    recent_dates = {}
    for entry in history:
        d = entry["date"]
        recent_dates[d] = recent_dates.get(d, 0) + 1

    # Days active
    unique_days = len(set(e["date"] for e in history))

    # Type counts
    type_counts = Counter(e.get("type", "sentence") for e in history)

    return {
        "total_sentences": total_sentences,
        "total_reviewed": total_reviewed,
        "total_bookmarked": total_bookmarked,
        "streak": streak,
        "avg_this_week": avg_this_week,
        "avg_last_week": avg_last_week,
        "score_trend": "up" if avg_this_week > avg_last_week else ("down" if avg_this_week < avg_last_week else "same"),
        "weakest_rule": weakest_rule,
        "verdicts": dict(verdicts),
        "unique_days": unique_days,
        "recent_dates": recent_dates,
        "type_counts": dict(type_counts),
        "total_vocabulary": type_counts.get("vocabulary", 0),
        "total_idioms": type_counts.get("idiom", 0),
        "total_emails": type_counts.get("email", 0),
        "total_challenges": type_counts.get("challenge", 0),
        "total_drills": type_counts.get("grammar_drill", 0),
    }


def _calculate_streak(history: list[dict], today: date) -> int:
    """Calculate consecutive days of usage ending today or yesterday."""
    if not history:
        return 0

    dates_used = sorted(set(date.fromisoformat(e["date"]) for e in history), reverse=True)

    if not dates_used:
        return 0

    if dates_used[0] == today:
        streak_start = today
    elif dates_used[0] == today - timedelta(days=1):
        streak_start = today - timedelta(days=1)
    else:
        return 0

    streak = 1
    current = streak_start
    for d in dates_used[1:]:
        expected = current - timedelta(days=1)
        if d == expected:
            streak += 1
            current = d
        elif d < expected:
            break

    return streak


def get_weekly_chart_data(history: list[dict]) -> list[dict]:
    """Get data for last 14 days for charts."""
    today = date.today()
    data = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        d_str = d.isoformat()
        day_entries = [e for e in history if e["date"] == d_str]
        scores = [e["score"] for e in day_entries if e.get("score", 0) > 0]
        data.append({
            "date": d.strftime("%b %d"),
            "count": len(day_entries),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        })
    return data


def generate_report(history: list[dict]) -> dict:
    """Generate a detailed progress report."""
    stats = calculate_stats(history)
    chart_data = get_weekly_chart_data(history)

    sentences = [e for e in history if e.get("type", "sentence") == "sentence"]

    # Group mistakes by rule
    rules = {}
    for entry in sentences:
        if entry.get("verdict") in ("incorrect", "unnatural"):
            rule = entry.get("rule", "Unknown")
            if rule not in rules:
                rules[rule] = []
            rules[rule].append(entry)

    top_mistakes = sorted(rules.items(), key=lambda x: len(x[1]), reverse=True)[:10]

    # Improvement tracking
    if len(sentences) >= 4:
        mid = len(sentences) // 2
        first_half = [e["score"] for e in sentences[:mid] if e.get("score", 0) > 0]
        second_half = [e["score"] for e in sentences[mid:] if e.get("score", 0) > 0]
        first_avg = round(sum(first_half) / len(first_half), 1) if first_half else 0
        second_avg = round(sum(second_half) / len(second_half), 1) if second_half else 0
    else:
        first_avg = second_avg = 0

    return {
        "stats": stats,
        "chart_data": chart_data,
        "top_mistakes": top_mistakes,
        "first_half_avg": first_avg,
        "second_half_avg": second_avg,
        "total_entries": len(history),
    }
