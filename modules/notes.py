import re
from datetime import date
from pathlib import Path

NOTES_DIR = Path(__file__).resolve().parent.parent / "Notes"
_DATE_SUFFIX = re.compile(r"^(?P<title>.*)_(?P<date>\d{4}-\d{2}-\d{2})$")


class NoteStore:
    """Stores each note as Notes/<title>_<date>.txt."""

    def __init__(self, directory: Path = NOTES_DIR) -> None:
        self.directory = directory

    @staticmethod
    def _safe_title(title: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", title.strip()).strip(". ")
        return cleaned[:100]

    def list_notes(self) -> list[dict[str, str]]:
        """Return notes as {'name', 'title', 'date'}, newest first."""
        if not self.directory.is_dir():
            return []
        notes = []
        for path in self.directory.glob("*.txt"):
            match = _DATE_SUFFIX.match(path.stem)
            title, day = (match["title"], match["date"]) if match else (path.stem, "")
            notes.append({"name": path.name, "title": title, "date": day})
        return sorted(notes, key=lambda n: (n["date"], n["title"]), reverse=True)

    def read(self, name: str) -> str:
        return (self.directory / name).read_text(encoding="utf-8")

    def save(self, title: str, content: str, old_name: str | None = None) -> str:
        """Save a note and return its file name.

        A renamed note moves to a new file; an existing note keeps its date.
        """
        safe = self._safe_title(title)
        if not safe:
            raise ValueError("Please enter a title for the note.")
        day = date.today().isoformat()
        if old_name:
            match = _DATE_SUFFIX.match(Path(old_name).stem)
            if match:
                day = match["date"]
        name = f"{safe}_{day}.txt"
        if name != old_name and (self.directory / name).exists():
            raise ValueError("A note with this title and date already exists.")
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / name).write_text(content, encoding="utf-8")
        if old_name and old_name != name:
            (self.directory / old_name).unlink(missing_ok=True)
        return name

    def delete(self, name: str) -> None:
        (self.directory / name).unlink(missing_ok=True)
