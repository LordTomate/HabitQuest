"""Data models for HabitQuest."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Category:
    """A routine day with the tasks that should be completed together."""

    name: str
    tasks: list[str]

    def __post_init__(self) -> None:
        """Validate that a category contains usable task names."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Category name must be a non-empty string.")
        if not isinstance(self.tasks, list) or not self.tasks:
            raise ValueError("Category tasks must be a non-empty list.")
        if any(not isinstance(task, str) or not task.strip() for task in self.tasks):
            raise ValueError("Every task must be a non-empty string.")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the category."""
        return {"name": self.name, "tasks": self.tasks}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Category":
        """Create a category from loaded JSON data."""
        return cls(name=data["name"], tasks=list(data["tasks"]))


@dataclass
class Routine:
    """A rotating routine such as a push/pull/legs training plan."""

    name: str
    categories: list[Category]
    day_index: int = 0
    paused: bool = False

    def __post_init__(self) -> None:
        """Validate routine fields after construction."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Routine name must be a non-empty string.")
        if not isinstance(self.categories, list) or not self.categories:
            raise ValueError("Routine categories must be a non-empty list.")
        if any(not isinstance(category, Category) for category in self.categories):
            raise TypeError("Routine categories must contain Category objects.")
        if self.day_index < 0:
            raise ValueError("Routine day_index must not be negative.")

    @property
    def current_category(self) -> Category:
        """Return the category scheduled for the current cycle day."""
        return self.categories[self.day_index % len(self.categories)]

    def advance_days(self, days: int) -> None:
        """Move the routine forward by a number of days."""
        if days < 0:
            raise ValueError("days must not be negative.")
        self.day_index = (self.day_index + days) % len(self.categories)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the routine."""
        return {
            "categories": [category.to_dict() for category in self.categories],
            "day_index": self.day_index,
            "paused": self.paused,
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "Routine":
        """Create a routine from loaded JSON data."""
        categories = [Category.from_dict(item) for item in data["categories"]]
        return cls(
            name=name,
            categories=categories,
            day_index=int(data.get("day_index", 0)),
            paused=bool(data.get("paused", False)),
        )


@dataclass
class UserProfile:
    """Progress data for the local HabitQuest user."""

    xp: int = 0
    level: int = 1
    streak: int = 0
    last_checked_date: str = ""
    last_all_done_date: str = ""
    last_completed_date: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate profile counters after construction."""
        if self.xp < 0:
            raise ValueError("XP must not be negative.")
        if self.level < 1:
            raise ValueError("Level must be at least 1.")
        if self.streak < 0:
            raise ValueError("Streak must not be negative.")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the profile."""
        return {
            "xp": self.xp,
            "level": self.level,
            "streak": self.streak,
            "last_checked_date": self.last_checked_date,
            "last_all_done_date": self.last_all_done_date,
            "last_completed_date": self.last_completed_date,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        """Create a profile from loaded JSON data."""
        return cls(
            xp=int(data.get("xp", 0)),
            level=int(data.get("level", 1)),
            streak=int(data.get("streak", 0)),
            last_checked_date=str(data.get("last_checked_date", "")),
            last_all_done_date=str(data.get("last_all_done_date", "")),
            last_completed_date=str(data.get("last_completed_date", "")),
            history=list(data.get("history", [])),
        )
