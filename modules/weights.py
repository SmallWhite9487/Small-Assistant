import csv
from pathlib import Path

WEIGHT_FILE = Path(__file__).resolve().parent.parent / "weights.csv"
DEFAULT_WEIGHT = 1.0
NEW_WORD_FACTOR = 1.1
MIN_WEIGHT = 0.1
MAX_WEIGHT = 20.0
CORRECT_FACTOR = 0.8
WRONG_FACTOR = 1.25


class WeightStore:
    """Persists per-word review weights as `uuid,weight` rows."""

    def __init__(self, path: Path = WEIGHT_FILE):
        self.path = path

    def load(self) -> dict[str, float]:
        if not self.path.exists():
            return {}
        weights: dict[str, float] = {}
        with self.path.open("r", newline="", encoding="utf-8") as file:
            for row in csv.reader(file):
                if len(row) < 2 or row[0] == "uuid":
                    continue
                try:
                    weights[row[0]] = float(row[1])
                except ValueError:
                    continue
        return weights

    def save(self, weights: dict[str, float]) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(("uuid", "weight"))
            for word_id, weight in weights.items():
                writer.writerow((word_id, f"{weight:.6f}"))

    def sync(self, weights: dict[str, float], word_ids: list[str]) -> bool:
        """Drop weights of deleted words and give new words 110% of the average.

        Returns True when the mapping changed.
        """
        changed = False
        valid = set(word_ids)
        for word_id in [key for key in weights if key not in valid]:
            del weights[word_id]
            changed = True
        missing = [word_id for word_id in word_ids if word_id not in weights]
        if missing:
            average = sum(weights.values()) / len(weights) if weights else DEFAULT_WEIGHT
            initial = min(MAX_WEIGHT, max(MIN_WEIGHT, average * NEW_WORD_FACTOR))
            for word_id in missing:
                weights[word_id] = initial
            changed = True
        return changed

    @staticmethod
    def adjusted(weight: float, correct: bool) -> float:
        factor = CORRECT_FACTOR if correct else WRONG_FACTOR
        return min(MAX_WEIGHT, max(MIN_WEIGHT, weight * factor))
