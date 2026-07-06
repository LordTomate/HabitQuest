"""Tkinter user interface for HabitQuest with a modern dark theme."""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, simpledialog, ttk

from engine import HabitQuestEngine

# Central color palette for the dark "riced" theme. Keeping every color in one
# place makes it trivial to re-theme the whole app from a single spot.
COLORS = {
    "bg": "#12141c",           # window background
    "surface": "#1b1e2b",      # cards and rows
    "surface_alt": "#252a3d",  # hover / selected state
    "accent": "#7c5cff",       # primary brand color (XP, highlights)
    "accent_soft": "#9d84ff",  # lighter accent for hover
    "text": "#e7e9f0",         # primary text
    "text_muted": "#8b90a5",   # secondary text
    "success": "#3ddc97",      # completed tasks / streak
    "track": "#2a2e40",        # progress bar track
}

# Preferred UI fonts in priority order; the first one installed on the system
# is used, otherwise Tk's built-in default is a safe fallback.
PREFERRED_FONTS = (
    "Inter",
    "Segoe UI",
    "SF Pro Text",
    "Ubuntu",
    "Cantarell",
    "Noto Sans",
    "DejaVu Sans",
)


class HabitQuestApp:
    """Shows today's tasks and delegates state changes to the engine."""

    def __init__(self, root: tk.Tk, engine: HabitQuestEngine | None = None) -> None:
        self.root = root
        self.engine = engine or HabitQuestEngine()

        self.root.title("HabitQuest")
        self.root.geometry("440x640")
        self.root.minsize(400, 560)
        self.root.configure(bg=COLORS["bg"])

        self._setup_fonts()
        self._setup_styles()
        self._build_layout()

        self.refresh_ui()

    # ---- theme setup ----------------------------------------------------

    def _setup_fonts(self) -> None:
        """Pick the nicest available font family and derive named fonts."""
        available = set(tkfont.families(self.root))
        family = next((f for f in PREFERRED_FONTS if f in available), "TkDefaultFont")

        self.font_title = tkfont.Font(family=family, size=20, weight="bold")
        self.font_heading = tkfont.Font(family=family, size=11, weight="bold")
        self.font_stat = tkfont.Font(family=family, size=16, weight="bold")
        self.font_body = tkfont.Font(family=family, size=11)
        self.font_small = tkfont.Font(family=family, size=9)
        self.font_task = tkfont.Font(family=family, size=11)
        self.font_task_done = tkfont.Font(family=family, size=11, overstrike=True)

    def _setup_styles(self) -> None:
        """Configure ttk styles so themed widgets match the dark palette."""
        style = ttk.Style(self.root)
        # "clam" is the ttk theme that allows the most color customization.
        style.theme_use("clam")

        style.configure(
            "Accent.TButton",
            background=COLORS["accent"],
            foreground="#ffffff",
            font=self.font_body,
            borderwidth=0,
            focuscolor=COLORS["accent"],
            padding=(14, 8),
        )
        style.map("Accent.TButton", background=[("active", COLORS["accent_soft"])])

        style.configure(
            "Ghost.TButton",
            background=COLORS["surface_alt"],
            foreground=COLORS["text"],
            font=self.font_body,
            borderwidth=0,
            padding=(14, 8),
        )
        style.map("Ghost.TButton", background=[("active", COLORS["track"])])

    # ---- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        """Assemble the static widget tree once; content is filled on refresh."""
        container = tk.Frame(self.root, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=18, pady=18)

        # Title bar.
        tk.Label(
            container,
            text="\u2694  HabitQuest",
            font=self.font_title,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(anchor="w")

        # Stat cards row (Level / XP / Streak).
        stats = tk.Frame(container, bg=COLORS["bg"])
        stats.pack(fill="x", pady=(14, 0))
        self.level_value = self._make_stat_card(stats, "LEVEL", COLORS["accent_soft"])
        self.xp_value = self._make_stat_card(stats, "XP", COLORS["text"])
        self.streak_value = self._make_stat_card(stats, "STREAK", COLORS["success"])

        # XP progress toward the next level.
        xp_box = tk.Frame(container, bg=COLORS["bg"])
        xp_box.pack(fill="x", pady=(16, 0))
        self.progress_caption = tk.Label(
            xp_box,
            text="",
            font=self.font_small,
            bg=COLORS["bg"],
            fg=COLORS["text_muted"],
        )
        self.progress_caption.pack(anchor="w", pady=(0, 4))
        self.xp_canvas = tk.Canvas(
            xp_box, height=12, bg=COLORS["bg"], highlightthickness=0, bd=0
        )
        self.xp_canvas.pack(fill="x")
        self._xp_fraction = 0.0
        self.xp_canvas.bind("<Configure>", lambda _e: self._draw_xp_bar())

        # "Today" section heading + progress count.
        header = tk.Frame(container, bg=COLORS["bg"])
        header.pack(fill="x", pady=(18, 6))
        tk.Label(
            header,
            text="Today",
            font=self.font_heading,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(side="left")
        self.status_label = tk.Label(
            header,
            text="",
            font=self.font_small,
            bg=COLORS["bg"],
            fg=COLORS["text_muted"],
        )
        self.status_label.pack(side="right")

        # Scrollable task area (handles routines with many tasks).
        self.tasks_frame = self._make_scrollable(container)

        # Footer action buttons.
        footer = tk.Frame(container, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(14, 0))
        ttk.Button(
            footer,
            text="Manage routines",
            style="Ghost.TButton",
            command=self.open_routine_manager,
        ).pack(side="left")
        ttk.Button(
            footer,
            text="Rest day",
            style="Accent.TButton",
            command=self.claim_rest_day,
        ).pack(side="right")

    def _make_stat_card(
        self, parent: tk.Frame, label: str, value_color: str
    ) -> tk.Label:
        """Create one stat tile and return its value Label for later updates."""
        card = tk.Frame(parent, bg=COLORS["surface"])
        card.pack(side="left", expand=True, fill="x", padx=4)
        value = tk.Label(
            card,
            text="-",
            font=self.font_stat,
            bg=COLORS["surface"],
            fg=value_color,
        )
        value.pack(pady=(12, 0))
        tk.Label(
            card,
            text=label,
            font=self.font_small,
            bg=COLORS["surface"],
            fg=COLORS["text_muted"],
        ).pack(pady=(0, 12))
        return value

    def _make_scrollable(self, parent: tk.Frame) -> tk.Frame:
        """Return an inner frame that scrolls vertically inside a canvas."""
        wrapper = tk.Frame(parent, bg=COLORS["bg"])
        wrapper.pack(fill="both", expand=True)

        canvas = tk.Canvas(wrapper, bg=COLORS["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLORS["bg"])

        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Keep the scroll region and inner width in sync with content/size.
        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(window, width=e.width),
        )
        # Mouse wheel scrolling while the window is focused.
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"),
        )

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return inner

    # ---- rendering ------------------------------------------------------

    def refresh_ui(self) -> None:
        """Redraw stats, XP bar, and today's task rows."""
        profile = self.engine.profile
        self.level_value.config(text=str(profile.level))
        self.xp_value.config(text=str(profile.xp))
        # Tk 8.6 cannot render astral-plane emoji, so use a BMP star glyph.
        self.streak_value.config(
            text=f"\u2605 {profile.streak}" if profile.streak else "0"
        )

        self._update_xp_progress()
        self.rebuild_tasks()
        self.refresh_status()

    def _update_xp_progress(self) -> None:
        """Compute progress within the current level and redraw the XP bar."""
        profile = self.engine.profile
        floor = self.engine.total_xp_to_reach_level(profile.level)
        needed = self.engine.xp_for_level(profile.level)
        gained = profile.xp - floor

        self._xp_fraction = max(0.0, min(1.0, gained / needed)) if needed else 0.0
        self.progress_caption.config(
            text=f"{gained} / {needed} XP to level {profile.level + 1}"
        )
        self._draw_xp_bar()

    def _draw_xp_bar(self) -> None:
        """Render the rounded XP progress bar onto its canvas."""
        canvas = self.xp_canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        height = int(canvas["height"])
        if width <= 1:
            return

        radius = height / 2
        # Track (empty portion).
        self._rounded_rect(canvas, 0, 0, width, height, radius, COLORS["track"])
        # Filled portion representing current progress.
        fill_width = radius * 2 + (width - radius * 2) * self._xp_fraction
        if self._xp_fraction > 0:
            self._rounded_rect(
                canvas, 0, 0, fill_width, height, radius, COLORS["accent"]
            )

    @staticmethod
    def _rounded_rect(
        canvas: tk.Canvas,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        r: float,
        color: str,
    ) -> None:
        """Draw a filled rounded rectangle using a smoothed polygon."""
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        canvas.create_polygon(points, fill=color, outline=color, smooth=True)

    def rebuild_tasks(self) -> None:
        """Draw a clickable, grouped row for each task scheduled today."""
        for child in self.tasks_frame.winfo_children():
            child.destroy()

        today_tasks = self.engine.get_today_tasks()
        if not today_tasks:
            tk.Label(
                self.tasks_frame,
                text="No tasks scheduled today. Enjoy the rest!",
                font=self.font_body,
                bg=COLORS["bg"],
                fg=COLORS["text_muted"],
                pady=20,
            ).pack(anchor="w")
            return

        # Group consecutive tasks under a "Routine \u00b7 Category" heading.
        current_group: str | None = None
        for task in today_tasks:
            group = f"{task['routine']} \u00b7 {task['category']}"
            if group != current_group:
                current_group = group
                tk.Label(
                    self.tasks_frame,
                    text=group.upper(),
                    font=self.font_small,
                    bg=COLORS["bg"],
                    fg=COLORS["text_muted"],
                ).pack(anchor="w", pady=(10, 4))

            self._make_task_row(task)

    def _make_task_row(self, task: dict[str, str]) -> None:
        """Build a single hover-highlighting, click-to-toggle task row."""
        done = task["key"] in self.engine.completed_today
        base_bg = COLORS["surface"]
        hover_bg = COLORS["surface_alt"]

        row = tk.Frame(self.tasks_frame, bg=base_bg, cursor="hand2")
        row.pack(fill="x", pady=3)

        check = tk.Label(
            row,
            text="\u2611" if done else "\u2610",
            font=self.font_task,
            bg=base_bg,
            fg=COLORS["success"] if done else COLORS["text_muted"],
        )
        check.pack(side="left", padx=(12, 8), pady=9)

        text = tk.Label(
            row,
            text=task["task"],
            font=self.font_task_done if done else self.font_task,
            bg=base_bg,
            fg=COLORS["text_muted"] if done else COLORS["text"],
            anchor="w",
        )
        text.pack(side="left", fill="x", expand=True, pady=9)

        # Whole row is clickable; bind children so clicks anywhere register.
        widgets = (row, check, text)
        for widget in widgets:
            widget.bind("<Button-1>", lambda _e, k=task["key"]: self.toggle_task(k))
            widget.bind("<Enter>", lambda _e: self._set_row_bg(widgets, hover_bg))
            widget.bind("<Leave>", lambda _e: self._set_row_bg(widgets, base_bg))

    @staticmethod
    def _set_row_bg(widgets: tuple[tk.Widget, ...], color: str) -> None:
        """Apply a background color to every widget in a task row (hover)."""
        for widget in widgets:
            widget.configure(bg=color)

    def refresh_status(self) -> None:
        """Update the 'done / total' counter for today."""
        total_tasks = len(self.engine.get_today_tasks())
        self.status_label.config(
            text=f"{len(self.engine.completed_today)}/{total_tasks} done"
        )

    # ---- actions --------------------------------------------------------

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


if __name__ == "__main__":
    root = tk.Tk()
    app = HabitQuestApp(root)
    root.mainloop()
