"""
Challenges module — daily writing challenge prompts.
"""

import hashlib
from datetime import date

CHALLENGE_POOL = [
    # Descriptive
    {"prompt": "Describe your morning routine in 3 sentences.", "category": "descriptive", "difficulty": "easy"},
    {"prompt": "Describe your favorite place to relax. What makes it special?", "category": "descriptive", "difficulty": "easy"},
    {"prompt": "Describe the weather today and how it affects your mood.", "category": "descriptive", "difficulty": "easy"},
    {"prompt": "Describe your workspace or study area in detail.", "category": "descriptive", "difficulty": "easy"},
    {"prompt": "Describe a meal you recently enjoyed. What made it good?", "category": "descriptive", "difficulty": "easy"},
    {"prompt": "Describe your commute to work or school.", "category": "descriptive", "difficulty": "easy"},
    {"prompt": "Describe a person you admire without naming them.", "category": "descriptive", "difficulty": "medium"},
    {"prompt": "Describe what your city looks like at night.", "category": "descriptive", "difficulty": "medium"},

    # Formal / Professional
    {"prompt": "Write a polite email declining a meeting invitation.", "category": "formal", "difficulty": "medium"},
    {"prompt": "Write a message to your manager asking for a day off.", "category": "formal", "difficulty": "medium"},
    {"prompt": "Write a follow-up email after a job interview thanking the interviewer.", "category": "formal", "difficulty": "medium"},
    {"prompt": "Write a message introducing yourself to a new team.", "category": "formal", "difficulty": "medium"},
    {"prompt": "Write an email requesting feedback on your recent project.", "category": "formal", "difficulty": "medium"},
    {"prompt": "Write a professional message apologizing for a delayed response.", "category": "formal", "difficulty": "easy"},
    {"prompt": "Write an email to a client explaining a project delay.", "category": "formal", "difficulty": "hard"},
    {"prompt": "Write a LinkedIn connection request to someone in your industry.", "category": "formal", "difficulty": "medium"},

    # Casual / Social
    {"prompt": "Write a message inviting a friend to watch a movie this weekend.", "category": "casual", "difficulty": "easy"},
    {"prompt": "Write a thank-you message to a friend who helped you move.", "category": "casual", "difficulty": "easy"},
    {"prompt": "Write a message canceling plans with a friend politely.", "category": "casual", "difficulty": "easy"},
    {"prompt": "Write a birthday wish for a close friend.", "category": "casual", "difficulty": "easy"},
    {"prompt": "Write a message recommending a restaurant to a friend.", "category": "casual", "difficulty": "easy"},
    {"prompt": "Write a message congratulating a friend on their new job.", "category": "casual", "difficulty": "easy"},

    # Opinion / Persuasion
    {"prompt": "Write 3 sentences arguing why remote work is better than office work.", "category": "opinion", "difficulty": "medium"},
    {"prompt": "Write 3 sentences about why everyone should learn a second language.", "category": "opinion", "difficulty": "medium"},
    {"prompt": "Write your opinion on whether social media helps or hurts communication.", "category": "opinion", "difficulty": "hard"},
    {"prompt": "Explain why reading books is still important in the digital age.", "category": "opinion", "difficulty": "medium"},
    {"prompt": "Write 3 reasons why cooking at home is better than eating out.", "category": "opinion", "difficulty": "medium"},
    {"prompt": "Argue for or against: 'AI will replace most jobs in 10 years.'", "category": "opinion", "difficulty": "hard"},

    # Storytelling / Creative
    {"prompt": "Write a short story in 3 sentences about missing a train.", "category": "creative", "difficulty": "medium"},
    {"prompt": "Continue this story: 'When I opened the door, I couldn't believe what I saw...'", "category": "creative", "difficulty": "medium"},
    {"prompt": "Write about a funny incident that happened to you recently.", "category": "creative", "difficulty": "medium"},
    {"prompt": "Write a story about a day when everything went wrong.", "category": "creative", "difficulty": "medium"},
    {"prompt": "Describe a dream you had recently (real or imaginary).", "category": "creative", "difficulty": "medium"},
    {"prompt": "Write about the best gift you ever received and why it was special.", "category": "creative", "difficulty": "easy"},

    # Instructions / How-to
    {"prompt": "Explain how to make chai in 4 steps.", "category": "instructional", "difficulty": "easy"},
    {"prompt": "Explain to someone how to use Google Maps to find directions.", "category": "instructional", "difficulty": "easy"},
    {"prompt": "Write instructions for setting up a new phone.", "category": "instructional", "difficulty": "medium"},
    {"prompt": "Explain how to prepare for a job interview in 3 steps.", "category": "instructional", "difficulty": "medium"},
    {"prompt": "Write a step-by-step guide to making a good first impression.", "category": "instructional", "difficulty": "medium"},

    # Comparison
    {"prompt": "Compare living in a city vs living in a small town.", "category": "comparison", "difficulty": "medium"},
    {"prompt": "Compare two apps or tools you use daily. Which is better?", "category": "comparison", "difficulty": "medium"},
    {"prompt": "Compare learning from YouTube vs learning from a teacher.", "category": "comparison", "difficulty": "medium"},
    {"prompt": "Compare working in a team vs working alone.", "category": "comparison", "difficulty": "medium"},

    # Hypothetical
    {"prompt": "If you could travel anywhere tomorrow, where would you go and why?", "category": "hypothetical", "difficulty": "easy"},
    {"prompt": "If you could have dinner with any famous person, who and why?", "category": "hypothetical", "difficulty": "medium"},
    {"prompt": "What would you do if you won a lottery of 1 crore rupees?", "category": "hypothetical", "difficulty": "easy"},
    {"prompt": "If you could change one thing about your city, what would it be?", "category": "hypothetical", "difficulty": "medium"},
    {"prompt": "Imagine you are the CEO of a tech company. Write your first email to employees.", "category": "hypothetical", "difficulty": "hard"},
    {"prompt": "If you could learn any skill instantly, what would you choose and why?", "category": "hypothetical", "difficulty": "easy"},

    # Professional scenarios
    {"prompt": "Write a Slack message asking your team for status updates on a project.", "category": "professional", "difficulty": "medium"},
    {"prompt": "Write a message to HR asking about the company's leave policy.", "category": "professional", "difficulty": "medium"},
    {"prompt": "Write a short presentation introduction for a project demo.", "category": "professional", "difficulty": "hard"},
    {"prompt": "Write an email to a vendor negotiating a better price.", "category": "professional", "difficulty": "hard"},
]


def get_todays_challenge() -> dict:
    """Get today's challenge — deterministic based on date."""
    today_str = date.today().isoformat()
    hash_val = int(hashlib.md5(today_str.encode()).hexdigest(), 16)
    index = hash_val % len(CHALLENGE_POOL)
    challenge = CHALLENGE_POOL[index].copy()
    challenge["date"] = today_str
    return challenge


def get_challenge_categories() -> list[str]:
    """Get all unique challenge categories."""
    return sorted(set(c["category"] for c in CHALLENGE_POOL))
