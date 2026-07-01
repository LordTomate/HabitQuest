"""Unit tests for HabitQuest.

Run with: python -m unittest test_habit_quest.py

Note: these tests create real Tkinter widgets, which requires a display. In a
headless CI environment, wrap the test command with `xvfb-run` (e.g.
`xvfb-run python -m unittest test_habit_quest.py`) or these tests will fail with
"no display name" errors.
"""

import tkinter as tk
import unittest

from ui import SAMPLE_TASKS, HabitQuestApp


class TestHabitQuestApp(unittest.TestCase):
    """Tests for the task-tracking logic in `HabitQuestApp`."""

    def setUp(self) -> None:
        """Create a fresh Tk root and app before each test."""
        self.root = tk.Tk()
        self.app = HabitQuestApp(self.root)

    def tearDown(self) -> None:
        """Destroy the Tk root after each test so windows don't pile up."""
        self.root.destroy()

    def test_starts_with_nothing_completed(self) -> None:
        """A freshly built app should have no tasks checked off yet."""
        self.assertEqual(self.app.completed, set())
        self.assertEqual(
            self.app.status_label.cget("text"),
            f"0/{len(SAMPLE_TASKS)} tasks done today",
        )

    def test_toggle_task_marks_done(self) -> None:
        """Toggling a task on should add it to `completed` and update the label."""
        task = SAMPLE_TASKS[0]
        var = tk.BooleanVar(value=True)

        self.app.toggle_task(task, var)

        self.assertIn(task, self.app.completed)
        self.assertEqual(
            self.app.status_label.cget("text"),
            f"1/{len(SAMPLE_TASKS)} tasks done today",
        )

    def test_toggle_task_marks_undone(self) -> None:
        """Toggling a completed task back off should remove it from `completed`."""
        task = SAMPLE_TASKS[0]
        on_var = tk.BooleanVar(value=True)
        off_var = tk.BooleanVar(value=False)

        self.app.toggle_task(task, on_var)
        self.app.toggle_task(task, off_var)

        self.assertNotIn(task, self.app.completed)
        self.assertEqual(
            self.app.status_label.cget("text"),
            f"0/{len(SAMPLE_TASKS)} tasks done today",
        )

    def test_toggle_untracked_task_is_a_no_op(self) -> None:
        """Toggling off a task that was never completed should not raise or go negative."""
        off_var = tk.BooleanVar(value=False)

        self.app.toggle_task("Not A Real Task", off_var)

        self.assertEqual(self.app.completed, set())


if __name__ == "__main__":
    unittest.main()
