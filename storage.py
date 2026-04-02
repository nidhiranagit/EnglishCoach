"""
Storage module — read/write history.json for all entry types.
Supports typed entries: sentence, vocabulary, idiom, email, grammar_drill, conversation, challenge.
"""

import json
import os
import uuid
from datetime import datetime, date
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w") as f:
            json.dump([], f)


def _backfill_type(history: list[dict]) -> list[dict]:
    """Ensure all entries have a type field. Existing entries default to 'sentence'."""
    for entry in history:
        if "type" not in entry:
            entry["type"] = "sentence"
    return history


def load_history() -> list[dict]:
    _ensure_data_dir()
    with open(HISTORY_FILE, "r") as f:
        try:
            history = json.load(f)
            return _backfill_type(history)
        except json.JSONDecodeError:
            return []


def save_history(history: list[dict]):
    _ensure_data_dir()
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _make_base_entry(**extra_fields) -> dict:
    """Create a base entry with common fields + any extra fields."""
    entry = {
        "id": str(uuid.uuid4())[:8],
        "date": date.today().isoformat(),
        "reviewed": False,
        "review_dates": [],
        "times_reviewed": 0,
        "bookmarked": False,
        "notes": "",
    }
    entry.update(extra_fields)
    return entry


def add_entry(
    original: str,
    corrected: str,
    explanation: str,
    rule: str,
    score: int,
    verdict: str,
) -> dict:
    """Add a sentence entry (backward compatible)."""
    return add_typed_entry(
        entry_type="sentence",
        original=original,
        corrected=corrected,
        explanation=explanation,
        rule=rule,
        score=score,
        verdict=verdict,
    )


def add_typed_entry(entry_type: str, **fields) -> dict:
    """Add an entry of any type with arbitrary fields."""
    history = load_history()
    entry = _make_base_entry(type=entry_type, **fields)
    history.append(entry)
    save_history(history)
    return entry


def update_entry(entry_id: str, updates: dict):
    history = load_history()
    for entry in history:
        if entry["id"] == entry_id:
            entry.update(updates)
            break
    save_history(history)


def get_entry(entry_id: str) -> Optional[dict]:
    history = load_history()
    for entry in history:
        if entry["id"] == entry_id:
            return entry
    return None


def get_today_entries() -> list[dict]:
    """Get today's sentence entries only (preserves 5/day limit for sentences)."""
    today = date.today().isoformat()
    return [e for e in load_history() if e["date"] == today and e.get("type", "sentence") == "sentence"]


def get_today_entries_by_type(entry_type: str) -> list[dict]:
    """Get today's entries of a specific type."""
    today = date.today().isoformat()
    return [e for e in load_history() if e["date"] == today and e.get("type") == entry_type]


def get_entries_by_type(entry_type: str) -> list[dict]:
    """Get all entries of a specific type."""
    return [e for e in load_history() if e.get("type") == entry_type]


def get_bookmarked() -> list[dict]:
    return [e for e in load_history() if e.get("bookmarked", False)]


def get_entries_with_notes() -> list[dict]:
    return [e for e in load_history() if e.get("notes", "").strip()]
