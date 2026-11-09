import os
import requests

from flask import Blueprint, request, jsonify, session, current_app

from .auth import student_required
from .models import Student



ai_tutor_bp = Blueprint(
    "ai_tutor",
    __name__,
    url_prefix="/api/ai"
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


SYSTEM_PROMPT = """
You are YoungVerse AI, a friendly educational tutor for PSEB students
studying in Classes 5th to 10th.

Your responsibilities:
1. Explain academic concepts in simple language.
2. Give step-by-step explanations.
3. Support Mathematics, Science, English, Punjabi, Hindi and Social Science.
4. Adapt explanations to the student's class level.
5. Respond in the language selected by the student.
6. Encourage understanding instead of memorising answers.
7. For homework, explain the method and help the student learn.
8. If a question is outside your educational scope, respond politely.

Never pretend to know information you are unsure about.
"""


@ai_tutor_bp.route("/chat", methods=["POST"])
@student_required
def ai_chat():

    data = request.get_json(silent=True) or {}

    question = str(data.get("question", "")).strip()
    subject = str(data.get("subject", "General")).strip()
    language = str(data.get("language", "English")).strip()

    if not question:
        return jsonify({
            "success": False,
            "message": "Please enter a question."
        }), 400

    if len(question) > 4000:
        return jsonify({
            "success": False,
            "message": "Question is too long."
        }), 400

    allowed_languages = ["English", "Hindi", "Punjabi"]
    if language not in allowed_languages:
        language = "English"

    allowed_subjects = [
        "Mathematics",
        "Science",
        "English",
        "Punjabi",
        "Hindi",
        "Social Science",
        "General"
    ]

    if subject not in allowed_subjects:
        subject = "General"

    student = Student.query.get(session.get("student_id"))

    if not student or not student.is_active:
        return jsonify({
            "success": False,
            "message": "Student account is inactive."
        }), 403

    api_key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")

    if not api_key or not model:
        return jsonify({
            "success": False,
            "message": "AI Tutor is not configured."
        }), 503

    user_message = f"""
Student class: {student.class_name}
Board: {student.board}
Subject: {subject}
Required response language: {language}

Student question:
{question}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "YoungVerse AI"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.5,
        "max_tokens": 1000000
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=45
        )

        if response.status_code != 200:
            current_app.logger.error(
                "OpenRouter error: %s",
                response.text[:1000]
            )

            return jsonify({
                "success": False,
                "message": "AI service could not answer right now."
            }), 502

        result = response.json()

        answer = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        if not isinstance(answer, str) or not answer.strip():
            return jsonify({
                "success": False,
                "message": "AI returned an empty response."
            }), 502

        return jsonify({
            "success": True,
            "answer": answer.strip(),
            "subject": subject,
            "language": language
        })

    except requests.Timeout:
        return jsonify({
            "success": False,
            "message": "AI response timed out. Please try again."
        }), 504

    except requests.RequestException:
        current_app.logger.exception("AI Tutor connection failed")

        return jsonify({
            "success": False,
            "message": "Could not connect to AI service."
        }), 502