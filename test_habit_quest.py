"""Unit tests for HabitQuest."""

import os
import tempfile
import tkinter as tk
import unittest
from datetime import date
from unittest.mock import Mock, patch

from engine import HabitQuestEngine
from ui import HabitQuestApp, force_dark_window_decorations


class FakeClock:
    """Mutable date provider for deterministic engine tests."""

    def __init__(self, today: date) -> None:
        self.current_day = today

    def today(self) -> date:
        """Return the configured current date."""
        return self.current_day


class TestHabitQuestEngine(unittest.TestCase):
    """Tests for progress, persistence, and routine rotation."""

    def setUp(self) -> None:
        """Create a fresh engine with an isolated save file."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.clock = FakeClock(date(2026, 1, 1))
        self.engine = HabitQuestEngine(
            save_path=os.path.join(self.temp_dir.name, "habitquest.json"),
            today_provider=self.clock.today,
        )

    def tearDown(self) -> None:
        """Clean up temporary save data."""
        self.temp_dir.cleanup()

    def test_default_tasks_start_on_push_day(self) -> None:
        """A new save starts with the push workout scheduled."""
        task_names = [task["task"] for task in self.engine.get_today_tasks()]

        self.assertEqual(task_names, ["Bench Press", "Overhead Press", "Triceps"])
        self.assertEqual(self.engine.completed_today, set())

    def test_toggle_task_awards_xp_and_persists_completion(self) -> None:
        """Completing a task adds XP and survives reloading the engine."""
        task_key = next(iter(self.engine.get_all_today_task_keys()))

        self.assertTrue(self.engine.toggle_task(task_key))
        reloaded = HabitQuestEngine(
            save_path=self.engine.save_path,
            today_provider=self.clock.today,
        )

        self.assertEqual(self.engine.profile.xp, 10)
        self.assertIn(task_key, reloaded.completed_today)
        self.assertEqual(reloaded.profile.xp, 10)

    def test_completing_all_tasks_claims_streak_once(self) -> None:
        """Finishing every task for a day increases the streak once."""
        for task_key in sorted(self.engine.get_all_today_task_keys()):
            self.engine.toggle_task(task_key)

        self.assertEqual(self.engine.profile.streak, 1)
        self.assertEqual(self.engine.profile.last_all_done_date, "2026-01-01")
        self.assertEqual(len(self.engine.profile.history), 1)

    def test_unchecking_completed_day_restores_previous_streak(self) -> None:
        """Undoing today's completed day should keep yesterday's streak intact."""
        for task_key in sorted(self.engine.get_all_today_task_keys()):
            self.engine.toggle_task(task_key)
        self.clock.current_day = date(2026, 1, 2)
        self.engine.check_new_day()
        today_keys = sorted(self.engine.get_all_today_task_keys())
        for task_key in today_keys:
            self.engine.toggle_task(task_key)

        self.engine.toggle_task(today_keys[0])

        self.assertEqual(self.engine.profile.streak, 1)
        self.assertEqual(self.engine.profile.last_completed_date, "2026-01-01")
        self.assertEqual(self.engine.profile.last_all_done_date, "2026-01-01")

    def test_new_day_advances_routine_cycle(self) -> None:
        """Opening the app on a later day moves the routine to the next category."""
        self.clock.current_day = date(2026, 1, 2)

        self.engine.check_new_day()
        task_names = [task["task"] for task in self.engine.get_today_tasks()]

        self.assertEqual(task_names, ["Rows", "Lat Pulldown", "Biceps"])

    def test_unknown_task_key_is_rejected(self) -> None:
        """Invalid task keys fail loudly instead of corrupting progress data."""
        with self.assertRaises(ValueError):
            self.engine.toggle_task("Training::Push::Not A Real Task")

    def test_add_routine_adds_tasks_to_today(self) -> None:
        """Adding a routine should expose its tasks in today's checklist."""
        self.engine.add_routine("Morning", [("Wake", ["Drink Water", "Stretch"])])
        task_names = [task["task"] for task in self.engine.get_today_tasks()]

        self.assertIn("Drink Water", task_names)
        self.assertIn("Stretch", task_names)

    def test_add_routine_rejects_duplicate_name(self) -> None:
        """Routine names should stay unique to avoid accidental overwrites."""
        with self.assertRaises(ValueError):
            self.engine.add_routine("Training", [("Push", ["Bench Press"])])

    def test_update_routine_renames_and_replaces_categories(self) -> None:
        """Editing a routine should update both name and task plan."""
        self.engine.update_routine(
            current_name="Training",
            new_name="Strength",
            categories=[("Upper", ["Pull-up", "Dip"])],
        )

        self.assertIn("Strength", self.engine.routines)
        self.assertNotIn("Training", self.engine.routines)
        task_names = [task["task"] for task in self.engine.get_today_tasks()]
        self.assertIn("Pull-up", task_names)
        self.assertNotIn("Bench Press", task_names)


class TestRoutineInputParsing(unittest.TestCase):
    """Tests for converting routine text input into structured categories."""

    def test_parse_categories_input_valid(self) -> None:
        """Expected format should parse into category/task tuples."""
        parsed = HabitQuestApp.parse_categories_input(
            "Push: Bench Press, Overhead Press; Pull: Rows, Biceps"
        )

        self.assertEqual(
            parsed,
            [
                ("Push", ["Bench Press", "Overhead Press"]),
                ("Pull", ["Rows", "Biceps"]),
            ],
        )

    def test_parse_categories_input_invalid(self) -> None:
        """Missing ':' should fail with a helpful error."""
        with self.assertRaises(ValueError):
            HabitQuestApp.parse_categories_input("Push Bench Press")


class TestWindowDecorations(unittest.TestCase):
    """Tests for requesting native dark window borders."""

    @patch("ui.sys.platform", "linux")
    @patch("ui.shutil.which", side_effect=lambda name: f"/usr/bin/{name}")
    @patch("ui.subprocess.run")
    def test_x11_requests_dark_system_decorations(
        self, run: Mock, _which: Mock
    ) -> None:
        """X11 should receive the dark hint on Tk and its native parents."""
        window = Mock()
        window.tk.call.return_value = "x11"
        window.winfo_id.return_value = 0x123
        run.side_effect = [
            Mock(stdout="Parent window id: 0x456 (has no name)\n"),
            Mock(stdout="Parent window id: 0x789 (has no name)\n"),
            Mock(returncode=0),
            Mock(returncode=0),
            Mock(returncode=0),
        ]

        applied = force_dark_window_decorations(window)

        self.assertTrue(applied)
        commands = [call.args[0] for call in run.call_args_list]
        xprop_commands = commands[2:]
        self.assertEqual(
            [command[2] for command in xprop_commands],
            ["0x123", "0x456", "0x789"],
        )
        self.assertTrue(
            all(
                command[-3:] == ["-set", "_GTK_THEME_VARIANT", "dark"]
                for command in xprop_commands
            )
        )


@unittest.skipUnless(os.environ.get("DISPLAY"), "Tkinter UI tests need a display")
class TestHabitQuestApp(unittest.TestCase):
    """Smoke tests for the Tkinter UI wiring."""

    def setUp(self) -> None:
        """Create a fresh Tk root, engine, and app before each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.clock = FakeClock(date(2026, 1, 1))
        self.engine = HabitQuestEngine(
            save_path=os.path.join(self.temp_dir.name, "habitquest.json"),
            today_provider=self.clock.today,
        )
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = HabitQuestApp(self.root, self.engine)

    def tearDown(self) -> None:
        """Destroy widgets and temporary save data after each test."""
        self.root.destroy()
        self.temp_dir.cleanup()

    def test_status_starts_with_nothing_completed(self) -> None:
        """The UI starts with no completed tasks shown."""
        self.assertEqual(self.app.status_label.cget("text"), "0/3 done")

    def test_toggle_task_refreshes_status(self) -> None:
        """Clicking through the UI updates the engine-backed status label."""
        task_key = next(iter(self.engine.get_all_today_task_keys()))

        self.app.toggle_task(task_key)

        self.assertEqual(self.app.status_label.cget("text"), "1/3 done")


if __name__ == "__main__":
    unittest.main()
