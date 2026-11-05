import json
import logging
import os
import time
from urllib.request import Request, urlopen

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

log = logging.getLogger("small_assistant")


class AIServiceError(Exception):
    """The AI provider rejected or could not serve the request."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class AIService:
    """All AI calls: provider access plus the prompts for each feature."""

    WORD_CHECK_BATCH_SIZE = 50

    @staticmethod
    def generate_response(
        prompt: str,
        system_instruction: str,
        provider: str,
        json_mode: bool = False,
        json_format: dict[str, object] | None = None,
    ) -> str:
        if provider == "local":
            ollama_base_url = os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            ).strip().rstrip("/")
            ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:12b").strip()
            try:
                with urlopen(f"{ollama_base_url}/api/tags", timeout=3) as response:
                    installed_models = json.load(response).get("models", [])
                matching_model = next(
                    (
                        model.get("name") or model.get("model")
                        for model in installed_models
                        if (model.get("name") or model.get("model", "")).casefold()
                        == ollama_model.casefold()
                    ),
                    None,
                )
            except (OSError, ValueError, TypeError):
                matching_model = None

            if not matching_model:
                raise ValueError(
                    f"Ollama model {ollama_model!r} was not found at "
                    f"{ollama_base_url}. Start Ollama or set OLLAMA_MODEL in .env."
                )

            payload = {
                "model": matching_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "options": {"temperature": 0.2},
            }
            if json_mode:
                payload["format"] = json_format or {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "word": {"type": "string"},
                            "reading": {"type": "string"},
                            "meaning": {"type": "string"},
                            "part_of_speech": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": [
                            "id",
                            "word",
                            "reading",
                            "meaning",
                            "part_of_speech",
                            "reason",
                        ],
                        "additionalProperties": False,
                    },
                }
            request = Request(
                f"{ollama_base_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=180) as response:
                result = json.load(response)
            feedback = result.get("message", {}).get("content", "").strip()
            if not feedback:
                raise ValueError("The local AI returned an empty response. Please try again.")
            return feedback
        if provider != "online":
            raise ValueError(f"Unknown AI service: {provider}")

        api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv(
            "OPENAI_API_KEY", ""
        ).strip()
        if not api_key:
            raise ValueError(
                "Add your API key to GEMINI_API_KEY in .env to use the Online API."
            )

        base_url = os.getenv("GEMINI_BASE_URL", "").strip()
        model = os.getenv("GEMINI_MODEL", "").strip() or os.getenv(
            "OPENAI_MODEL", "gemini-3.8-flash"
        ).strip()
        if not model:
            raise ValueError("Set a model name in the GEMINI_MODEL setting in .env.")

        if base_url:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(base_url=base_url),
            )
        else:
            client = genai.Client(api_key=api_key)
        config = {
            "system_instruction": system_instruction,
            "temperature": 0.2,
        }
        if json_mode:
            config["response_mime_type"] = "application/json"
        fallbacks = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.8-flash,gemini-3.5-flash-lite")
        models = [model]
        for name in fallbacks.split(","):
            name = name.strip()
            if name and name not in models:
                models.append(name)
        response = None
        last_error: genai_errors.APIError | None = None
        busy = False
        for index, name in enumerate(models):
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=name,
                        contents=prompt,
                        config=config,
                    )
                    break
                except genai_errors.APIError as error:
                    last_error = error
                    code = getattr(error, "code", None)
                    busy = busy or code in {429, 500, 502, 503, 504}
                    log.warning(
                        "AI request failed (model %s, HTTP %s, attempt %d/2): %s",
                        name, code, attempt + 1, error,
                    )
                    if code in {401, 403}:
                        raise AIServiceError(
                            "The AI service rejected the API key. Check GEMINI_API_KEY in .env.",
                            502,
                        ) from error
                    if code in {429, 500, 502, 503, 504} and attempt == 0 and index == len(models) - 1:
                        time.sleep(2)
                        continue
                    break
            if response is not None:
                if index:
                    log.warning("AI fell back from %s to %s", model, name)
                break
        if response is None:
            code = getattr(last_error, "code", None)
            message = (
                "The AI service is busy right now. Please try again in a moment."
                if busy
                else f"The AI service returned an error (HTTP {code}). Check GEMINI_MODEL and GEMINI_FALLBACK_MODELS in .env."
            )
            raise AIServiceError(message, 503 if busy else 502) from last_error
        if not response.text:
            raise ValueError("The AI returned an empty response. Please try again.")
        return response.text.strip()

    @classmethod
    def composition_feedback(
        cls,
        words: list[str],
        text: str,
        provider: str,
        language: str = "English",
        grammar_points: list[dict[str, str]] | None = None,
    ) -> dict[str, str]:
        schema: dict[str, object] = {
            "type": "object",
            "properties": {
                "corrected": {"type": "string"},
                "evaluation": {"type": "string"},
            },
            "required": ["corrected", "evaluation"],
            "additionalProperties": False,
        }
        prompt = json.dumps(
            {
                "evaluation_language": language,
                "required_words": words,
                "required_grammar_points": grammar_points or [],
                "composition": text,
            },
            ensure_ascii=False,
        )
        system_instruction = (
            "You mark a Japanese learner's short composition that must use every word "
            "in required_words (inflected or conjugated forms are fine) and every grammar "
            "pattern in required_grammar_points. Check that each grammar pattern is used "
            "naturally in the composition and name any missing or misused words or grammar. "
            "Return a JSON object with "
            "'corrected': the composition rewritten in Japanese with grammar and wording fixed, "
            "keeping the learner's meaning and using all required words and grammar points; "
            "do not translate the composition into the evaluation language. "
            "'evaluation': a brief evaluation covering grammar, naturalness "
            "and use of every required word and grammar point (say which were missing or misused), "
            "listing the main mistakes and why. "
            "LANGUAGE RULE: the evaluation must be written entirely in "
            + language
            + " (the evaluation_language field), even though the composition is Japanese. "
            "Only quoted Japanese excerpts from the composition may stay in Japanese; "
            "all explanations, labels and sentences around them must be in "
            + language
            + "."
        )
        response = cls.generate_response(
            prompt, system_instruction, provider, json_mode=True, json_format=schema
        )
        try:
            result = json.loads(response)
        except json.JSONDecodeError as error:
            raise ValueError("The AI returned invalid data. Please try again.") from error
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("corrected"), str)
            or not isinstance(result.get("evaluation"), str)
        ):
            raise ValueError("The AI returned an incomplete result. Please try again.")
        return {"corrected": result["corrected"], "evaluation": result["evaluation"]}

    @classmethod
    def word_suggestions(
        cls, words: list[dict[str, str]], provider: str, language: str = "English"
    ) -> list[dict[str, str]]:
        original_by_id = {word["id"]: word for word in words}
        prompt = json.dumps(
            [
                {
                    "id": word["id"],
                    "word": word["word"],
                    "reading": word["reading"],
                    "meaning": word["meaning"],
                    "part_of_speech": word.get("part_of_speech", ""),
                }
                for word in words
            ],
            ensure_ascii=False,
        )
        system_instruction = (
            "Check each Japanese vocabulary record for accurate spelling, kana reading, "
            "meaning or translation, and primary part of speech. Preserve the language "
            "and style of each existing meaning; do not translate it into another language. "
            "Use a concise English part_of_speech tag such as n, v, adj, or adv. Keep "
            "valid entries unchanged and do not guess when a name or context is ambiguous. "
            "Return only a JSON array with one object per input and exactly these string "
            "fields: id, word, reading, meaning, part_of_speech, reason. Preserve each id "
            "exactly. The reason should briefly say what needs correction, or say "
            "that the entry looks correct. Write every reason entirely in "
            + language
            + "; only quoted Japanese words may stay in Japanese."
        )
        schema: dict[str, object] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "word": {"type": "string"},
                    "reading": {"type": "string"},
                    "meaning": {"type": "string"},
                    "part_of_speech": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "id",
                    "word",
                    "reading",
                    "meaning",
                    "part_of_speech",
                    "reason",
                ],
                "additionalProperties": False,
            },
        }
        response = cls.generate_response(
            prompt,
            system_instruction,
            provider,
            json_mode=True,
            json_format=schema,
        )
        try:
            suggestions = json.loads(response)
        except json.JSONDecodeError as error:
            raise ValueError("The AI returned invalid word-check data. Please try again.") from error
        if isinstance(suggestions, dict) and len(words) == 1:
            suggestions = [suggestions]
        if not isinstance(suggestions, list):
            raise ValueError("The AI returned an invalid word-check list. Please try again.")

        parsed_by_id: dict[str, dict[str, str]] = {}
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                raise ValueError("The AI returned an invalid word-check item.")
            word_id = suggestion.get("id")
            if word_id not in original_by_id or word_id in parsed_by_id:
                raise ValueError("The AI returned mismatched word-check results.")
            original = original_by_id[word_id]
            parsed_by_id[word_id] = {
                key: suggestion.get(key, original.get(key, ""))
                for key in ("word", "reading", "meaning", "part_of_speech")
            } | {"id": word_id, "reason": suggestion.get("reason", "")}
            if any(not isinstance(value, str) for value in parsed_by_id[word_id].values()):
                raise ValueError("The AI returned invalid text in a word-check result.")

        if parsed_by_id.keys() != original_by_id.keys():
            raise ValueError("The AI did not return a result for every selected word.")
        return [parsed_by_id[word["id"]] for word in words]

    @classmethod
    def grammar_suggestions(
        cls, items: list[dict[str, str]], provider: str, language: str = "English"
    ) -> list[dict[str, str]]:
        keys = ("pattern", "connection", "meaning", "example", "category")
        original_by_id = {item["id"]: item for item in items}
        prompt = json.dumps(
            [{"id": item["id"], **{key: item.get(key, "") for key in keys}} for item in items],
            ensure_ascii=False,
        )
        system_instruction = (
            "Check each Japanese grammar point or particle record for accuracy: the pattern "
            "spelling, how it connects to other words (connection), its meaning or usage, "
            "and whether the Japanese example sentence is natural and really uses the pattern. "
            "Language rules: write meaning in English (a concise English explanation, even if "
            "the existing text is in another language); keep pattern, connection, example and "
            "category in Japanese, with no translation or romaji. "
            "Keep valid entries unchanged and do not invent content for empty fields. "
            "Return only a JSON array with one object per input and exactly these string "
            "fields: id, pattern, connection, meaning, example, category, reason. Preserve each "
            "id exactly. The reason briefly says what needs correction, or that the entry looks "
            "correct. Write every reason entirely in "
            + language
            + "; only quoted Japanese may stay in Japanese."
        )
        string = {"type": "string"}
        schema: dict[str, object] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {key: string for key in ("id", *keys, "reason")},
                "required": ["id", *keys, "reason"],
                "additionalProperties": False,
            },
        }
        response = cls.generate_response(
            prompt, system_instruction, provider, json_mode=True, json_format=schema
        )
        try:
            suggestions = json.loads(response)
        except json.JSONDecodeError as error:
            raise ValueError("The AI returned invalid grammar-check data. Please try again.") from error
        if isinstance(suggestions, dict) and len(items) == 1:
            suggestions = [suggestions]
        if not isinstance(suggestions, list):
            raise ValueError("The AI returned an invalid grammar-check list. Please try again.")
        parsed: dict[str, dict[str, str]] = {}
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                raise ValueError("The AI returned an invalid grammar-check item.")
            item_id = suggestion.get("id")
            if item_id not in original_by_id or item_id in parsed:
                raise ValueError("The AI returned mismatched grammar-check results.")
            original = original_by_id[item_id]
            result = {key: suggestion.get(key, original.get(key, "")) for key in keys}
            result |= {"id": item_id, "reason": suggestion.get("reason", "")}
            if any(not isinstance(value, str) for value in result.values()):
                raise ValueError("The AI returned invalid text in a grammar-check result.")
            parsed[item_id] = result
        if parsed.keys() != original_by_id.keys():
            raise ValueError("The AI did not return a result for every selected item.")
        return [parsed[item["id"]] for item in items]

    @classmethod
    def word_suggestions_batched(
        cls, words: list[dict[str, str]], provider: str
    ) -> list[dict[str, str]]:
        suggestions: list[dict[str, str]] = []
        for start in range(0, len(words), cls.WORD_CHECK_BATCH_SIZE):
            suggestions.extend(
                cls.word_suggestions(
                    words[start : start + cls.WORD_CHECK_BATCH_SIZE], provider
                )
            )
        return suggestions
