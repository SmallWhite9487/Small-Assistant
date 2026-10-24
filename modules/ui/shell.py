import threading
import tkinter as tk
from tkinter import ttk


class ShellMixin:
    """Window chrome shared by every page: theme, sidebar, headings, helpers."""

    BACKGROUND = "#f3f6f2"
    SURFACE = "#ffffff"
    INK = "#1b2b25"
    MUTED = "#65756d"
    GREEN = "#24634c"
    ERROR = "#a33d32"
    TILE = "#eef3ef"
    TILE_HOVER = "#e0e9e2"

    def _build_shell(self) -> None:
        style = ttk.Style(self.ui)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=self.BACKGROUND)
        style.configure("TLabel", background=self.BACKGROUND, foreground=self.INK)
        style.configure("TButton", padding=(12, 8), font=("TkDefaultFont", 10))
        style.configure(
            "Accent.TButton",
            background=self.GREEN,
            foreground="#ffffff",
            padding=(14, 9),
        )
        style.map("Accent.TButton", background=[("active", "#194d3a")])
        style.configure(
            "Treeview",
            rowheight=34,
            background=self.SURFACE,
            fieldbackground=self.SURFACE,
            foreground=self.INK,
            font=("TkDefaultFont", 10),
        )
        style.configure("Treeview.Heading", font=("TkDefaultFont", 10, "bold"))

        sidebar = tk.Frame(self.ui, bg="#e6ede7", width=205, padx=20, pady=24)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(
            sidebar,
            text="スモー助手\nSUMOU JOSYU",
            justify="left",
            bg="#e6ede7",
            fg=self.GREEN,
            font=("TkDefaultFont", 17, "bold"),
        ).pack(anchor="w", pady=(0, 34))
        ttk.Button(sidebar, text="⌂   Home", command=self.show_home).pack(
            fill="x", pady=(0, 8)
        )
        ttk.Button(
            sidebar, text="◷   Review", command=self.show_review
        ).pack(fill="x", pady=(8, 0))
        ttk.Button(
            sidebar, text="★   Revision all", command=self.show_revision_all
        ).pack(fill="x", pady=(8, 0))
        ttk.Button(
            sidebar, text="✐   Notes", command=self.show_notes
        ).pack(fill="x", pady=(8, 0))
        ttk.Button(
            sidebar, text="✎   Grammar check", command=self.show_grammar_check
        ).pack(fill="x", pady=(8, 0))
        ttk.Button(
            sidebar, text="あ   Kana reader", command=self.show_kana_reader
        ).pack(fill="x", pady=(8, 0))
        ttk.Button(
            sidebar, text="✓   Check word info", command=self.show_word_check
        ).pack(fill="x", pady=(8, 0))
        tk.Label(
            sidebar,
            text="Your personal\nJapanese Learning Helper",
            justify="left",
            bg="#e6ede7",
            fg=self.MUTED,
            font=("TkDefaultFont", 9),
        ).pack(side="bottom", anchor="w")

        # Keep Space/Enter from re-triggering a sidebar button that kept focus.
        for button in sidebar.winfo_children():
            if isinstance(button, ttk.Button):
                button.configure(takefocus=False)

        self.content = tk.Frame(self.ui, bg=self.BACKGROUND, padx=34, pady=28)
        self.content.pack(side="left", fill="both", expand=True)

    def _clear_content(self) -> None:
        self._page_generation += 1
        for widget in self.content.winfo_children():
            widget.destroy()
        self.content.focus_set()

    def _heading(self, title: str, subtitle: str) -> None:
        tk.Label(
            self.content,
            text=title,
            bg=self.BACKGROUND,
            fg=self.INK,
            font=("TkDefaultFont", 23, "bold"),
        ).pack(anchor="w")
        tk.Label(
            self.content,
            text=subtitle,
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("TkDefaultFont", 10),
        ).pack(anchor="w", pady=(4, 20))

    def _provider_selector(
        self, parent: tk.Misc, bg: str, pady: tuple[int, int]
    ) -> tk.StringVar:
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=pady)
        tk.Label(
            row,
            text="AI service",
            bg=bg,
            fg=self.INK,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left", padx=(0, 12))
        variable = tk.StringVar(self.ui, value="local")
        ttk.Radiobutton(
            row, text="Local AI (Ollama)", value="local", variable=variable
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            row, text="Online API", value="online", variable=variable
        ).pack(side="left")
        return variable

    def _scrollable_area(self, parent: tk.Misc, bg: str) -> tk.Frame:
        """Create a canvas-backed scrolling frame with mouse-wheel support."""
        canvas = tk.Canvas(parent, bg=bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=bg)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>", lambda event: canvas.itemconfigure(window, width=event.width)
        )
        canvas.configure(yscrollcommand=scrollbar.set, yscrollincrement=24)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_mousewheel(event: tk.Event) -> None:
            if not canvas.winfo_exists():
                return
            if inner.winfo_reqheight() <= canvas.winfo_height():
                return
            hovered = self.ui.winfo_containing(*self.ui.winfo_pointerxy())
            if hovered is not None and hovered.winfo_class() in {"Text", "Treeview"}:
                return
            if event.num == 4:
                steps = -3
            elif event.num == 5:
                steps = 3
            elif abs(event.delta) >= 120:
                steps = -3 * (event.delta // 120 if event.delta > 0 else -(-event.delta // 120))
            else:
                # macOS wheels and trackpads report small deltas
                steps = -event.delta
            if steps:
                canvas.yview_scroll(int(steps), "units")

        # Page-wide binding so the wheel works anywhere on the page, like Home.
        sequences = ("<MouseWheel>", "<Button-4>", "<Button-5>")
        for sequence in sequences:
            self.ui.bind_all(sequence, on_mousewheel)

        def on_touchpad(event: tk.Event) -> None:
            # Tk 9 sends trackpad gestures as <TouchpadScroll> with packed deltas.
            if not canvas.winfo_exists():
                return
            total = inner.winfo_reqheight()
            if total <= canvas.winfo_height():
                return
            deltas = self.ui.tk.call("tk::PreciseScrollDeltas", event.delta)
            dy = int(float(deltas[1]))
            if dy:
                canvas.yview_moveto(canvas.yview()[0] - dy / total)

        try:
            self.ui.bind_all("<TouchpadScroll>", on_touchpad)
            sequences += ("<TouchpadScroll>",)
        except tk.TclError:
            pass

        def unbind_wheel(_event: tk.Event) -> None:
            for sequence in sequences:
                self.ui.unbind_all(sequence)

        canvas.bind("<Destroy>", unbind_wheel)
        inner.canvas = canvas
        return inner

    def _run_in_background(self, work, on_done) -> None:
        """Run work() off the UI thread, then on_done(result, error) on it.

        The callback is skipped if the user has navigated to another page.
        """
        page_generation = self._page_generation

        def target() -> None:
            try:
                result, error = work(), None
            except Exception as caught_error:
                result, error = None, caught_error

            def finish() -> None:
                if page_generation == self._page_generation:
                    on_done(result, error)

            self.ui.after(0, finish)

        threading.Thread(target=target, daemon=True).start()

    def _flat_button(self, parent, text, command, accent=False, small=False) -> tk.Label:
        """Label-based button: honors colors on every platform, unlike tk.Button on macOS."""
        base = self.GREEN if accent else self.TILE
        hover = "#194d3a" if accent else self.TILE_HOVER
        button = tk.Label(
            parent,
            text=text,
            bg=base,
            fg="#ffffff" if accent else self.INK,
            cursor="hand2",
            padx=14 if small else 18,
            pady=5 if small else 14,
            font=("TkDefaultFont", 10 if small else 12),
        )
        button.base_bg = base
        button.hover_bg = hover
        button.enabled = True
        button.command = command

        def click(_event) -> None:
            if button.enabled:
                button.command()

        def enter(_event) -> None:
            if button.enabled and button.cget("bg") == button.base_bg:
                button.config(bg=button.hover_bg)

        def leave(_event) -> None:
            if button.cget("bg") == button.hover_bg:
                button.config(bg=button.base_bg)

        button.bind("<Button-1>", click)
        button.bind("<Enter>", enter)
        button.bind("<Leave>", leave)
        return button

    def _set_enabled(self, button: tk.Label, enabled: bool) -> None:
        button.enabled = enabled
        button.config(
            fg=self.INK if enabled else "#a5b2aa", cursor="hand2" if enabled else "arrow"
        )

    def _segmented(self, parent, caption, labels, variable, on_change) -> dict:
        group = tk.Frame(parent, bg=self.BACKGROUND)
        group.pack(side="left", padx=(0, 22))
        tk.Label(
            group, text=caption, bg=self.BACKGROUND, fg=self.MUTED, font=("TkDefaultFont", 10)
        ).pack(side="left", padx=(0, 8))
        track = tk.Frame(group, bg="#d7e2da", padx=2, pady=2)
        track.pack(side="left")
        segments = []
        control = {"segments": segments, "variable": variable, "enabled": True}

        def paint() -> None:
            for index, segment in enumerate(segments):
                selected = variable.get() == index
                segment.config(
                    bg=self.GREEN if selected else "#d7e2da",
                    fg="#ffffff" if selected else (self.INK if control["enabled"] else "#9aa8a0"),
                    cursor="hand2" if control["enabled"] else "arrow",
                )

        def select(index: int) -> None:
            if not control["enabled"] or variable.get() == index:
                return
            variable.set(index)
            paint()
            on_change()

        for index, text in enumerate(labels):
            segment = tk.Label(track, text=text, padx=14, pady=4, font=("TkDefaultFont", 10, "bold"))
            segment.pack(side="left")
            segment.bind("<Button-1>", lambda _e, i=index: select(i))
            segments.append(segment)
        control["paint"] = paint
        paint()
        return control

    def _set_segmented_enabled(self, control: dict, enabled: bool) -> None:
        control["enabled"] = enabled
        control["paint"]()
