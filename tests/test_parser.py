from pathlib import Path

import pytest

from fellow_ekg import EKGCommandError, parse_cli_output, parse_firmware_info, parse_state

# Real responses captured from a kettle on firmware 1.2.5CL.
FIXTURES = Path(__file__).parent / "fixtures"
STATE_HTML = (FIXTURES / "state.html").read_text()
TEMP_HTML = (FIXTURES / "temp.html").read_text()
ROOT_HTML = (FIXTURES / "root.html").read_text()

FORM = '<form action="cli" method="GET"><input name="cmd"></form>\n'
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
    info = parse_firmware_info(ROOT_HTML)
    assert info.version == "1.2.5CL CLI"
    assert info.build_date == "Dec 10 2025"
    assert info.build_time == "05:25:49"
    assert info.running_partition == "ota_0"


def test_real_state_output():
    lines = parse_cli_output(STATE_HTML, "state")
    # Log lines from other tags ("Main: OTA ...") and the ret trailer are dropped.
    assert lines[0] == "scrname=wnd"
    assert lines[-1] == "ble conn=0"
    assert not any("OTA" in line or "ret 0" in line for line in lines)

    state = parse_state(lines)
    assert state.mode == "S_Off"
    assert state.temperature == pytest.approx(26.16, abs=0.01)
    assert state.target_temperature == pytest.approx(96.11, abs=0.01)
    assert state.boil_temperature == 100.0
    assert state.display_setpoint == (205.0, "F")
    assert state.screen == "wnd"
    assert state.ble_connected is False
    assert state.kettle_flags == {"ho": 0, "wd": 0, "nw": 0, "ipb": 0, "bf": 0, "tr": 0}
    assert state.values["ticks"].count(" ") == 2


def test_real_temp_output():
    # 'temp' prints stats only once tstprd is set; plain lines are kept.
    lines = parse_cli_output(TEMP_HTML, "temp")
    assert lines[0] == "temp av 0.000000"
    assert not any("tstprd" in line for line in lines)


def test_fahrenheit_values_convert_to_celsius():
    state = parse_state(["tempr=212 F"])
    assert state.temperature == pytest.approx(100.0)


def test_missing_fields_are_none():
    state = parse_state([])
    assert state.temperature is None
    assert state.mode is None
    assert state.ble_connected is None
    assert state.kettle_flags == {}


def test_help_lines_logged_by_cli_are_kept():
    assert parse_cli_output(HELP_SNIPPET, "help") == ["reset : reset", "state : print state"]


def test_unknown_command_raises():
    with pytest.raises(EKGCommandError, match="cannot find command"):
        parse_cli_output(UNKNOWN_CMD, "wifion")


def test_nonzero_return_raises():
    body = FORM + "I (1) Cli: cmd len 4: 'temp'\nI (2) Cli: command 'temp' ret 1\n"
    with pytest.raises(EKGCommandError, match="returned 1"):
        parse_cli_output(body, "temp")


def test_stale_output_from_other_command_is_rejected():
    with pytest.raises(EKGCommandError, match="no output"):
        parse_cli_output(UNKNOWN_CMD, "state")


def test_only_output_after_last_echo():
    body = HELP_SNIPPET + "I (1) Cli: cmd len 5: 'state'\nmode=S_Off\nI (2) Cli: command 'state' ret 0\n"
    assert parse_cli_output(body, "state") == ["mode=S_Off"]
