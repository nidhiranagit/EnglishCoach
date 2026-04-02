"""
Analyzer module — analyzes English sentences using the configured LLM provider.
"""

import json
import time

from llm_provider import call_llm

SYSTEM_PROMPT = """You are an English coach. Analyze this sentence and return ONLY valid JSON:
{
  "verdict": "natural" | "unnatural" | "incorrect",
  "corrected": "corrected sentence or same if already natural",
  "explanation": "short explanation in simple Hinglish (Hindi+English mix)",
  "rule": "one-line grammar or usage rule",
  "score": 1-10
}

Scoring guide:
- 10: Perfect, sounds completely natural
- 7-9: Minor issues, still understandable
- 4-6: Noticeable errors that affect clarity
- 1-3: Major errors, hard to understand

Be encouraging but honest. The explanation should help a Hindi speaker understand the mistake."""


def analyze_sentence(sentence: str) -> dict:
    """Analyze a sentence using the configured LLM provider. Retries once on failure."""
    for attempt in range(2):
        try:
            raw = call_llm(SYSTEM_PROMPT, sentence, max_tokens=500)

            # Try to extract JSON from the response
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw)

            # Validate required fields
            required = ["verdict", "corrected", "explanation", "rule", "score"]
            for key in required:
                if key not in result:
                    raise ValueError(f"Missing field: {key}")

            result["score"] = max(1, min(10, int(result["score"])))
            return result

        except Exception as e:
            if attempt == 0:
                time.sleep(1)
                continue
            return {
                "verdict": "error",
                "corrected": sentence,
                "explanation": f"API error: {str(e)[:100]}",
                "rule": "Could not analyze — try again later",
                "score": 0,
            }
