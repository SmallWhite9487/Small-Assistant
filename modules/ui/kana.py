import tkinter as tk
from tkinter import ttk


class KanaReaderMixin:
    """Split a sentence into speakable parts with kana readings."""

    def show_kana_reader(self) -> None:
        self._clear_content()
        self._heading("Kana reader", "Break Japanese into speakable parts with kana readings.")

        input_panel = tk.Frame(self.content, bg=self.SURFACE, padx=18, pady=16)
        input_panel.pack(fill="x", anchor="n")
        provider_var = self._provider_selector(input_panel, self.SURFACE, (0, 12))
        tk.Label(
            input_panel,
            text="Japanese sentence",
            bg=self.SURFACE,
            fg=self.INK,
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        sentence_input = tk.Text(
            input_panel,
            height=4,
            wrap="word",
            font=("TkDefaultFont", 12),
            undo=True,
            padx=10,
            pady=9,
        )
        sentence_input.pack(fill="x", expand=True)
        actions = tk.Frame(input_panel, bg=self.SURFACE)
        actions.pack(fill="x", pady=(10, 0))

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
        result_header.pack(fill="x", pady=(0, 8))
        tk.Label(
            result_header,
            text="Speakable parts",
            bg=self.SURFACE,
            fg=self.INK,
            font=("TkDefaultFont", 11, "bold"),
        ).pack(side="left")
        copy_button = ttk.Button(result_header, text="Copy full kana", state="disabled")
        copy_button.pack(side="right")
        full_reading = tk.Label(
            result_panel,
            text="",
            bg=self.SURFACE,
            fg=self.GREEN,
            font=("TkDefaultFont", 14, "bold"),
            anchor="w",
            justify="left",
            wraplength=620,
        )
        full_reading.pack(fill="x", pady=(0, 12))

        token_area = tk.Frame(result_panel, bg=self.SURFACE)
        token_area.pack(fill="both", expand=True)
        token_frame = self._scrollable_area(token_area, self.SURFACE)

        def copy_full_reading() -> None:
            reading = full_reading.cget("text")
            if reading:
                self.ui.clipboard_clear()
                self.ui.clipboard_append(reading)
                status.config(text="Kana copied", fg=self.GREEN)

        copy_button.config(command=copy_full_reading)

        def render_segments(segments: list[tuple[str, str]]) -> None:
            for widget in token_frame.winfo_children():
                widget.destroy()
            visible_segments = [
                segment for segment in segments if not segment[0].isspace()
            ]
            for index, (surface, reading) in enumerate(visible_segments):
                row, column = divmod(index, 6)
                token = tk.Frame(token_frame, bg="#edf2ee", padx=8, pady=9)
                token.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)
                tk.Label(
                    token,
                    text=surface,
                    bg="#edf2ee",
                    fg=self.INK,
                    font=("TkDefaultFont", 12, "bold"),
                    wraplength=92,
                    justify="center",
                ).pack(fill="x")
                tk.Label(
                    token,
                    text=reading,
                    bg="#edf2ee",
                    fg=self.GREEN,
                    font=("TkDefaultFont", 10),
                    wraplength=92,
                    justify="center",
                ).pack(fill="x", pady=(4, 0))
            for column in range(6):
                token_frame.columnconfigure(column, weight=1, uniform="kana_tokens")

            kana = "".join(reading for _surface, reading in segments)
            full_reading.config(text=kana)
            copy_button.config(state="normal" if kana else "disabled")
            status.config(
                text=f"AI returned {len(visible_segments)} speakable part(s).",
                fg=self.GREEN,
            )

        def convert_sentence() -> None:
            sentence = sentence_input.get("1.0", "end-1c").strip()
            if not sentence:
                status.config(text="Enter a Japanese sentence first.", fg=self.ERROR)
                sentence_input.focus_set()
                return

            start_button.config(state="disabled")
            copy_button.config(state="disabled")
            full_reading.config(text="")
            status.config(text="Asking the AI to cut the sentence and add kana...", fg=self.MUTED)
            provider = provider_var.get()

            def finish(segments, error) -> None:
                start_button.config(state="normal")
                if error is not None:
                    status.config(text=str(error), fg=self.ERROR)
                    return
                render_segments(segments)

            self._run_in_background(
                lambda: self.ai.reading_segments(sentence, provider), finish
            )

        def insert_example() -> None:
            sentence_input.delete("1.0", "end")
            sentence_input.insert("1.0", "２０２６年3月１２日")
            convert_sentence()

        ttk.Button(actions, text="Use date example", command=insert_example).pack(
            side="left"
        )
        start_button = ttk.Button(
            actions,
            text="Start cutting words",
            style="Accent.TButton",
            command=convert_sentence,
        )
        start_button.pack(side="right")
