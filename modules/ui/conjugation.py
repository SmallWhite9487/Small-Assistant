import tkinter as tk

from ..conjugation import ADJECTIVE_FORMS, FORMS, conjugate, conjugate_adjective


FORM_HELP = {
    "ます形": "Polite form. Used in everyday polite speech.\n食べます = (I) eat",
    "ない形": "Negative form. Says the action does not happen.\n食べない = (I) don't eat",
    "た形": "Past form. Says the action happened.\n食べた = (I) ate",
    "て形": "Connecting form. Joins actions, makes requests (〜てください) and continuous (〜ている).\n食べて = eat and...",
    "可能形": "Potential form. Means can / be able to do.\n食べられる = can eat",
    "意志形": "Volitional form. Means let's do / I will do.\n食べよう = let's eat",
    "命令形": "Imperative form. A blunt command.\n食べろ = Eat!",
    "条件形": "Conditional (ば) form. Means if / provided that.\n食べれば = if (you) eat",
    "受身形": "Passive form. The subject has the action done to them.\n食べられる = be eaten",
    "使役形": "Causative form. Make or let someone do it.\n食べさせる = make/let eat",
}


ADJECTIVE_HELP = {
    "丁寧形": "Polite form with です.\n高いです = it is expensive",
    "否定形": "Negative form. Says it is not so.\n高くない / 静かじゃない = is not",
    "過去形": "Past form. Says it was so.\n高かった / 静かだった = was",
    "過去否定": "Past negative. Says it was not so.\n高くなかった = was not",
    "て形": "Connecting form. Joins descriptions.\n高くて安い… / 静かで… = and",
    "副詞形": "Adverb form. Describes how an action is done.\n高く / 静かに = highly / quietly",
    "条件形": "Conditional. Means if / provided that.\n高ければ / 静かなら = if it is",
    "たら形": "Conditional (たら). Means if / when it becomes so.\n高かったら = if it is expensive",
    "名詞化": "Turns the adjective into a noun for degree.\n高さ = height",
    "推量形": "Conjecture. Means probably.\n高いだろう = it is probably expensive",
}

BASE_HELP = "Dictionary form: the original, unconjugated form you look up in a dictionary."

ADJECTIVE_GROUPS = (
    ("Everyday", ("丁寧形", "否定形", "過去形", "過去否定")),
    ("Connecting", ("て形", "副詞形", "条件形", "たら形")),
    ("Other", ("名詞化", "推量形")),
)
VERB_GROUPS = (
    ("Everyday", ("ます形", "ない形", "た形", "て形")),
    ("Meaning & intent", ("可能形", "意志形", "命令形", "条件形")),
    ("Voice", ("受身形", "使役形")),
)


class ConjugationMixin:
    """Type a verb in any form and see its conjugations."""

    @staticmethod
    def _conjugation_mode(text: str) -> int | None:
        """0 for verbs, 1 for adjectives/nouns, None when the word cannot be conjugated."""
        if conjugate(text) is not None:
            return 0
        if conjugate_adjective(text) is not None:
            return 1
        return None

    def open_conjugation_for(self, text: str) -> None:
        mode = self._conjugation_mode(text)
        if mode is not None:
            self.show_conjugation(text, mode)

    def _attach_tooltip(self, widget: tk.Misc, text: str) -> None:
        tip: list[tk.Toplevel] = []

        def show(_event) -> None:
            if tip:
                return
            popup = tk.Toplevel(widget)
            popup.wm_overrideredirect(True)
            popup.attributes("-topmost", True)
            tk.Label(
                popup, text=text, justify="left", wraplength=260, bg="#1b2b25", fg="#ffffff",
                padx=12, pady=8, font=("TkDefaultFont", 10),
            ).pack()
            popup.update_idletasks()
            x = widget.winfo_rootx() + widget.winfo_width() - popup.winfo_reqwidth()
            popup.wm_geometry(f"+{max(x, 0)}+{widget.winfo_rooty() + widget.winfo_height() + 6}")
            tip.append(popup)

        def hide(_event) -> None:
            while tip:
                tip.pop().destroy()

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)
        widget.bind("<Destroy>", hide, add="+")

    def show_conjugation(self, initial: str = "", mode: int = 0) -> None:
        self._clear_content()
        self._heading(
            "Conjugation",
            "Type a word in any form. Switch between verbs and adjectives / nouns.",
        )

        mode_var = tk.IntVar(self.ui, value=mode)
        top = tk.Frame(self.content, bg=self.BACKGROUND)
        top.pack(fill="x", pady=(0, 10))
        search = tk.Frame(
            self.content, bg=self.SURFACE, padx=18, pady=10,
            highlightthickness=1, highlightbackground="#d7e2da", highlightcolor=self.GREEN,
        )
        search.pack(fill="x")
        entry_var = tk.StringVar()
        entry = tk.Entry(
            search, textvariable=entry_var, relief="flat", bg=self.SURFACE, fg=self.INK,
            font=("TkDefaultFont", 24), highlightthickness=0, insertbackground=self.INK,
        )
        entry.pack(fill="x")
        base_label = tk.Label(
            self.content, text="", bg=self.BACKGROUND, fg=self.MUTED, anchor="w",
            font=("TkDefaultFont", 10),
        )
        base_label.pack(fill="x", pady=(8, 4))

        body = self._scrollable_area(self.content, self.BACKGROUND)
        columns = 4
        values: dict[str, tk.Label] = {}

        def build_tile(
            parent: tk.Frame, name: str, column: int, help_text: str, bar: str | None = None
        ) -> None:
            tile = tk.Frame(parent, bg=self.SURFACE, cursor="hand2")
            tile.grid(row=0, column=column, padx=(0 if column == 0 else 8, 0), sticky="nsew")
            tk.Frame(tile, bg=bar or self.GREEN, height=3).pack(fill="x")
            inner = tk.Frame(tile, bg=self.SURFACE, padx=14, pady=12)
            inner.pack(fill="both", expand=True)
            header = tk.Frame(inner, bg=self.SURFACE)
            header.pack(fill="x")
            tk.Label(
                header, text=name, bg=self.SURFACE, fg=self.MUTED,
                font=("TkDefaultFont", 10, "bold"),
            ).pack(side="left")
            info = tk.Label(
                header, text="i", bg="#dcebe2", fg=self.GREEN, width=2, cursor="question_arrow",
                font=("TkDefaultFont", 9, "bold italic"),
            )
            info.pack(side="right")
            self._attach_tooltip(info, help_text)
            value = tk.Label(
                inner, text="—", bg=self.SURFACE, fg=self.MUTED, anchor="w",
                font=("TkDefaultFont", 19, "bold"), justify="left",
            )
            value.pack(fill="x", pady=(10, 0))
            value.bind("<Configure>", lambda e, v=value: v.config(wraplength=max(e.width - 2, 40)))
            values[name] = value

            def paint(color: str) -> None:
                for widget in (tile, inner, header, value):
                    widget.config(bg=color)
                for child in header.winfo_children():
                    if child is not info:
                        child.config(bg=color)

            for widget in (tile, inner, header, value):
                widget.bind("<Enter>", lambda _e: paint("#f1f7f3"))
                widget.bind("<Leave>", lambda _e: paint(self.SURFACE))
                widget.bind("<Button-1>", lambda _e, v=value: self._copy_conjugation(v, base_label))

        def build_tiles() -> None:
            for child in body.winfo_children():
                child.destroy()
            values.clear()
            adjective = mode_var.get() == 1
            groups = ADJECTIVE_GROUPS if adjective else VERB_GROUPS
            help_map = ADJECTIVE_HELP if adjective else FORM_HELP
            for title, names in groups:
                tk.Label(
                    body, text=title.upper(), bg=self.BACKGROUND, fg=self.MUTED, anchor="w",
                    font=("TkDefaultFont", 9, "bold"),
                ).pack(fill="x", pady=(14, 6))
                row = tk.Frame(body, bg=self.BACKGROUND)
                row.pack(fill="x")
                for column in range(columns):
                    row.columnconfigure(column, weight=1, uniform=f"forms_{title}")
                for column, name in enumerate(names):
                    build_tile(row, name, column, help_map[name])
                if title == groups[-1][0]:
                    build_tile(row, "原形", 3, BASE_HELP, bar="#9aa8a0")

        def update(*_args) -> None:
            text = entry_var.get().strip()
            adjective = mode_var.get() == 1
            if text:
                result = conjugate_adjective(text) if adjective else conjugate(text)
            else:
                result = None
            if result is None:
                hint = "Try 高い, 静かな or 学生." if adjective else "Try 食べる, 書く or 勉強する."
                kind = "adjective or noun" if adjective else "verb"
                base_label.config(
                    text=f"Not recognised as a {kind}." if text else hint,
                    fg=self.ERROR if text else self.MUTED,
                )
                for value in values.values():
                    value.config(text="—", fg=self.MUTED, font=("TkDefaultFont", 19, "bold"))
                return
            if adjective:
                base, kind, forms = result[0], result[1], result[2]
                label = f"Dictionary form: {base}   ·   {kind}   ·   click a form to copy"
            else:
                base, forms = result
                label = f"Dictionary form: {base}   ·   click a form to copy"
            base_label.config(text=label, fg=self.MUTED)
            forms = {**forms, "原形": base}
            for name, value in values.items():
                size = 19 if len(forms[name]) <= 6 else 15 if len(forms[name]) <= 10 else 12
                value.config(text=forms[name], fg=self.INK, font=("TkDefaultFont", size, "bold"))

        def on_mode_change() -> None:
            build_tiles()
            update()

        self._segmented(top, "Type", ["Verb", "Adjective / noun"], mode_var, on_mode_change)
        entry_var.trace_add("write", update)
        build_tiles()
        update()
        if initial:
            entry_var.set(initial)
        entry.focus_set()

    def _copy_conjugation(self, value: tk.Label, status: tk.Label) -> None:
        text = value.cget("text")
        if text and text != "—":
            self.ui.clipboard_clear()
            self.ui.clipboard_append(text)
            status.config(text=f"Copied {text}", fg=self.GREEN)
