# fellow-ekg

Async Python library for controlling a **Fellow Stagg EKG Pro** electric kettle
over your local network, with no cloud and no app.

The EKG Pro is discontinued and its app no longer works, but the kettle's
firmware still runs a small HTTP server with a debug command line. This
library wraps that interface so the kettle can be used from scripts and
Home Assistant.

> Not affiliated with or endorsed by Fellow. Use at your own risk; see
> [Safety](#safety).

## Features

- Find kettles on the LAN via mDNS
- Read firmware info, water temperature, target and boil temperatures, and kettle mode
- Turn the heater on and off, with an automatic shut-off timer
- Fully async (`aiohttp`), and accepts a shared session, as Home Assistant expects
- Small: one required dependency (`aiohttp`), with `zeroconf` optional for discovery

## Installation

```bash
pip install "fellow-ekg[discovery] @ git+https://github.com/maddox/fellow-ekg"
```

Drop the `[discovery]` extra if you don't need mDNS discovery.
Requires Python 3.11+.

## Quick start

```python
import asyncio
from fellow_ekg import EKGClient, async_discover

async def main():
    kettles = await async_discover(timeout=5)
    print(kettles)

    async with EKGClient(kettles[0].host) as kettle:
        print(await kettle.get_firmware_info())
        state = await kettle.get_state()
        print(state.mode, state.temperature, state.target_temperature)
        # S_Off 26.04 96.11

asyncio.run(main())
```

## Discovery

Kettles advertise `_ekg._tcp.local.` over mDNS with a hostname like
`EKG-f0-73-3c.local.`. The suffix is the last three bytes of the MAC address
and is exposed as `unique_id`.

```python
await async_discover(timeout=5)
# [DiscoveredKettle(name='EKG', hostname='EKG-f0-73-3c.local.', host='192.168.30.22',
#                   mdns_port=8888, mac_suffix='f0:73:3c')]
```

The advertised port (8888) isn't the CLI; the client always talks to port 80.
Pass an existing `AsyncZeroconf` instance via `aiozc=` to reuse it.

## API

### `EKGClient(host, session=None, *, port=80, timeout=10)`

| Method | Kettle command | Returns / notes |
|---|---|---|
| `get_firmware_info()` | `GET /` | `FirmwareInfo(version, build_date, build_time, running_partition)`. No side effects; good for connection checks |
| `get_state()` | `state` | `EKGState`; see below. One request returns everything |
| `get_temperature()` | `state` | Current water temperature in °C (`float \| None`) |
| `heat_on(max_seconds=600)` | `heaton` | Turns the heater on and schedules `heatoff` after `max_seconds` |
| `heat_off()` | `heatoff` | Turns the heater off and cancels the timer |
| `command(cmd)` | any | Escape hatch: returns output lines for any CLI command |
| `close()` | | Closes the session if the client created it |

Errors:

- `EKGConnectionError`: the kettle is unreachable, timed out, or returned an HTTP error
- `EKGCommandError`: the kettle rejected the command, or produced no output for it
- Both inherit from `EKGError`

### `EKGState`

All temperatures are in °C, whatever the kettle's display units are.

| Property | Source line | Example |
|---|---|---|
| `mode` | `mode=S_Off` | `"S_Off"` |
| `temperature` | `tempr=26.110954 C` | `26.11`, the current water temperature |
| `target_temperature` | `temprT=96.111115 C` | `96.11`, the kettle's own target (set on the dial) |
| `boil_temperature` | `temprB=100.000000 C` | `100.0`, adjusted for the altitude setting |
| `display_setpoint` | `temps=205 F` | `(205.0, "F")`, the target as the display shows it |
| `screen` | `scrname=wnd` | `"wnd"` |
| `clock` | `clock=16:39` | `"16:39"` |
| `ble_connected` | `ble conn=0` | `False` |
| `kettle_flags` | `ketl= ho 0 wd 0 nw 0 ipb 0 bf 0 tr 0` | `{"ho": 0, ...}`; meanings unknown |
| `values` | every `key=value` line | `dict[str, str]`, verbatim |
| `raw` | all output lines | `list[str]` |

Full `state` output from a real kettle:

```
scrname=wnd
value=50663463
mode=S_Off
tempr=26.110954 C
temprB=100.000000 C
temprT=96.111115 C
ketl= ho 0 wd 0 nw 0 ipb 0 bf 0 tr 0
temps=205 F
tempsc=205 F
units=0
clock=16:39
ticks=-1430236073 -1439438423 -1430237792
ble conn=0
```

### Discovery

- `async_discover(timeout=5.0, aiozc=None) -> list[DiscoveredKettle]`
- `kettle_from_service_info(info) -> DiscoveredKettle | None`: turns a zeroconf
  `ServiceInfo` into a `DiscoveredKettle`
- `SERVICE_TYPE = "_ekg._tcp.local."`

## Home Assistant

This library is meant to back a custom integration:

- Create the client with HA's shared session:
  `EKGClient(host, async_get_clientsession(hass))`
- Add `"zeroconf": ["_ekg._tcp.local."]` to `manifest.json` so HA discovers
  kettles automatically, and use `DiscoveredKettle.unique_id` as the config
  entry's unique ID
- Use `get_firmware_info()` in the config flow to check the connection
- Poll `get_state()` with a `DataUpdateCoordinator`

## Safety

`heat_on()` sends `heaton`, which **switches the heater relay pin directly**.
It very likely bypasses the kettle's own target-temperature control and
boil-dry protection. Once on, the heater stays on until something turns it off.

The library adds a safety net: `heat_on()` sends `heatoff` after
`max_seconds` (default 10 minutes). That timer only lasts as long as the
Python process does. If you build on this:

- Turn the heater off when the water reaches your target temperature
- Never run it with an empty kettle
- Don't pass `max_seconds=None` unless you have another way to shut it off

## How it works

The kettle is an ESP32 that serves:

| Endpoint | What it is |
|---|---|
| `GET /` | Status page: firmware version, build date, OTA partition layout |
| `GET /cli?cmd=<command>` | Debug CLI. Returns an HTML form plus ESP-IDF log lines |
| `GET /api` | Exists, but its request format is unknown |

None of these require authentication. A CLI response looks like:

```
<form action="cli" method="GET">...</form>
I (2864731213) Cli: cmd len 5: 'state'
I (2864731223) Main: OTA vd 1 ldt 2765075 ...
scrname=wnd
mode=S_Off
I (2864731243) Cli: command 'state' ret 0
```

The page appears to show a shared log buffer that can include output from
earlier commands. The parser keeps only the lines between the *last* echo of
the command it sent and that command's `ret` trailer. It drops log lines from
other tasks, and raises an error if the echo is missing or `ret` isn't 0. It
never returns stale output. The client also sends commands one at a time.

The `temp` command looks like the obvious way to read temperature, but it only
reports statistics after `tstprd` has been set, and returns zeros otherwise.
The library reads temperature from `state` instead.

Firmware this was built against: `1.2.5CL CLI` (built Dec 10 2025), with
factory partition `1.1.14SSB`.

### Notable CLI commands

`help` lists about 80 commands. Highlights:

| Group | Commands |
|---|---|
| Read-only | `state`, `temp`, `prts` (settings), `prtclock`, `fwinfo`, `heapprt`, `logprt`, `bc` |
| Physical controls | `1`, `2` (short press), `1d`/`1u`, `2d`/`2u` (press/release), `left`/`right` (dial) |
| Settings | `setunitsc`/`setunitsf`, `setclock`, `setanalog`/`setdigital`, `setaltitudem`/`setaltitudef`, `setsetting` |
| Heater (raw GPIO) | `heaton`/`heatoff`, `warmon`/`warmoff`, `warmduty` |
| Wi-Fi / BLE | `wifiprt`, `wifioff`, `wifista`, `wifisap`, `provreset`, `bleen`/`bledis` |
| Firmware (dangerous) | `httpfw <url>`, `setpart`, `eraseotherpart`, `clrsettings`, `reset` |

The button and dial commands go through the kettle's normal UI logic, so
they're likely a safer route to "heat to target temperature" than raw GPIO.
That's a possible future addition.

## Security note

Anyone who can reach the kettle on port 80 can turn on the heater or flash new
firmware. Put it on an isolated IoT VLAN and block its internet access. Allow
only your Home Assistant host to reach it.

## Known gaps

- Only the `S_Off` mode has been observed so far. Other mode names, such as
  heating or hold, are passed through as-is.
- The `ketl` flags and `units` values aren't decoded yet.
- Heat control is raw GPIO, not "heat to X°".

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

The tests use real responses captured from a kettle (`tests/fixtures/`) and a
fake kettle on localhost. They never touch a real device.
