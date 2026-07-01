"""Tkinter user interface for HabitQuest."""

import tkinter as tk
from tkinter import ttk

from engine import HabitQuestEngine


class HabitQuestApp:
    """Shows today's tasks and delegates state changes to the engine."""

    def __init__(self, root: tk.Tk, engine: HabitQuestEngine | None = None) -> None:
        self.root = root
        self.engine = engine or HabitQuestEngine()

        self.root.title("HabitQuest")
        self.root.geometry("360x320")

        self.summary_label = ttk.Label(root, text="", font=("TkDefaultFont", 11, "bold"))
        self.status_label = ttk.Label(root, text="")
        self.tasks_frame = ttk.Frame(root, padding=10)
        self.rest_button = ttk.Button(root, text="Rest day", command=self.claim_rest_day)

        self.summary_label.pack(pady=(10, 0))
        self.status_label.pack(pady=(10, 0))
        self.tasks_frame.pack(fill="both", expand=True)
        self.rest_button.pack(pady=(0, 10))

        self.refresh_ui()

    def refresh_ui(self) -> None:
        """Redraw labels and today's task checkboxes."""
        self.summary_label.config(
            text=(
                f"Level {self.engine.profile.level} | "
                f"{self.engine.profile.xp} XP | "
                f"Streak {self.engine.profile.streak}"
            )
        )
        self.rebuild_tasks()
        self.refresh_status()

    def rebuild_tasks(self) -> None:
        """Draw a checkbox for each task scheduled today."""
        for child in self.tasks_frame.winfo_children():
            child.destroy()

        today_tasks = self.engine.get_today_tasks()
        if not today_tasks:
            ttk.Label(self.tasks_frame, text="No tasks scheduled today.").pack(anchor="w")
            return

        for task in today_tasks:
            var = tk.BooleanVar(value=task["key"] in self.engine.completed_today)
            checkbox = ttk.Checkbutton(
                self.tasks_frame,
                text=f"{task['category']}: {task['task']}",
                variable=var,
                command=lambda key=task["key"]: self.toggle_task(key),
            )
            checkbox.pack(anchor="w")

    def toggle_task(self, task_key: str) -> None:
        """Toggle a task in the engine and refresh the screen."""
        self.engine.toggle_task(task_key)
        self.refresh_ui()

    def claim_rest_day(self) -> None:
        """Protect today's streak as a rest day and refresh the screen."""
        self.engine.claim_rest_day()
        self.refresh_ui()

    def refresh_status(self) -> None:
        """Update the daily progress label."""
        total_tasks = len(self.engine.get_today_tasks())
        self.status_label.config(
            text=f"{len(self.engine.completed_today)}/{total_tasks} tasks done today"
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = HabitQuestApp(root)
    root.mainloop()
