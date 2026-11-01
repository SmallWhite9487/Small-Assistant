import csv
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parent.parent
for path in (str(ROOT), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from dotenv import load_dotenv  # noqa: E402

from modules.ai_service import AIService  # noqa: E402
from modules.notes import NoteStore  # noqa: E402
from modules.storage import VocabularyStore  # noqa: E402
from ui import (  # noqa: E402
    HomePageMixin,
    CompositionMixin,
    ConjugationMixin,
    NotesPageMixin,
    ReviewPageMixin,
    RevisionPageMixin,
    ShellMixin,
    WordCheckMixin,
    WordFormMixin,
)


class SmallAssistant(
    ShellMixin,
    HomePageMixin,
    WordFormMixin,
    ReviewPageMixin,
    RevisionPageMixin,
    NotesPageMixin,
    CompositionMixin,
    ConjugationMixin,
    WordCheckMixin,
):
    """Main process: owns the window, the word data, storage and the AI service.

    Each page lives in its own module under modules/ui and is mixed in here.
    """

    def __init__(self):
        load_dotenv(dotenv_path=ROOT / ".env")
        self.ui = tk.Tk()
        self.ui.title("スモー助手 | Small-Assistant")
        self.ui.geometry("960x650")
        self.ui.minsize(760, 520)
        self.ui.configure(bg=self.BACKGROUND)
        self.store = VocabularyStore()
        self.ai = AIService()
        self.notes = NoteStore()
        self._page_generation = 0

        try:
            self.words = self.store.load()
        except (OSError, csv.Error, UnicodeError) as error:
            self.words = []
            messagebox.showerror("Could not load words", str(error), parent=self.ui)

        self._build_shell()
        self.show_home()

    def run(self) -> None:
        self.ui.mainloop()


if __name__ == "__main__":
    SmallAssistant().run()