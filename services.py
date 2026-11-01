"""Data and AI helpers shared by the Flask routes.

The web app reuses the ``modules`` package for parsing and AI, and keeps its
data at the repository root (``words.csv``, ``Notes/`` and ``user_data/``).
"""

from __future__ import annotations

import csv
import json
import os
import re
import secrets
import string
import sys
import tempfile
import threading
import uuid
from urllib.parse import urlencode
from urllib.request import urlopen
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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
USER_DATA = WEB_DIR / "user_data"
DEVICE_CODE = re.compile(r"[A-Z0-9]{6}")
PROFILE_NAME = re.compile(r"[A-Za-z0-9]{1,15}")


def _seed_web_data() -> None:
    WEB_NOTES.mkdir(parents=True, exist_ok=True)


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
            "part_of_speech": _text(data, "part_of_speech", 40),
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
                part_of_speech=(
                    _text(data, "part_of_speech", 40)
                    if "part_of_speech" in data
                    else entry["part_of_speech"]
                ),
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
            if "part_of_speech" in change:
                prepared[word_id]["part_of_speech"] = _text(
                    change, "part_of_speech", 40
                )
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
        language = {"zh-TW": "Traditional Chinese (繁體中文)", "ko": "Korean (한국어)"}.get(data.get("language"), "English")
        try:
            return AIService.composition_feedback([w.strip() for w in words], text.strip(), provider, language)
        except ValueError as error:
            raise ApiError(str(error)) from error
        except OSError as error:
            raise ApiError(f"The AI service could not be reached: {error}", 502) from error

class MachineTranslationService:
    """Translate display-only meanings without changing vocabulary data."""

    TARGETS = {"zh-TW", "ko"}

    @classmethod
    def meaning(cls, meaning: object, language: object) -> str:
        if not isinstance(meaning, str) or not meaning.strip():
            raise ApiError("Meaning is required.")
        if language not in cls.TARGETS:
            raise ApiError("Translation is only available for Traditional Chinese or Korean.")
        query = urlencode({"client": "gtx", "sl": "en", "tl": language, "dt": "t", "q": meaning.strip()})
        try:
            with urlopen(f"https://translate.googleapis.com/translate_a/single?{query}", timeout=15) as response:
                data = json.load(response)
            translation = "".join(item[0] for item in data[0] if item and item[0]).strip()
        except (OSError, ValueError, IndexError, TypeError) as error:
            raise ApiError(f"Machine translation could not be completed: {error}", 502) from error
        if not translation:
            raise ApiError("Machine translation returned an empty result.", 502)
        return translation


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


class UserDataService:
    """Named cross-device profiles containing ratings, weights, and answer times."""

    ALPHABET = string.ascii_uppercase + string.digits
    RATINGS = {"again": 1, "hard": 2, "good": 3, "easy": 4}

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or USER_DATA
        self.lock = threading.Lock()

    @staticmethod
    def valid_code(code: object) -> bool:
        return isinstance(code, str) and DEVICE_CODE.fullmatch(code) is not None

    @staticmethod
    def _valid_profile_name(name: object) -> bool:
        return isinstance(name, str) and PROFILE_NAME.fullmatch(name) is not None

    def _profile_path(self, name: str) -> Path:
        if not self._valid_profile_name(name):
            raise ApiError("Profile names must use 1 to 15 English letters or numbers.")
        return self.directory / f"{name}.csv"

    def new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(self.ALPHABET) for _ in range(6))
            if not (USER_WEIGHTS / f"{code}.csv").exists() and not (self.directory / f"{code}.csv").exists():
                return code

    def _read_rows(self, path: Path) -> dict[str, tuple[int, float, float]]:
        records: dict[str, tuple[int, float, float]] = {}
        try:
            with path.open("r", newline="", encoding="utf-8") as file:
                for row in csv.reader(file):
                    if len(row) != 4:
                        continue
                    try:
                        rating = int(row[1])
                        weight = float(row[2])
                        duration = float(row[3])
                    except ValueError:
                        continue
                    if row[0] and 0 <= rating <= 4 and MIN_WEIGHT <= weight <= MAX_WEIGHT and duration >= 0:
                        records[row[0]] = (rating, weight, duration)
        except OSError as error:
            raise ApiError(f"Could not read your learning data: {error}", 500) from error
        return records

    def _read_profile(self, name: str) -> tuple[list[str], dict[str, tuple[int, float, float]]]:
        path = self._profile_path(name)
        try:
            with path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                devices = next(reader, [])
                if not devices or not all(self.valid_code(device) for device in devices):
                    raise ApiError("Profile data is invalid.", 500)
                records = self._read_records(reader)
        except OSError as error:
            raise ApiError(f"Could not read your learning data: {error}", 500) from error
        return list(dict.fromkeys(devices)), records

    @staticmethod
    def _read_records(rows) -> dict[str, tuple[int, float, float]]:
        records: dict[str, tuple[int, float, float]] = {}
        for row in rows:
            if len(row) != 4:
                continue
            try:
                rating = int(row[1])
                weight = float(row[2])
                duration = float(row[3])
            except ValueError:
                continue
            if row[0] and 0 <= rating <= 4 and MIN_WEIGHT <= weight <= MAX_WEIGHT and duration >= 0:
                records[row[0]] = (rating, weight, duration)
        return records

    def _legacy_records(self, code: str) -> dict[str, tuple[int, float, float]]:
        path = self.directory / f"{code}.csv"
        if path.exists():
            return self._read_rows(path)
        path = USER_WEIGHTS / f"{code}.csv"
        records: dict[str, tuple[int, float, float]] = {}
        if not path.exists():
            return records
        try:
            with path.open("r", newline="", encoding="utf-8") as file:
                for row in csv.reader(file):
                    if len(row) < 2 or row[0] == "uuid":
                        continue
                    try:
                        weight = float(row[1])
                    except ValueError:
                        continue
                    if MIN_WEIGHT <= weight <= MAX_WEIGHT:
                        records[row[0]] = (0, weight, 0.0)
        except OSError as error:
            raise ApiError(f"Could not migrate your weights: {error}", 500) from error
        return records

    def _write_profile(self, name: str, devices: list[str], records: dict[str, tuple[int, float, float]]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._profile_path(name)
        handle, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(devices)
                for word_id, (rating, weight, duration) in records.items():
                    writer.writerow((word_id, rating, f"{weight:.6f}", f"{duration:.3f}"))
            os.replace(temporary, path)
        except OSError as error:
            Path(temporary).unlink(missing_ok=True)
            raise ApiError(f"Could not save your learning data: {error}", 500) from error

    def profile_for_device(self, code: str) -> str | None:
        if not self.valid_code(code) or not self.directory.exists():
            return None
        for path in self.directory.glob("*.csv"):
            if not self._valid_profile_name(path.stem):
                continue
            try:
                with path.open(newline="", encoding="utf-8") as file:
                    devices = next(csv.reader(file), [])
            except OSError as error:
                raise ApiError(f"Could not read profile data: {error}", 500) from error
            if devices and all(self.valid_code(device) for device in devices) and code in devices:
                return path.stem
        return None

    def profiles(self) -> list[str]:
        if not self.directory.exists():
            return []
        profiles = []
        for path in self.directory.glob("*.csv"):
            if not self._valid_profile_name(path.stem):
                continue
            try:
                with path.open(newline="", encoding="utf-8") as file:
                    devices = next(csv.reader(file), [])
            except OSError as error:
                raise ApiError(f"Could not read profile data: {error}", 500) from error
            if devices and all(self.valid_code(device) for device in devices):
                profiles.append(path.stem)
        return sorted(profiles, key=str.casefold)

    def create_profile(self, name: object, code: str) -> str:
        if not self.valid_code(code):
            raise ApiError("Invalid device code.", 400)
        if not self._valid_profile_name(name):
            raise ApiError("Use 1 to 15 English letters or numbers for the profile name.")
        profile = str(name)
        with self.lock:
            if any(existing.casefold() == profile.casefold() for existing in self.profiles()):
                raise ApiError("That profile name is already in use.", 409)
            records = self._legacy_records(code)
            self._write_profile(profile, [code], records)
            legacy_path = self.directory / f"{code}.csv"
            if legacy_path != self._profile_path(profile):
                legacy_path.unlink(missing_ok=True)
        return profile

    def select_profile(self, name: object, code: str) -> str:
        if not self.valid_code(code):
            raise ApiError("Invalid device code.", 400)
        if not self._valid_profile_name(name):
            raise ApiError("Invalid profile name.")
        profile = str(name)
        with self.lock:
            devices, records = self._read_profile(profile)
            if code not in devices:
                devices.append(code)
                self._write_profile(profile, devices, records)
        return profile

    def _active_profile(self, code: str) -> str:
        profile = self.profile_for_device(code)
        if not profile:
            raise ApiError("Choose or create a learning profile first.", 409)
        return profile

    @staticmethod
    def _duration(value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ApiError("duration must be a number.")
        duration = float(value)
        if not 0 <= duration <= 3600:
            raise ApiError("duration must be between 0 and 3600 seconds.")
        return duration

    def weights(self, code: str, valid_ids: set[str]) -> dict[str, float]:
        with self.lock:
            profile = self.profile_for_device(code)
            if not profile:
                return {}
            _, data = self._read_profile(profile)
            return {
                word_id: record[1]
                for word_id, record in data.items()
                if word_id in valid_ids
            }

    def set_weight(self, code: str, word_id: str, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ApiError("Weight must be a number.")
        weight = float(value)
        if not MIN_WEIGHT <= weight <= MAX_WEIGHT:
            raise ApiError(f"Weight must be between {MIN_WEIGHT} and {MAX_WEIGHT}.")
        with self.lock:
            profile = self._active_profile(code)
            devices, records = self._read_profile(profile)
            rating, _, duration = records.get(word_id, (0, 1.0, 0.0))
            records[word_id] = (rating, weight, duration)
            self._write_profile(profile, devices, records)
        return weight

    def reset(self, code: str) -> None:
        with self.lock:
            try:
                profile = self._active_profile(code)
                devices, _ = self._read_profile(profile)
                self._write_profile(profile, devices, {})
            except OSError as error:
                raise ApiError(f"Could not reset your learning data: {error}", 500) from error

    def grade(self, code: str, word_id: str, rating: object, correct: object, duration: object) -> dict:
        if rating not in self.RATINGS:
            raise ApiError("rating must be again, hard, good, or easy.")
        if not isinstance(correct, bool):
            raise ApiError("correct must be true or false.")
        seconds = self._duration(duration)
        changes = {
            "again": 0.30,
            "hard": 0.20,
            "good": -0.10 if correct else 0.10,
            "easy": -0.20,
        }
        with self.lock:
            profile = self._active_profile(code)
            devices, records = self._read_profile(profile)
            _, previous_weight, _ = records.get(word_id, (0, 1.0, 0.0))
            weight = min(MAX_WEIGHT, max(MIN_WEIGHT, previous_weight * (1 + changes[rating])))
            record = (self.RATINGS[rating], weight, seconds)
            records[word_id] = record
            self._write_profile(profile, devices, records)
        return {"rating": record[0], "weight": record[1], "duration": record[2]}

    def statistics(self, code: str, word_ids: set[str]) -> dict:
        with self.lock:
            profile = self.profile_for_device(code)
            if not profile:
                records = {}
            else:
                _, data = self._read_profile(profile)
                records = {
                    word_id: record
                    for word_id, record in data.items()
                    if word_id in word_ids
                }
        rated = [record for record in records.values() if record[0] > 0]
        ratings = {}
        for name, value in self.RATINGS.items():
            matching = [record[2] for record in rated if record[0] == value]
            ratings[name] = {
                "count": len(matching),
                "average_duration": sum(matching) / len(matching) if matching else 0,
            }
        return {
            "total": len(word_ids),
            "reviewed": len(rated),
            "average_duration": sum(record[2] for record in rated) / len(rated) if rated else 0,
            "ratings": ratings,
        }


_seed_web_data()
