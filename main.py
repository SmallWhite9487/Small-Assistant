import csv
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from dotenv import load_dotenv

from modules.ai_service import AIService
from modules.notes import NoteStore
from modules.storage import VocabularyStore
from modules.ui import (
    HomePageMixin,
    CompositionMixin,
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
    WordCheckMixin,
):
    """Main process: owns the window, the word data, storage and the AI service.

    Each page lives in its own module under modules/ui and is mixed in here.
    """

    def __init__(self):
        load_dotenv(dotenv_path=Path(__file__).with_name(".env"))
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