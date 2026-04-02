"""
Flask web app — English Coach with full UI.
"""

import os
import json
from datetime import date, datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from markupsafe import Markup

from storage import (
    load_history, save_history, add_entry, add_typed_entry, update_entry,
    get_entry, get_today_entries, get_today_entries_by_type, get_entries_by_type,
    get_bookmarked, get_entries_with_notes,
)
from analyzer import analyze_sentence
from review import get_due_sentences, get_due_items, check_answer, mark_reviewed
from stats import calculate_stats, get_weekly_chart_data, generate_report
from ai_helpers import (
    extract_vocabulary, compare_sentences, analyze_email,
    generate_grammar_drill, get_idiom_of_the_day, improve_conversation,
)
from challenges import get_todays_challenge
from llm_provider import get_available_providers, get_current_provider_info, save_config

app = Flask(__name__)
app.secret_key = "english-coach-secret-key"


# ---------------------------------------------------------------------------
# Context processors & filters
# ---------------------------------------------------------------------------

@app.context_processor
def inject_due_count():
    """Make due_count available in all templates for the nav badge."""
    try:
        history = load_history()
        return {"due_count": len(get_due_sentences(history))}
    except Exception:
        return {"due_count": 0}


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
    try:
        score = int(score)
    except (ValueError, TypeError):
        return "#6b7280"
    if score >= 8:
        return "#10b981"
    elif score >= 5:
        return "#f59e0b"
    else:
        return "#ef4444"


# ---------------------------------------------------------------------------
# Core pages (existing)
# ---------------------------------------------------------------------------

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

    # Auto-extract vocabulary from corrections
    if result["corrected"].lower().strip() != sentence.lower().strip():
        try:
            vocab_words = extract_vocabulary(sentence, result["corrected"], result["explanation"])
            for word_data in vocab_words:
                add_typed_entry(
                    entry_type="vocabulary",
                    word=word_data.get("word", ""),
                    meaning=word_data.get("meaning", ""),
                    example=word_data.get("example", ""),
                    explanation_hi=word_data.get("explanation_hi", ""),
                    source_sentence_id=entry["id"],
                )
        except Exception:
            pass  # Vocabulary extraction is best-effort

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

    # Determine what to check against based on entry type
    entry_type = entry.get("type", "sentence")
    if entry_type == "vocabulary":
        correct = entry.get("meaning", "")
    elif entry_type == "idiom":
        correct = entry.get("phrase", "")
    else:
        correct = entry.get("corrected", "")

    result = check_answer(user_answer, correct)

    updated = mark_reviewed(entry)
    update_entry(entry_id, updated)

    return jsonify({
        **result,
        "explanation": entry.get("explanation", entry.get("explanation_hi", "")),
        "rule": entry.get("rule", ""),
        "verdict": entry.get("verdict", ""),
        "score": entry.get("score", 0),
        "type": entry_type,
    })


@app.route("/history")
def history_page():
    history = load_history()
    # Only show sentence-type entries in history (keep backward compat)
    sentences = [e for e in history if e.get("type", "sentence") == "sentence"]
    history_sorted = sorted(sentences, key=lambda x: x["date"], reverse=True)
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

    sentences = [e for e in history if e.get("type", "sentence") == "sentence"]
    for entry in sorted(sentences, key=lambda x: x["date"], reverse=True):
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

    bookmarked = [e for e in history if e.get("bookmarked")]
    if bookmarked:
        lines.append("## Bookmarked Sentences")
        lines.append("")
        for entry in bookmarked:
            lines.append(f"- **{entry.get('original', entry.get('phrase', ''))}** → {entry.get('corrected', entry.get('meaning', ''))} ({entry.get('rule', entry.get('type', ''))})")
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


# ---------------------------------------------------------------------------
# Feature 1: Vocabulary Builder
# ---------------------------------------------------------------------------

@app.route("/vocabulary")
def vocabulary_page():
    vocab_entries = get_entries_by_type("vocabulary")
    vocab_entries = sorted(vocab_entries, key=lambda x: x["date"], reverse=True)

    filter_type = request.args.get("filter")
    mastered_count = sum(1 for e in vocab_entries if e.get("times_reviewed", 0) >= 3)
    due_vocab = get_due_items(load_history(), entry_type="vocabulary")
    due_vocab_count = len(due_vocab)

    if filter_type == "due":
        due_ids = {e["id"] for e in due_vocab}
        vocab_entries = [e for e in vocab_entries if e["id"] in due_ids]
    elif filter_type == "mastered":
        vocab_entries = [e for e in vocab_entries if e.get("times_reviewed", 0) >= 3]
    elif filter_type == "bookmarked":
        vocab_entries = [e for e in vocab_entries if e.get("bookmarked")]

    return render_template(
        "vocabulary.html",
        vocab_entries=vocab_entries,
        mastered_count=mastered_count,
        due_vocab_count=due_vocab_count,
        filter=filter_type,
    )


# ---------------------------------------------------------------------------
# Feature 2: Daily Challenges
# ---------------------------------------------------------------------------

@app.route("/challenge")
def challenge_page():
    challenge = get_todays_challenge()
    today_challenges = get_today_entries_by_type("challenge")
    today_entry = today_challenges[0] if today_challenges else None

    past_challenges = get_entries_by_type("challenge")
    past_challenges = sorted(past_challenges, key=lambda x: x["date"], reverse=True)

    # Calculate challenge streak
    challenge_dates = sorted(set(e["date"] for e in past_challenges), reverse=True)
    challenge_streak = 0
    today_str = date.today().isoformat()
    from datetime import timedelta
    check_date = date.today()
    for d_str in challenge_dates:
        d = date.fromisoformat(d_str)
        if d == check_date or d == check_date - timedelta(days=1):
            challenge_streak += 1
            check_date = d - timedelta(days=1)
        else:
            break

    return render_template(
        "challenge.html",
        challenge=challenge,
        today_done=today_entry is not None,
        today_entry=today_entry,
        past_challenges=past_challenges,
        challenge_streak=challenge_streak,
        total_challenges=len(past_challenges),
    )


@app.route("/challenge/submit", methods=["POST"])
def challenge_submit():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Please write something"}), 400

    today_challenges = get_today_entries_by_type("challenge")
    if today_challenges:
        return jsonify({"error": "You already completed today's challenge!"}), 400

    challenge = get_todays_challenge()
    result = analyze_sentence(text)
    if result["verdict"] == "error":
        return jsonify({"error": result["explanation"]}), 500

    entry = add_typed_entry(
        entry_type="challenge",
        original=text,
        corrected=result["corrected"],
        explanation=result["explanation"],
        rule=result["rule"],
        score=result["score"],
        verdict=result["verdict"],
        challenge_prompt=challenge["prompt"],
        challenge_category=challenge["category"],
    )

    return jsonify({**entry, **result})


# ---------------------------------------------------------------------------
# Feature 3: Sentence Comparison
# ---------------------------------------------------------------------------

@app.route("/compare")
def compare_page():
    return render_template("compare.html")


@app.route("/compare", methods=["POST"])
def compare_post():
    data = request.get_json()
    a = data.get("sentence_a", "").strip()
    b = data.get("sentence_b", "").strip()
    if not a or not b:
        return jsonify({"error": "Please enter both sentences"}), 400

    result = compare_sentences(a, b)
    if "error" in result:
        return jsonify({"error": f"Analysis failed: {result['error']}"}), 500

    result["sentence_a"] = a
    result["sentence_b"] = b
    return jsonify(result)


# ---------------------------------------------------------------------------
# Feature 4: Email/Message Writing Practice
# ---------------------------------------------------------------------------

@app.route("/email")
def email_page():
    past_emails = get_entries_by_type("email")
    past_emails = sorted(past_emails, key=lambda x: x["date"], reverse=True)
    return render_template("email.html", past_emails=past_emails)


@app.route("/email/analyze", methods=["POST"])
def email_analyze():
    data = request.get_json()
    text = data.get("text", "").strip()
    template = data.get("template", "").strip()
    if not text:
        return jsonify({"error": "Please write something"}), 400
    if not template:
        return jsonify({"error": "Please select a template"}), 400

    result = analyze_email(text, template)
    if "error" in result:
        return jsonify({"error": f"Analysis failed: {result['error']}"}), 500

    entry = add_typed_entry(
        entry_type="email",
        original=text,
        corrected=result.get("corrected", text),
        email_type=template,
        tone_score=result.get("tone_score", 0),
        formality_score=result.get("formality_score", 0),
        clarity_score=result.get("clarity_score", 0),
        overall_score=result.get("overall_score", 0),
        tone_feedback=result.get("tone_feedback", ""),
        formality_feedback=result.get("formality_feedback", ""),
        clarity_feedback=result.get("clarity_feedback", ""),
        tips=result.get("tips", []),
        score=result.get("overall_score", 0),
        verdict="natural" if result.get("overall_score", 0) >= 8 else "unnatural" if result.get("overall_score", 0) >= 5 else "incorrect",
    )

    return jsonify({**result, "id": entry["id"]})


# ---------------------------------------------------------------------------
# Feature 5: Grammar Drills
# ---------------------------------------------------------------------------

@app.route("/drills")
def drills_page():
    history = load_history()
    stats = calculate_stats(history)
    total_drills = stats.get("total_drills", 0)
    weakest_rule = stats["weakest_rule"][0] if stats["weakest_rule"] else None

    return render_template("drills.html", total_drills=total_drills, weakest_rule=weakest_rule)


@app.route("/drills/generate", methods=["POST"])
def drills_generate():
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Please select a topic"}), 400

    # Get past mistakes related to this topic for personalized drills
    history = load_history()
    sentences = [e for e in history if e.get("type", "sentence") == "sentence"]
    past_mistakes = []
    for e in sentences:
        if e.get("verdict") in ("incorrect", "unnatural"):
            rule = e.get("rule", "").lower()
            if topic.replace("_", " ") in rule or topic.replace("_", "-") in rule:
                past_mistakes.append(f"{e['original']} → {e['corrected']}")

    result = generate_grammar_drill(topic, past_mistakes)
    if "error" in result:
        return jsonify({"error": f"Failed to generate drill: {result['error']}"}), 500

    return jsonify(result)


@app.route("/drills/check", methods=["POST"])
def drills_check():
    data = request.get_json()
    topic = data.get("topic", "")
    user_answers = data.get("answers", [])

    # Re-generate to get correct answers (stored in session would be better, but keeping it simple)
    history = load_history()
    sentences = [e for e in history if e.get("type", "sentence") == "sentence"]
    past_mistakes = []
    for e in sentences:
        if e.get("verdict") in ("incorrect", "unnatural"):
            rule = e.get("rule", "").lower()
            if topic.replace("_", " ") in rule or topic.replace("_", "-") in rule:
                past_mistakes.append(f"{e['original']} → {e['corrected']}")

    drill = generate_grammar_drill(topic, past_mistakes)
    if "error" in drill:
        return jsonify({"error": f"Failed to check: {drill['error']}"}), 500

    exercises = drill.get("exercises", [])
    results = []
    correct_count = 0

    for i, ex in enumerate(exercises):
        user_ans = user_answers[i] if i < len(user_answers) else ""
        is_correct = user_ans.strip().lower() == ex["answer"].strip().lower()
        if is_correct:
            correct_count += 1
        results.append({
            "sentence": ex["sentence"],
            "user_answer": user_ans,
            "correct_answer": ex["answer"],
            "is_correct": is_correct,
            "explanation_hi": ex.get("explanation_hi", ""),
        })

    # Save drill result
    add_typed_entry(
        entry_type="grammar_drill",
        topic=topic,
        score=correct_count,
        total=len(exercises),
        results=results,
    )

    return jsonify({"score": correct_count, "total": len(exercises), "results": results})


# ---------------------------------------------------------------------------
# Feature 6: Idiom & Phrase of the Day
# ---------------------------------------------------------------------------

@app.route("/idiom")
def idiom_page():
    idiom_entries = get_entries_by_type("idiom")
    idiom_entries_sorted = sorted(idiom_entries, key=lambda x: x["date"], reverse=True)

    today_idioms = get_today_entries_by_type("idiom")
    today_idiom = today_idioms[0] if today_idioms else None

    due_idioms = get_due_items(load_history(), entry_type="idiom")

    return render_template(
        "idiom.html",
        today_idiom=today_idiom,
        past_idioms=idiom_entries_sorted,
        total_idioms=len(idiom_entries),
        due_idiom_count=len(due_idioms),
    )


@app.route("/idiom/generate", methods=["POST"])
def idiom_generate():
    today_idioms = get_today_entries_by_type("idiom")
    if today_idioms:
        return jsonify({"error": "Already have today's idiom!", "idiom": today_idioms[0]})

    seen = [e.get("phrase", "") for e in get_entries_by_type("idiom")]
    result = get_idiom_of_the_day(seen)
    if "error" in result:
        return jsonify({"error": f"Failed to generate idiom: {result['error']}"}), 500

    entry = add_typed_entry(
        entry_type="idiom",
        phrase=result["phrase"],
        meaning=result["meaning"],
        example=result["example"],
        explanation_hi=result["explanation_hi"],
        usage_tip=result.get("usage_tip", ""),
        category=result.get("category", "general"),
    )

    return jsonify({**entry, **result})


# ---------------------------------------------------------------------------
# Feature 7: Conversation Replay
# ---------------------------------------------------------------------------

@app.route("/conversation")
def conversation_page():
    past = get_entries_by_type("conversation")
    past = sorted(past, key=lambda x: x["date"], reverse=True)
    return render_template("conversation.html", past_conversations=past)


@app.route("/conversation/improve", methods=["POST"])
def conversation_improve():
    data = request.get_json()
    lines = data.get("lines", [])
    if not lines or len(lines) < 2:
        return jsonify({"error": "Please write at least 2 lines"}), 400

    result = improve_conversation(lines)
    if "error" in result:
        return jsonify({"error": f"Failed to improve: {result['error']}"}), 500

    entry = add_typed_entry(
        entry_type="conversation",
        original="\n".join(lines),
        line_count=len(lines),
        lines=result.get("lines", []),
        overall_tips=result.get("overall_tips", []),
    )

    return jsonify({**result, "id": entry["id"]})


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.route("/settings")
def settings_page():
    providers = get_available_providers()
    current = get_current_provider_info()
    return render_template("settings.html", providers=providers, current=current)


@app.route("/settings", methods=["POST"])
def settings_save():
    data = request.get_json()
    provider = data.get("provider", "").strip()
    model = data.get("model", "").strip()
    if not provider or not model:
        return jsonify({"error": "Provider and model are required"}), 400
    save_config({"provider": provider, "model": model})
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5050)
