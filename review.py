"""
Review module — spaced repetition logic.
"""

from datetime import date, timedelta
from difflib import SequenceMatcher


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


def get_due_sentences(history: list[dict]) -> list[dict]:
    """Return sentences that are due for review today."""
    today = date.today()
    due = []

    for entry in history:
        if entry.get("verdict") == "natural" and entry.get("score", 0) >= 9:
            # Perfect sentences don't need review
            continue
        if entry.get("verdict") == "error":
            continue

        times = entry.get("times_reviewed", 0)
        interval = get_review_interval(times)

        # Determine the reference date (last review or original date)
        if entry.get("review_dates") and len(entry["review_dates"]) > 0:
            last_review = date.fromisoformat(entry["review_dates"][-1])
        else:
            last_review = date.fromisoformat(entry["date"])

        next_due = last_review + timedelta(days=interval)

        if today >= next_due:
            due.append(entry)

    return due


def check_answer(user_answer: str, correct_answer: str) -> dict:
    """Compare user's answer to the correct version."""
    user_clean = user_answer.strip().lower().rstrip(".")
    correct_clean = correct_answer.strip().lower().rstrip(".")

    similarity = SequenceMatcher(None, user_clean, correct_clean).ratio()

    is_correct = similarity >= 0.95  # Allow very minor typos

    return {
        "is_correct": is_correct,
        "similarity": round(similarity * 100, 1),
        "user_answer": user_answer.strip(),
        "correct_answer": correct_answer,
    }


def mark_reviewed(entry: dict) -> dict:
    """Update entry after review."""
    today = date.today().isoformat()
    entry["reviewed"] = True
    entry["times_reviewed"] = entry.get("times_reviewed", 0) + 1
    if "review_dates" not in entry:
        entry["review_dates"] = []
    entry["review_dates"].append(today)
    return entry
