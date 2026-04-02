"""
AI Helpers — shared LLM utilities and feature-specific AI functions.
Uses llm_provider for multi-provider support (Anthropic/OpenAI/Ollama).
"""

import json
import time

from llm_provider import call_llm


def call_llm_json(system_prompt: str, user_message: str, required_fields: list[str], max_tokens: int = 500) -> dict:
    """Call LLM and parse JSON response. Retries once on failure."""
    for attempt in range(2):
        try:
            raw = call_llm(system_prompt, user_message, max_tokens)
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw)
            for key in required_fields:
                if key not in result:
                    raise ValueError(f"Missing field: {key}")
            return result
        except Exception as e:
            if attempt == 0:
                time.sleep(1)
                continue
            return {"error": str(e)[:200]}


# ---------------------------------------------------------------------------
# Feature-specific AI functions
# ---------------------------------------------------------------------------

def extract_vocabulary(original: str, corrected: str, explanation: str) -> list[dict]:
    """Extract vocabulary words from a sentence correction."""
    prompt = """You are an English vocabulary coach for Hindi speakers.
Given an original sentence and its corrected version, extract 1-3 important/better English words
that the learner should add to their vocabulary.

Return ONLY valid JSON — an array of objects:
[
  {
    "word": "the word or short phrase",
    "meaning": "simple meaning in English",
    "example": "a short example sentence using this word",
    "explanation_hi": "meaning explained in simple Hinglish"
  }
]

Rules:
- Only extract words that are genuinely useful to learn
- Skip very basic words (the, is, a, etc.)
- If the corrected sentence is identical to original, return empty array []
- Focus on words that were IMPROVED or ADDED in the correction
- Keep explanations short and clear"""

    user_msg = f"Original: {original}\nCorrected: {corrected}\nExplanation: {explanation}"
    result = call_llm_json(prompt, user_msg, [], max_tokens=600)
    if isinstance(result, list):
        return result
    if "error" in result:
        return []
    return []


def compare_sentences(sentence_a: str, sentence_b: str) -> dict:
    """Compare two sentence versions and explain which is better."""
    prompt = """You are an English language expert. Compare two versions of a sentence.
Return ONLY valid JSON:
{
  "winner": "a" or "b",
  "score_a": 1-10,
  "score_b": 1-10,
  "explanation": "Clear explanation in simple Hinglish of why one is better",
  "improved": "The best possible version of this sentence",
  "differences": ["list of specific differences between the two"]
}

Be specific about grammar, naturalness, clarity, and tone."""

    user_msg = f"Sentence A: {sentence_a}\nSentence B: {sentence_b}"
    return call_llm_json(prompt, user_msg,
                         ["winner", "score_a", "score_b", "explanation", "improved", "differences"],
                         max_tokens=600)


def analyze_email(email_text: str, context_type: str) -> dict:
    """Analyze an email/message for tone, formality, and clarity."""
    prompt = f"""You are an English business communication coach for Hindi speakers.
The user is writing a "{context_type}" message. Analyze it and return ONLY valid JSON:
{{
  "tone_score": 1-10,
  "formality_score": 1-10,
  "clarity_score": 1-10,
  "overall_score": 1-10,
  "corrected": "improved version of the full email/message",
  "tone_feedback": "short feedback on tone in Hinglish",
  "formality_feedback": "short feedback on formality in Hinglish",
  "clarity_feedback": "short feedback on clarity in Hinglish",
  "tips": ["list of 2-3 specific improvement tips"]
}}

Context types and expected style:
- manager_email: professional, respectful, clear
- client_reply: polite, confident, solution-oriented
- cold_email: concise, value-driven, not pushy
- linkedin_message: professional but warm, networking tone
- decline_meeting: polite, firm, offers alternative
- follow_up: persistent but polite, adds value"""

    return call_llm_json(prompt, email_text,
                         ["tone_score", "formality_score", "clarity_score", "overall_score", "corrected"],
                         max_tokens=800)


def generate_grammar_drill(topic: str, past_mistakes: list[str]) -> dict:
    """Generate fill-in-the-blank grammar exercises."""
    mistakes_context = ""
    if past_mistakes:
        mistakes_context = f"\n\nHere are the user's past mistakes related to this topic (use these to create relevant exercises):\n" + "\n".join(f"- {m}" for m in past_mistakes[:10])

    prompt = f"""You are an English grammar teacher for Hindi speakers.
Create 5 fill-in-the-blank exercises on the topic: "{topic}".{mistakes_context}

Return ONLY valid JSON:
{{
  "topic": "{topic}",
  "exercises": [
    {{
      "sentence": "She ___ to the store yesterday.",
      "blank_position": "the word(s) that fill the blank",
      "answer": "went",
      "options": ["went", "go", "goes", "going"],
      "explanation_hi": "short Hinglish explanation of why this answer is correct"
    }}
  ]
}}

Rules:
- Make exercises progressively harder (easy → medium → hard)
- Each exercise must have exactly 4 options
- Explanations should help Hindi speakers understand the grammar rule
- If past mistakes are given, create exercises that address those specific patterns"""

    return call_llm_json(prompt, f"Generate exercises for: {topic}",
                         ["topic", "exercises"], max_tokens=1000)


def get_idiom_of_the_day(seen_idioms: list[str]) -> dict:
    """Generate a new idiom/phrase not in the seen list."""
    seen_context = ""
    if seen_idioms:
        seen_context = "\n\nDo NOT repeat these previously shown idioms:\n" + "\n".join(f"- {s}" for s in seen_idioms[-50:])

    prompt = f"""You are an English idiom and phrase teacher for Hindi speakers.
Pick ONE useful, commonly-used English idiom or phrase that would be helpful for everyday and professional use.{seen_context}

Return ONLY valid JSON:
{{
  "phrase": "the idiom or phrase",
  "meaning": "what it means in simple English",
  "example": "a natural example sentence using this phrase",
  "explanation_hi": "meaning and usage explained in simple Hinglish",
  "usage_tip": "when and where to use this phrase",
  "category": "business" | "casual" | "academic" | "emotional" | "daily"
}}"""

    return call_llm_json(prompt, "Give me an idiom of the day",
                         ["phrase", "meaning", "example", "explanation_hi"], max_tokens=400)


def improve_conversation(conversation_lines: list[str]) -> dict:
    """Improve each line of a conversation dialogue."""
    formatted = "\n".join(f"Line {i+1}: {line}" for i, line in enumerate(conversation_lines))

    prompt = """You are an English conversation coach for Hindi speakers.
The user has written a multi-line conversation or dialogue. Improve each line to sound
more natural and fluent while keeping the same meaning.

Return ONLY valid JSON:
{
  "lines": [
    {
      "original": "the original line",
      "improved": "the improved, more natural version",
      "explanation": "short Hinglish explanation of what was improved and why"
    }
  ],
  "overall_tips": ["2-3 general tips about the conversation style"]
}

Rules:
- Keep the same intent and meaning for each line
- Make improvements natural, not overly formal
- If a line is already good, keep it and say so in the explanation
- Focus on how native speakers would actually say things"""

    return call_llm_json(prompt, formatted,
                         ["lines", "overall_tips"], max_tokens=1200)
