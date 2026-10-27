import random
import tkinter as tk
from tkinter import ttk


class CompositionMixin:
    """Write a composition using randomly drawn vocabulary, then get AI marking."""

    @staticmethod
    def _word_used(word: str, text: str) -> bool:
        """Accept inflected forms by also matching the word without its last kana."""
        if word in text:
            return True
        last = word[-1]
        is_kana = "\u3040" <= last <= "\u30ff"
        return is_kana and len(word) > 1 and word[:-1] in text

    def _card(self, parent, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg=self.SURFACE, padx=20, pady=16)
        card.pack(fill="x", pady=(0, 14))
        tk.Label(
            card, text=title.upper(), bg=self.SURFACE, fg=self.MUTED,
            font=self._font(9, "bold"),
        ).pack(anchor="w", pady=(0, 10))
        return card

    @staticmethod
    def _flow_chips(container: tk.Frame, chips: list[tk.Widget]) -> None:
        """Lay chips out left to right, wrapping to the container's width."""

        def layout(_event=None) -> None:
            width = container.winfo_width()
            row = column = x = 0
            for chip in chips:
                need = chip.winfo_reqwidth() + 10
                if x and x + need > width:
                    row, column, x = row + 1, 0, 0
                chip.grid(row=row, column=column, padx=(0, 8), pady=(0, 8), sticky="w")
                column += 1
                x += need

        container.bind("<Configure>", layout)
        container.after_idle(layout)

    def show_composition(self) -> None:
        self._clear_content()
        self._heading(
            "Composition",
            "Write using every random word, then let the AI correct and review it.",
        )
        body = self._scrollable_area(self.content, self.BACKGROUND)

        count_var = tk.IntVar(self.ui, value=0)
        drawn: list[dict[str, str]] = []

        words_card = self._card(body, "Your words")
        controls = tk.Frame(words_card, bg=self.SURFACE)
        controls.pack(fill="x", pady=(0, 12))
        chip_area = tk.Frame(words_card, bg=self.SURFACE, height=44)
        chip_area.pack(fill="x")
        placeholder = tk.Label(
            chip_area, text="Press “Draw words” to get started. Click a word to swap it.",
            bg=self.SURFACE, fg=self.MUTED, font=self._font(11),
        )
        placeholder.grid(row=0, column=0, sticky="w")
        chip_widgets: list[tk.Widget] = []

        write_card = self._card(body, "Your composition")
        composition_input = tk.Text(
            write_card, height=7, wrap="word", font=self._font(13), undo=True,
            padx=12, pady=10, relief="flat", bg=self.TILE, fg=self.INK,
            highlightthickness=1, highlightbackground="#d7e2da", highlightcolor=self.GREEN,
            insertbackground=self.INK,
        )
        composition_input.pack(fill="x")

        footer = tk.Frame(write_card, bg=self.SURFACE)
        footer.pack(fill="x", pady=(12, 0))
        provider_var = self._provider_selector(footer, self.SURFACE, (0, 0))
        provider_var_row = footer.winfo_children()[0]
        provider_var_row.pack_configure(side="left", fill="none")
        submit_button = ttk.Button(
            footer, text="Submit for marking", style="Accent.TButton",
            command=lambda: submit(),
        )
        submit_button.pack(side="right")

        status = tk.Label(
            body, text="", bg=self.BACKGROUND, fg=self.MUTED, font=self._font(10),
            justify="left", anchor="w",
        )
        status.pack(fill="x", pady=(0, 10))
        status.bind("<Configure>", lambda e: status.config(wraplength=max(e.width - 4, 100)))

        result_card = self._card(body, "Feedback")
        result = tk.Text(
            result_card, height=10, wrap="word", font=self._font(12), padx=12, pady=10,
            relief="flat", bg=self.TILE, fg=self.INK, highlightthickness=0, state="disabled",
        )
        result.pack(fill="x")
        result.tag_configure("title", font=self._font(11, "bold"), foreground=self.GREEN)

        def clear_result() -> None:
            result.config(state="normal")
            result.delete("1.0", "end")
            result.config(state="disabled")

        def replace_word(index: int) -> None:
            used = {item["id"] for item in drawn}
            pool = [item for item in self.words if item["id"] not in used]
            if not pool:
                status.config(text="No other saved words to swap in.", fg=self.ERROR)
                return
            drawn[index] = random.choice(pool)
            render_chips()
            status.config(text="", fg=self.MUTED)

        def render_chips() -> None:
            for chip in chip_widgets:
                chip.destroy()
            chip_widgets.clear()
            placeholder.grid_forget()
            for index, item in enumerate(drawn):
                label = item["word"]
                if item.get("reading") and item["reading"] != item["word"]:
                    label += f"  {item['reading']}"
                chip = tk.Label(
                    chip_area, text=label, bg="#dcebe2", fg=self.GREEN, cursor="hand2",
                    font=self._font(12, "bold"), padx=12, pady=6,
                )
                chip.bind("<Button-1>", lambda _e, i=index: replace_word(i))
                chip.bind("<Enter>", lambda _e, c=chip: c.config(bg="#c9e0d3"))
                chip.bind("<Leave>", lambda _e, c=chip: c.config(bg="#dcebe2"))
                chip_widgets.append(chip)
            self._flow_chips(chip_area, chip_widgets)

        def draw_words() -> None:
            count = 5 if count_var.get() == 0 else 10
            if len(self.words) < count:
                status.config(
                    text=f"You need at least {count} saved words (you have {len(self.words)}).",
                    fg=self.ERROR,
                )
                return
            drawn[:] = random.sample(self.words, count)
            render_chips()
            composition_input.delete("1.0", "end")
            clear_result()
            status.config(text="", fg=self.MUTED)
            composition_input.focus_set()

        self._segmented(controls, "Words", ["5", "10"], count_var, lambda: None)
        ttk.Button(controls, text="⟳  Draw words", command=draw_words).pack(side="left")
        for segmented_child in controls.winfo_children():
            self._restyle_background(segmented_child, self.SURFACE)

        def submit() -> None:
            if not drawn:
                status.config(text="Draw words first.", fg=self.ERROR)
                return
            text = composition_input.get("1.0", "end-1c").strip()
            missing = [item["word"] for item in drawn if not self._word_used(item["word"], text)]
            if missing:
                status.config(text="Not used yet: " + "、".join(missing), fg=self.ERROR)
                return

            submit_button.config(state="disabled")
            status.config(text="Marking...", fg=self.MUTED)
            clear_result()
            words = [item["word"] for item in drawn]
            provider = provider_var.get()

            def finish(feedback, error) -> None:
                submit_button.config(state="normal")
                if error is not None:
                    status.config(text=str(error), fg=self.ERROR)
                    return
                result.config(state="normal")
                result.insert("end", "Corrected\n", "title")
                result.insert("end", feedback["corrected"] + "\n\n")
                result.insert("end", "Evaluation\n", "title")
                result.insert("end", feedback["evaluation"])
                result.config(state="disabled")
                status.config(text="Marking ready", fg=self.GREEN)

            self._run_in_background(
                lambda: self.ai.composition_feedback(words, text, provider), finish
            )

    def _restyle_background(self, widget: tk.Misc, bg: str) -> None:
        """Repaint a tk widget tree that was built for the page background."""
        if isinstance(widget, (tk.Frame, tk.Label)) and widget.cget("bg") == self.BACKGROUND:
            widget.config(bg=bg)
        for child in widget.winfo_children():
            self._restyle_background(child, bg)
