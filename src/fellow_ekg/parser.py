"""Pure parsing helpers for the kettle's HTTP responses.

The CLI endpoint (``GET /cli?cmd=<command>``) returns a small HTML form
followed by ESP-IDF log lines, e.g.::

    <form ...>...</form>
    I (2855011443) Cli: cmd len 4: 'help'
    I (2855011453) Cli: reset : reset

The page appears to show the device's recent log buffer, so it can contain
output from earlier commands. We only keep lines after the *last* echo of
the command we sent.
"""

from __future__ import annotations

import html
import re

from .exceptions import EKGCommandError
from .models import EKGState, FirmwareInfo, Temperature

# "I (2855011453) Cli: " -- level letter, tick count, tag
_LOG_PREFIX = re.compile(r"^[EWIDV] \(\d+\) [^:]+:\s?")
_CMD_ECHO = re.compile(r"cmd len \d+: '(?P<cmd>.*)'$")
_NUMBER = r"(-?\d+(?:\.\d+)?)"


def _split_lines(text: str) -> list[str]:
    text = re.sub(r"<form.*?</form>", "", text, flags=re.S | re.I)
    # Tags act as line breaks: "<h1>EKG</h1>Current version: ..." must split.
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_cli_output(body: str, command: str) -> list[str]:
    """Return the log lines produced by ``command``, minus ESP-IDF prefixes.

    Raises EKGCommandError if the firmware says the command doesn't exist.
    """
    lines = [_LOG_PREFIX.sub("", line) for line in _split_lines(body)]

    start = None
    for i, line in enumerate(lines):
        m = _CMD_ECHO.search(line)
        if m and m.group("cmd") == command:
            start = i + 1
    if start is None:
        # No echo of our command: don't risk returning stale output.
        raise EKGCommandError(f"no output for command {command!r}")

    output = lines[start:]
    for line in output:
        if line.startswith("cannot find command"):
            raise EKGCommandError(line)
    return output


def parse_firmware_info(body: str) -> FirmwareInfo:
    """Parse the status page served at ``/``."""
    text = "\n".join(_split_lines(body))

    def grab(label: str) -> str | None:
        m = re.search(rf"^{label}:\s*(.*)$", text, flags=re.M)
        return m.group(1).strip() or None if m else None

    return FirmwareInfo(
        version=grab("Current version"),
        build_date=grab("Build date"),
        build_time=grab("Build time"),
        running_partition=grab("Running partition"),
    )


def _labelled(text: str, *labels: str) -> float | None:
    for label in labels:
        m = re.search(rf"\b{label}\b\s*[:=]?\s*{_NUMBER}", text, flags=re.I)
        if m:
            return float(m.group(1))
    return None


def parse_temperature(lines: list[str]) -> Temperature:
    """Parse ``temp`` output ("print tempr min/max/av").

    The exact format hasn't been observed yet, so this looks for labelled
    numbers (min, max, av/avg, cur/current/temp) and falls back to the first
    number on the line as the current reading.
    """
    text = " ".join(lines)
    # Compact form, e.g. "min/max/av: 20.1/95.3/60.0"
    m = re.search(rf"min/max/av\w*\s*[:=]?\s*{_NUMBER}\s*/\s*{_NUMBER}\s*/\s*{_NUMBER}", text, re.I)
    if m:
        minimum, maximum, average = (float(g) for g in m.groups())
    else:
        minimum = _labelled(text, "min")
        maximum = _labelled(text, "max")
        average = _labelled(text, "avg", "av", "average")
    current = _labelled(text, "current", "cur", "now", "tempr", "temp")
    if current is None:
        current = average
    if current is None:
        m = re.search(_NUMBER, text)
        current = float(m.group(1)) if m else None
    return Temperature(current, minimum, maximum, average, raw=list(lines))


def parse_state(lines: list[str]) -> EKGState:
    """Best-effort ``key: value`` / ``key=value`` parse of ``state`` output."""
    values: dict[str, str] = {}
    for line in lines:
        # A line may hold several "a=1 b=2" pairs.
        pairs = re.findall(r"(\w[\w .-]*?)\s*=\s*([^\s,;]+)", line)
        if pairs:
            for key, value in pairs:
                values[key.strip().lower()] = value
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            if key.strip() and value.strip():
                values[key.strip().lower()] = value.strip()
    return EKGState(values=values, raw=list(lines))
