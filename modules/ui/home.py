import csv
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk


class HomePageMixin:
    """Word list page: search, toggle AI check, edit and delete."""

    def show_home(self) -> None:
        self._clear_content()
        today = date.today().isoformat()
        todays_words = sum(word["added_on"] == today for word in self.words)
        self._heading("Your words", "Collect new vocabulary and come back to it each day.")

        summary = tk.Frame(self.content, bg=self.SURFACE, padx=18, pady=14)
        summary.pack(fill="x", pady=(0, 18))
        tk.Label(
            summary,
            text=f"{len(self.words)} words saved",
            bg=self.SURFACE,
            fg=self.INK,
            font=self._font(12, "bold"),
        ).pack(side="left")
        tk.Label(
            summary,
            text=f"{todays_words} added today",
            bg=self.SURFACE,
            fg=self.GREEN,
            font=self._font(10, "bold"),
        ).pack(side="right")

        toolbar = tk.Frame(self.content, bg=self.BACKGROUND)
        toolbar.pack(fill="x", pady=(0, 10))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_words())
        search = ttk.Entry(toolbar, textvariable=self.search_var)
        search.pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(
            toolbar,
            text="＋  Add word",
            style="Accent.TButton",
            command=self.show_add_form,
        ).pack(side="right", padx=(12, 0))
        actions = tk.Frame(self.content, bg=self.BACKGROUND)
        actions.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(actions, text="Delete", command=self.delete_selected).pack(side="left")
        ttk.Button(
            actions, text="Check flagged words", command=self.show_word_check
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Review today's words",
            style="Accent.TButton",
            command=lambda: self.show_review(False),
        ).pack(side="right")
        ttk.Button(
            actions, text="⇄  Conjugate", command=self.conjugate_selected
        ).pack(side="right", padx=(0, 8))

        table_frame = tk.Frame(self.content, bg=self.SURFACE)
        table_frame.pack(fill="both", expand=True)
        columns = ("word", "reading", "meaning", "added_on", "check_ai")
        self.word_table = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse", height=4
        )
        for column, title, width in (
            ("word", "JAPANESE", 150),
            ("reading", "READING", 120),
            ("meaning", "MEANING", 210),
            ("added_on", "ADDED", 90),
            ("check_ai", "AI CHECK", 80),
        ):
            self.word_table.heading(column, text=title)
            self.word_table.column(column, width=width, anchor="w")
        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.word_table.yview
        )
        self.word_table.configure(yscrollcommand=scrollbar.set)
        self.word_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.word_table.bind("<Button-1>", self._toggle_check_from_table)
        self.word_table.bind("<Double-1>", self._edit_from_table)
        self._render_words()

    def _render_words(self) -> None:
        if not hasattr(self, "word_table") or not self.word_table.winfo_exists():
            return
        query = self.search_var.get().strip().casefold()
        self.word_table.delete(*self.word_table.get_children())
        for word in self.words:
            searchable = " ".join(
                word[field] for field in ("word", "reading", "meaning", "notes")
            ).casefold()
            if query and query not in searchable:
                continue
            self.word_table.insert(
                "",
                "end",
                iid=word["id"],
                values=(
                    word["word"],
                    word["reading"],
                    word["meaning"],
                    word["added_on"],
                    word["check_ai"],
                ),
            )

    def _toggle_check_from_table(self, event: tk.Event) -> str | None:
        if self.word_table.identify_column(event.x) != "#5":
            return None
        item_id = self.word_table.identify_row(event.y)
        word = next((item for item in self.words if item["id"] == item_id), None)
        if not word:
            return None
        word["check_ai"] = "False" if word["check_ai"] == "True" else "True"
        try:
            self.store.save(self.words)
        except (OSError, csv.Error) as error:
            word["check_ai"] = "False" if word["check_ai"] == "True" else "True"
            messagebox.showerror("Could not save changes", str(error), parent=self.ui)
        self._render_words()
        return "break"

    def _edit_from_table(self, event: tk.Event) -> None:
        if self.word_table.identify_column(event.x) != "#5":
            self.edit_selected()

    def _selected_word(self) -> dict[str, str] | None:
        selected = self.word_table.selection()
        if not selected:
            messagebox.showinfo("Select a word", "Choose a word from the list first.", parent=self.ui)
            return None
        return next((word for word in self.words if word["id"] == selected[0]), None)

    def conjugate_selected(self) -> None:
        selected = self.word_table.selection()
        word = next((w for w in self.words if selected and w["id"] == selected[0]), None)
        if word:
            self.open_conjugation_for(word["word"])

    def edit_selected(self) -> None:
        word = self._selected_word()
        if word:
            self.show_form(word)

    def delete_selected(self) -> None:
        word = self._selected_word()
        if not word:
            return
        if not messagebox.askyesno(
            "Delete word", f"Delete {word['word']} from your list?", parent=self.ui
        ):
            return
        self.words = [item for item in self.words if item["id"] != word["id"]]
        try:
            self.store.save(self.words)
        except (OSError, csv.Error) as error:
            messagebox.showerror("Could not save changes", str(error), parent=self.ui)
            return
        self.show_home()
