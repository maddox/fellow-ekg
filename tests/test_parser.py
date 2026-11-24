import pytest

from fellow_ekg import (
    EKGCommandError,
    parse_cli_output,
    parse_firmware_info,
    parse_state,
    parse_temperature,
)

FORM = """
            <form action="cli" method="GET">
            <label for="x">CLI Command:</label><br>
            <input type="text" id="cli" name="cmd"><br>
            </form>
            """

# Captured from the real device.
ROOT_PAGE = (
    "<h1>EKG</h1>Current version: 1.2.5CL CLI<br>\nBuild time: 05:25:49<br>\n"
    "Build date: Dec 10 2025<br>\nBoot partition: ota_0<br>\n"
    "Running partition: ota_0<br>\nLast invalid partition: <br>\n"
)
UNKNOWN_CMD = FORM + (
    "I (2855006113) Cli: cmd len 7: 'wifion'\n"
    "I (2855006113) Cli: cannot find command 'wifion'\n"
)
HELP_SNIPPET = FORM + (
    "I (2855011443) Cli: cmd len 4: 'help'<br>\n"
    "I (2855011453) Cli: reset : reset<br>\n"
    "I (2855011453) Cli: state : print state<br>\n"
)


def test_firmware_info():
    info = parse_firmware_info(ROOT_PAGE)
    assert info.version == "1.2.5CL CLI"
    assert info.build_date == "Dec 10 2025"
    assert info.build_time == "05:25:49"
    assert info.running_partition == "ota_0"


def test_cli_output_strips_form_and_prefixes():
    assert parse_cli_output(HELP_SNIPPET, "help") == ["reset : reset", "state : print state"]


def test_unknown_command_raises():
    with pytest.raises(EKGCommandError, match="cannot find command"):
        parse_cli_output(UNKNOWN_CMD, "wifion")


def test_stale_output_from_other_command_is_rejected():
    # The page showed the previous 'wifion' output when no cmd was given.
    with pytest.raises(EKGCommandError, match="no output"):
        parse_cli_output(UNKNOWN_CMD, "temp")


def test_only_output_after_last_echo():
    body = HELP_SNIPPET + "I (1) Cli: cmd len 4: 'temp'\nI (2) Cli: av 55.0\n"
    assert parse_cli_output(body, "temp") == ["av 55.0"]


@pytest.mark.parametrize(
    "lines, expected",
    [
        (["tempr min 20.5 max 98.0 av 60.25"], (60.25, 20.5, 98.0, 60.25)),
        (["min/max/av: 20/90/50"], (50.0, 20.0, 90.0, 50.0)),
        (["current=71.2 min=70.9 max=71.5 avg=71.1"], (71.2, 70.9, 71.5, 71.1)),
        (["42.5"], (42.5, None, None, None)),
        ([], (None, None, None, None)),
    ],
)
def test_temperature_formats(lines, expected):
    t = parse_temperature(lines)
    assert (t.current, t.minimum, t.maximum, t.average) == expected
    assert t.raw == lines


def test_state_parsing():
    state = parse_state(["mode: HEATING", "target=96 hold=1", "no separator here"])
    assert state.values == {"mode": "HEATING", "target": "96", "hold": "1"}
    assert len(state.raw) == 3
