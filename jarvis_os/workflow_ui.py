"""Desktop workflow library and editor."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk


class WorkflowWindow(tk.Toplevel):
    def __init__(self, parent, engine):
        super().__init__(parent)
        self.engine = engine
        self.repository = engine.repository
        self.title("J.A.R.V.I.S Workflows")
        self.geometry("900x620")
        self.transient(parent)
        self._build()
        self.refresh()

    def _build(self):
        left = ttk.Frame(self, padding=12)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Workflow library", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 8))
        self.listbox = tk.Listbox(left, width=30, height=25)
        self.listbox.pack(fill="y", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.load_selected)
        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=8)
        ttk.Button(controls, text="New", command=self.new).pack(side="left")
        ttk.Button(controls, text="Run", command=self.run_selected).pack(side="left", padx=5)
        ttk.Button(controls, text="Delete", command=self.delete_selected).pack(side="left")

        form = ttk.Frame(self, padding=16)
        form.pack(side="left", fill="both", expand=True)
        ttk.Label(form, text="Name").pack(anchor="w")
        self.name = ttk.Entry(form)
        self.name.pack(fill="x", pady=(2, 10))
        ttk.Label(form, text="Trigger").pack(anchor="w")
        self.trigger_type = ttk.Combobox(form, values=("manual", "voice", "daily"), state="readonly")
        self.trigger_type.set("voice")
        self.trigger_type.pack(fill="x", pady=(2, 8))
        ttk.Label(form, text="Voice phrase or daily time (HH:MM)").pack(anchor="w")
        self.trigger_value = ttk.Entry(form)
        self.trigger_value.pack(fill="x", pady=(2, 10))
        ttk.Label(form, text="Steps (JSON list)").pack(anchor="w")
        self.steps = tk.Text(form, height=17, wrap="none", font=("Consolas", 10))
        self.steps.pack(fill="both", expand=True, pady=(2, 8))
        self.steps.insert("1.0", '[\n  {"action": "open_app", "arguments": {"name": "notepad"}}\n]')
        ttk.Label(
            form,
            text='Step types: action, delay {"type":"delay","seconds":2}, condition {"type":"condition","setting":"privacy_mode","equals":false}',
            wraplength=570,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Button(form, text="Save workflow", command=self.save).pack(anchor="e")
        self.selected_id = None

    def refresh(self):
        self.items = self.repository.all()
        self.listbox.delete(0, "end")
        for workflow in self.items:
            self.listbox.insert("end", workflow.name + ("" if workflow.enabled else " (disabled)"))

    def new(self):
        self.selected_id = None
        self.name.delete(0, "end")
        self.trigger_type.set("voice")
        self.trigger_value.delete(0, "end")
        self.steps.delete("1.0", "end")
        self.steps.insert("1.0", '[\n  {"action": "open_app", "arguments": {"name": "notepad"}}\n]')

    def load_selected(self, _event=None):
        selection = self.listbox.curselection()
        if not selection:
            return
        workflow = self.items[selection[0]]
        self.selected_id = workflow.id
        self.name.delete(0, "end"); self.name.insert(0, workflow.name)
        self.trigger_type.set(workflow.trigger.get("type", "manual"))
        value = workflow.trigger.get("phrase", workflow.trigger.get("time", ""))
        self.trigger_value.delete(0, "end"); self.trigger_value.insert(0, value)
        self.steps.delete("1.0", "end"); self.steps.insert("1.0", json.dumps(workflow.steps, indent=2))

    def save(self):
        try:
            steps = json.loads(self.steps.get("1.0", "end").strip())
            trigger_type = self.trigger_type.get()
            trigger = {"type": trigger_type}
            if trigger_type == "voice":
                trigger["phrase"] = self.trigger_value.get().strip()
            elif trigger_type == "daily":
                trigger["time"] = self.trigger_value.get().strip()
            if self.selected_id:
                from .workflows import Workflow
                workflow = Workflow(self.selected_id, self.name.get().strip(), trigger, steps)
                self.repository.validate(workflow)
                self.repository.save(workflow)
            else:
                self.repository.create(self.name.get(), trigger, steps)
            self.refresh()
            messagebox.showinfo("Workflows", "Workflow saved.", parent=self)
        except Exception as exc:
            messagebox.showerror("Invalid workflow", str(exc), parent=self)

    def run_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        workflow = self.items[selection[0]]
        threading.Thread(target=self._run, args=(workflow,), daemon=True).start()

    def _run(self, workflow):
        result = self.engine.run(workflow)
        self.after(0, lambda: messagebox.showinfo("Workflow result", result.message, parent=self))

    def delete_selected(self):
        selection = self.listbox.curselection()
        if selection and messagebox.askyesno("Delete workflow", "Delete the selected workflow?", parent=self):
            self.repository.delete(self.items[selection[0]].id)
            self.refresh()
