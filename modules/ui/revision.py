import random
import unicodedata
import tkinter as tk
from tkinter import messagebox

from ..weights import WeightStore


class RevisionPageMixin:
    """Weighted multiple-choice review: wrong answers make a word appear more often.

    Keys: 1-4 answer, T tip, Space/Enter next.
    """

    CHOICE_COUNT = 4
    AUTO_ADVANCE_MS = 700
    RIGHT_BG = "#bfe3cd"
    WRONG_BG = "#f0c4be"

    def show_revision_all(self) -> None:
        self._clear_content()
        self.weight_store = getattr(self, "weight_store", None) or WeightStore()
        try:
            self.weights = self.weight_store.load()
            if self.weight_store.sync(self.weights, [w["id"] for w in self.words]):
                self.weight_store.save(self.weights)
        except OSError as error:
            self.weights = {w["id"]: 1.0 for w in self.words}
            messagebox.showerror("Could not load weights", str(error), parent=self.ui)

        self.revision_mode = tk.IntVar(self.ui, value=0)
        self.revision_target = tk.IntVar(self.ui, value=0)
        self.revision_input = tk.IntVar(self.ui, value=0)
        self.revision_entry = None
        self.revision_undo = None
        self.revision_stats = {"answered": 0, "correct": 0, "streak": 0}
        self.revision_token = 0
        self.revision_word = None
        self.revision_choice_buttons = []

        self._heading("Revision all", "Pick or type the right answer. Words you miss come back more often.")

        if len(self.words) < 2:
            tk.Label(
                self.content,
                text="Add at least two words to use Revision all.",
                bg=self.BACKGROUND,
                fg=self.MUTED,
            ).pack(anchor="w")
            return

        settings = tk.Frame(self.content, bg=self.BACKGROUND)
        settings.pack(fill="x", pady=(0, 12))
        self.revision_show_control = self._segmented(
            settings, "Show", ("原文", "読み"), self.revision_mode, self._render_revision_prompt
        )
        self.revision_guess_control = self._segmented(
            settings, "Guess", ("意思", "原文"), self.revision_target, self._retarget_revision
        )
        self._segmented(
            settings, "Answer", ("選項", "輸入"), self.revision_input, self._retarget_revision
        )
        self.revision_stats_label = tk.Label(
            settings, text="", bg=self.BACKGROUND, fg=self.MUTED, font=self._font(10)
        )
        self.revision_stats_label.pack(side="right")

        footer = tk.Frame(self.content, bg=self.BACKGROUND)
        footer.pack(side="bottom", fill="x", pady=(12, 0))
        self.revision_weight_label = tk.Label(
            footer, text="", bg=self.BACKGROUND, fg=self.MUTED, font=self._font(9)
        )
        self.revision_weight_label.pack(side="left")
        reset = self._flat_button(footer, "Reset weights", self._reset_revision_weights, small=True)
        reset.pack(side="right")

        self.revision_card = tk.Frame(self.content, bg=self.SURFACE, padx=36, pady=28)
        self.revision_card.pack(fill="both", expand=True)
        card = self.revision_card
        self.revision_prompt = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.INK, font=self._font(34, "bold")
        )
        self.revision_prompt.pack(pady=(4, 2))
        self.revision_tip_label = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.GREEN, font=self._font(15), wraplength=600
        )
        self.revision_tip_label.pack(pady=(0, 2))
        self.revision_tip_button = self._flat_button(card, "Tip  (T)", self._revision_tip, small=True)
        self.revision_tip_button.pack(pady=(6, 0))

        self.revision_buttons_frame = tk.Frame(card, bg=self.SURFACE)
        self.revision_buttons_frame.pack(fill="x", pady=(30, 0))
        self.revision_buttons_frame.columnconfigure(0, weight=1, uniform="choice")
        self.revision_buttons_frame.columnconfigure(1, weight=1, uniform="choice")

        self.revision_feedback = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.MUTED, wraplength=600, font=self._font(11)
        )
        self.revision_feedback.pack(pady=(16, 6))
        self.revision_actions = tk.Frame(card, bg=self.SURFACE)
        self.revision_override = self._flat_button(
            self.revision_actions, "I was right", self._override_revision, small=True
        )
        self.revision_next = self._flat_button(
            self.revision_actions, "Next  (Space)", self._next_revision_question, accent=True
        )
        self.revision_next.pack(side="left")

        self.ui.bind("<Key>", self._on_revision_key)
        card.bind("<Destroy>", lambda e: self.ui.unbind("<Key>") if e.widget is card else None)
        self._next_revision_question()

    # ---- state ---------------------------------------------------------

    def _answer_field(self) -> str:
        if self.revision_input.get() == 1:
            return "reading"
        return "word" if self.revision_target.get() == 1 else "meaning"

    def _expected_answer(self, word: dict[str, str]) -> str:
        field = self._answer_field()
        return word[field] or word["word"]

    @staticmethod
    def _normalize_kana(text: str) -> str:
        """Fold width and katakana to hiragana so both scripts count as the same answer."""
        text = unicodedata.normalize("NFKC", text).strip()
        return "".join(
            chr(ord(char) - 0x60) if "\u30a1" <= char <= "\u30f6" else char
            for char in text
        )

    def _key_hint(self) -> str:
        return "" if self.revision_input.get() == 1 else "  (T)"

    def _update_revision_status(self) -> None:
        stats = self.revision_stats
        accuracy = f"{stats['correct'] * 100 // stats['answered']}%" if stats["answered"] else "–"
        self.revision_stats_label.config(
            text=f"{stats['answered']} answered  ·  {accuracy}  ·  streak {stats['streak']}"
        )
        if self.revision_word:
            weight = self.weights.get(self.revision_word["id"], 1.0)
            self.revision_weight_label.config(text=f"Word weight {weight:.2f}")

    def _retarget_revision(self) -> None:
        typing = self.revision_input.get() == 1
        self._set_segmented_enabled(
            self.revision_show_control, self.revision_target.get() == 0 and not typing
        )
        self._set_segmented_enabled(self.revision_guess_control, not typing)
        if self.revision_word:
            self._next_revision_question(keep_word=True)

    def _pick_weighted_word(self) -> dict[str, str]:
        previous = self.revision_word
        pool = [w for w in self.words if not previous or w["id"] != previous["id"]]
        weights = [max(self.weights.get(w["id"], 1.0), 0.0001) for w in pool]
        return random.choices(pool, weights=weights, k=1)[0]

    def _next_revision_question(self, keep_word: bool = False) -> None:
        if not self.revision_card.winfo_exists():
            return
        self.revision_token += 1
        word = self.revision_word if keep_word and self.revision_word else self._pick_weighted_word()
        field = self._answer_field()
        self.revision_word = word
        self.revision_answered = False
        self.revision_tips = 0
        self.revision_tip_label.config(text="")
        self.revision_tip_button.config(text=f"Tip{self._key_hint()}")
        self._set_enabled(self.revision_tip_button, True)
        self.revision_undo = None
        self.revision_override.pack_forget()

        for child in self.revision_buttons_frame.winfo_children():
            child.destroy()
        self.revision_choice_buttons = []
        self.revision_entry = None
        if self.revision_input.get() == 1:
            self._build_revision_input()
        else:
            seen = {word[field]}
            distractors = []
            others = [w for w in self.words if w["id"] != word["id"]]
            random.shuffle(others)
            for other in others:
                if other[field] not in seen:
                    seen.add(other[field])
                    distractors.append(other[field])
                if len(distractors) == self.CHOICE_COUNT - 1:
                    break
            options = distractors + [word[field]]
            random.shuffle(options)

            for index, option in enumerate(options):
                button = self._flat_button(
                    self.revision_buttons_frame,
                    f"{index + 1}   {option}",
                    lambda o=option: self._answer_revision(o),
                )
                button.config(wraplength=250)
                button.option = option
                button.grid(row=index // 2, column=index % 2, sticky="ew", padx=6, pady=6)
                self.revision_choice_buttons.append(button)
        self.revision_feedback.config(text="")
        self.revision_actions.pack_forget()
        self._render_revision_prompt()
        self._update_revision_status()

    def _build_revision_input(self) -> None:
        frame = self.revision_buttons_frame
        row = tk.Frame(frame, bg=self.SURFACE)
        row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=6)
        entry = tk.Entry(
            row,
            font=self._font(16),
            relief="flat",
            bg=self.TILE,
            fg=self.INK,
            insertbackground=self.INK,
            highlightthickness=2,
            highlightbackground="#d7e2da",
            highlightcolor=self.GREEN,
            disabledbackground=self.TILE,
            disabledforeground=self.INK,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=8)
        entry.bind("<Return>", lambda _e: self._submit_revision_input())
        self._flat_button(
            row, "Check  (Enter)", self._submit_revision_input, accent=True, small=True
        ).pack(side="left", padx=(10, 0))
        self.revision_entry = entry
        entry.focus_set()

    def _submit_revision_input(self) -> None:
        entry = self.revision_entry
        if self.revision_answered or entry is None or not entry.winfo_exists():
            return
        typed = entry.get().strip()
        if typed:
            self._answer_revision(typed)

    def _override_revision(self) -> None:
        """The user says their typed answer was right: redo the weight and stats as a hit."""
        if not self.revision_undo or not self.revision_answered:
            return
        previous_weight, previous_streak = self.revision_undo
        self.revision_undo = None
        word = self.revision_word
        stats = self.revision_stats
        stats["correct"] += 1
        stats["streak"] = previous_streak + 1
        self.weights[word["id"]] = WeightStore.adjusted(previous_weight, True)
        try:
            self.weight_store.save(self.weights)
        except OSError as error:
            messagebox.showerror("Could not save weights", str(error), parent=self.ui)
        self._update_revision_status()
        self.revision_actions.pack_forget()
        self.revision_feedback.config(
            text=f"Marked as correct.  {word['word']}（{word['reading']}） = {word['meaning']}",
            fg=self.GREEN,
        )
        token = self.revision_token
        self.ui.after(self.AUTO_ADVANCE_MS, lambda: self._auto_advance(token))

    def _render_revision_prompt(self) -> None:
        word = self.revision_word
        if not word or not self.revision_prompt.winfo_exists():
            return
        text = word["word"]
        if self.revision_input.get() == 0 and (
            self.revision_mode.get() == 1 or self.revision_target.get() == 1
        ):
            text = word["reading"] or word["word"]
        self.revision_prompt.config(text=text)

    def _revision_tip(self) -> None:
        if self.revision_answered or self.revision_tips >= 2:
            return
        word = self.revision_word
        self.revision_tips += 1
        typing = self.revision_input.get() == 1
        guessing_word = self.revision_target.get() == 1 and not typing
        if self.revision_tips == 1:
            if typing:
                text = word["meaning"]
            elif guessing_word:
                text = word["meaning"]
            elif self.revision_mode.get() == 1:
                text = word["word"]
            else:
                text = word["reading"] or word["word"]
            self.revision_tip_label.config(text=text)
            self.revision_tip_button.config(
                text=f"More tip: {'reading' if typing else 'original' if guessing_word else 'meaning'}{self._key_hint()}"
            )
        else:
            if typing:
                extra = self._expected_answer(word)
            else:
                extra = word["word"] if guessing_word else word["meaning"]
            self.revision_tip_label.config(
                text=f"{self.revision_tip_label.cget('text')}  =  {extra}"
            )
            self.revision_tip_button.config(text=f"Tip{self._key_hint()}")
            self._set_enabled(self.revision_tip_button, False)

    def _answer_revision(self, chosen: str) -> None:
        if self.revision_answered:
            return
        self.revision_answered = True
        word = self.revision_word
        field = self._answer_field()
        if self.revision_entry is not None:
            correct = self._normalize_kana(chosen) == self._normalize_kana(
                self._expected_answer(word)
            )
        else:
            correct = chosen == word[field]
        counted_correct = correct and self.revision_tips < 2
        self._set_enabled(self.revision_tip_button, False)
        typed_mode = self.revision_entry is not None
        if typed_mode:
            self.revision_entry.config(state="disabled")
            self.revision_card.focus_set()

        for button in self.revision_choice_buttons:
            if button.option == word[field]:
                button.config(bg=self.RIGHT_BG)
            elif button.option == chosen:
                button.config(bg=self.WRONG_BG)
            button.enabled = False
            button.config(cursor="arrow")

        stats = self.revision_stats
        self.revision_undo = (self.weights.get(word["id"], 1.0), stats["streak"])
        stats["answered"] += 1
        stats["correct"] += int(counted_correct)
        stats["streak"] = stats["streak"] + 1 if counted_correct else 0
        self.weights[word["id"]] = WeightStore.adjusted(
            self.weights.get(word["id"], 1.0), counted_correct
        )
        try:
            self.weight_store.save(self.weights)
        except OSError as error:
            messagebox.showerror("Could not save weights", str(error), parent=self.ui)
        self._update_revision_status()

        if counted_correct:
            token = self.revision_token
            self.ui.after(self.AUTO_ADVANCE_MS, lambda: self._auto_advance(token))
            return
        prefix = "Correct, but tips were used.  " if correct else "Not quite.  "
        if typed_mode and not correct:
            prefix += f"You typed: {chosen}\n"
        self.revision_feedback.config(
            text=f"{prefix}{word['word']}（{word['reading']}） = {word['meaning']}",
            fg=self.ERROR,
        )
        if typed_mode and not correct and self.revision_tips < 2:
            self.revision_override.pack(side="left", padx=(0, 10), before=self.revision_next)
        else:
            self.revision_override.pack_forget()
        self.revision_actions.pack(pady=(6, 0))

    def _auto_advance(self, token: int) -> None:
        if token == self.revision_token:
            self._next_revision_question()

    def _on_revision_key(self, event: tk.Event) -> None:
        if not self.revision_card.winfo_exists():
            return
        if event.widget is self.revision_entry:
            return
        typing = self.revision_input.get() == 1
        if typing and not self.revision_answered:
            return
        if not typing and event.char and event.char in "1234":
            index = int(event.char) - 1
            if index < len(self.revision_choice_buttons):
                self.revision_choice_buttons[index].command()
        elif event.char.lower() == "t":
            self._revision_tip()
        elif event.keysym in {"space", "Return", "Right"}:
            if self.revision_answered and self.revision_next.winfo_ismapped():
                self._next_revision_question()

    # ---- weights -------------------------------------------------------

    def _reset_revision_weights(self) -> None:
        if not messagebox.askyesno(
            "Reset weights", "Reset every word's weight to 1?", parent=self.ui
        ):
            return
        if not messagebox.askyesno(
            "Reset weights",
            "This cannot be undone. Really reset all weights?",
            icon="warning",
            parent=self.ui,
        ):
            return
        self.weights = {w["id"]: 1.0 for w in self.words}
        try:
            self.weight_store.save(self.weights)
        except OSError as error:
            messagebox.showerror("Could not save weights", str(error), parent=self.ui)
            return
        self._update_revision_status()
        messagebox.showinfo("Reset weights", "All weights are back to 1.", parent=self.ui)
