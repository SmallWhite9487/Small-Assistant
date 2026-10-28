import json
import os
from urllib.request import Request, urlopen

from google import genai
from google.genai import types


class AIService:
    """All AI calls: provider access plus the prompts for each feature."""

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
                            "reason": {"type": "string"},
                        },
                        "required": ["id", "word", "reading", "meaning", "reason"],
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
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        if not response.text:
            raise ValueError("The AI returned an empty response. Please try again.")
        return response.text.strip()

    @classmethod
    def composition_feedback(
        cls, words: list[str], text: str, provider: str
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
        prompt = json.dumps({"required_words": words, "composition": text}, ensure_ascii=False)
        system_instruction = (
            "You mark a Japanese learner's short composition that must use every word "
            "in required_words (inflected or conjugated forms are fine). Check each "
            "required word was used correctly and name any that are missing. Return a JSON object with "
            "'corrected': the composition rewritten with grammar and wording fixed, "
            "keeping the learner's meaning and all required words, and "
            "'evaluation': a brief evaluation in English covering grammar, naturalness "
            "and use of every required word (say which words were missing or misused), listing the main mistakes and why."
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
        cls, words: list[dict[str, str]], provider: str
    ) -> list[dict[str, str]]:
        original_by_id = {word["id"]: word for word in words}
        prompt = json.dumps(
            [
                {
                    "id": word["id"],
                    "word": word["word"],
                    "reading": word["reading"],
                    "meaning": word["meaning"],
                }
                for word in words
            ],
            ensure_ascii=False,
        )
        system_instruction = (
            "Check each Japanese vocabulary record for accurate kanji/kana spelling, "
            "kana reading, and meaning or translation. Preserve the language and "
            "style of each existing meaning; do not translate it into another language. "
            "Keep valid entries unchanged and do not guess when a name or context is "
            "ambiguous. Return only a JSON array with one object per input and exactly "
            "these string fields: id, word, reading, meaning, reason. Preserve each id "
            "exactly. The reason should briefly say what needs correction, or say "
            "'Looks correct.'"
        )
        response = cls.generate_response(
            prompt, system_instruction, provider, json_mode=True
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
                for key in ("word", "reading", "meaning")
            } | {"id": word_id, "reason": suggestion.get("reason", "")}
            if any(not isinstance(value, str) for value in parsed_by_id[word_id].values()):
                raise ValueError("The AI returned invalid text in a word-check result.")

        if parsed_by_id.keys() != original_by_id.keys():
            raise ValueError("The AI did not return a result for every selected word.")
        return [parsed_by_id[word["id"]] for word in words]
