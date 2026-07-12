"""Business logic and persistence for HabitQuest."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Callable

from models import Category, Routine, UserProfile


class HabitQuestEngine:
    """Coordinates routines, progress, rewards, streaks, and save data."""

    DEFAULT_SAVE_PATH = Path("habitquest_data.json")
    TASK_XP_REWARD = 10

    def __init__(
        self,
        save_path: str | Path = DEFAULT_SAVE_PATH,
        today_provider: Callable[[], date] | None = None,
    ) -> None:
        self.save_path = Path(save_path)
        self.today_provider = today_provider or date.today
        self.profile = UserProfile()
        self.routines: dict[str, Routine] = {}
        self.completed_by_date: dict[str, set[str]] = {}
        self.completed_today: set[str] = set()

        self.load_data()
        self.check_new_day()
        self.load_today_completions()

    def get_default_data(self) -> dict[str, Any]:
        """Return the starter routine and an empty profile."""
        training = Routine(
            name="Training",
            categories=[
                Category("Push", ["Bench Press", "Overhead Press", "Triceps"]),
                Category("Pull", ["Rows", "Lat Pulldown", "Biceps"]),
                Category("Legs", ["Squats", "Romanian Deadlift", "Calves"]),
            ],
        )
        return {
            "profile": UserProfile().to_dict(),
            "routines": {training.name: training.to_dict()},
            "completed_by_date": {},
        }

    def xp_for_level(self, level: int) -> int:
        """Return how many XP are needed to move from this level to the next."""
        if level < 1:
            raise ValueError("level must be at least 1.")
        return level * 100

    def total_xp_to_reach_level(self, level: int) -> int:
        """Return total XP required to have reached a given level."""
        if level < 1:
            raise ValueError("level must be at least 1.")
        return sum(
            self.xp_for_level(current_level) for current_level in range(1, level)
        )

    def check_new_day(self) -> None:
        """Advance routine cycles and reset stale streaks when a new day starts."""
        today = self._today_string()
        if not self.profile.last_checked_date:
            self.profile.last_checked_date = today
            self.save_data()
            return

        last_checked = date.fromisoformat(self.profile.last_checked_date)
        elapsed_days = (self.today_provider() - last_checked).days
        if elapsed_days <= 0:
            return

        for routine in self.routines.values():
            if not routine.paused:
                routine.advance_days(elapsed_days)

        if self.profile.last_completed_date:
            last_completed = date.fromisoformat(self.profile.last_completed_date)
            if (self.today_provider() - last_completed).days > 1:
                self.profile.streak = 0
        else:
            self.profile.streak = 0

        self.profile.last_checked_date = today
        self.load_today_completions()
        self.save_data()

    def load_today_completions(self) -> None:
        """Load the completion set for the current date into memory."""
        self.completed_today = set(
            self.completed_by_date.get(self._today_string(), set())
        )

    def calc_xp_reward(self) -> int:
        """Return the XP reward for completing one task."""
        return self.TASK_XP_REWARD

    def toggle_task(self, task_key: str) -> bool:
        """Toggle a task and return True when it is completed after the toggle."""
        if not isinstance(task_key, str):
            raise TypeError("task_key must be a string.")
        if task_key not in self.get_all_today_task_keys():
            raise ValueError(f"Unknown task key: {task_key}")

        if task_key in self.completed_today:
            self.completed_today.remove(task_key)
            self.profile.xp = max(0, self.profile.xp - self.calc_xp_reward())
            self._undo_today_streak_if_needed()
            completed = False
        else:
            self.completed_today.add(task_key)
            self.profile.xp += self.calc_xp_reward()
            completed = True

        self.profile.level = self._level_for_xp(self.profile.xp)
        self.completed_by_date[self._today_string()] = set(self.completed_today)
        self._claim_day_if_all_tasks_done()
        self.save_data()
        return completed

    def save_data(self) -> None:
        """Persist current state to JSON with an atomic file replacement."""
        data = {
            "profile": self.profile.to_dict(),
            "routines": {
                routine_name: routine.to_dict()
                for routine_name, routine in self.routines.items()
            },
            "completed_by_date": {
                completion_date: sorted(task_keys)
                for completion_date, task_keys in self.completed_by_date.items()
            },
        }
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.save_path.parent,
            delete=False,
        ) as temp_file:
            json.dump(data, temp_file, indent=2, ensure_ascii=False)
            temp_file.write("\n")
            temp_name = temp_file.name
        os.replace(temp_name, self.save_path)

    def load_data(self) -> None:
        """Load state from disk, or initialize default data if no save exists yet."""
        if self.save_path.exists():
            with self.save_path.open("r", encoding="utf-8") as save_file:
                data = json.load(save_file)
        else:
            data = self.get_default_data()

        self.profile = UserProfile.from_dict(data.get("profile", {}))
        self.routines = {
            routine_name: Routine.from_dict(routine_name, routine_data)
            for routine_name, routine_data in data.get("routines", {}).items()
        }
        if not self.routines:
            defaults = self.get_default_data()
            self.routines = {
                routine_name: Routine.from_dict(routine_name, routine_data)
                for routine_name, routine_data in defaults["routines"].items()
            }

        self.completed_by_date = {
            completion_date: set(task_keys)
            for completion_date, task_keys in data.get("completed_by_date", {}).items()
        }
        self.completed_today = set(
            self.completed_by_date.get(self._today_string(), set())
        )

    def get_all_today_task_keys(self) -> set[str]:
        """Return all task keys scheduled for today."""
        return {task["key"] for task in self.get_today_tasks()}

    def get_cycle_overview(self) -> list[dict[str, Any]]:
        """Return each active routine's position in its cycle and what follows.

        For every non-paused routine this reports the current category, the
        1-based day within the cycle, the cycle length, and the ordered list
        of upcoming categories. The UI uses this to make the rotation visible.
        """
        overview: list[dict[str, Any]] = []
        for routine in self.routines.values():
            if routine.paused:
                continue
            length = len(routine.categories)
            position = routine.day_index % length
            upcoming = [
                routine.categories[(position + offset) % length].name
                for offset in range(1, length)
            ]
            overview.append(
                {
                    "routine": routine.name,
                    "current": routine.current_category.name,
                    "position": position + 1,
                    "length": length,
                    "upcoming": upcoming,
                }
            )
        return overview

    def get_today_tasks(self) -> list[dict[str, str]]:
        """Return display-ready task information for all active routines today."""
        tasks: list[dict[str, str]] = []
        for routine in self.routines.values():
            if routine.paused:
                continue
            category = routine.current_category
            for task_name in category.tasks:
                tasks.append(
                    {
                        "key": self._task_key(routine.name, category.name, task_name),
                        "routine": routine.name,
                        "category": category.name,
                        "task": task_name,
                    }
                )
        return tasks

    def add_routine(
        self, name: str, categories: list[tuple[str, list[str]]], paused: bool = False
    ) -> Routine:
        """Create a new routine and persist it."""
        routine_name = self._normalize_routine_name(name)
        if routine_name in self.routines:
            raise ValueError(f"Routine already exists: {routine_name}")

        category_objects = self._build_categories(categories)
        routine = Routine(name=routine_name, categories=category_objects, paused=paused)
        self.routines[routine_name] = routine
        self._cleanup_today_completions()
        self.save_data()
        return routine

    def update_routine(
        self,
        current_name: str,
        new_name: str,
        categories: list[tuple[str, list[str]]],
        paused: bool | None = None,
    ) -> Routine:
        """Update an existing routine and persist the changed values."""
        current_key = self._normalize_routine_name(current_name)
        if current_key not in self.routines:
            raise ValueError(f"Unknown routine: {current_key}")

        target_name = self._normalize_routine_name(new_name)
        if target_name != current_key and target_name in self.routines:
            raise ValueError(f"Routine already exists: {target_name}")

        original = self.routines[current_key]
        category_objects = self._build_categories(categories)
        new_day_index = original.day_index % len(category_objects)
        updated = Routine(
            name=target_name,
            categories=category_objects,
            day_index=new_day_index,
            paused=original.paused if paused is None else paused,
        )

        if target_name != current_key:
            del self.routines[current_key]
        self.routines[target_name] = updated
        self._cleanup_today_completions()
        self.save_data()
        return updated

    def claim_rest_day(self) -> bool:
        """Count today as protected rest without requiring task completion."""
        today = self._today_string()
        if self.profile.last_completed_date == today:
            return False

        yesterday = date.fromordinal(self.today_provider().toordinal() - 1).isoformat()
        if self.profile.last_completed_date == yesterday:
            self.profile.streak += 1
        else:
            self.profile.streak = 1

        self.profile.last_completed_date = today
        self.profile.last_all_done_date = today
        self.profile.history.append(
            {
                "date": today,
                "type": "rest",
                "streak": self.profile.streak,
                "xp": self.profile.xp,
            }
        )
        self.save_data()
        return True

    def _today_string(self) -> str:
        """Return today's date as an ISO string."""
        return self.today_provider().isoformat()

    def _task_key(self, routine_name: str, category_name: str, task_name: str) -> str:
        """Build the stable key used for today's completion set."""
        return f"{routine_name}::{category_name}::{task_name}"

    def _level_for_xp(self, xp: int) -> int:
        """Convert total XP into the current level."""
        level = 1
        while xp >= self.total_xp_to_reach_level(level + 1):
            level += 1
        return level

    def _claim_day_if_all_tasks_done(self) -> None:
        """Increase the streak once when every scheduled task is complete."""
        today = self._today_string()
        all_task_keys = self.get_all_today_task_keys()
        if not all_task_keys or not all_task_keys.issubset(self.completed_today):
            return
        if self.profile.last_all_done_date == today:
            return

        yesterday = date.fromordinal(self.today_provider().toordinal() - 1).isoformat()
        if self.profile.last_completed_date == yesterday:
            self.profile.streak += 1
        else:
            self.profile.streak = 1

        self.profile.last_all_done_date = today
        self.profile.last_completed_date = today
        self.profile.history.append(
            {
                "date": today,
                "type": "tasks",
                "completed_tasks": len(all_task_keys),
                "streak": self.profile.streak,
                "xp": self.profile.xp,
            }
        )

    def _undo_today_streak_if_needed(self) -> None:
        """Undo today's streak claim when a completed day becomes incomplete."""
        today = self._today_string()
        if self.profile.last_all_done_date != today:
            return

        self.profile.history = [
            item
            for item in self.profile.history
            if not (item.get("date") == today and item.get("type") == "tasks")
        ]
        previous_completion = self._previous_completion_before(today)
        if previous_completion is None:
            self.profile.last_all_done_date = ""
            self.profile.last_completed_date = ""
            self.profile.streak = 0
            return

        self.profile.last_all_done_date = str(previous_completion["date"])
        self.profile.last_completed_date = str(previous_completion["date"])
        self.profile.streak = int(previous_completion["streak"])

    def _previous_completion_before(self, today: str) -> dict[str, Any] | None:
        """Return the most recent protected day before today, if one exists."""
        for item in reversed(self.profile.history):
            if item.get("date") != today and item.get("type") in {"tasks", "rest"}:
                return item
        return None

    def _normalize_routine_name(self, name: str) -> str:
        """Validate and normalize a routine name."""
        if not isinstance(name, str):
            raise TypeError("Routine name must be a string.")
        normalized = name.strip()
        if not normalized:
            raise ValueError("Routine name must not be empty.")
        return normalized

    def _build_categories(
        self, categories: list[tuple[str, list[str]]]
    ) -> list[Category]:
        """Convert validated category input tuples into Category objects."""
        if not isinstance(categories, list) or not categories:
            raise ValueError("A routine needs at least one category.")

        built_categories: list[Category] = []
        for category in categories:
            if (
                not isinstance(category, tuple)
                or len(category) != 2
                or not isinstance(category[1], list)
            ):
                raise TypeError(
                    "Categories must use (category_name, [task1, task2, ...]) tuples."
                )
            category_name, task_names = category
            built_categories.append(Category(name=category_name, tasks=task_names))
        return built_categories

    def _cleanup_today_completions(self) -> None:
        """Remove stale completion keys after routine changes."""
        valid_keys = self.get_all_today_task_keys()
        self.completed_today &= valid_keys
        self.completed_by_date[self._today_string()] = set(self.completed_today)
