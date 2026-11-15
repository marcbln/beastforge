"""Stable error hierarchy for beastforge.

Every failure that reaches the CLI is a :class:`BeastforgeError` with a closed
``code``, an actionable ``remedy``, and an exit code from the documented set
(``cli:errors``, research D9). Stack traces are never part of the contract.
"""

from __future__ import annotations

from typing import Any


class BeastforgeError(Exception):
    """A user-actionable failure with a stable code and exit status."""

    exit_code: int = 3

    def __init__(
        self,
        code: str,
        message: str,
        *,
        location: dict[str, str] | None = None,
        expected: Any = None,
        actual: Any = None,
        remedy: str,
        suggestion: str | None = None,
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.location = location or {"path": ""}
        self.expected = expected
        self.actual = actual
        self.remedy = remedy
        self.suggestion = suggestion
        if exit_code is not None:
            self.exit_code = exit_code


class UsageError(BeastforgeError):
    """The invocation itself is wrong (unknown flag, malformed ``--set``)."""

    exit_code = 2

    def __init__(self, code: str, message: str, *, remedy: str, **kwargs: Any) -> None:
        super().__init__(code, message, remedy=remedy, **kwargs)


class NotFoundError(BeastforgeError):
    """A named creature, recipe, or texture does not exist."""

    exit_code = 4


class IOFailure(BeastforgeError):
    """Filesystem or environment failure."""

    exit_code = 1
