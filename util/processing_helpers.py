from typing import Any

def normalize_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)

def normalize_languages(languages: list[str] | None) -> set[str] | None:
    if not languages:
        return None
    return {language.strip().lower() for language in languages}