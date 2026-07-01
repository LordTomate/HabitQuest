"""HabitQuest UI (minimal prototype).

Self-contained first pass at the interface, built to click through and test by hand
before any data model or persistence logic exists. Task data is hardcoded here for
now; nothing is saved between runs.
"""

import tkinter as tk
from tkinter import ttk

# Hardcoded sample tasks for today - will later come from a Routine/engine instead.
SAMPLE_TASKS = ["Bench Press", "Overhead Press", "Triceps"]


class HabitQuestApp:
    """Shows today's tasks as checkboxes and tracks how many are done."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.completed: set[str] = set()

        self.root.title("HabitQuest")
        self.status_label = ttk.Label(root, text="")
        self.tasks_frame = ttk.Frame(root, padding=10)

        self.status_label.pack(pady=(10, 0))
        self.tasks_frame.pack(fill="both", expand=True)

        self.build_tasks()

    def build_tasks(self) -> None:
        """Draw a checkbox for each task in SAMPLE_TASKS."""
        for task in SAMPLE_TASKS:
            var = tk.BooleanVar(value=task in self.completed)
            checkbox = ttk.Checkbutton(
                self.tasks_frame,
                text=task,
                variable=var,
                command=lambda t=task, v=var: self.toggle_task(t, v),
            )
            checkbox.pack(anchor="w")

        self.refresh_status()

    def toggle_task(self, task: str, var: tk.BooleanVar) -> None:
        """Mark a task done/undone and refresh the status label."""
        if var.get():
            self.completed.add(task)
        else:
            self.completed.discard(task)
        self.refresh_status()

    def refresh_status(self) -> None:
        """Update the "done so far" label."""
        self.status_label.config(
            text=f"{len(self.completed)}/{len(SAMPLE_TASKS)} tasks done today"
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = HabitQuestApp(root)
    root.mainloop()
