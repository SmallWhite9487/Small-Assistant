import tkinter as tk
from tkinter import ttk


class GrammarCheckMixin:
    """Grammar correction page."""

    def show_grammar_check(self) -> None:
        self._clear_content()
        self._heading("Grammar check", "Get a natural correction in the same language.")

        input_panel = tk.Frame(self.content, bg=self.SURFACE, padx=18, pady=16)
        input_panel.pack(fill="x", anchor="n")
        provider_var = self._provider_selector(input_panel, self.SURFACE, (0, 12))
        tk.Label(
            input_panel,
            text="Sentence",
            bg=self.SURFACE,
            fg=self.INK,
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w", pady=(0, 9))
        sentence_input = tk.Text(
            input_panel,
            height=5,
            wrap="word",
            font=("TkDefaultFont", 11),
            undo=True,
            padx=10,
            pady=9,
        )
        sentence_input.pack(fill="x", expand=True)

        status = tk.Label(
            self.content,
            text="",
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("TkDefaultFont", 9),
        )
        status.pack(anchor="w", pady=(7, 6))

        result_panel = tk.Frame(self.content, bg=self.SURFACE, padx=18, pady=16)
        result_panel.pack(fill="both", expand=True)
        result_header = tk.Frame(result_panel, bg=self.SURFACE)
        result_header.pack(fill="x", pady=(0, 9))
        tk.Label(
            result_header,
            text="Corrected sentence",
            bg=self.SURFACE,
            fg=self.INK,
            font=("TkDefaultFont", 11, "bold"),
        ).pack(side="left")
        result = tk.Text(
            result_panel,
            height=5,
            wrap="word",
            font=("TkDefaultFont", 12),
            padx=10,
            pady=9,
            state="disabled",
        )
        result.pack(fill="both", expand=True)

        def copy_correction() -> None:
            correction = result.get("1.0", "end-1c").strip()
            if correction:
                self.ui.clipboard_clear()
                self.ui.clipboard_append(correction)
                status.config(text="Correction copied")

        copy_button = ttk.Button(
            result_header, text="Copy", command=copy_correction, state="disabled"
        )
        copy_button.pack(side="right")

        def check_sentence() -> None:
            sentence = sentence_input.get("1.0", "end-1c").strip()
            if not sentence:
                status.config(text="Enter a sentence to check.", fg=self.ERROR)
                sentence_input.focus_set()
                return

            check_button.config(state="disabled")
            copy_button.config(state="disabled")
            status.config(text="Checking...", fg=self.MUTED)
            result.config(state="normal")
            result.delete("1.0", "end")
            result.config(state="disabled")
            provider = provider_var.get()

            def finish(feedback, error) -> None:
                if error is not None:
                    feedback = str(error)
                result.config(state="normal")
                result.insert("1.0", feedback)
                result.config(state="disabled")
                status.config(
                    text="Correction ready" if error is None else feedback,
                    fg=self.GREEN if error is None else self.ERROR,
                )
                check_button.config(state="normal")
                copy_button.config(state="normal" if error is None else "disabled")

            self._run_in_background(
                lambda: self.ai.grammar_feedback(sentence, provider), finish
            )

        actions = tk.Frame(self.content, bg=self.BACKGROUND)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(
            actions,
            text="Clear",
            command=lambda: (sentence_input.delete("1.0", "end"), sentence_input.focus_set()),
        ).pack(side="left")
        check_button = ttk.Button(
            actions,
            text="Check sentence",
            style="Accent.TButton",
            command=check_sentence,
        )
        check_button.pack(side="right")
