from .conjugation import ConjugationMixin
from .form import WordFormMixin
from .home import HomePageMixin
from .composition import CompositionMixin
from .notes import NotesPageMixin
from .review import ReviewPageMixin
from .revision import RevisionPageMixin
from .shell import ShellMixin
from .word_check import WordCheckMixin

__all__ = [
    "HomePageMixin",
    "CompositionMixin",
    "ConjugationMixin",
    "NotesPageMixin",
    "ReviewPageMixin",
    "RevisionPageMixin",
    "ShellMixin",
    "WordCheckMixin",
    "WordFormMixin",
]
