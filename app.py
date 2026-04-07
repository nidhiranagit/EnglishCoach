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
    generate_visual_word,
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
# Feature 8: Role Play
# ---------------------------------------------------------------------------

ROLEPLAY_SCENARIOS = {
    "ds_interview": {
        "id": "ds_interview",
        "title": "Data Science Interview",
        "icon": "🧠",
        "description": "Practice being interviewed for a Data Science role at a US tech company.",
        "your_role": "Job Candidate",
        "ai_name": "Alex",
        "ai_title": "Senior Data Scientist, TechCorp USA",
        "tags": ["Technical", "Career"],
        "metric_categories": ["Technical Knowledge", "Communication", "Problem Solving", "Cultural Fit"],
        "starter": "Hey! Good to meet you. I'm Alex, Senior Data Scientist here at TechCorp. We've got about 45 minutes — I'll ask you some technical questions and we'll chat about your experience. Let's start simple: can you walk me through your background in data science?",
        "ai_role_prompt": "You are Alex, a Senior Data Scientist at a US tech company conducting a job interview for a Data Science role. You're friendly but professional. Ask questions about Python, machine learning, statistics, SQL, past projects, problem-solving, and behavioral scenarios. React naturally to the candidate's answers — follow up, dig deeper, or move to the next topic. Keep responses short (2-4 sentences).",
    },
    "vendor_sales": {
        "id": "vendor_sales",
        "title": "Vendor Sales Pitch",
        "icon": "💼",
        "description": "You are selling your product/service to an American business buyer.",
        "your_role": "Sales Person / Vendor",
        "ai_name": "Mike",
        "ai_title": "Procurement Manager, US Enterprise",
        "tags": ["Business", "Sales"],
        "metric_categories": ["Persuasion", "Product Knowledge", "Handling Objections", "Professionalism"],
        "starter": "Hey, thanks for taking the time. I've got about 20 minutes before my next call. So — what exactly are you selling, and why should I care?",
        "ai_role_prompt": "You are Mike, a Procurement Manager at a US company. Someone is pitching you a product or service. You're busy, slightly skeptical, but open-minded. Ask tough but fair questions: pricing, ROI, competitors, implementation, support. React realistically to what the vendor says. Keep responses short and direct (2-4 sentences).",
    },
    "salary_negotiation": {
        "id": "salary_negotiation",
        "title": "Salary Negotiation",
        "icon": "💰",
        "description": "Negotiate your salary with an American HR manager after getting a job offer.",
        "your_role": "Job Candidate",
        "ai_name": "Sarah",
        "ai_title": "HR Manager, US Tech Company",
        "tags": ["Career", "Business"],
        "metric_categories": ["Negotiation Skill", "Confidence", "Market Awareness", "Professionalism"],
        "starter": "Hi! Congratulations again on the offer. I wanted to loop back with you on the compensation package. We offered $95,000 base. Have you had a chance to review everything?",
        "ai_role_prompt": "You are Sarah, an HR Manager at a US tech company. You've made a job offer at $95,000 and the candidate wants to negotiate. You have budget flexibility up to $110,000 but won't reveal it easily. Be professional, fair, and realistic. Hold your ground at first, but be open to reasonable arguments. Keep responses short and natural (2-4 sentences).",
    },
    "it_colleague": {
        "id": "it_colleague",
        "title": "American IT Colleague",
        "icon": "💻",
        "description": "Casual tech conversation with an American IT colleague — troubleshoot, discuss projects, or just small talk.",
        "your_role": "Your Role",
        "ai_name": "Jake",
        "ai_title": "Software Engineer, US Team",
        "tags": ["Casual", "Technical"],
        "metric_categories": ["Communication", "Technical Discussion", "Friendliness", "Clarity"],
        "starter": "Hey! How's it going? I saw you were working on that API integration — how's that coming along? I might have run into a similar issue last week.",
        "ai_role_prompt": "You are Jake, a friendly American software engineer. You're having a casual work conversation with a colleague — could be about a tech problem, a project, or just catching up. Use natural American work language, light humor, tech slang. Keep it real and conversational (2-4 sentences).",
    },
    "job_application": {
        "id": "job_application",
        "title": "Impress the Hiring Manager",
        "icon": "🎯",
        "description": "Talk to an American hiring manager and convince them to hire you. Make your case!",
        "your_role": "Job Applicant",
        "ai_name": "Lisa",
        "ai_title": "VP of Engineering, US Startup",
        "tags": ["Career", "Interview"],
        "metric_categories": ["Impact & Value", "Storytelling", "Confidence", "Relevance"],
        "starter": "So I looked at your resume — interesting background. But honestly, we have 50 applications. Tell me something that makes you stand out. Why should it be you?",
        "ai_role_prompt": "You are Lisa, VP of Engineering at a US tech startup. You're evaluating a candidate who is trying to impress you and get hired. You're direct, no-nonsense, and value people who are clear about their value. Push back on vague answers, ask follow-up questions, challenge their claims. Be realistic — sometimes impressed, sometimes skeptical. (2-4 sentences per response).",
    },
    "english_teacher": {
        "id": "english_teacher",
        "title": "English Teacher",
        "icon": "📖",
        "description": "Practice free conversation with a patient American English teacher who helps you improve.",
        "your_role": "Student",
        "ai_name": "Ms. Karen",
        "ai_title": "English Teacher, USA",
        "tags": ["Learning", "Casual"],
        "metric_categories": ["Fluency", "Sentence Structure", "Expressiveness", "Active Listening"],
        "starter": "Hi! Welcome. I'm here to help you practice your English — no pressure at all. We can talk about anything you like: your day, your work, your hobbies, or anything you want to get better at expressing. What would you like to talk about today?",
        "ai_role_prompt": "You are Ms. Karen, a warm and patient American English teacher. Your student is a Hindi speaker practicing conversational English. Encourage them, gently correct major mistakes inline (e.g., 'you could also say...'), ask follow-up questions to keep the conversation going. Keep it light and supportive. (2-4 sentences per response).",
    },
}


@app.route("/roleplay")
def roleplay_page():
    return render_template("roleplay.html", scenarios=ROLEPLAY_SCENARIOS)


@app.route("/roleplay/<scenario_id>")
def roleplay_session(scenario_id):
    scenario = ROLEPLAY_SCENARIOS.get(scenario_id)
    if not scenario:
        return "Scenario not found", 404
    return render_template("roleplay_chat.html", scenario=scenario)


@app.route("/roleplay/<scenario_id>/message", methods=["POST"])
def roleplay_message(scenario_id):
    from ai_helpers import roleplay_respond
    scenario = ROLEPLAY_SCENARIOS.get(scenario_id)
    if not scenario:
        return jsonify({"error": "Scenario not found"}), 404

    data = request.get_json()
    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    if len(user_message) > 500:
        return jsonify({"error": "Message too long (max 500 chars)"}), 400

    result = roleplay_respond(
        scenario_id, scenario["ai_role_prompt"], history, user_message,
        scenario.get("metric_categories", [])
    )
    return jsonify(result)


@app.route("/roleplay/custom")
def roleplay_custom_page():
    return render_template("roleplay_custom.html")


@app.route("/roleplay/custom/message", methods=["POST"])
def roleplay_custom_message():
    from ai_helpers import roleplay_respond
    data = request.get_json()
    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []
    resume = (data.get("resume") or "").strip()
    jd = (data.get("jd") or "").strip()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    if not resume or not jd:
        return jsonify({"error": "Resume and JD are required"}), 400

    ai_role_prompt = f"""You are a senior hiring manager at a US tech company conducting a job interview.
You have the candidate's resume and the job description in front of you.
Your job is to evaluate whether this candidate is a good fit for THIS specific role.

CANDIDATE'S RESUME:
{resume[:3000]}

JOB DESCRIPTION:
{jd[:2000]}

Interview style:
- Ask questions that directly relate to the JD requirements and the candidate's resume claims
- Probe their experience — ask for specifics, examples, numbers, tools
- Mix technical questions (based on JD skills) with behavioral questions
- If they mention something on their resume, dig deeper — verify depth vs surface knowledge
- Be friendly but thorough. Push back on vague or generic answers
- Keep responses short (2-4 sentences)
- React naturally to their answers — follow up, challenge, or move on"""

    metric_categories = ["Technical Fit", "Experience Depth", "Communication", "Role Alignment"]

    result = roleplay_respond(
        "custom_interview", ai_role_prompt, history, user_message, metric_categories
    )
    return jsonify(result)


# ---------------------------------------------------------------------------
# Feature 9: Visual Vocabulary
# ---------------------------------------------------------------------------

VISUAL_VOCAB_FILE = os.path.join(os.path.dirname(__file__), "data", "visual_vocab_history.json")


def _load_visual_history():
    if os.path.exists(VISUAL_VOCAB_FILE):
        try:
            with open(VISUAL_VOCAB_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_visual_history(history):
    os.makedirs(os.path.dirname(VISUAL_VOCAB_FILE), exist_ok=True)
    with open(VISUAL_VOCAB_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _fetch_duckduckgo_images(search_terms, word):
    """Fetch images via DuckDuckGo image search (no API key needed, best relevance)."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []

    images = []
    seen_urls = set()
    ddgs = DDGS()
    for term in search_terms[:3]:
        try:
            results = ddgs.images(term, max_results=3)
            for r in results:
                url = r.get("image", "")
                if url and url not in seen_urls and not url.endswith(".svg"):
                    seen_urls.add(url)
                    images.append({
                        "url": url,
                        "alt": term,
                        "credit": r.get("source", "Web"),
                    })
                    break
        except Exception:
            pass
    return images


def _fetch_pexels_images(search_terms):
    """Fetch images from Pexels API if key available."""
    import requests as http_req
    key = os.environ.get("PEXELS_API_KEY", "")
    if not key:
        return None
    images = []
    for term in search_terms[:3]:
        try:
            resp = http_req.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": key},
                params={"query": term, "per_page": 3, "size": "medium"},
                timeout=5,
            )
            if resp.status_code == 200:
                photos = resp.json().get("photos", [])
                if photos:
                    images.append({
                        "url": photos[0]["src"]["medium"],
                        "alt": term,
                        "credit": photos[0].get("photographer", "Pexels"),
                    })
        except Exception:
            pass
    return images if images else None


def _get_image_urls(search_terms, word):
    """Get image URLs — tries DuckDuckGo → Pexels → placeholder."""
    # 1. DuckDuckGo (no key needed, best relevance for all word types)
    ddg = _fetch_duckduckgo_images(search_terms, word)
    if ddg and len(ddg) >= 2:
        return ddg

    # 2. Pexels (best quality, needs API key)
    pexels = _fetch_pexels_images(search_terms)
    if pexels and len(pexels) >= 2:
        return pexels

    # 3. Fallback: combine whatever we got + placeholder
    all_imgs = (ddg or []) + (pexels or [])
    while len(all_imgs) < 3:
        idx = len(all_imgs)
        all_imgs.append({
            "url": f"https://placehold.co/400x300/1e293b/818cf8?text={search_terms[idx] if idx < len(search_terms) else word}",
            "alt": search_terms[idx] if idx < len(search_terms) else word,
            "credit": "No image found",
        })
    return all_imgs[:3]


@app.route("/visual-vocab")
def visual_vocab_page():
    history = _load_visual_history()
    return render_template("visual_vocab.html", word_count=len(history))


@app.route("/visual-vocab/next", methods=["POST"])
def visual_vocab_next():
    history = _load_visual_history()
    exclude = [w["word"].lower() for w in history]

    word_data = generate_visual_word(exclude)
    if "error" in word_data:
        return jsonify({"error": f"Failed to generate word: {word_data['error']}"}), 500

    word = word_data.get("word", "").strip()
    if not word:
        return jsonify({"error": "No word generated"}), 500

    if word.lower() in exclude:
        word_data = generate_visual_word(exclude + [word.lower()])
        if "error" in word_data:
            return jsonify({"error": f"Failed to generate word: {word_data['error']}"}), 500
        word = word_data.get("word", "").strip()

    search_terms = word_data.get("image_searches", [word])
    images = _get_image_urls(search_terms, word)
    word_data["images"] = images

    history.append({
        "word": word.lower(),
        "data": word_data,
        "date": datetime.now().isoformat(),
    })
    _save_visual_history(history)

    return jsonify({**word_data, "total_words": len(history)})


@app.route("/visual-vocab/speak", methods=["POST"])
def visual_vocab_speak():
    """Generate speech audio using OpenAI TTS API."""
    import requests as http_req
    data = request.get_json()
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return jsonify({"error": "OpenAI API key not configured"}), 500

    try:
        resp = http_req.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "tts-1",
                "input": text,
                "voice": "alloy",
                "response_format": "mp3",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return jsonify({"error": f"TTS failed: {resp.status_code}"}), 500

        import base64
        audio_b64 = base64.b64encode(resp.content).decode("utf-8")
        return jsonify({"audio": audio_b64})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@app.route("/visual-vocab/history")
def visual_vocab_history():
    history = _load_visual_history()
    return jsonify(list(reversed(history)))


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
