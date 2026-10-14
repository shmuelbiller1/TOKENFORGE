"""Optional offline R&D chronology window (separate from regular optimization)."""
from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from research_history import MAX_VERSIONS, compare_revisions, render_history


class ResearchWindow:
    def __init__(self, parent: tk.Misc):
        self.window = tk.Toplevel(parent)
        self.window.title("TokenForge — R&D History")
        self.window.geometry("1000x740")
        self.items: list[tuple[str, str]] = []
        self.report: dict | None = None
        self.events: queue.Queue = queue.Queue()

        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="R&D Revision History", font=("Arial", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer, wraplength=940,
            text=("Add copies of each revision and put them in oldest-to-newest "
                  "order. Comparisons are deterministic and offline. Exact repeated "
                  "extracted passages share an index, but every occurrence is kept. "
                  "Only you can supply reasons or supporting evidence."),
        ).pack(anchor="w", pady=(3, 8))
        project_row = ttk.Frame(outer)
        project_row.pack(fill="x")
        ttk.Label(project_row, text="Project:").pack(side="left")
        self.project = tk.StringVar(value="Research project")
        ttk.Entry(project_row, textvariable=self.project).pack(side="left", padx=8, fill="x", expand=True)

        ttk.Label(outer, text="Revisions (oldest first; select one to move or annotate):").pack(anchor="w", pady=(8, 2))
        file_row = ttk.Frame(outer)
        file_row.pack(fill="x")
        self.file_list = tk.Listbox(file_row, height=7, exportselection=False)
        self.file_list.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(file_row, orient="vertical", command=self.file_list.yview)
        sb.pack(side="left", fill="y")
        self.file_list.configure(yscrollcommand=sb.set)
        actions = ttk.Frame(file_row)
        actions.pack(side="left", padx=8)
        for name, callback in (
            ("Add files", self.add_versions),
            ("Remove", self.remove_version),
            ("Move up", lambda: self.move(-1)),
            ("Move down", lambda: self.move(1)),
            ("Explain change", self.edit_note),
        ):
            ttk.Button(actions, text=name, command=callback).pack(fill="x", pady=2)

        run_row = ttk.Frame(outer)
        run_row.pack(fill="x", pady=8)
        self.run_btn = ttk.Button(run_row, text="Compare revisions", command=self.compare)
        self.run_btn.pack(side="left")
        self.save_txt_btn = ttk.Button(
            run_row, text="Save history TXT", state="disabled", command=self.save_txt)
        self.save_txt_btn.pack(side="left", padx=6)
        self.save_json_btn = ttk.Button(
            run_row, text="Save evidence JSON", state="disabled", command=self.save_json)
        self.save_json_btn.pack(side="left")
        self.status = tk.StringVar(value="Add at least two revisions. No documents are uploaded.")
        ttk.Label(outer, textvariable=self.status, wraplength=940).pack(anchor="w")

        self.output = ScrolledText(outer, wrap="word")
        self.output.pack(fill="both", expand=True, pady=(8, 0))
        self.output.configure(state="disabled")
        self.window.after(100, self.poll)

    def _selected(self) -> int | None:
        selection = self.file_list.curselection()
        return selection[0] if selection else None

    def _show(self, index: int | None = None) -> None:
        self.file_list.delete(0, "end")
        for i, (path, note) in enumerate(self.items, 1):
            preview = note.replace("\n", " ").strip()[:85]
            self.file_list.insert(
                "end",
                f"{i:>2}. {Path(path).name}" +
                (f"  | {preview}" if preview else ""),
            )
        if index is not None and 0 <= index < len(self.items):
            self.file_list.selection_set(index)
            self.file_list.see(index)
        self._invalidate()

    def _invalidate(self) -> None:
        self.report = None
        self.save_txt_btn.configure(state="disabled")
        self.save_json_btn.configure(state="disabled")
        self.status.set("Comparison needs to be run or rerun after any change.")

    def add_versions(self) -> None:
        files = filedialog.askopenfilenames(
            parent=self.window, title="Add research revision files")
        if not files:
            return
        if len(files) + len(self.items) > MAX_VERSIONS:
            return messagebox.showerror(
                "Too many versions", f"Maximum is {MAX_VERSIONS} files.", parent=self.window)
        self.items.extend((str(p), "") for p in files)
        self._show(len(self.items) - 1)

    def remove_version(self) -> None:
        index = self._selected()
        if index is not None:
            self.items.pop(index)
            self._show(min(index, len(self.items) - 1))

    def move(self, offset: int) -> None:
        index = self._selected()
        if index is None or not 0 <= index + offset < len(self.items):
            return
        self.items[index], self.items[index + offset] = self.items[index + offset], self.items[index]
        self._show(index + offset)

    def edit_note(self) -> None:
        index = self._selected()
        if index is None:
            return
        path, old = self.items[index]
        note = simpledialog.askstring(
            "Researcher-supplied reason or evidence",
            "State what changed and WHY (write 'unknown' if not established). "
            "This text will be labeled as your note, not a verified conclusion.",
            parent=self.window, initialvalue=old,
        )
        if note is not None:
            self.items[index] = path, note
            self._show(index)

    def compare(self) -> None:
        if len(self.items) < 2:
            return messagebox.showerror(
                "Select revisions", "Please add at least two versions.", parent=self.window)
        self.run_btn.configure(state="disabled")
        self._invalidate()
        self.status.set("Comparing local copies without altering the source documents...")
        paths = [p for p, _ in self.items]
        notes = [note for _, note in self.items]
        project = self.project.get()

        def worker() -> None:
            try:
                report = compare_revisions(paths, project=project, notes=notes)
                self.events.put(("ok", report))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self) -> None:
        if not self.window.winfo_exists():
            return
        try:
            while True:
                status, value = self.events.get_nowait()
                self.run_btn.configure(state="normal")
                if status == "error":
                    self.status.set("Comparison failed.")
                    messagebox.showerror("R&D comparison", value, parent=self.window)
                    continue
                self.report = value
                self.output.configure(state="normal")
                self.output.delete("1.0", "end")
                self.output.insert("end", render_history(value))
                self.output.configure(state="disabled")
                self.save_txt_btn.configure(state="normal")
                self.save_json_btn.configure(state="normal")
                self.status.set(
                    f"{len(value['versions'])} versions; "
                    f"{len(value['comparisons'])} chronological comparisons; "
                    f"{value['exact_repetitions']['repeated_extracted_passages']} "
                    "exact repeated extracted passages; "
                    f"{value['exact_sentence_candidates']['repeated_candidates']} "
                    "exact sentence candidates. Review evidence before using it.")
        except queue.Empty:
            pass
        self.window.after(100, self.poll)

    def save_txt(self) -> None:
        if self.report is None:
            return
        dest = filedialog.asksaveasfilename(
            parent=self.window, defaultextension=".txt",
            filetypes=[("Text", "*.txt")], title="Save R&D comparison")
        if dest:
            Path(dest).write_text(render_history(self.report), encoding="utf-8")

    def save_json(self) -> None:
        if self.report is None:
            return
        dest = filedialog.asksaveasfilename(
            parent=self.window, defaultextension=".json",
            filetypes=[("JSON", "*.json")], title="Save verifiable R&D evidence")
        if dest:
            Path(dest).write_text(
                json.dumps(self.report, indent=2, ensure_ascii=False), encoding="utf-8")
