"""
Flask web app — English Coach with full UI.
"""

import os
import json
from datetime import date, datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from markupsafe import Markup

from storage import load_history, save_history, add_entry, update_entry, get_entry, get_today_entries, get_bookmarked, get_entries_with_notes
from analyzer import analyze_sentence
from review import get_due_sentences, check_answer, mark_reviewed
from stats import calculate_stats, get_weekly_chart_data, generate_report

app = Flask(__name__)
app.secret_key = "english-coach-secret-key"


@app.context_processor
def inject_due_count():
    """Make due_count available in all templates for the nav badge."""
    try:
        history = load_history()
        return {"due_count": len(get_due_sentences(history))}
    except Exception:
        return {"due_count": 0}


@app.route("/")
def dashboard():
    history = load_history()
    stats = calculate_stats(history)
    chart_data = get_weekly_chart_data(history)
    due = get_due_sentences(history)
    today_entries = get_today_entries()
    return render_template(
        "dashboard.html",
        stats=stats,
        chart_data=json.dumps(chart_data),
        due_count=len(due),
        today_count=len(today_entries),
        today_entries=today_entries,
    )


@app.route("/session")
def session_page():
    today_entries = get_today_entries()
    remaining = max(0, 5 - len(today_entries))
    return render_template("session.html", today_entries=today_entries, remaining=remaining)


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    sentence = data.get("sentence", "").strip()
    if not sentence:
        return jsonify({"error": "Please enter a sentence"}), 400

    today_entries = get_today_entries()
    if len(today_entries) >= 5:
        return jsonify({"error": "Aaj ka limit khatam! (Today's limit of 5 sentences reached)"}), 400

    result = analyze_sentence(sentence)
    if result["verdict"] == "error":
        return jsonify({"error": result["explanation"]}), 500

    entry = add_entry(
        original=sentence,
        corrected=result["corrected"],
        explanation=result["explanation"],
        rule=result["rule"],
        score=result["score"],
        verdict=result["verdict"],
    )

    return jsonify({**entry, **result})


@app.route("/review")
def review_page():
    history = load_history()
    due = get_due_sentences(history)
    return render_template("review.html", due_sentences=due, total_due=len(due))


@app.route("/review/check", methods=["POST"])
def review_check():
    data = request.get_json()
    entry_id = data.get("entry_id")
    user_answer = data.get("answer", "").strip()

    entry = get_entry(entry_id)
    if not entry:
        return jsonify({"error": "Entry not found"}), 404

    result = check_answer(user_answer, entry["corrected"])

    # Mark as reviewed
    updated = mark_reviewed(entry)
    update_entry(entry_id, updated)

    return jsonify({
        **result,
        "explanation": entry["explanation"],
        "rule": entry["rule"],
        "verdict": entry["verdict"],
        "score": entry["score"],
    })


@app.route("/history")
def history_page():
    history = load_history()
    # Sort by date descending
    history_sorted = sorted(history, key=lambda x: x["date"], reverse=True)
    filter_type = request.args.get("filter", "all")
    if filter_type == "bookmarked":
        history_sorted = [e for e in history_sorted if e.get("bookmarked")]
    elif filter_type == "notes":
        history_sorted = [e for e in history_sorted if e.get("notes", "").strip()]
    elif filter_type == "incorrect":
        history_sorted = [e for e in history_sorted if e.get("verdict") == "incorrect"]
    elif filter_type == "unnatural":
        history_sorted = [e for e in history_sorted if e.get("verdict") == "unnatural"]

    return render_template("history.html", entries=history_sorted, filter_type=filter_type)


@app.route("/entry/<entry_id>/bookmark", methods=["POST"])
def toggle_bookmark(entry_id):
    entry = get_entry(entry_id)
    if entry:
        update_entry(entry_id, {"bookmarked": not entry.get("bookmarked", False)})
    return jsonify({"ok": True, "bookmarked": not entry.get("bookmarked", False)})


@app.route("/entry/<entry_id>/note", methods=["POST"])
def save_note(entry_id):
    data = request.get_json()
    note = data.get("note", "")
    update_entry(entry_id, {"notes": note})
    return jsonify({"ok": True})


@app.route("/notes")
def notes_page():
    history = load_history()
    noted = [e for e in history if e.get("notes", "").strip()]
    bookmarked = [e for e in history if e.get("bookmarked", False)]
    return render_template("notes.html", noted=noted, bookmarked=bookmarked)


@app.route("/report")
def report_page():
    history = load_history()
    report = generate_report(history)
    return render_template("report.html", report=report, chart_data=json.dumps(report["chart_data"]))


@app.route("/export/markdown")
def export_markdown():
    history = load_history()
    report = generate_report(history)
    stats = report["stats"]

    lines = []
    lines.append("# English Coach — Progress Report")
    lines.append(f"**Generated:** {date.today().isoformat()}")
    lines.append(f"**Total Sentences:** {stats['total_sentences']}")
    lines.append(f"**Streak:** {stats['streak']} days")
    lines.append(f"**Avg Score This Week:** {stats['avg_this_week']}")
    lines.append("")
    lines.append("## All Sentences")
    lines.append("")

    for entry in sorted(history, key=lambda x: x["date"], reverse=True):
        emoji = "✅" if entry["verdict"] == "natural" else "⚠️" if entry["verdict"] == "unnatural" else "❌"
        lines.append(f"### {emoji} {entry['date']} — Score: {entry['score']}/10")
        lines.append(f"**Original:** {entry['original']}")
        if entry["original"] != entry["corrected"]:
            lines.append(f"**Corrected:** {entry['corrected']}")
        lines.append(f"**Explanation:** {entry['explanation']}")
        lines.append(f"**Rule:** {entry['rule']}")
        if entry.get("notes"):
            lines.append(f"**My Notes:** {entry['notes']}")
        lines.append("")

    # Bookmarked section
    bookmarked = [e for e in history if e.get("bookmarked")]
    if bookmarked:
        lines.append("## Bookmarked Sentences")
        lines.append("")
        for entry in bookmarked:
            lines.append(f"- **{entry['original']}** → {entry['corrected']} ({entry['rule']})")
        lines.append("")

    content = "\n".join(lines)
    filepath = os.path.join(os.path.dirname(__file__), "data", "english_coach_report.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return send_file(filepath, as_attachment=True, download_name="english_coach_report.md")


@app.route("/export/json")
def export_json():
    history = load_history()
    filepath = os.path.join(os.path.dirname(__file__), "data", "english_coach_export.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    return send_file(filepath, as_attachment=True, download_name="english_coach_export.json")


@app.template_filter("verdict_color")
def verdict_color(verdict):
    colors = {
        "natural": "#10b981",
        "unnatural": "#f59e0b",
        "incorrect": "#ef4444",
    }
    return colors.get(verdict, "#6b7280")


@app.template_filter("verdict_emoji")
def verdict_emoji(verdict):
    emojis = {
        "natural": "✅",
        "unnatural": "⚠️",
        "incorrect": "❌",
    }
    return emojis.get(verdict, "❓")


@app.template_filter("score_color")
def score_color(score):
    if score >= 8:
        return "#10b981"
    elif score >= 5:
        return "#f59e0b"
    else:
        return "#ef4444"


if __name__ == "__main__":
    app.run(debug=True, port=5050)
