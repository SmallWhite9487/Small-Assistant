import csv
import tkinter as tk
import uuid
from datetime import date
from tkinter import messagebox, ttk


class WordFormMixin:
    """Add / edit word page."""

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
