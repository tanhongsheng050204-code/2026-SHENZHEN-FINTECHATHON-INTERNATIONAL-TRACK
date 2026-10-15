from functools import lru_cache

from app.config import get_settings


@lru_cache(maxsize=2)
def _client(api_key: str, timeout_ms: int):
    from google import genai

    return genai.Client(
        api_key=api_key,
        http_options={"timeout": timeout_ms},
    )


def gemini_client():
    """Return a retained, timeout-bounded client for the current process."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return _client(settings.gemini_api_key, settings.gemini_timeout_seconds * 1_000)


def voice_client():
    """The client for voice transcription: VOICE_GEMINI_API_KEY, else GEMINI_API_KEY."""
    settings = get_settings()
    key = getattr(settings, "voice_gemini_api_key", None) or settings.gemini_api_key
    if not key:
        raise RuntimeError("No Gemini key is configured for voice")
    return _client(key, settings.gemini_timeout_seconds * 1_000)
