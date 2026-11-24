from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FirmwareInfo:
    """Parsed from the kettle's status page at ``/``."""

    version: str | None
    build_date: str | None
    build_time: str | None
    running_partition: str | None


@dataclass(frozen=True)
class Temperature:
    """Output of the ``temp`` CLI command.

    ``current`` is the best guess at the live reading: an explicitly labelled
    current value if the firmware prints one, otherwise the average.
    """

    current: float | None
    minimum: float | None
    maximum: float | None
    average: float | None
    raw: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EKGState:
    """Output of the ``state`` CLI command.

    The output format isn't documented, so ``values`` is a best-effort parse of
    ``key: value`` / ``key=value`` pairs, and ``raw`` keeps every line.
    """

    values: dict[str, str]
    raw: list[str] = field(default_factory=list)
