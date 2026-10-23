import csv
import json
import os
import re
import threading
import tkinter as tk
import unicodedata
import uuid
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from google import genai
from google.genai import types


DATA_FILE = Path(__file__).with_name("words.csv")
CSV_FIELDS = ("id", "word", "reading", "meaning", "notes", "check_ai", "added_on")


class VocabularyStore:
    def __init__(self, path: Path = DATA_FILE):
        self.path = path

    def load(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []

        with self.path.open("r", newline="", encoding="utf-8") as file:
            rows = csv.DictReader(file)
            words = []
            for row in rows:
                if not (row.get("word") or "").strip():
                    continue
                word = {field: row.get(field, "") or "" for field in CSV_FIELDS}
                word["check_ai"] = (
                    "False"
                    if word["check_ai"].strip().casefold() in {"false", "0", "no"}
                    else "True"
                )
                words.append(word)
            return words

    def save(self, words: list[dict[str, str]]) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(words)


class UI:
    BACKGROUND = "#f3f6f2"
    SURFACE = "#ffffff"
    INK = "#1b2b25"
    MUTED = "#65756d"
    GREEN = "#24634c"

    def __init__(self):
        self.ui = tk.Tk()
        self.ui.title("スモー助手 | Small-Assistant")
        self.ui.geometry("960x650")
        self.ui.minsize(760, 520)
        self.ui.configure(bg=self.BACKGROUND)
        self.store = VocabularyStore()
        self._page_generation = 0
        load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

        try:
            self.words = self.store.load()
        except (OSError, csv.Error, UnicodeError) as error:
            self.words = []
            messagebox.showerror("Could not load words", str(error), parent=self.ui)

        self._build_shell()
        self.show_home()

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
            sidebar, text="◷   Review today", command=self.show_review
        ).pack(fill="x")
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

        self.content = tk.Frame(self.ui, bg=self.BACKGROUND, padx=34, pady=28)
        self.content.pack(side="left", fill="both", expand=True)

    def _clear_content(self) -> None:
        self._page_generation += 1
        for widget in self.content.winfo_children():
            widget.destroy()

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
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side="left")
        tk.Label(
            summary,
            text=f"{todays_words} added today",
            bg=self.SURFACE,
            fg=self.GREEN,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="right")

        toolbar = tk.Frame(self.content, bg=self.BACKGROUND)
        toolbar.pack(fill="x", pady=(0, 10))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_words())
        search = ttk.Entry(toolbar, textvariable=self.search_var)
        search.pack(side="left", fill="x", expand=True, ipady=5)
        search.insert(0, "")
        ttk.Button(
            toolbar,
            text="＋  Add word",
            style="Accent.TButton",
            command=self.show_add_form,
        ).pack(side="right", padx=(12, 0))
        table_frame = tk.Frame(self.content, bg=self.SURFACE)
        table_frame.pack(fill="both", expand=True)
        columns = ("word", "reading", "meaning", "added_on", "check_ai")
        self.word_table = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
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

        actions = tk.Frame(self.content, bg=self.BACKGROUND)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="Edit selected", command=self.edit_selected).pack(
            side="left"
        )
        ttk.Button(actions, text="Delete selected", command=self.delete_selected).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(
            actions,
            text="Check flagged words",
            command=self.show_word_check,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Review today's words",
            style="Accent.TButton",
            command=self.show_review,
        ).pack(side="right")

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

    def _toggle_check_from_table(self, event: tk.Event) -> None:
        if self.word_table.identify_column(event.x) != "#5":
            return
        item_id = self.word_table.identify_row(event.y)
        word = next((item for item in self.words if item["id"] == item_id), None)
        if not word:
            return
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

    def show_add_form(self) -> None:
        self.show_form()

    def show_form(self, word: dict[str, str] | None = None) -> None:
        self._clear_content()
        editing = word is not None
        self._heading(
            "Edit word" if editing else "Add a word",
            "Save the spelling, how to read it, and what it means.",
        )

        form = tk.Frame(self.content, bg=self.SURFACE, padx=22, pady=20)
        form.pack(fill="x", anchor="n")
        values = word or {}
        fields = (
            ("Japanese word", "word", True),
            ("Kana reading", "reading", False),
            ("Meaning", "meaning", True),
        )
        variables: dict[str, tk.StringVar] = {}
        for row, (label, key, required) in enumerate(fields):
            tk.Label(
                form,
                text=f"{label}{' *' if required else ''}",
                bg=self.SURFACE,
                fg=self.INK,
                font=("TkDefaultFont", 10, "bold"),
            ).grid(row=row * 2, column=0, sticky="w", pady=(0, 5 if row == 0 else 0))
            variable = tk.StringVar(value=values.get(key, ""))
            variables[key] = variable
            ttk.Entry(form, textvariable=variable).grid(
                row=row * 2 + 1, column=0, sticky="ew", ipady=5, pady=(0, 14)
            )

        tk.Label(
            form,
            text="Notes (optional)",
            bg=self.SURFACE,
            fg=self.INK,
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=6, column=0, sticky="w", pady=(0, 5))
        notes = tk.Text(form, height=4, wrap="word", font=("TkDefaultFont", 10))
        notes.grid(row=7, column=0, sticky="ew")
        notes.insert("1.0", values.get("notes", ""))
        check_ai_var = tk.BooleanVar(value=values.get("check_ai", "True") == "True")
        ttk.Checkbutton(
            form,
            text="Check this word with AI",
            variable=check_ai_var,
        ).grid(row=8, column=0, sticky="w", pady=(12, 0))
        form.columnconfigure(0, weight=1)

        actions = tk.Frame(self.content, bg=self.BACKGROUND)
        actions.pack(fill="x", pady=14)
        ttk.Button(actions, text="Cancel", command=self.show_home).pack(side="left")

        def save_word() -> None:
            japanese = variables["word"].get().strip()
            meaning = variables["meaning"].get().strip()
            if not japanese or not meaning:
                messagebox.showwarning(
                    "Missing information",
                    "Enter a Japanese word and its meaning.",
                    parent=self.ui,
                )
                return

            updated = {
                "id": values.get("id", str(uuid.uuid4())),
                "word": japanese,
                "reading": variables["reading"].get().strip(),
                "meaning": meaning,
                "notes": notes.get("1.0", "end-1c").strip(),
                "check_ai": str(check_ai_var.get()),
                "added_on": values.get("added_on", date.today().isoformat()),
            }
            if editing:
                self.words = [updated if item["id"] == values["id"] else item for item in self.words]
            else:
                self.words.append(updated)
            try:
                self.store.save(self.words)
            except (OSError, csv.Error) as error:
                messagebox.showerror("Could not save word", str(error), parent=self.ui)
                return
            self.show_home()

        ttk.Button(
            actions, text="Save word", style="Accent.TButton", command=save_word
        ).pack(side="right")

    def _selected_word(self) -> dict[str, str] | None:
        selected = self.word_table.selection()
        if not selected:
            messagebox.showinfo("Select a word", "Choose a word from the list first.", parent=self.ui)
            return None
        return next((word for word in self.words if word["id"] == selected[0]), None)

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

    def show_review(self) -> None:
        self._clear_content()
        today = date.today().isoformat()
        self.review_words = [word for word in self.words if word["added_on"] == today]
        self.review_index = 0
        self.review_revealed = False
        self._heading("Today's review", "A quick look at the words you collected today.")

        if not self.review_words:
            empty = tk.Frame(self.content, bg=self.SURFACE, padx=28, pady=32)
            empty.pack(fill="x", anchor="n")
            tk.Label(
                empty,
                text="No words added today",
                bg=self.SURFACE,
                fg=self.INK,
                font=("TkDefaultFont", 16, "bold"),
            ).pack(anchor="w")
            tk.Label(
                empty,
                text="Words you add will appear here for a same-day review.",
                bg=self.SURFACE,
                fg=self.MUTED,
            ).pack(anchor="w", pady=(7, 0))
            ttk.Button(self.content, text="Back to home", command=self.show_home).pack(
                anchor="w", pady=16
            )
            return

        self.review_count = tk.Label(
            self.content,
            text="",
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("TkDefaultFont", 10),
        )
        self.review_count.pack(anchor="e", pady=(0, 8))
        card = tk.Frame(self.content, bg=self.SURFACE, padx=36, pady=32)
        card.pack(fill="both", expand=True)
        self.review_word_label = tk.Label(
            card,
            text="",
            bg=self.SURFACE,
            fg=self.INK,
            font=("TkDefaultFont", 34, "bold"),
        )
        self.review_word_label.pack(pady=(12, 18))
        self.review_reading_label = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.GREEN, font=("TkDefaultFont", 15)
        )
        self.review_reading_label.pack(pady=4)
        self.review_meaning_label = tk.Label(
            card, text="", bg=self.SURFACE, fg=self.INK, font=("TkDefaultFont", 16)
        )
        self.review_meaning_label.pack(pady=4)
        self.review_notes_label = tk.Label(
            card,
            text="",
            bg=self.SURFACE,
            fg=self.MUTED,
            font=("TkDefaultFont", 10),
            wraplength=600,
        )
        self.review_notes_label.pack(pady=(6, 14))
        self.reveal_button = ttk.Button(
            card, text="Show reading and meaning", command=self._toggle_reveal
        )
        self.reveal_button.pack(pady=(6, 4))

        navigation = tk.Frame(self.content, bg=self.BACKGROUND)
        navigation.pack(fill="x", pady=(12, 0))
        ttk.Button(navigation, text="← Previous", command=lambda: self._move_review(-1)).pack(
            side="left"
        )
        ttk.Button(navigation, text="Next →", command=lambda: self._move_review(1)).pack(
            side="right"
        )
        self._render_review_card()

    def show_kana_reader(self) -> None:
        self._clear_content()
        self._heading("Kana reader", "Break Japanese into speakable parts with kana readings.")

        input_panel = tk.Frame(self.content, bg=self.SURFACE, padx=18, pady=16)
        input_panel.pack(fill="x", anchor="n")
        provider_var = tk.StringVar(self.ui, value="local")
        provider_row = tk.Frame(input_panel, bg=self.SURFACE)
        provider_row.pack(fill="x", pady=(0, 12))
        tk.Label(
            provider_row,
            text="AI service",
            bg=self.SURFACE,
            fg=self.INK,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            provider_row,
            text="Local AI (Ollama)",
            value="local",
            variable=provider_var,
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            provider_row,
            text="Online API",
            value="online",
            variable=provider_var,
        ).pack(side="left")
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

        token_canvas = tk.Canvas(result_panel, bg=self.SURFACE, highlightthickness=0)
        token_scrollbar = ttk.Scrollbar(
            result_panel, orient="vertical", command=token_canvas.yview
        )
        token_frame = tk.Frame(token_canvas, bg=self.SURFACE)
        token_window = token_canvas.create_window((0, 0), window=token_frame, anchor="nw")
        token_frame.bind(
            "<Configure>",
            lambda _event: token_canvas.configure(scrollregion=token_canvas.bbox("all")),
        )
        token_canvas.bind(
            "<Configure>",
            lambda event: token_canvas.itemconfigure(token_window, width=event.width),
        )
        token_canvas.configure(yscrollcommand=token_scrollbar.set)
        token_canvas.pack(side="left", fill="both", expand=True)
        token_scrollbar.pack(side="right", fill="y")

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
                status.config(text="Enter a Japanese sentence first.", fg="#a33d32")
                sentence_input.focus_set()
                return

            start_button.config(state="disabled")
            copy_button.config(state="disabled")
            full_reading.config(text="")
            status.config(text="Asking the AI to cut the sentence and add kana...", fg=self.MUTED)
            page_generation = self._page_generation
            provider = provider_var.get()

            def request_reading() -> None:
                try:
                    segments = self._get_ai_reading_segments(sentence, provider)
                    error = None
                except Exception as caught_error:
                    segments = []
                    error = caught_error

                def finish() -> None:
                    if page_generation != self._page_generation:
                        return
                    start_button.config(state="normal")
                    if error is not None:
                        status.config(text=str(error), fg="#a33d32")
                        return
                    render_segments(segments)

                self.ui.after(0, finish)

            threading.Thread(target=request_reading, daemon=True).start()

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

    def show_grammar_check(self) -> None:
        self._clear_content()
        self._heading("Grammar check", "Get a natural correction in the same language.")

        input_panel = tk.Frame(self.content, bg=self.SURFACE, padx=18, pady=16)
        input_panel.pack(fill="x", anchor="n")
        provider_var = tk.StringVar(self.ui, value="local")
        provider_row = tk.Frame(input_panel, bg=self.SURFACE)
        provider_row.pack(fill="x", pady=(0, 12))
        tk.Label(
            provider_row,
            text="AI service",
            bg=self.SURFACE,
            fg=self.INK,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            provider_row,
            text="Local AI (Ollama)",
            value="local",
            variable=provider_var,
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            provider_row,
            text="Online API",
            value="online",
            variable=provider_var,
        ).pack(side="left")
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
                status.config(text="Enter a sentence to check.", fg="#a33d32")
                sentence_input.focus_set()
                return

            check_button.config(state="disabled")
            copy_button.config(state="disabled")
            status.config(text="Checking...", fg=self.MUTED)
            result.config(state="normal")
            result.delete("1.0", "end")
            result.config(state="disabled")
            page_generation = self._page_generation
            provider = provider_var.get()

            def request_feedback() -> None:
                try:
                    feedback = self._get_grammar_feedback(sentence, provider)
                    error = None
                except Exception as caught_error:
                    feedback = str(caught_error)
                    error = caught_error

                def finish() -> None:
                    if page_generation != self._page_generation:
                        return
                    result.config(state="normal")
                    result.insert("1.0", feedback)
                    result.config(state="disabled")
                    status.config(
                        text="Correction ready" if error is None else feedback,
                        fg=self.GREEN if error is None else "#a33d32",
                    )
                    check_button.config(state="normal")
                    copy_button.config(state="normal" if error is None else "disabled")

                self.ui.after(0, finish)

            threading.Thread(target=request_feedback, daemon=True).start()

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

    @staticmethod
    def _generate_ai_response(
        prompt: str,
        system_instruction: str,
        provider: str,
        json_mode: bool = False,
        json_format: dict[str, object] | None = None,
    ) -> str:
        if provider == "local":
            ollama_base_url = os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            ).strip().rstrip("/")
            ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:12b").strip()
            try:
                with urlopen(f"{ollama_base_url}/api/tags", timeout=3) as response:
                    installed_models = json.load(response).get("models", [])
                matching_model = next(
                    (
                        model.get("name") or model.get("model")
                        for model in installed_models
                        if (model.get("name") or model.get("model", "")).casefold()
                        == ollama_model.casefold()
                    ),
                    None,
                )
            except (OSError, ValueError, TypeError):
                matching_model = None

            if not matching_model:
                raise ValueError(
                    f"Ollama model {ollama_model!r} was not found at "
                    f"{ollama_base_url}. Start Ollama or set OLLAMA_MODEL in .env."
                )

            payload = {
                "model": matching_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "options": {"temperature": 0.2},
            }
            if json_mode:
                payload["format"] = json_format or {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "word": {"type": "string"},
                            "reading": {"type": "string"},
                            "meaning": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["id", "word", "reading", "meaning", "reason"],
                        "additionalProperties": False,
                    },
                }
            request = Request(
                f"{ollama_base_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=180) as response:
                result = json.load(response)
            feedback = result.get("message", {}).get("content", "").strip()
            if not feedback:
                raise ValueError("The local AI returned an empty response. Please try again.")
            return feedback
        if provider != "online":
            raise ValueError(f"Unknown AI service: {provider}")

        api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv(
            "OPENAI_API_KEY", ""
        ).strip()
        if not api_key:
            raise ValueError(
                "Add your API key to GEMINI_API_KEY in .env to use the Online API."
            )

        base_url = os.getenv("GEMINI_BASE_URL", "").strip()
        model = os.getenv("GEMINI_MODEL", "").strip() or os.getenv(
            "OPENAI_MODEL", "gemini-3.8-flash"
        ).strip()
        if not model:
            raise ValueError("Set a model name in the GEMINI_MODEL setting in .env.")

        if base_url:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(base_url=base_url),
            )
        else:
            client = genai.Client(api_key=api_key)
        config = {
            "system_instruction": system_instruction,
            "temperature": 0.2,
        }
        if json_mode:
            config["response_mime_type"] = "application/json"
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**config),
        )
        if not response.text:
            raise ValueError("The AI returned an empty response. Please try again.")
        return response.text.strip()

    @staticmethod
    def _get_ai_reading_segments(
        sentence: str, provider: str
    ) -> list[tuple[str, str]]:
        schema: dict[str, object] = {
            "type": "object",
            "properties": {
                "segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "surface": {"type": "string"},
                            "kana": {"type": "string"},
                        },
                        "required": ["surface", "kana"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["segments"],
            "additionalProperties": False,
        }
        prompt = json.dumps(
            {"sentence": sentence}, ensure_ascii=False
        )
        system_instruction = (
            "Split the Japanese sentence into natural word-sized chunks for a learner "
            "to speak aloud. For every chunk, return its exact surface text and its "
            "reading written in hiragana. Keep particles as their own chunks. Use the "
            "contextual reading for dates and numbers. Preserve every input character "
            "in order, including punctuation and spaces; do not add, omit, translate, "
            "or correct text. For punctuation or spaces, use that same mark as kana. "
            "Return only a JSON object with a segments array."
        )
        response = UI._generate_ai_response(
            prompt,
            system_instruction,
            provider,
            json_mode=True,
            json_format=schema,
        )
        try:
            result = json.loads(response)
        except json.JSONDecodeError as error:
            raise ValueError("The AI returned invalid kana data. Please try again.") from error
        if not isinstance(result, dict) or not isinstance(result.get("segments"), list):
            raise ValueError("The AI returned an invalid segmentation. Please try again.")

        segments = []
        for segment in result["segments"]:
            if not isinstance(segment, dict):
                raise ValueError("The AI returned an invalid word segment.")
            surface = segment.get("surface")
            kana = segment.get("kana")
            if not isinstance(surface, str) or not surface or not isinstance(kana, str):
                raise ValueError("The AI returned an incomplete word segment.")
            segments.append((surface, kana))

        normalized_input = unicodedata.normalize("NFKC", sentence)
        normalized_output = unicodedata.normalize(
            "NFKC", "".join(surface for surface, _kana in segments)
        )
        if not segments or normalized_output != normalized_input:
            raise ValueError("The AI did not preserve the full sentence. Please try again.")
        if any(re.search(r"[一-龯々a-zA-Z0-9]", kana) for _surface, kana in segments):
            raise ValueError("The AI returned a reading that is not fully in kana.")
        return segments

    @staticmethod
    def _get_grammar_feedback(sentence: str, provider: str = "local") -> str:
        system_instruction = (
            "You are a grammar correction tool. Output only the user's "
            "sentence with grammar and wording corrected. Do not explain, "
            "add headings, quotation marks, markdown, alternatives, "
            "translations, or commentary. Preserve the original language, "
            "meaning, tone, and formatting. Do not add ideas or details. "
            "If the sentence is already correct, return it unchanged. "
            "If it is ambiguous, make the smallest correction possible."
        )
        return UI._generate_ai_response(sentence, system_instruction, provider)

    @staticmethod
    def _get_word_suggestions(
        words: list[dict[str, str]], provider: str
    ) -> list[dict[str, str]]:
        original_by_id = {word["id"]: word for word in words}
        prompt = json.dumps(
            [
                {
                    "id": word["id"],
                    "word": word["word"],
                    "reading": word["reading"],
                    "meaning": word["meaning"],
                }
                for word in words
            ],
            ensure_ascii=False,
        )
        system_instruction = (
            "Check each Japanese vocabulary record for accurate kanji/kana spelling, "
            "kana reading, and meaning or translation. Preserve the language and "
            "style of each existing meaning; do not translate it into another language. "
            "Keep valid entries unchanged and do not guess when a name or context is "
            "ambiguous. Return only a JSON array with one object per input and exactly "
            "these string fields: id, word, reading, meaning, reason. Preserve each id "
            "exactly. The reason should briefly say what needs correction, or say "
            "'Looks correct.'"
        )
        response = UI._generate_ai_response(
            prompt, system_instruction, provider, json_mode=True
        )
        try:
            suggestions = json.loads(response)
        except json.JSONDecodeError as error:
            raise ValueError("The AI returned invalid word-check data. Please try again.") from error
        if isinstance(suggestions, dict) and len(words) == 1:
            suggestions = [suggestions]
        if not isinstance(suggestions, list):
            raise ValueError("The AI returned an invalid word-check list. Please try again.")

        parsed_by_id: dict[str, dict[str, str]] = {}
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                raise ValueError("The AI returned an invalid word-check item.")
            word_id = suggestion.get("id")
            if word_id not in original_by_id or word_id in parsed_by_id:
                raise ValueError("The AI returned mismatched word-check results.")
            original = original_by_id[word_id]
            parsed_by_id[word_id] = {
                key: suggestion.get(key, original.get(key, ""))
                for key in ("word", "reading", "meaning")
            } | {"id": word_id, "reason": suggestion.get("reason", "")}
            if any(not isinstance(value, str) for value in parsed_by_id[word_id].values()):
                raise ValueError("The AI returned invalid text in a word-check result.")

        if parsed_by_id.keys() != original_by_id.keys():
            raise ValueError("The AI did not return a result for every selected word.")
        return [parsed_by_id[word["id"]] for word in words]

    def show_word_check(self) -> None:
        self._clear_content()
        queued_words = [word for word in self.words if word["check_ai"] == "True"]
        self._heading(
            "Check word information",
            "Check kanji, kana reading, and meaning for words marked True.",
        )

        provider_row = tk.Frame(self.content, bg=self.BACKGROUND)
        provider_row.pack(fill="x", pady=(0, 10))
        tk.Label(
            provider_row,
            text="AI service",
            bg=self.BACKGROUND,
            fg=self.INK,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left", padx=(0, 12))
        provider_var = tk.StringVar(self.ui, value="local")
        ttk.Radiobutton(
            provider_row,
            text="Local AI (Ollama)",
            value="local",
            variable=provider_var,
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            provider_row,
            text="Online API",
            value="online",
            variable=provider_var,
        ).pack(side="left")

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
        canvas = tk.Canvas(results_frame, bg=self.BACKGROUND, highlightthickness=0)
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=canvas.yview)
        result_list = tk.Frame(canvas, bg=self.BACKGROUND)
        result_window = canvas.create_window((0, 0), window=result_list, anchor="nw")
        result_list.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(result_window, width=event.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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

        page_generation = self._page_generation

        def render_suggestions(suggestions: list[dict[str, str]]) -> None:
            for widget in result_list.winfo_children():
                widget.destroy()

            for suggestion in suggestions:
                word = next(
                    item for item in self.words if item["id"] == suggestion["id"]
                )
                card = tk.Frame(result_list, bg=self.SURFACE, padx=14, pady=12)
                card.pack(fill="x", pady=(0, 8))
                tk.Label(
                    card,
                    text=word["word"],
                    bg=self.SURFACE,
                    fg=self.INK,
                    font=("TkDefaultFont", 13, "bold"),
                ).pack(anchor="w")

                changed_fields = []
                for key, label in (
                    ("word", "Kanji / kana"),
                    ("reading", "Reading"),
                    ("meaning", "Meaning"),
                ):
                    if word[key] != suggestion[key]:
                        changed_fields.append(key)
                    before = word[key] or "(empty)"
                    after = suggestion[key] or "(empty)"
                    text = (
                        f"{label}: {before} -> {after}"
                        if word[key] != suggestion[key]
                        else f"{label}: {before}"
                    )
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

                button_holder: list[ttk.Button] = []

                def apply_suggestion(
                    target: dict[str, str] = word,
                    proposed: dict[str, str] = suggestion,
                    button_holder: list[ttk.Button] = button_holder,
                ) -> None:
                    previous = {key: target[key] for key in ("word", "reading", "meaning")}
                    for key in previous:
                        target[key] = proposed[key]
                    try:
                        self.store.save(self.words)
                    except (OSError, csv.Error) as error:
                        target.update(previous)
                        messagebox.showerror(
                            "Could not save correction", str(error), parent=self.ui
                        )
                        return
                    if button_holder:
                        button_holder[0].config(text="Applied", state="disabled")

                apply_button = ttk.Button(
                    card,
                    text="Apply corrections" if changed_fields else "No changes needed",
                    command=apply_suggestion,
                    state="normal" if changed_fields else "disabled",
                )
                apply_button.pack(anchor="e", pady=(8, 0))
                button_holder.append(apply_button)

        def check_flagged_words() -> None:
            if not queued_words:
                return
            check_button.config(state="disabled")
            status.config(text=f"Checking {len(queued_words)} word(s)...", fg=self.MUTED)
            words_to_check = [dict(word) for word in queued_words]
            provider = provider_var.get()

            def request_suggestions() -> None:
                try:
                    suggestions = self._get_word_suggestions(words_to_check, provider)
                    error = None
                except Exception as caught_error:
                    suggestions = []
                    error = caught_error

                def finish() -> None:
                    if page_generation != self._page_generation:
                        return
                    if error is not None:
                        status.config(text=str(error), fg="#a33d32")
                        check_button.config(state="normal")
                        return

                    for word in queued_words:
                        word["check_ai"] = "False"
                    try:
                        self.store.save(self.words)
                    except (OSError, csv.Error) as save_error:
                        for word in queued_words:
                            word["check_ai"] = "True"
                        status.config(text=str(save_error), fg="#a33d32")
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

                self.ui.after(0, finish)

            threading.Thread(target=request_suggestions, daemon=True).start()

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

    def _render_review_card(self) -> None:
        word = self.review_words[self.review_index]
        self.review_count.config(
            text=f"{self.review_index + 1} / {len(self.review_words)}"
        )
        self.review_word_label.config(text=word["word"])
        self.review_reading_label.config(text=word["reading"] if self.review_revealed else "")
        self.review_meaning_label.config(text=word["meaning"] if self.review_revealed else "")
        self.review_notes_label.config(
            text=word["notes"] if self.review_revealed and word["notes"] else ""
        )
        self.reveal_button.config(
            text="Hide answer" if self.review_revealed else "Show reading and meaning"
        )

    def _toggle_reveal(self) -> None:
        self.review_revealed = not self.review_revealed
        self._render_review_card()

    def _move_review(self, amount: int) -> None:
        self.review_index = (self.review_index + amount) % len(self.review_words)
        self.review_revealed = False
        self._render_review_card()

    def run(self) -> None:
        self.ui.mainloop()


if __name__ == "__main__":
    app = UI()
    app.run()