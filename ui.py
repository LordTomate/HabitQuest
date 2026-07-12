"""Tkinter user interface for HabitQuest with a modern dark theme."""

import os
import shutil
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from tkinter import messagebox, ttk

from engine import HabitQuestEngine

# Directory holding bundled images (mascot / icon). Resolved relative to this
# file so the app works no matter what the current working directory is.
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
MASCOT_FILE = "mascot.png"

# Pixels reserved at the bottom of the screen when maximizing the borderless
# WSLg window, so the footer buttons stay clear of the OS taskbar.
TASKBAR_MARGIN = 48

# Central color palette for the dark "riced" theme. Keeping every color in one
# place makes it trivial to re-theme the whole app from a single spot.
COLORS = {
    "bg": "#12141c",  # window background
    "surface": "#1b1e2b",  # cards and rows
    "surface_alt": "#252a3d",  # hover / selected state
    "accent": "#7c5cff",  # primary brand color (XP, highlights)
    "accent_soft": "#9d84ff",  # lighter accent for hover
    "text": "#e7e9f0",  # primary text
    "text_muted": "#8b90a5",  # secondary text
    "success": "#3ddc97",  # completed tasks / streak
    "track": "#2a2e40",  # progress bar track
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


def _x11_window_ids(window: tk.Tk | tk.Toplevel) -> list[str]:
    """Return Tk's X11 window ID followed by up to two native parents."""
    window_ids = [hex(window.winfo_id())]
    xwininfo = shutil.which("xwininfo")
    if xwininfo is None:
        return window_ids

    current_id = window_ids[0]
    for _level in range(2):
        try:
            result = subprocess.run(
                [xwininfo, "-id", current_id, "-tree"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1,
            )
        except (OSError, subprocess.SubprocessError):
            break

        parent_id = ""
        for line in result.stdout.splitlines():
            if "Parent window id:" in line:
                parent_id = line.split("Parent window id:", 1)[1].split()[0]
                break
        if not parent_id or parent_id in window_ids:
            break
        window_ids.append(parent_id)
        current_id = parent_id

    return window_ids


def _is_wslg() -> bool:
    """Return whether the app is running through WSLg."""
    return bool(os.environ.get("WSL_DISTRO_NAME") and os.environ.get("WAYLAND_DISPLAY"))


def force_dark_window_decorations(window: tk.Tk | tk.Toplevel) -> bool:
    """Ask the operating system to draw a dark title bar and border.

    Tk does not expose native decoration colors. Windows provides a DWM
    attribute, while Linux compositors commonly honor `_GTK_THEME_VARIANT`.
    Unsupported systems quietly keep their default decorations.
    """
    window.update_idletasks()

    if sys.platform == "win32":
        try:
            import ctypes

            window_id = window.winfo_id()
            handle = ctypes.windll.user32.GetParent(window_id) or window_id
            enabled = ctypes.c_int(1)
            # Attribute 20 is current; 19 supports older Windows 10 builds.
            for attribute in (20, 19):
                result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    handle,
                    attribute,
                    ctypes.byref(enabled),
                    ctypes.sizeof(enabled),
                )
                if result == 0:
                    return True
        except (AttributeError, OSError, tk.TclError):
            return False
        return False

    try:
        if window.tk.call("tk", "windowingsystem") != "x11":
            return False
        xprop = shutil.which("xprop")
        if xprop is None:
            return False
        applied = False
        # WSLg decorates parent windows rather than Tk's inner widget window.
        for window_id in _x11_window_ids(window):
            result = subprocess.run(
                [
                    xprop,
                    "-id",
                    window_id,
                    "-f",
                    "_GTK_THEME_VARIANT",
                    "8u",
                    "-set",
                    "_GTK_THEME_VARIANT",
                    "dark",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
            applied = result.returncode == 0 or applied
        return applied
    except (OSError, subprocess.SubprocessError, tk.TclError):
        return False


class HabitQuestApp:
    """Shows today's tasks and delegates state changes to the engine."""

    def __init__(self, root: tk.Tk, engine: HabitQuestEngine | None = None) -> None:
        self.root = root
        self.engine = engine or HabitQuestEngine()
        self.uses_custom_decorations = _is_wslg()
        self._drag_offset = (0, 0)
        self._is_maximized = False
        self._restore_geometry = ""
        self._restore_custom_chrome_on_map = False

        self.root.title("HabitQuest")
        self.root.geometry("440x674" if self.uses_custom_decorations else "440x640")
        self.root.minsize(400, 594 if self.uses_custom_decorations else 560)
        self.root.configure(
            bg=COLORS["track"] if self.uses_custom_decorations else COLORS["bg"]
        )
        if self.uses_custom_decorations:
            self.root.overrideredirect(True)

        self._setup_fonts()
        self._setup_styles()
        self._load_images()
        self._build_window_chrome()
        self._build_layout()

        self.refresh_ui()
        if self.uses_custom_decorations:
            # Borderless WSLg windows are unmanaged by the compositor, so they
            # are not auto-placed or focused and default to the +0+0 corner,
            # where they hide behind other windows. Center and raise the window
            # so it reliably appears in front.
            self._center_on_screen()
        else:
            force_dark_window_decorations(self.root)

        # Raise the window above other applications on launch regardless of the
        # decoration mode, otherwise it can open hidden behind the editor.
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def _center_on_screen(self) -> None:
        """Place the window in the middle of the screen.

        Unmanaged (overrideredirect) WSLg windows default to +0+0, which can
        leave them hidden behind other windows. Centering gives a reliable,
        visible placement.
        """
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = max((self.root.winfo_screenwidth() - width) // 2, 0)
        y = max((self.root.winfo_screenheight() - height) // 2, 0)
        self.root.geometry(f"+{x}+{y}")

    # ---- theme setup ----------------------------------------------------

    def _load_images(self) -> None:
        """Load the mascot artwork and use it as window/taskbar icon.

        Tk keeps only a weak reference to PhotoImages, so we store them on
        the instance to stop them from being garbage-collected (which would
        make the pictures disappear). If the file is missing we degrade
        gracefully to the text-only UI instead of crashing.
        """
        self.mascot_image = None
        self.icon_image = None
        path = os.path.join(ASSET_DIR, MASCOT_FILE)
        if not os.path.exists(path):
            return

        try:
            original = tk.PhotoImage(file=path)
        except tk.TclError:
            # Unsupported format or corrupt file: skip the imagery quietly.
            return

        # PhotoImage.subsample only shrinks by whole-number factors, so we
        # round to the nearest factor that lands near the desired pixel size.
        self.mascot_image = self._subsample_to(original, target_width=56)
        self.icon_image = self._subsample_to(original, target_width=64)
        # Set the icon for the title bar / taskbar (True => also for children).
        self.root.iconphoto(True, self.icon_image)

    @staticmethod
    def _subsample_to(image: tk.PhotoImage, target_width: int) -> tk.PhotoImage:
        """Return a copy of `image` scaled down close to `target_width` px."""
        factor = max(1, round(image.width() / target_width))
        return image.subsample(factor, factor) if factor > 1 else image

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

        # Dark vertical scrollbar that blends into the window instead of the
        # bright default. "clam" lets us recolor the trough, thumb, and arrows.
        style.configure(
            "Dark.Vertical.TScrollbar",
            background=COLORS["surface_alt"],  # the draggable thumb
            troughcolor=COLORS["bg"],  # the track behind the thumb
            bordercolor=COLORS["bg"],
            arrowcolor=COLORS["text_muted"],
            borderwidth=0,
        )
        style.map(
            "Dark.Vertical.TScrollbar",
            background=[("active", COLORS["track"])],
        )

    def _build_window_chrome(self) -> None:
        """Build a dark draggable title bar when WSLg ignores theme hints."""
        self.content_root: tk.Misc = self.root
        if not self.uses_custom_decorations:
            return

        title_bar = tk.Frame(
            self.root,
            height=34,
            bg=COLORS["surface"],
            cursor="fleur",
        )
        title_bar.pack(fill="x", padx=1, pady=(1, 0))
        title_bar.pack_propagate(False)

        title_label = tk.Label(
            title_bar,
            text="HabitQuest",
            font=self.font_small,
            bg=COLORS["surface"],
            fg=COLORS["text"],
        )
        title_label.pack(side="left", padx=12)

        def make_control(
            text: str,
            command: Callable[[], None],
            hover_background: str = COLORS["surface_alt"],
        ) -> tk.Button:
            """Add one native-like control to the custom title bar."""
            button = tk.Button(
                title_bar,
                text=text,
                command=command,
                font=self.font_body,
                bg=COLORS["surface"],
                fg=COLORS["text_muted"],
                activebackground=hover_background,
                activeforeground="#ffffff",
                relief="flat",
                borderwidth=0,
                width=4,
                cursor="arrow",
            )
            button.pack(side="right", fill="y")
            button.bind("<Enter>", lambda _event: button.configure(bg=hover_background))
            button.bind(
                "<Leave>", lambda _event: button.configure(bg=COLORS["surface"])
            )
            return button

        make_control("×", self.root.destroy, "#c42b1c")
        self.maximize_button = make_control("□", self._toggle_maximize)
        make_control("−", self._minimize_window)

        for widget in (title_bar, title_label):
            widget.bind("<ButtonPress-1>", self._start_window_drag)
            widget.bind("<B1-Motion>", self._drag_window)
            widget.bind("<Double-Button-1>", lambda _event: self._toggle_maximize())
        self.root.bind("<Map>", self._restore_custom_chrome)

        self.content_root = tk.Frame(self.root, bg=COLORS["bg"])
        self.content_root.pack(fill="both", expand=True, padx=1, pady=(0, 1))

    def _start_window_drag(self, event: tk.Event) -> None:
        """Remember the pointer offset used to drag custom WSLg chrome."""
        if self._is_maximized:
            pointer_fraction = event.x_root / max(self.root.winfo_width(), 1)
            self._toggle_maximize()
            self.root.update_idletasks()
            self.root.geometry(
                f"+{round(event.x_root - self.root.winfo_width() * pointer_fraction)}"
                f"+{max(event.y_root - 16, 0)}"
            )
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )

    def _drag_window(self, event: tk.Event) -> None:
        """Move the custom-decorated WSLg window with the pointer."""
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _toggle_maximize(self) -> None:
        """Toggle custom WSLg chrome between maximized and restored sizes."""
        if self._is_maximized:
            self.root.geometry(self._restore_geometry)
        else:
            self._restore_geometry = self.root.geometry()
            # Leave room for the OS taskbar so the footer buttons stay on-screen
            # and clickable; a borderless window sized to the full screen height
            # extends behind the taskbar.
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight() - TASKBAR_MARGIN
            self.root.geometry(f"{width}x{height}+0+0")
        self._is_maximized = not self._is_maximized
        self.maximize_button.configure(text="❐" if self._is_maximized else "□")

    def _minimize_window(self) -> None:
        """Keep native management active while WSLg is minimized."""
        self._restore_custom_chrome_on_map = True
        self.root.overrideredirect(False)
        self.root.iconify()

    def _restore_custom_chrome(self, event: tk.Event) -> None:
        """Reapply custom chrome after WSLg restores a minimized window."""
        if event.widget is not self.root or not self._restore_custom_chrome_on_map:
            return
        self._restore_custom_chrome_on_map = False
        self.root.after_idle(lambda: self.root.overrideredirect(True))

    def _prepare_toplevel(self, window: tk.Toplevel) -> None:
        """Apply the appropriate native or WSLg decoration treatment."""
        if self.uses_custom_decorations:
            window.overrideredirect(True)
        else:
            force_dark_window_decorations(window)

    # ---- layout ---------------------------------------------------------

    def _build_layout(self) -> None:
        """Assemble the static widget tree once; content is filled on refresh."""
        container = tk.Frame(self.content_root, bg=COLORS["bg"])
        container.pack(fill="both", expand=True, padx=18, pady=18)

        # Title bar: mascot artwork (if available) alongside the app name.
        title_bar = tk.Frame(container, bg=COLORS["bg"])
        title_bar.pack(fill="x")
        if self.mascot_image is not None:
            tk.Label(
                title_bar,
                image=self.mascot_image,
                bg=COLORS["bg"],
            ).pack(side="left", padx=(0, 10))
        tk.Label(
            title_bar,
            text="HabitQuest",
            font=self.font_title,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(side="left")

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

        # Footer action buttons. Anchored to the bottom so they always keep
        # their slot even when the task list grows tall.
        footer = tk.Frame(container, bg=COLORS["bg"])
        footer.pack(side="bottom", fill="x", pady=(14, 0))
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
        scrollbar = ttk.Scrollbar(
            wrapper,
            orient="vertical",
            command=canvas.yview,
            style="Dark.Vertical.TScrollbar",
        )
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
        canvas.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))

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
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1,
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
        cycle_by_routine = {
            info["routine"]: info for info in self.engine.get_cycle_overview()
        }
        current_group: str | None = None
        for task in today_tasks:
            group = f"{task['routine']} \u00b7 {task['category']}"
            if group != current_group:
                current_group = group
                self._make_group_header(task, cycle_by_routine.get(task["routine"]))

            self._make_task_row(task)

    def _make_group_header(
        self, task: dict[str, str], cycle: dict[str, object] | None
    ) -> None:
        """Render a routine/category heading with its cycle position and preview."""
        header = tk.Frame(self.tasks_frame, bg=COLORS["bg"])
        header.pack(fill="x", pady=(10, 4))

        tk.Label(
            header,
            text=f"{task['routine']} \u00b7 {task['category']}".upper(),
            font=self.font_small,
            bg=COLORS["bg"],
            fg=COLORS["text_muted"],
        ).pack(side="left")

        if cycle:
            # Show where today sits in the rotation, e.g. "DAY 1/3".
            tk.Label(
                header,
                text=f"DAY {cycle['position']}/{cycle['length']}",
                font=self.font_small,
                bg=COLORS["bg"],
                fg=COLORS["accent_soft"],
            ).pack(side="right")

        upcoming = cycle["upcoming"] if cycle else []
        if upcoming:
            # Spell out the next categories so the cycle order is obvious.
            preview = "  \u2192  ".join(str(name) for name in upcoming)
            tk.Label(
                self.tasks_frame,
                text=f"Next: {preview}",
                font=self.font_small,
                bg=COLORS["bg"],
                fg=COLORS["text_muted"],
                anchor="w",
            ).pack(anchor="w", pady=(0, 2))

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
        """Protect today's streak as a rest day and show graphical feedback."""
        claimed = self.engine.claim_rest_day()
        self.refresh_ui()
        self._show_rest_dialog(claimed)

    def _show_rest_dialog(self, claimed: bool) -> None:
        """Show a themed popup celebrating (or noting) the rest day."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Rest day")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.resizable(False, False)

        frame = tk.Frame(dialog, bg=COLORS["bg"])
        frame.pack(fill="both", expand=True, padx=32, pady=26)

        # Large crescent-moon glyph (BMP so Tk 8.6 can render it).
        icon_font = tkfont.Font(family=self.font_title.cget("family"), size=46)
        tk.Label(
            frame,
            text="\u263e",
            font=icon_font,
            bg=COLORS["bg"],
            fg=COLORS["accent_soft"],
        ).pack()

        if claimed:
            title = "Rest day claimed"
            message = (
                f"Your streak is safe at \u2605 {self.engine.profile.streak}.\n"
                "Recharge and come back strong!"
            )
        else:
            title = "Already resting"
            message = "Today is already protected.\nEnjoy your break!"

        tk.Label(
            frame,
            text=title,
            font=self.font_heading,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(pady=(12, 4))
        tk.Label(
            frame,
            text=message,
            font=self.font_body,
            bg=COLORS["bg"],
            fg=COLORS["text_muted"],
            justify="center",
        ).pack()

        ttk.Button(
            frame, text="Nice", style="Accent.TButton", command=dialog.destroy
        ).pack(pady=(20, 0))

        dialog.bind("<Return>", lambda _e: dialog.destroy())
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.grab_set()
        self._center_over_root(dialog)
        self._prepare_toplevel(dialog)
        self.root.wait_window(dialog)

    def _center_over_root(self, window: tk.Toplevel) -> None:
        """Position a Toplevel centered over the main window."""
        window.update_idletasks()
        x = (
            self.root.winfo_rootx()
            + (self.root.winfo_width() - window.winfo_width()) // 2
        )
        y = (
            self.root.winfo_rooty()
            + (self.root.winfo_height() - window.winfo_height()) // 2
        )
        window.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    # ---- routine manager ------------------------------------------------

    def open_routine_manager(self) -> None:
        """Open a themed window for adding and editing routines."""
        window = tk.Toplevel(self.root)
        window.title("Manage routines")
        window.geometry("480x360")
        window.configure(bg=COLORS["bg"])
        window.transient(self.root)

        tk.Label(
            window,
            text="Routines",
            font=self.font_heading,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(anchor="w", padx=16, pady=(16, 8))

        routines_listbox = tk.Listbox(
            window,
            height=10,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            highlightthickness=0,
            borderwidth=0,
            font=self.font_body,
            activestyle="none",
        )
        routines_listbox.pack(fill="both", expand=True, padx=16, pady=8)

        buttons = tk.Frame(window, bg=COLORS["bg"])
        buttons.pack(fill="x", padx=16, pady=(0, 16))

        ttk.Button(
            buttons,
            text="Add routine",
            style="Accent.TButton",
            command=lambda: self.add_routine_from_dialog(routines_listbox),
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Edit selected",
            style="Ghost.TButton",
            command=lambda: self.edit_selected_routine(routines_listbox),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            buttons,
            text="Close",
            style="Ghost.TButton",
            command=window.destroy,
        ).pack(side="right")

        self.refresh_routine_listbox(routines_listbox)
        if self.uses_custom_decorations:
            self._center_over_root(window)
        self._prepare_toplevel(window)

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
        """Show a themed modal dialog and return (name, categories) or None."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.resizable(False, False)

        frame = tk.Frame(dialog, bg=COLORS["bg"])
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(
            frame,
            text=title,
            font=self.font_heading,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        ).pack(anchor="w", pady=(0, 12))

        name_entry = self._make_dialog_entry(frame, "Routine name", initial_name)
        tasks_entry = self._make_dialog_entry(
            frame,
            "Categories and tasks",
            initial_categories_text,
            hint="Push: Bench Press, Overhead Press; Pull: Rows, Biceps",
            width=44,
        )

        # Collect the raw entry values only when the user confirms.
        result: dict[str, tuple[str, str] | None] = {"value": None}

        def on_save() -> None:
            result["value"] = (name_entry.get(), tasks_entry.get())
            dialog.destroy()

        buttons = tk.Frame(frame, bg=COLORS["bg"])
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(
            buttons, text="Cancel", style="Ghost.TButton", command=dialog.destroy
        ).pack(side="right")
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=on_save).pack(
            side="right", padx=(0, 8)
        )

        name_entry.focus_set()
        dialog.bind("<Return>", lambda _e: on_save())
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.grab_set()
        if self.uses_custom_decorations:
            self._center_over_root(dialog)
        self._prepare_toplevel(dialog)
        self.root.wait_window(dialog)

        if result["value"] is None:
            return None
        name, categories_text = result["value"]
        categories = self.parse_categories_input(categories_text)
        return name, categories

    def _make_dialog_entry(
        self,
        parent: tk.Frame,
        label: str,
        initial: str,
        hint: str = "",
        width: int = 32,
    ) -> tk.Entry:
        """Create a labeled, dark-themed text entry and return the Entry."""
        tk.Label(
            parent,
            text=label,
            font=self.font_small,
            bg=COLORS["bg"],
            fg=COLORS["text_muted"],
        ).pack(anchor="w")
        if hint:
            tk.Label(
                parent,
                text=hint,
                font=self.font_small,
                bg=COLORS["bg"],
                fg=COLORS["text_muted"],
            ).pack(anchor="w")
        entry = tk.Entry(
            parent,
            width=width,
            font=self.font_body,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["track"],
            highlightcolor=COLORS["accent"],
        )
        entry.insert(0, initial)
        entry.pack(fill="x", ipady=6, pady=(2, 12))
        return entry

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


def main() -> None:
    """Create the root window, launch the app, and run the event loop."""
    root = tk.Tk()
    HabitQuestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
