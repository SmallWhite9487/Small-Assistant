import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

MARKER_FG = "#8aa398"
INLINE_RULES = (
    ("code", re.compile(r"(`)([^`\n]+)(`)")),
    ("bold", re.compile(r"(\*\*)(.+?)(\*\*)")),
    ("strike", re.compile(r"(~~)(.+?)(~~)")),
    ("italic", re.compile(r"(?<![*\w])(\*)([^*\n]+?)(\*)(?!\*)")),
    ("italic", re.compile(r"(?<![_\w])(_)([^_\n]+?)(_)(?![_\w])")),
)
LINK_RULE = re.compile(r"(\[)([^\]\n]+)(\]\([^)\n]*\))")
LINE_RULES = (
    ("h3", re.compile(r"^(### )(.*)$")),
    ("h2", re.compile(r"^(## )(.*)$")),
    ("h1", re.compile(r"^(# )(.*)$")),
    ("quote", re.compile(r"^(> ?)(.*)$")),
    ("task", re.compile(r"^(\s*- \[[ xX]\] )(.*)$")),
    ("bullet", re.compile(r"^(\s*(?:[-*+]|\d+\.) )(.*)$")),
)
HEADING_PREFIX = re.compile(r"^#{1,3} ")
RULE_LINE = re.compile(r"\s*([-*_])(\s*\1){2,}\s*")


class NotesPageMixin:
    """Markdown notes: a formatting toolbar, live styling and a clean preview."""

    def show_notes(self) -> None:
        self._clear_content()
        self._heading("Notes", "Format with the toolbar or type Markdown; the symbols stay hidden.")
        self.current_note = None
        self.note_preview = False

        body = tk.Frame(self.content, bg=self.BACKGROUND)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=self.BACKGROUND)
        left.pack(side="left", fill="y", padx=(0, 16))
        self.note_list = tk.Listbox(
            left, width=24, activestyle="none", exportselection=False, relief="flat",
            bg=self.SURFACE, fg=self.INK, highlightthickness=0, font=("TkDefaultFont", 11),
            selectbackground="#dcebe2", selectforeground=self.GREEN,
        )
        ttk.Button(left, text="＋  New note", command=self._new_note).pack(
            side="bottom", fill="x", pady=(10, 0)
        )
        self.note_list.pack(fill="both", expand=True)
        self.note_list.bind("<<ListboxSelect>>", self._open_selected_note)

        card = tk.Frame(body, bg=self.SURFACE, padx=18, pady=14)
        card.pack(side="left", fill="both", expand=True)
        self.note_title_var = tk.StringVar()
        tk.Entry(
            card, textvariable=self.note_title_var, relief="flat", bg=self.SURFACE,
            fg=self.INK, font=("TkDefaultFont", 18, "bold"), highlightthickness=0,
            insertbackground=self.INK,
        ).pack(fill="x")
        tk.Frame(card, bg="#d7e2da", height=1).pack(fill="x", pady=(8, 8))

        self._build_note_toolbar(card)

        actions = tk.Frame(card, bg=self.SURFACE)
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(actions, text="Save", style="Accent.TButton", command=self._save_note).pack(
            side="left"
        )
        ttk.Button(actions, text="Delete", command=self._delete_note).pack(side="left", padx=(8, 0))
        self.note_status = tk.Label(
            actions, text="", bg=self.SURFACE, fg=self.MUTED, font=("TkDefaultFont", 9)
        )
        self.note_status.pack(side="right")
        text_frame = tk.Frame(card, bg=self.SURFACE)
        text_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.note_text = tk.Text(
            text_frame, wrap="word", undo=True, bg=self.SURFACE, fg=self.INK, relief="flat",
            padx=2, pady=6, font=("TkDefaultFont", 12), highlightthickness=0,
            insertbackground=self.INK, spacing1=2, spacing3=2,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.note_text.yview)
        self.note_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.note_text.pack(side="left", fill="both", expand=True)
        self._configure_note_tags()
        self.note_text.bind("<<Modified>>", self._on_note_modified)
        for sequence in ("<Command-s>", "<Control-s>"):
            self.note_text.bind(sequence, lambda _e: (self._save_note(), "break")[1])
        for sequence in ("<Command-b>", "<Control-b>"):
            self.note_text.bind(sequence, lambda _e: (self._wrap_selection("**"), "break")[1])
        for sequence in ("<Command-i>", "<Control-i>"):
            self.note_text.bind(sequence, lambda _e: (self._wrap_selection("*"), "break")[1])

        self._refresh_note_list()

    def _build_note_toolbar(self, parent: tk.Misc) -> None:
        bar = tk.Frame(parent, bg=self.SURFACE)
        bar.pack(fill="x")
        family = tkfont.nametofont("TkDefaultFont").actual("family")
        buttons = [
            ("B", {"weight": "bold"}, lambda: self._wrap_selection("**")),
            ("I", {"slant": "italic"}, lambda: self._wrap_selection("*")),
            ("S", {"overstrike": True}, lambda: self._wrap_selection("~~")),
            ("‹›", {}, lambda: self._wrap_selection("`")),
            None,
            ("H1", {"weight": "bold"}, lambda: self._toggle_line_prefix("# ")),
            ("H2", {"weight": "bold"}, lambda: self._toggle_line_prefix("## ")),
            ("H3", {"weight": "bold"}, lambda: self._toggle_line_prefix("### ")),
            None,
            ("•", {}, lambda: self._toggle_line_prefix("- ")),
            ("1.", {}, lambda: self._toggle_line_prefix("1. ")),
            ("☐", {}, lambda: self._toggle_line_prefix("- [ ] ")),
            ("❝", {}, lambda: self._toggle_line_prefix("> ")),
            None,
            ("🔗", {}, self._insert_link),
            ("―", {}, self._insert_rule),
        ]
        self._note_toolbar_fonts = []
        for spec in buttons:
            if spec is None:
                tk.Frame(bar, bg="#d7e2da", width=1, height=20).pack(side="left", padx=6)
                continue
            text, font_options, command = spec
            font = tkfont.Font(family=family, size=11, **font_options)
            self._note_toolbar_fonts.append(font)
            button = tk.Label(
                bar, text=text, bg=self.TILE, fg=self.INK, cursor="hand2", width=3, pady=4,
                font=font,
            )
            button.pack(side="left", padx=2)
            button.bind("<Button-1>", lambda _e, c=command: c())
            button.bind("<Enter>", lambda _e, b=button: b.config(bg=self.TILE_HOVER))
            button.bind("<Leave>", lambda _e, b=button: b.config(bg=self.TILE))

        self.preview_button = tk.Label(
            bar, text="Preview", bg=self.TILE, fg=self.INK, cursor="hand2", padx=12, pady=4,
            font=("TkDefaultFont", 10, "bold"),
        )
        self.preview_button.pack(side="right")
        self.preview_button.bind("<Button-1>", lambda _e: self._toggle_note_preview())

    def _configure_note_tags(self) -> None:
        family = tkfont.nametofont("TkDefaultFont").actual("family")

        def make(size=12, **options) -> tkfont.Font:
            return tkfont.Font(family=family, size=size, **options)

        self._note_fonts = {
            "h1": make(24, weight="bold"),
            "h2": make(19, weight="bold"),
            "h3": make(15, weight="bold"),
            "bold": make(weight="bold"),
            "italic": make(slant="italic"),
            "code": tkfont.Font(family="Menlo", size=11),
            "strike": make(overstrike=True),
        }
        text = self.note_text
        for name, font in self._note_fonts.items():
            text.tag_configure(name, font=font)
        text.tag_configure("h1", foreground=self.GREEN)
        text.tag_configure("h2", foreground=self.GREEN)
        text.tag_configure("code", background="#eef3ef", foreground="#8a3b2f")
        text.tag_configure("quote", foreground=self.MUTED, lmargin1=14, lmargin2=14)
        text.tag_configure("bullet", lmargin1=10, lmargin2=26)
        text.tag_configure("task", lmargin1=10, lmargin2=26)
        text.tag_configure("link", foreground="#2f6fb0", underline=True)
        text.tag_configure("rule", foreground="#b9c7bf")
        text.tag_configure("marker", foreground=MARKER_FG, elide=True)

    # --- Markdown styling -------------------------------------------------

    def _on_note_modified(self, _event=None) -> None:
        if not self.note_text.edit_modified():
            return
        self.note_text.edit_modified(False)
        self._style_note()

    def _style_note(self) -> None:
        text = self.note_text
        for tag in (*self._note_fonts, "quote", "bullet", "task", "link", "rule", "marker"):
            text.tag_remove(tag, "1.0", "end")
        in_fence = False
        for number, line in enumerate(text.get("1.0", "end-1c").split("\n"), start=1):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                text.tag_add("marker", f"{number}.0", f"{number}.end")
                continue
            if in_fence:
                text.tag_add("code", f"{number}.0", f"{number}.end")
                continue
            if RULE_LINE.fullmatch(line):
                text.tag_add("rule", f"{number}.0", f"{number}.end")
                continue
            for tag, rule in LINE_RULES:
                match = rule.match(line)
                if match:
                    text.tag_add(tag, f"{number}.0", f"{number}.end")
                    text.tag_add("marker", f"{number}.0", f"{number}.{match.end(1)}")
                    break
            for tag, rule in (*INLINE_RULES, ("link", LINK_RULE)):
                for match in rule.finditer(line):
                    start, end = match.start(2), match.end(2)
                    text.tag_add(tag, f"{number}.{start}", f"{number}.{end}")
                    text.tag_add("marker", f"{number}.{match.start(1)}", f"{number}.{start}")
                    text.tag_add("marker", f"{number}.{end}", f"{number}.{match.end(3)}")

    def _toggle_note_preview(self) -> None:
        self.note_preview = not self.note_preview
        text = self.note_text
        text.config(state="disabled" if self.note_preview else "normal")
        self.preview_button.config(
            text="Edit" if self.note_preview else "Preview",
            bg=self.GREEN if self.note_preview else self.TILE,
            fg="#ffffff" if self.note_preview else self.INK,
        )

    # --- Toolbar actions --------------------------------------------------

    def _selection_or_none(self) -> tuple[str, str] | None:
        try:
            return self.note_text.index("sel.first"), self.note_text.index("sel.last")
        except tk.TclError:
            return None

    def _wrap_selection(self, marker: str) -> None:
        if self.note_preview:
            return
        text = self.note_text
        selection = self._selection_or_none()
        size = len(marker)
        if selection is None:
            text.insert("insert", marker * 2)
            text.mark_set("insert", f"insert-{size}c")
        else:
            start, end = selection
            before = text.get(f"{start}-{size}c", start)
            after = text.get(end, f"{end}+{size}c")
            if before == marker and after == marker:
                text.delete(end, f"{end}+{size}c")
                text.delete(f"{start}-{size}c", start)
            else:
                text.insert(end, marker)
                text.insert(start, marker)
                text.tag_add("sel", f"{start}+{size}c", f"{end}+{size}c")
        text.focus_set()

    def _selected_lines(self) -> range:
        selection = self._selection_or_none()
        if selection is None:
            line = int(self.note_text.index("insert").split(".")[0])
            return range(line, line + 1)
        first = int(selection[0].split(".")[0])
        last = int(selection[1].split(".")[0])
        if selection[1].endswith(".0") and last > first:
            last -= 1
        return range(first, last + 1)

    def _toggle_line_prefix(self, prefix: str) -> None:
        if self.note_preview:
            return
        text = self.note_text
        lines = list(self._selected_lines())
        is_heading = HEADING_PREFIX.match(prefix) is not None
        all_have = all(text.get(f"{n}.0", f"{n}.end").startswith(prefix) for n in lines)
        for number in lines:
            current = text.get(f"{number}.0", f"{number}.end")
            if all_have:
                text.delete(f"{number}.0", f"{number}.{len(prefix)}")
                continue
            if current.startswith(prefix):
                continue
            existing = HEADING_PREFIX.match(current) if is_heading else None
            if existing:
                text.delete(f"{number}.0", f"{number}.{existing.end()}")
            text.insert(f"{number}.0", prefix)
        text.focus_set()

    def _insert_link(self) -> None:
        if self.note_preview:
            return
        text = self.note_text
        selection = self._selection_or_none()
        label = text.get(*selection) if selection else "text"
        if selection:
            text.delete(*selection)
        text.insert("insert", f"[{label}](https://)")
        text.mark_set("insert", "insert-1c")
        text.focus_set()

    def _insert_rule(self) -> None:
        if self.note_preview:
            return
        text = self.note_text
        line = text.get("insert linestart", "insert lineend")
        text.insert("insert lineend", ("\n" if line else "") + "---\n")
        text.focus_set()

    # --- Note list and persistence ---------------------------------------

    def _refresh_note_list(self, select: str | None = None) -> None:
        try:
            self.note_items = self.notes.list_notes()
        except OSError as error:
            self.note_items = []
            messagebox.showerror("Could not read notes", str(error), parent=self.ui)
        self.note_list.delete(0, "end")
        for index, note in enumerate(self.note_items):
            self.note_list.insert("end", f" {note['title']}  ·  {note['date']}")
            if note["name"] == select:
                self.note_list.selection_set(index)

    def _set_note_content(self, content: str) -> None:
        if self.note_preview:
            self._toggle_note_preview()
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", content)
        self.note_text.edit_reset()
        self.note_status.config(text="")

    def _new_note(self) -> None:
        self.current_note = None
        self.note_list.selection_clear(0, "end")
        self.note_title_var.set("")
        self._set_note_content("")

    def _open_selected_note(self, _event: tk.Event) -> None:
        selected = self.note_list.curselection()
        if not selected:
            return
        note = self.note_items[selected[0]]
        try:
            content = self.notes.read(note["name"])
        except (OSError, UnicodeError) as error:
            messagebox.showerror("Could not open note", str(error), parent=self.ui)
            return
        self.current_note = note["name"]
        self.note_title_var.set(note["title"])
        self._set_note_content(content)

    def _save_note(self) -> None:
        content = self.note_text.get("1.0", "end-1c")
        try:
            name = self.notes.save(self.note_title_var.get(), content, self.current_note)
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not save note", str(error), parent=self.ui)
            return
        self.current_note = name
        self._refresh_note_list(select=name)
        self.note_status.config(text="Saved")

    def _delete_note(self) -> None:
        if not self.current_note:
            messagebox.showinfo("Select a note", "Choose a note first.", parent=self.ui)
            return
        if not messagebox.askyesno("Delete note", "Delete this note?", parent=self.ui):
            return
        try:
            self.notes.delete(self.current_note)
        except OSError as error:
            messagebox.showerror("Could not delete note", str(error), parent=self.ui)
            return
        self._new_note()
        self._refresh_note_list()
