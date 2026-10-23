import csv
import tkinter as tk
from tkinter import messagebox, ttk

FIELDS = ("word", "reading", "meaning")


class WordCheckMixin:
    """AI check of flagged words, with per-word and apply-all corrections."""

    def show_word_check(self) -> None:
        self._clear_content()
        queued_words = [word for word in self.words if word["check_ai"] == "True"]
        self._heading(
            "Check word information",
            "Check kanji, kana reading, and meaning for words marked True.",
        )

        provider_var = self._provider_selector(self.content, self.BACKGROUND, (0, 10))

        count_text = (
            f"{len(queued_words)} word(s) marked True and ready to check."
            if queued_words
            else "No words are marked True. Toggle AI CHECK in the word list or edit a word to include it."
        )
        tk.Label(
            self.content,
            text=count_text,
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("TkDefaultFont", 9),
        ).pack(anchor="w", pady=(0, 6))

        status = tk.Label(
            self.content,
            text="",
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("TkDefaultFont", 9),
            wraplength=650,
            justify="left",
        )
        status.pack(anchor="w", pady=(0, 8))

        results_frame = tk.Frame(self.content, bg=self.BACKGROUND)
        results_frame.pack(fill="both", expand=True)
        result_list = self._scrollable_area(results_frame, self.BACKGROUND)
        canvas = result_list.canvas

        for word in queued_words:
            tk.Label(
                result_list,
                text=f"{word['word']}    {word['reading']}    {word['meaning']}",
                bg=self.SURFACE,
                fg=self.INK,
                anchor="w",
                padx=12,
                pady=8,
                wraplength=610,
                justify="left",
            ).pack(fill="x", pady=(0, 4))

        pending: list[tuple[dict[str, str], dict[str, str], ttk.Button]] = []

        def unapplied() -> list[tuple[dict[str, str], dict[str, str], ttk.Button]]:
            return [
                item
                for item in pending
                if item[2].winfo_exists() and str(item[2].cget("state")) != "disabled"
            ]

        def commit(changes) -> bool:
            """Apply and save changes together; roll back all if saving fails."""
            previous = [(target, {key: target[key] for key in FIELDS}) for target, _p, _b in changes]
            for target, proposed, _button in changes:
                for key in FIELDS:
                    target[key] = proposed[key]
            try:
                self.store.save(self.words)
            except (OSError, csv.Error) as error:
                for target, old in previous:
                    target.update(old)
                messagebox.showerror("Could not save corrections", str(error), parent=self.ui)
                return False
            for _target, _proposed, button in changes:
                button.config(text="Applied", state="disabled")
            if not unapplied():
                apply_all_button.config(state="disabled")
            return True

        def apply_all() -> None:
            changes = unapplied()
            if changes and commit(changes):
                status.config(text=f"Applied {len(changes)} correction(s).", fg=self.GREEN)

        def render_suggestions(suggestions: list[dict[str, str]]) -> None:
            pending.clear()
            for widget in result_list.winfo_children():
                widget.destroy()
            canvas.yview_moveto(0)

            for suggestion in suggestions:
                word = next(item for item in self.words if item["id"] == suggestion["id"])
                card = tk.Frame(result_list, bg=self.SURFACE, padx=14, pady=12)
                card.pack(fill="x", pady=(0, 8))
                tk.Label(
                    card,
                    text=word["word"],
                    bg=self.SURFACE,
                    fg=self.INK,
                    font=("TkDefaultFont", 13, "bold"),
                ).pack(anchor="w")

                changed = False
                for key, label in (
                    ("word", "Kanji / kana"),
                    ("reading", "Reading"),
                    ("meaning", "Meaning"),
                ):
                    before = word[key] or "(empty)"
                    after = suggestion[key] or "(empty)"
                    if word[key] != suggestion[key]:
                        changed = True
                        text = f"{label}: {before} -> {after}"
                    else:
                        text = f"{label}: {before}"
                    tk.Label(
                        card,
                        text=text,
                        bg=self.SURFACE,
                        fg=self.INK,
                        anchor="w",
                        justify="left",
                        wraplength=600,
                    ).pack(fill="x", pady=(3, 0))

                if suggestion["reason"]:
                    tk.Label(
                        card,
                        text=suggestion["reason"],
                        bg=self.SURFACE,
                        fg=self.MUTED,
                        anchor="w",
                        justify="left",
                        wraplength=600,
                    ).pack(fill="x", pady=(6, 0))

                apply_button = ttk.Button(
                    card,
                    text="Apply corrections" if changed else "No changes needed",
                    state="normal" if changed else "disabled",
                )
                apply_button.pack(anchor="e", pady=(8, 0))
                if changed:
                    entry = (word, suggestion, apply_button)
                    apply_button.config(command=lambda entry=entry: commit([entry]))
                    pending.append(entry)

            apply_all_button.config(state="normal" if pending else "disabled")

        def check_flagged_words() -> None:
            if not queued_words:
                return
            check_button.config(state="disabled")
            apply_all_button.config(state="disabled")
            status.config(text=f"Checking {len(queued_words)} word(s)...", fg=self.MUTED)
            words_to_check = [dict(word) for word in queued_words]
            provider = provider_var.get()

            def finish(suggestions, error) -> None:
                if error is not None:
                    status.config(text=str(error), fg=self.ERROR)
                    check_button.config(state="normal")
                    return

                for word in queued_words:
                    word["check_ai"] = "False"
                try:
                    self.store.save(self.words)
                except (OSError, csv.Error) as save_error:
                    for word in queued_words:
                        word["check_ai"] = "True"
                    status.config(text=str(save_error), fg=self.ERROR)
                    check_button.config(state="normal")
                    return

                status.config(
                    text=(
                        f"Checked {len(queued_words)} word(s). Their AI CHECK flags "
                        "are now False. Apply any suggested corrections below."
                    ),
                    fg=self.GREEN,
                )
                render_suggestions(suggestions)

            self._run_in_background(
                lambda: self.ai.word_suggestions(words_to_check, provider), finish
            )

        actions = tk.Frame(self.content, bg=self.BACKGROUND)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Back to words", command=self.show_home).pack(side="left")
        check_button = ttk.Button(
            actions,
            text="Check flagged words",
            style="Accent.TButton",
            command=check_flagged_words,
            state="normal" if queued_words else "disabled",
        )
        check_button.pack(side="right")
        apply_all_button = ttk.Button(
            actions,
            text="Apply all AI changes",
            command=apply_all,
            state="disabled",
        )
        apply_all_button.pack(side="right", padx=(0, 8))
