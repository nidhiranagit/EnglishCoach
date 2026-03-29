"""
Storage module — read/write history.json for all sentence data.
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


def load_history() -> list[dict]:
    _ensure_data_dir()
    with open(HISTORY_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_history(history: list[dict]):
    _ensure_data_dir()
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def add_entry(
    original: str,
    corrected: str,
    explanation: str,
    rule: str,
    score: int,
    verdict: str,
) -> dict:
    history = load_history()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "date": date.today().isoformat(),
        "original": original,
        "corrected": corrected,
        "explanation": explanation,
        "rule": rule,
        "score": score,
        "verdict": verdict,
        "reviewed": False,
        "review_dates": [],
        "times_reviewed": 0,
        "bookmarked": False,
        "notes": "",
    }
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
    today = date.today().isoformat()
    return [e for e in load_history() if e["date"] == today]


def get_bookmarked() -> list[dict]:
    return [e for e in load_history() if e.get("bookmarked", False)]


def get_entries_with_notes() -> list[dict]:
    return [e for e in load_history() if e.get("notes", "").strip()]
