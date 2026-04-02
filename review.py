"""
Review module — spaced repetition logic for all entry types.
"""

from datetime import date, timedelta
from difflib import SequenceMatcher

# Entry types that participate in spaced repetition
REVIEWABLE_TYPES = {"sentence", "vocabulary", "idiom", "email", "challenge"}

# Skip thresholds per type — entries meeting these criteria don't need review
SKIP_RULES = {
    "sentence": lambda e: e.get("verdict") == "natural" and e.get("score", 0) >= 9,
    "email": lambda e: e.get("overall_score", 0) >= 9,
}


def get_review_interval(times_reviewed: int) -> int:
    """Return days until next review based on times already reviewed."""
    if times_reviewed == 0:
        return 1
    elif times_reviewed == 1:
        return 3
    elif times_reviewed == 2:
        return 7
    else:
        return 14


def get_due_items(history: list[dict], entry_type: str = None) -> list[dict]:
    """Return items that are due for review today. Optionally filter by type."""
    today = date.today()
    due = []

    for entry in history:
        etype = entry.get("type", "sentence")

        # Skip non-reviewable types
        if etype not in REVIEWABLE_TYPES:
            continue

        # Filter by type if specified
        if entry_type and etype != entry_type:
            continue

        if entry.get("verdict") == "error":
            continue

        # Check skip rules for this type
        skip_fn = SKIP_RULES.get(etype)
        if skip_fn and skip_fn(entry):
            continue

        times = entry.get("times_reviewed", 0)
        interval = get_review_interval(times)

        if entry.get("review_dates") and len(entry["review_dates"]) > 0:
            last_review = date.fromisoformat(entry["review_dates"][-1])
        else:
            last_review = date.fromisoformat(entry["date"])

        next_due = last_review + timedelta(days=interval)

        if today >= next_due:
            due.append(entry)

    return due


def get_due_sentences(history: list[dict]) -> list[dict]:
    """Backward-compatible wrapper — returns all due items across all types."""
    return get_due_items(history)


def check_answer(user_answer: str, correct_answer: str, threshold: float = 0.95) -> dict:
    """Compare user's answer to the correct version."""
    user_clean = user_answer.strip().lower().rstrip(".")
    correct_clean = correct_answer.strip().lower().rstrip(".")

    similarity = SequenceMatcher(None, user_clean, correct_clean).ratio()
    is_correct = similarity >= threshold

    return {
        "is_correct": is_correct,
        "similarity": round(similarity * 100, 1),
        "user_answer": user_answer.strip(),
        "correct_answer": correct_answer,
    }


def check_vocabulary_answer(user_answer: str, correct_meaning: str) -> dict:
    """Check vocabulary recall — more lenient matching (60% threshold)."""
    return check_answer(user_answer, correct_meaning, threshold=0.60)


def check_idiom_answer(user_answer: str, correct_phrase: str) -> dict:
    """Check idiom recall — moderate matching (85% threshold)."""
    return check_answer(user_answer, correct_phrase, threshold=0.85)


def mark_reviewed(entry: dict) -> dict:
    """Update entry after review."""
    today = date.today().isoformat()
    entry["reviewed"] = True
    entry["times_reviewed"] = entry.get("times_reviewed", 0) + 1
    if "review_dates" not in entry:
        entry["review_dates"] = []
    entry["review_dates"].append(today)
    return entry
