# English Coach

A web-based English sentence practice app with AI-powered analysis and spaced repetition. Type any English sentence and get instant feedback on whether it sounds natural, what's wrong, and how to fix it — with explanations in simple Hinglish.

Powered by Anthropic's Claude API.

---

## Why We Built This

For many Hindi speakers, learning English grammar rules is one thing — but knowing whether a sentence actually *sounds natural* to a native speaker is a completely different challenge. Textbooks teach you the rules, but they don't tell you that "I am knowing the answer" is grammatically explainable yet sounds completely wrong to a native ear, or that "We discussed about the problem" has an invisible mistake most learners never catch.

We built English Coach to solve this exact gap. The idea is simple: you write how you'd naturally say something in English, and an AI coach tells you honestly — does this sound natural? If not, why not, and what's the better way to say it? No judgment, just clear feedback in Hinglish so it actually clicks.

But feedback alone doesn't build habits. You forget corrections the next day. That's why we added **spaced repetition** — the same science-backed method used by language apps worldwide. The sentences you got wrong come back after 1 day, then 3, then 7, then 14. Each time, you type the correction from memory. Over time, the correct form becomes automatic.

The core problems this solves:

- **"Is my sentence natural?"** — Not just grammatically correct, but would a native speaker actually say it this way?
- **"I keep making the same mistakes"** — The app tracks your most repeated error patterns and makes you review them
- **"I forget corrections the next day"** — Spaced repetition ensures you actually retain what you learn
- **"Grammar explanations are confusing in English"** — Explanations come in simple Hinglish so they're easier to absorb
- **"I have no way to track my progress"** — Dashboard, charts, streak tracking, and exportable reports show exactly how you're improving

This is a personal practice tool — 5 sentences a day, a few minutes of review, and over weeks you'll notice the difference in how naturally you write and speak English.

---

## Quick Start

### Prerequisites

- **Python 3.10+** installed on your computer
- **Anthropic API key** — get one free at [console.anthropic.com](https://console.anthropic.com/)

### Setup (one time)

1. Open your terminal/command prompt
2. Navigate to this folder:
   ```
   cd path/to/EnglishCoach
   ```
3. Open the `.env` file in any text editor and replace `your_api_key_here` with your actual API key:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxx-your-actual-key-here
   ```

### Run the app

**Option 1 — One command (recommended):**
```bash
python main.py
```
This will auto-install dependencies, auto-create `.env` if missing, and open your browser.

**Option 2 — Windows:**
Double-click `run.bat`

**Option 3 — Mac/Linux:**
```bash
bash run.sh
```

The app opens at **http://localhost:5050** in your browser.

Press `Ctrl+C` in the terminal to stop the app.

---

## Features

### 1. Practice Session (`/session`)
- Type up to **5 English sentences per day**
- Each sentence is analyzed by Claude AI and rated on a 1–10 scale
- Instant feedback with:
  - **Verdict**: natural / unnatural / incorrect
  - **Corrected version** of the sentence
  - **Explanation** in Hinglish (Hindi + English mix)
  - **Grammar rule** that applies

### 2. Spaced Repetition Review (`/review`)
- Sentences you got wrong come back for review on a smart schedule:
  - After **1 day** (first review)
  - After **3 days** (second review)
  - After **7 days** (third review)
  - After **14 days** (all subsequent reviews)
- You see the original wrong sentence and type the corrected version from memory
- Tracks your progress with similarity matching

### 3. Dashboard (`/`)
- Total sentences practiced
- Current streak (consecutive days)
- Average score this week vs last week (with trend arrow)
- Most common mistake pattern
- 14-day activity chart (sentences count + avg score)

### 4. History (`/history`)
- Browse all your past sentences with filters:
  - All / Incorrect / Unnatural / Bookmarked / With Notes
- Bookmark important sentences with the star button
- Add personal notes to any sentence for your own reference

### 5. Notes & Bookmarks (`/notes`)
- Quick access to all bookmarked sentences
- View all sentences where you've added personal notes

### 6. Progress Report (`/report`)
- Detailed score trend chart
- Improvement tracker (first half vs second half average)
- Verdict breakdown (natural / unnatural / incorrect counts)
- Top mistake patterns ranked by frequency
- Export as **Markdown** or **JSON**

---

## File Structure

```
EnglishCoach/
├── main.py            # Entry point — run this file
├── app.py             # Flask web server and routes
├── analyzer.py        # Anthropic API integration
├── storage.py         # Read/write history.json
├── review.py          # Spaced repetition logic
├── stats.py           # Dashboard and report calculations
├── requirements.txt   # Python dependencies
├── run.bat            # Windows one-click launcher
├── run.sh             # Mac/Linux one-click launcher
├── .env               # Your API key (create from .env.example)
├── .env.example       # Template for .env
├── README.md          # This file
├── templates/         # HTML templates
│   ├── base.html      # Shared layout (navbar, styles)
│   ├── dashboard.html
│   ├── session.html
│   ├── review.html
│   ├── history.html
│   ├── notes.html
│   └── report.html
└── data/
    └── history.json   # All your sentence data (auto-created)
```

---

## How It Works

### Sentence Analysis
When you type a sentence, it's sent to Claude (claude-sonnet-4-20250514) with a specialized prompt. The AI returns:
- A **verdict** (natural, unnatural, or incorrect)
- The **corrected** sentence
- An **explanation** in Hinglish so it's easy to understand
- A **grammar rule** that applies
- A **score** from 1 to 10

### Spaced Repetition
The app uses a spaced repetition algorithm to help you remember corrections. Sentences that you got wrong will reappear for review at increasing intervals (1 → 3 → 7 → 14 days). Each time you review, you type the correction from memory.

### Data Storage
Everything is stored locally in `data/history.json`. No data is sent anywhere except to the Anthropic API for analysis. You can export your full history as Markdown or JSON from the Report page.

---

## Example Usage

1. Open the app → see your Dashboard with stats
2. Click **Review** if there are sentences due (shown as a red badge)
3. Click **Practice** → type a sentence like "I am knowing the answer"
4. See the result: Score 4/10, verdict "incorrect", corrected to "I know the answer", with explanation about stative verbs
5. Next day: the app will ask you to review this sentence by typing the correction yourself
6. Track your improvement over time on the Report page

---

## Troubleshooting

**"ANTHROPIC_API_KEY not set"**
→ Open `.env` file and add your key. Get one at [console.anthropic.com](https://console.anthropic.com/)

**"ModuleNotFoundError: No module named 'flask'"**
→ Run: `pip install -r requirements.txt`

**Port 5050 already in use**
→ Another app is using that port. Either stop it, or edit `main.py` and change `port=5050` to another number like `5051`.

**App won't open in browser automatically**
→ Manually open **http://localhost:5050** in any browser.

---

## Dependencies

- `flask` — Web framework for the UI
- `anthropic` — Anthropic Python SDK for Claude API calls
- `python-dotenv` — Loads API key from `.env` file
- `markupsafe` — Template security (installed with Flask)

All dependencies are listed in `requirements.txt` and auto-installed when you run `main.py`.
