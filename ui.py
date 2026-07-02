"""Tkinter user interface for HabitQuest."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from engine import HabitQuestEngine


class HabitQuestApp:
    """Shows today's tasks and delegates state changes to the engine."""

    def __init__(self, root: tk.Tk, engine: HabitQuestEngine | None = None) -> None:
        self.root = root
        self.engine = engine or HabitQuestEngine()

        self.root.title("HabitQuest")
        self.root.geometry("360x320")

        self.summary_label = ttk.Label(
            root, text="", font=("TkDefaultFont", 11, "bold")
        )
        self.status_label = ttk.Label(root, text="")
        self.tasks_frame = ttk.Frame(root, padding=10)
        self.buttons_frame = ttk.Frame(root, padding=(10, 0, 10, 10))
        self.manage_routines_button = ttk.Button(
            self.buttons_frame,
            text="Manage routines",
            command=self.open_routine_manager,
        )
        self.rest_button = ttk.Button(
            self.buttons_frame, text="Rest day", command=self.claim_rest_day
        )

        self.summary_label.pack(pady=(10, 0))
        self.status_label.pack(pady=(10, 0))
        self.tasks_frame.pack(fill="both", expand=True)
        self.buttons_frame.pack(fill="x")
        self.manage_routines_button.pack(side="left")
        self.rest_button.pack(side="right")

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
            ttk.Label(self.tasks_frame, text="No tasks scheduled today.").pack(
                anchor="w"
            )
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

    def open_routine_manager(self) -> None:
        """Open a small window for adding and editing routines."""
        window = tk.Toplevel(self.root)
        window.title("Manage routines")
        window.geometry("460x320")
        window.transient(self.root)

        ttk.Label(
            window,
            text="Routines",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 0))

        routines_listbox = tk.Listbox(window, height=10)
        routines_listbox.pack(fill="both", expand=True, padx=10, pady=8)

        buttons = ttk.Frame(window)
        buttons.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(
            buttons,
            text="Add routine",
            command=lambda: self.add_routine_from_dialog(routines_listbox),
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Edit selected",
            command=lambda: self.edit_selected_routine(routines_listbox),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")

        self.refresh_routine_listbox(routines_listbox)

    def refresh_routine_listbox(self, routines_listbox: tk.Listbox) -> None:
        """Refresh the routine names shown in the manager window."""
        routines_listbox.delete(0, tk.END)
        for routine_name in sorted(self.engine.routines.keys()):
            routines_listbox.insert(tk.END, routine_name)

    def add_routine_from_dialog(self, routines_listbox: tk.Listbox) -> None:
        """Create a new routine from user-provided dialog input."""
        routine_data = self.ask_routine_data("Add routine")
        if routine_data is None:
            return

        routine_name, categories = routine_data
        try:
            self.engine.add_routine(routine_name, categories)
        except (TypeError, ValueError) as error:
            messagebox.showerror("Cannot add routine", str(error), parent=self.root)
            return

        self.refresh_routine_listbox(routines_listbox)
        self.refresh_ui()

    def edit_selected_routine(self, routines_listbox: tk.Listbox) -> None:
        """Edit the selected routine's name and category task plan."""
        selected = routines_listbox.curselection()
        if not selected:
            messagebox.showinfo(
                "Select a routine",
                "Please select a routine to edit.",
                parent=self.root,
            )
            return

        current_name = routines_listbox.get(selected[0])
        routine = self.engine.routines[current_name]
        category_text = self.serialize_categories_for_input(routine)
        routine_data = self.ask_routine_data(
            "Edit routine",
            initial_name=current_name,
            initial_categories_text=category_text,
        )
        if routine_data is None:
            return

        new_name, categories = routine_data
        try:
            self.engine.update_routine(current_name, new_name, categories)
        except (TypeError, ValueError) as error:
            messagebox.showerror("Cannot edit routine", str(error), parent=self.root)
            return

        self.refresh_routine_listbox(routines_listbox)
        self.refresh_ui()

    def ask_routine_data(
        self,
        title: str,
        initial_name: str = "",
        initial_categories_text: str = "",
    ) -> tuple[str, list[tuple[str, list[str]]]] | None:
        """Ask user for routine name and category/task definition text."""
        name = simpledialog.askstring(
            title,
            "Routine name:",
            initialvalue=initial_name,
            parent=self.root,
        )
        if name is None:
            return None

        categories_text = simpledialog.askstring(
            title,
            (
                "Categories and tasks (format):\n"
                "Push: Bench Press, Overhead Press; Pull: Rows, Biceps"
            ),
            initialvalue=initial_categories_text,
            parent=self.root,
        )
        if categories_text is None:
            return None

        categories = self.parse_categories_input(categories_text)
        return name, categories

    @staticmethod
    def parse_categories_input(text: str) -> list[tuple[str, list[str]]]:
        """Parse 'Category: task1, task2; ...' text into category tuples."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Please provide at least one category and task.")

        categories: list[tuple[str, list[str]]] = []
        for chunk in text.split(";"):
            item = chunk.strip()
            if not item:
                continue
            if ":" not in item:
                raise ValueError(
                    "Invalid format. Use 'Category: task1, task2; Category2: task3'."
                )
            category_name, task_text = item.split(":", 1)
            category_name = category_name.strip()
            task_names = [task.strip() for task in task_text.split(",") if task.strip()]
            if not category_name or not task_names:
                raise ValueError(
                    "Every category must have a name and at least one task."
                )
            categories.append((category_name, task_names))

        if not categories:
            raise ValueError("Please provide at least one valid category.")
        return categories

    @staticmethod
    def serialize_categories_for_input(routine: object) -> str:
        """Convert routine categories into dialog text format."""
        categories = getattr(routine, "categories", [])
        return "; ".join(
            f"{category.name}: {', '.join(category.tasks)}" for category in categories
        )

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
