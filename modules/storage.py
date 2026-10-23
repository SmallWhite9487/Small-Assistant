import csv
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "words.csv"
CSV_FIELDS = ("id", "word", "reading", "meaning", "notes", "check_ai", "added_on")


class VocabularyStore:
    def __init__(self, path: Path = DATA_FILE):
        self.path = path

    def load(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []

        with self.path.open("r", newline="", encoding="utf-8") as file:
            rows = csv.DictReader(file)
            words = []
            for row in rows:
                if not (row.get("word") or "").strip():
                    continue
                word = {field: row.get(field, "") or "" for field in CSV_FIELDS}
                word["check_ai"] = (
                    "False"
                    if word["check_ai"].strip().casefold() in {"false", "0", "no"}
                    else "True"
                )
                words.append(word)
            return words

    def save(self, words: list[dict[str, str]]) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(words)
