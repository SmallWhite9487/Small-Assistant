import random
import tkinter as tk
from datetime import date


class ReviewPageMixin:
    """Flash-card review with a Today / All scope switch.

    Keys: ← / → move, Space or Enter flips the card.
    """

    def show_review(self, all_words: bool | None = None) -> None:
        self._clear_content()
        if not hasattr(self, "review_scope"):
            self.review_scope = tk.IntVar(self.ui, value=0)
            self.review_order = tk.IntVar(self.ui, value=0)
        if all_words is not None:
            self.review_scope.set(1 if all_words else 0)
        self._heading("Review", "Flip through your words, today's or everything you saved.")

        settings = tk.Frame(self.content, bg=self.BACKGROUND)
        settings.pack(fill="x", pady=(0, 12))
        self._segmented(
            settings, "Scope", ("Today", "All"), self.review_scope, self._load_review_scope
        )
        self._segmented(
            settings, "Order", ("Random", "Original"), self.review_order, self._load_review_scope
        )
        self.review_count = tk.Label(
            settings, text="", bg=self.BACKGROUND, fg=self.MUTED, font=self._font(10)
        )
        self.review_count.pack(side="right")

        self.review_progress = tk.Canvas(
            self.content, height=4, bg="#d7e2da", highlightthickness=0
        )
        self.review_progress.pack(fill="x", pady=(0, 12))
        self.review_progress.bind("<Configure>", lambda _e: self._draw_review_progress())

        self.review_body = tk.Frame(self.content, bg=self.BACKGROUND)
        self.review_body.pack(fill="both", expand=True)
        self.ui.bind("<Key>", self._on_review_key)
        self.review_body.bind(
            "<Destroy>",
            lambda e: self.ui.unbind("<Key>") if e.widget is self.review_body else None,
        )
        self._load_review_scope()

    def _load_review_scope(self) -> None:
        for child in self.review_body.winfo_children():
            child.destroy()
        all_words = self.review_scope.get() == 1
        if all_words:
            self.review_words = list(self.words)
        else:
            today = date.today().isoformat()
            self.review_words = [w for w in self.words if w["added_on"] == today]
        if self.review_order.get() == 0:
            random.shuffle(self.review_words)
        self.review_index = 0
        self.review_revealed = False

        if not self.review_words:
            empty = tk.Frame(self.review_body, bg=self.SURFACE, padx=28, pady=32)
            empty.pack(fill="x", anchor="n")
            tk.Label(
                empty,
                text="No words saved yet" if all_words else "No words added today",
                bg=self.SURFACE,
                fg=self.INK,
                font=self._font(16, "bold"),
            ).pack(anchor="w")
            tk.Label(
                empty,
                text="Words you add will appear here for review.",
                bg=self.SURFACE,
                fg=self.MUTED,
            ).pack(anchor="w", pady=(7, 12))
            if not all_words and self.words:
                self._flat_button(
                    empty, "Review all words instead", lambda: self._set_review_scope(1), small=True
                ).pack(anchor="w")
            self.review_count.config(text="")
            self._draw_review_progress()
            return

        nav = tk.Frame(self.review_body, bg=self.BACKGROUND)
        nav.pack(side="bottom", fill="x", pady=(12, 0))
        self._flat_button(nav, "←  Previous", lambda: self._move_review(-1), small=True).pack(
            side="left"
        )
        self._flat_button(nav, "Next  →", lambda: self._move_review(1), accent=True, small=True).pack(
            side="right"
        )

        card = tk.Frame(self.review_body, bg=self.SURFACE, padx=36, pady=32)
        card.pack(fill="both", expand=True)
        self.review_card = card
        card.bind("<Button-1>", lambda _e: self._toggle_reveal())
        self.review_word_label = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.INK, font=self._font(34, "bold")
        )
        self.review_word_label.pack(pady=(12, 18))
        self.review_reading_label = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.GREEN, font=self._font(15)
        )
        self.review_reading_label.pack(pady=4)
        self.review_meaning_label = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.INK, font=self._font(16)
        )
        self.review_meaning_label.pack(pady=4)
        self.review_notes_label = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.MUTED, font=self._font(10), wraplength=600
        )
        self.review_notes_label.pack(pady=(6, 14))
        self.reveal_button = self._flat_button(card, "", self._toggle_reveal)
        self.reveal_button.pack(pady=(6, 4))
        self.review_conjugate_button = self._flat_button(
            card, "⇄  Conjugation", lambda: self.open_conjugation_for(
                self.review_words[self.review_index]["word"]
            ), small=True,
        )
        self._render_review_card()

    def _set_review_scope(self, value: int) -> None:
        self.review_scope.set(value)
        self.show_review()

    def _draw_review_progress(self) -> None:
        canvas = self.review_progress
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        words = getattr(self, "review_words", [])
        if words:
            width = canvas.winfo_width() * (self.review_index + 1) / len(words)
            canvas.create_rectangle(0, 0, width, 4, fill=self.GREEN, outline=self.GREEN)

    def _render_review_card(self) -> None:
        word = self.review_words[self.review_index]
        revealed = self.review_revealed
        self.review_count.config(text=f"{self.review_index + 1} / {len(self.review_words)}")
        self.review_word_label.config(text=word["word"])
        self.review_reading_label.config(text=word["reading"] if revealed else "")
        self.review_meaning_label.config(text=word["meaning"] if revealed else "")
        self.review_notes_label.config(text=word["notes"] if revealed and word["notes"] else "")
        self.reveal_button.config(text="Hide answer  (Space)" if revealed else "Show answer  (Space)")
        self._draw_review_progress()
        if self._conjugation_mode(word["word"]) is None:
            self.review_conjugate_button.pack_forget()
        elif not self.review_conjugate_button.winfo_ismapped():
            self.review_conjugate_button.pack(pady=(4, 0))

    def _toggle_reveal(self) -> None:
        if not self.review_words:
            return
        self.review_revealed = not self.review_revealed
        self._render_review_card()

    def _move_review(self, amount: int) -> None:
        if not self.review_words:
            return
        self.review_index = (self.review_index + amount) % len(self.review_words)
        self.review_revealed = False
        self._render_review_card()

    def _on_review_key(self, event: tk.Event) -> None:
        if not self.review_body.winfo_exists():
            return
        if event.keysym in {"space", "Return"}:
            self._toggle_reveal()
        elif event.keysym == "Right":
            self._move_review(1)
        elif event.keysym == "Left":
            self._move_review(-1)
