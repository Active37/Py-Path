import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


logger = logging.getLogger(__name__)


class TutorServiceError(Exception):
    pass


def get_ai_reply(question, lesson, history):
    if not settings.AI_API_KEY:
        logger.error(
            "AI tutor is unavailable because neither AI_API_KEY nor GEMINI_API_KEY is configured"
        )
        raise TutorServiceError(
            "AI tutoring is not configured. Set AI_API_KEY; AI_API_BASE_URL and "
            "AI_MODEL can be customized for your provider."
        )

    system_prompt = (
        "You are PyPath, a patient programming tutor for beginners through advanced learners. "
        "Teach accurately in small steps, explain jargon, give runnable examples, ask "
        "helpful questions, and adapt to the learner. Do not claim code was run. "
        "Answer questions about programming and the technologies taught in the current "
        "course. Match examples to the current course language, and distinguish HTML "
        "markup from programming languages when helpful. If a question is outside "
        "programming, briefly say so and redirect. "
        f"Course language: {lesson.get('language', 'Python')}. "
        f"Current lesson: {lesson['title']} ({lesson['track']}). "
        f"Lesson notes: {lesson['body']} Exercise: {lesson['exercise']}"
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": question})
    payload = json.dumps(
        {
            "model": settings.AI_MODEL,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 700,
        }
    ).encode("utf-8")
    request = Request(
        f"{settings.AI_API_BASE_URL.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            **(
                {"Authorization": f"Bearer {settings.AI_API_KEY}"}
                if settings.AI_API_KEY
                else {}
            ),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.AI_API_TIMEOUT) as response:
            result = json.loads(response.read(100_000).decode("utf-8"))
    except HTTPError as error:
        try:
            error_body = json.loads(error.read(10_000).decode("utf-8"))
            provider_message = error_body.get("error", {}).get("message", "")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            provider_message = ""
        if not isinstance(provider_message, str):
            provider_message = ""
        provider_message = " ".join(provider_message.split())[:300]
        if settings.AI_API_KEY:
            provider_message = provider_message.replace(settings.AI_API_KEY, "[redacted]")
        logger.warning("AI provider returned HTTP %s: %s", error.code, provider_message)
        detail = f" Provider says: {provider_message}" if provider_message else ""
        raise TutorServiceError(
            f"The AI tutor service returned HTTP {error.code}.{detail} "
            "Check the API key, model name, and Gemini API access."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        logger.warning("AI provider request failed: %s", error.__class__.__name__)
        raise TutorServiceError(
            "The AI tutor is temporarily unreachable. Please try again."
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("AI provider returned invalid JSON")
        raise TutorServiceError(
            "The AI tutor returned an invalid response. Please try again."
        ) from error

    try:
        reply = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        logger.warning("AI provider response did not contain a chat completion")
        raise TutorServiceError(
            "The AI tutor returned an unexpected response. Please try again."
        ) from error
    if not isinstance(reply, str) or not reply.strip():
        logger.warning("AI provider returned an empty chat completion")
        raise TutorServiceError("The AI tutor returned an empty response.")
    return reply.strip()[:8000]


def run_python_code(source_code, stdin="", language_id=None):
    if not settings.CODE_RUNNER_URL:
        raise TutorServiceError(
            "Code execution is not configured. Set CODE_RUNNER_URL to a self-hosted Judge0 API."
        )
    payload = json.dumps(
        {
            "source_code": source_code,
            "language_id": language_id or settings.CODE_RUNNER_LANGUAGE_ID,
            "stdin": stdin,
            "cpu_time_limit": 2,
            "wall_time_limit": 5,
            "memory_limit": 128000,
        }
    ).encode("utf-8")
    request_url = (
        f"{settings.CODE_RUNNER_URL.rstrip('/')}/submissions?"
        f"{urlencode({'base64_encoded': 'false', 'wait': 'true'})}"
    )
    headers = {"Content-Type": "application/json"}
    if settings.CODE_RUNNER_API_KEY:
        headers["X-Auth-Token"] = settings.CODE_RUNNER_API_KEY
    request = Request(request_url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=settings.CODE_RUNNER_TIMEOUT) as response:
            result = json.loads(response.read(100_000).decode("utf-8"))
    except HTTPError as error:
        logger.warning("Code runner returned HTTP %s", error.code)
        raise TutorServiceError(
            "The code runner rejected the request. Check its URL and API settings."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        logger.warning("Code runner request failed: %s", error.__class__.__name__)
        raise TutorServiceError(
            "The code runner is temporarily unreachable. Please try again."
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("Code runner returned invalid JSON")
        raise TutorServiceError(
            "The code runner returned an invalid response. Please try again."
        ) from error

    if not isinstance(result, dict):
        raise TutorServiceError("The code runner returned an unexpected response.")
    status = result.get("status")
    if not isinstance(status, dict):
        status = {}
    stdout = result.get("stdout")
    stderr = result.get("stderr") or result.get("compile_output")
    return {
        "stdout": stdout[:8000] if isinstance(stdout, str) else "",
        "stderr": stderr[:8000] if isinstance(stderr, str) else "",
        "status": status.get("description", "Unknown"),
    }
