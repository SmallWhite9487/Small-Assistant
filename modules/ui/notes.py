import tkinter as tk
from tkinter import messagebox, ttk


class NotesPageMixin:
    """Free-form notes, each stored as a txt file in the Notes folder."""

    def show_notes(self) -> None:
        self._clear_content()
        self._heading("Notes", "Write anything down. Each note is saved as a .txt file.")
        self.current_note = None

        body = tk.Frame(self.content, bg=self.BACKGROUND)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=self.BACKGROUND)
        left.pack(side="left", fill="y", padx=(0, 16))
        self.note_list = tk.Listbox(
            left,
            width=26,
            activestyle="none",
            exportselection=False,
            bg=self.SURFACE,
            fg=self.INK,
            highlightthickness=0,
            selectbackground=self.GREEN,
            selectforeground="#ffffff",
        )
        self.note_list.pack(fill="y", expand=True)
        self.note_list.bind("<<ListboxSelect>>", self._open_selected_note)
        ttk.Button(left, text="＋  New note", command=self._new_note).pack(
            fill="x", pady=(10, 0)
        )

        right = tk.Frame(body, bg=self.BACKGROUND)
        right.pack(side="left", fill="both", expand=True)
        self.note_title_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.note_title_var).pack(fill="x", ipady=5)
        text_frame = tk.Frame(right, bg=self.SURFACE)
        text_frame.pack(fill="both", expand=True, pady=10)
        self.note_text = tk.Text(
            text_frame, wrap="word", undo=True, bg=self.SURFACE, fg=self.INK,
            relief="flat", padx=10, pady=10,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.note_text.yview)
        self.note_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.note_text.pack(side="left", fill="both", expand=True)
        actions = tk.Frame(right, bg=self.BACKGROUND)
        actions.pack(fill="x")
        ttk.Button(
            actions, text="Save", style="Accent.TButton", command=self._save_note
        ).pack(side="left")
        ttk.Button(actions, text="Delete", command=self._delete_note).pack(
            side="left", padx=(8, 0)
        )
        self._refresh_note_list()

    def _refresh_note_list(self, select: str | None = None) -> None:
        try:
            self.note_items = self.notes.list_notes()
        except OSError as error:
            self.note_items = []
            messagebox.showerror("Could not read notes", str(error), parent=self.ui)
        self.note_list.delete(0, "end")
        for index, note in enumerate(self.note_items):
            self.note_list.insert("end", f"{note['title']}  ·  {note['date']}")
            if note["name"] == select:
                self.note_list.selection_set(index)

    def _new_note(self) -> None:
        self.current_note = None
        self.note_list.selection_clear(0, "end")
        self.note_title_var.set("")
        self.note_text.delete("1.0", "end")

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
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", content)

    def _save_note(self) -> None:
        content = self.note_text.get("1.0", "end-1c")
        try:
            name = self.notes.save(self.note_title_var.get(), content, self.current_note)
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not save note", str(error), parent=self.ui)
            return
        self.current_note = name
        self._refresh_note_list(select=name)

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
