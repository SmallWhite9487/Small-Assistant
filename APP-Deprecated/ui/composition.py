import random
import tkinter as tk
from tkinter import ttk


class CompositionMixin:
    """Write a composition using randomly drawn vocabulary, then get AI marking."""

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

        # Kept on the app object so a draft survives switching pages.
        if not hasattr(self, "composition_state"):
            self.composition_state = {
                "drawn": [], "count": 0, "text": "", "feedback": None,
                "message": "", "message_error": False, "provider": "local", "pending": False,
            }
        state = self.composition_state
        count_var = tk.IntVar(self.ui, value=state["count"])
        drawn: list[dict[str, str]] = state["drawn"]

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
        composition_input.insert("1.0", state["text"])
        composition_input.edit_reset()
        composition_input.edit_modified(False)
        composition_input.bind(
            "<<Modified>>",
            lambda _e: (
                composition_input.edit_modified(False),
                state.update(text=composition_input.get("1.0", "end-1c")),
            ),
        )

        footer = tk.Frame(write_card, bg=self.SURFACE)
        footer.pack(fill="x", pady=(12, 0))
        provider_var = self._provider_selector(footer, self.SURFACE, (0, 0))
        provider_var.set(state["provider"])
        provider_var.trace_add("write", lambda *_: state.update(provider=provider_var.get()))
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
            state["feedback"] = None
            result.config(state="normal")
            result.delete("1.0", "end")
            result.config(state="disabled")

        def show_feedback(feedback: dict[str, str]) -> None:
            result.config(state="normal")
            result.delete("1.0", "end")
            result.insert("end", "Corrected\n", "title")
            result.insert("end", feedback["corrected"] + "\n\n")
            result.insert("end", "Evaluation\n", "title")
            result.insert("end", feedback["evaluation"])
            result.config(state="disabled")

        def set_status(text: str, error: bool = False, ok: bool = False) -> None:
            state["message"], state["message_error"] = text, error
            status.config(text=text, fg=self.ERROR if error else self.GREEN if ok else self.MUTED)

        def replace_word(index: int) -> None:
            used = {item["id"] for item in drawn}
            pool = [item for item in self.words if item["id"] not in used]
            if not pool:
                set_status("No other saved words to swap in.", error=True)
                return
            drawn[index] = random.choice(pool)
            clear_result()
            render_chips()
            set_status("")

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
                set_status(
                    f"You need at least {count} saved words (you have {len(self.words)}).",
                    error=True,
                )
                return
            drawn[:] = random.sample(self.words, count)
            state["count"] = 0 if count == 5 else 1
            render_chips()
            composition_input.delete("1.0", "end")
            clear_result()
            set_status("")
            composition_input.focus_set()

        self._segmented(
            controls, "Words", ["5", "10"], count_var,
            lambda: state.update(count=count_var.get()),
        )
        ttk.Button(controls, text="⟳  Draw words", command=draw_words).pack(side="left")
        for segmented_child in controls.winfo_children():
            self._restyle_background(segmented_child, self.SURFACE)

        def poll_pending() -> None:
            if not result.winfo_exists():
                return
            if state["pending"]:
                self.ui.after(400, poll_pending)
                return
            submit_button.config(state="normal")
            if state["feedback"]:
                show_feedback(state["feedback"])
            set_status(state["message"], error=state["message_error"], ok=bool(state["feedback"]))

        def submit() -> None:
            if state["pending"]:
                return
            if not drawn:
                set_status("Draw words first.", error=True)
                return
            text = composition_input.get("1.0", "end-1c").strip()
            if not text:
                set_status("Write something first.", error=True)
                return

            submit_button.config(state="disabled")
            set_status("Marking...")
            clear_result()
            words = [item["word"] for item in drawn]
            provider = provider_var.get()
            state["pending"] = True

            def work() -> None:
                # Runs even if the user left the page, so the result is kept for their return.
                try:
                    state["feedback"] = self.ai.composition_feedback(words, text, provider)
                    state["message"], state["message_error"] = "Marking ready", False
                except Exception as error:
                    state["feedback"] = None
                    state["message"], state["message_error"] = str(error), True
                finally:
                    state["pending"] = False

            self._run_in_background(work, lambda _r, _e: poll_pending())

        render_chips() if drawn else None
        if state["feedback"]:
            show_feedback(state["feedback"])
        if state["pending"]:
            submit_button.config(state="disabled")
            set_status("Marking...")
            poll_pending()
        elif state["message"]:
            set_status(state["message"], error=state["message_error"], ok=bool(state["feedback"]))

    def _restyle_background(self, widget: tk.Misc, bg: str) -> None:
        """Repaint a tk widget tree that was built for the page background."""
        if isinstance(widget, (tk.Frame, tk.Label)) and widget.cget("bg") == self.BACKGROUND:
            widget.config(bg=bg)
        for child in widget.winfo_children():
            self._restyle_background(child, bg)
