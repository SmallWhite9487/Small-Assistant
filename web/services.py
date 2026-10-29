"""Data and AI helpers shared by the Flask routes.

The web app reuses the desktop modules for parsing and AI, but keeps its own
data under ``web/`` (``words.csv``, ``Notes/`` and ``user_weights/``) so
nothing done in the browser changes the desktop app's files. On first run the
web words and notes are seeded from the desktop copies.
"""

from __future__ import annotations

import csv
import os
import re
import secrets
import shutil
import string
import sys
import tempfile
import threading
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.ai_service import AIService  # noqa: E402
from modules.conjugation import (  # noqa: E402
    ADJECTIVE_GROUPS,
    ADJECTIVE_HELP,
    BASE_HELP,
    FORM_HELP,
    VERB_GROUPS,
    conjugate,
    conjugate_adjective,
)
from modules.notes import NoteStore  # noqa: E402
from modules.storage import CSV_FIELDS, VocabularyStore  # noqa: E402
from modules.weights import MAX_WEIGHT, MIN_WEIGHT  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent
WEB_WORDS = WEB_DIR / "words.csv"
WEB_NOTES = WEB_DIR / "Notes"
USER_WEIGHTS = WEB_DIR / "user_weights"
DEVICE_CODE = re.compile(r"[A-Z0-9]{6}")


def _seed_web_data() -> None:
    if not WEB_WORDS.exists() and (ROOT / "words.csv").exists():
        shutil.copyfile(ROOT / "words.csv", WEB_WORDS)
    if not WEB_NOTES.exists():
        if (ROOT / "Notes").is_dir():
            shutil.copytree(ROOT / "Notes", WEB_NOTES)
        else:
            WEB_NOTES.mkdir(parents=True)


class ApiError(Exception):
    """An error that should be shown to the browser as JSON."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _text(data: dict, key: str, limit: int = 2000) -> str:
    value = data.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ApiError(f"{key} must be text.")
    return value.strip()[:limit]


def _flag(data: dict, key: str, default: bool) -> str:
    value = data.get(key, default)
    if isinstance(value, str):
        value = value.strip().casefold() in {"1", "true", "yes", "on"}
    return "True" if bool(value) else "False"


def _atomic_write(path: Path, words: list[dict[str, str]]) -> None:
    """Write the CSV through a temp file so a crash cannot truncate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows({field: row.get(field, "") for field in CSV_FIELDS} for row in words)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


class WordService:
    """Serialised access to words.csv with validation for the web routes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or WEB_WORDS
        self.store = VocabularyStore(self.path)
        self.lock = threading.RLock()

    def all(self) -> list[dict[str, str]]:
        with self.lock:
            return self.store.load()

    def save(self, words: list[dict[str, str]]) -> None:
        with self.lock:
            _atomic_write(self.path, words)

    def create(self, data: dict) -> dict[str, str]:
        word = _text(data, "word", 200)
        meaning = _text(data, "meaning", 500)
        if not word or not meaning:
            raise ApiError("Enter a Japanese word and its meaning.")
        entry = {
            "id": str(uuid.uuid4()),
            "word": word,
            "reading": _text(data, "reading", 200),
            "meaning": meaning,
            "notes": _text(data, "notes", 4000),
            "check_ai": _flag(data, "check_ai", True),
            "added_on": date.today().isoformat(),
        }
        with self.lock:
            words = self.store.load()
            words.append(entry)
            _atomic_write(self.path, words)
        return entry

    def update(self, word_id: str, data: dict) -> dict[str, str]:
        word = _text(data, "word", 200)
        meaning = _text(data, "meaning", 500)
        if not word or not meaning:
            raise ApiError("Enter a Japanese word and its meaning.")
        with self.lock:
            words = self.store.load()
            entry = next((item for item in words if item["id"] == word_id), None)
            if entry is None:
                raise ApiError("That word no longer exists.", 404)
            entry.update(
                word=word,
                reading=_text(data, "reading", 200),
                meaning=meaning,
                notes=_text(data, "notes", 4000),
                check_ai=_flag(data, "check_ai", entry["check_ai"] == "True"),
            )
            _atomic_write(self.path, words)
            return dict(entry)

    def delete(self, word_id: str) -> None:
        with self.lock:
            words = self.store.load()
            remaining = [item for item in words if item["id"] != word_id]
            if len(remaining) == len(words):
                raise ApiError("That word no longer exists.", 404)
            _atomic_write(self.path, remaining)

    def set_check(self, word_id: str, enabled: bool) -> dict[str, str]:
        with self.lock:
            words = self.store.load()
            entry = next((item for item in words if item["id"] == word_id), None)
            if entry is None:
                raise ApiError("That word no longer exists.", 404)
            entry["check_ai"] = "True" if enabled else "False"
            _atomic_write(self.path, words)
            return dict(entry)

    def flagged(self) -> list[dict[str, str]]:
        return [item for item in self.all() if item["check_ai"] == "True"]

    def clear_flags(self, ids: set[str]) -> None:
        with self.lock:
            words = self.store.load()
            for entry in words:
                if entry["id"] in ids:
                    entry["check_ai"] = "False"
            _atomic_write(self.path, words)

    def apply_corrections(self, changes: list) -> list[dict[str, str]]:
        """Apply AI corrections in one atomic save, or change nothing."""
        if not isinstance(changes, list) or not changes:
            raise ApiError("No corrections were supplied.")
        prepared: dict[str, dict[str, str]] = {}
        for change in changes:
            if not isinstance(change, dict):
                raise ApiError("A correction was malformed.")
            word_id = _text(change, "id", 100)
            word = _text(change, "word", 200)
            meaning = _text(change, "meaning", 500)
            if not word or not meaning:
                raise ApiError("A correction was missing its word or meaning.")
            if word_id in prepared:
                raise ApiError("The same word was corrected twice.")
            prepared[word_id] = {
                "word": word,
                "reading": _text(change, "reading", 200),
                "meaning": meaning,
            }
        with self.lock:
            words = self.store.load()
            known = {item["id"] for item in words}
            if not prepared.keys() <= known:
                raise ApiError("One of the words no longer exists.", 409)
            applied = []
            for entry in words:
                change = prepared.get(entry["id"])
                if change is None:
                    continue
                entry.update(change)
                applied.append(dict(entry))
            _atomic_write(self.path, words)
            return applied


class NoteService:
    def __init__(self, directory: Path | None = None) -> None:
        self.store = NoteStore(directory or WEB_NOTES)
        self.lock = threading.Lock()

    @staticmethod
    def safe_name(name: object) -> str:
        raw = str(name or "")
        candidate = Path(raw).name
        if not raw or candidate != raw or not candidate.endswith(".txt") or candidate.startswith("."):
            raise ApiError("Unknown note.")
        return candidate

    def list(self) -> list[dict[str, str]]:
        with self.lock:
            return self.store.list_notes()

    def read(self, name: str) -> dict[str, str]:
        safe = self.safe_name(name)
        with self.lock:
            try:
                content = self.store.read(safe)
            except OSError as error:
                raise ApiError("That note could not be opened.", 404) from error
        item = next((note for note in self.store.list_notes() if note["name"] == safe), None)
        return {"name": safe, "title": item["title"] if item else safe, "date": item["date"] if item else "", "content": content}

    def save(self, data: dict) -> dict[str, str]:
        title = _text(data, "title", 120)
        content = data.get("content", "")
        if not isinstance(content, str):
            raise ApiError("Note content must be text.")
        if not title:
            raise ApiError("Please enter a title for the note.")
        old_name = data.get("old_name") or None
        if old_name is not None:
            old_name = self.safe_name(old_name)
        with self.lock:
            try:
                name = self.store.save(title, content, old_name)
            except ValueError as error:
                raise ApiError(str(error)) from error
            except OSError as error:
                raise ApiError("The note could not be saved.", 500) from error
        match = next((note for note in self.store.list_notes() if note["name"] == name), None)
        return {
            "name": name,
            "title": match["title"] if match else title,
            "date": match["date"] if match else date.today().isoformat(),
        }

    def delete(self, name: str) -> None:
        safe = self.safe_name(name)
        with self.lock:
            self.store.delete(safe)


class AIChecker:
    """Thin wrapper that turns module errors into ApiError messages."""

    @staticmethod
    def provider(data: dict) -> str:
        provider = data.get("provider", "local")
        if provider not in {"local", "online"}:
            raise ApiError("Unknown AI service.")
        return provider

    @classmethod
    def composition(cls, data: dict) -> dict[str, str]:
        words = data.get("words")
        text = data.get("text")
        if not isinstance(words, list) or not words or not all(isinstance(w, str) for w in words):
            raise ApiError("Draw some words before submitting.")
        if not isinstance(text, str) or not text.strip():
            raise ApiError("Write something first.")
        provider = cls.provider(data)
        try:
            return AIService.composition_feedback([w.strip() for w in words], text.strip(), provider)
        except ValueError as error:
            raise ApiError(str(error)) from error
        except OSError as error:
            raise ApiError(f"The AI service could not be reached: {error}", 502) from error


class ConjugationService:
    @staticmethod
    def payload(text: str, mode: int) -> dict:
        text = text.strip()
        if not text:
            return {"recognized": False}
        if mode == 1:
            result = conjugate_adjective(text)
        else:
            result = conjugate(text)
        if result is None:
            return {"recognized": False}
        if mode == 1:
            base, kind, forms = result
            groups, helps = ADJECTIVE_GROUPS, ADJECTIVE_HELP
        else:
            base, forms = result
            kind = None
            groups, helps = VERB_GROUPS, FORM_HELP
        forms = {**forms, "原形": base}
        payload = []
        for index, (title, names) in enumerate(groups):
            entries = [
                {"name": name, "value": forms.get(name, "—"), "help": helps.get(name, "")}
                for name in names
            ]
            if index == len(groups) - 1:
                entries.append({"name": "原形", "value": base, "help": BASE_HELP})
            payload.append({"title": title, "forms": entries})
        return {"recognized": True, "base": base, "kind": kind, "groups": payload}


class WeightService:
    """Per-device review weights in user_weights/<CODE>.csv.

    A row exists only for words the user has actually answered, so unseen
    words never get a stored weight.
    """

    ALPHABET = string.ascii_uppercase + string.digits

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or USER_WEIGHTS
        self.lock = threading.Lock()

    @classmethod
    def valid_code(cls, code: object) -> bool:
        return isinstance(code, str) and DEVICE_CODE.fullmatch(code) is not None

    def new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(self.ALPHABET) for _ in range(6))
            if not self._path(code).exists():
                return code

    def _path(self, code: str) -> Path:
        if not self.valid_code(code):
            raise ApiError("Invalid device code.", 400)
        return self.directory / f"{code}.csv"

    def _read(self, code: str) -> dict[str, float]:
        path = self._path(code)
        if not path.exists():
            return {}
        weights: dict[str, float] = {}
        with path.open("r", newline="", encoding="utf-8") as file:
            for row in csv.reader(file):
                if len(row) < 2 or row[0] == "uuid":
                    continue
                try:
                    value = float(row[1])
                except ValueError:
                    continue
                if MIN_WEIGHT <= value <= MAX_WEIGHT:
                    weights[row[0]] = value
        return weights

    def load(self, code: str, valid_ids: set[str]) -> dict[str, float]:
        with self.lock:
            try:
                return {k: v for k, v in self._read(code).items() if k in valid_ids}
            except OSError as error:
                raise ApiError(f"Could not read your weights: {error}", 500) from error

    def set(self, code: str, word_id: str, weight: object) -> float:
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ApiError("Weight must be a number.")
        value = float(weight)
        if not (MIN_WEIGHT <= value <= MAX_WEIGHT):
            raise ApiError(f"Weight must be between {MIN_WEIGHT} and {MAX_WEIGHT}.")
        with self.lock:
            try:
                weights = self._read(code)
                weights[word_id] = value
                self.directory.mkdir(parents=True, exist_ok=True)
                path = self._path(code)
                handle, temp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
                with os.fdopen(handle, "w", newline="", encoding="utf-8") as file:
                    writer = csv.writer(file)
                    writer.writerow(("uuid", "weight"))
                    for key, number in weights.items():
                        writer.writerow((key, f"{number:.6f}"))
                os.replace(temp, path)
            except OSError as error:
                raise ApiError(f"Could not save your weights: {error}", 500) from error
        return value

    def reset(self, code: str) -> None:
        with self.lock:
            try:
                self._path(code).unlink(missing_ok=True)
            except OSError as error:
                raise ApiError(f"Could not reset your weights: {error}", 500) from error


_seed_web_data()
