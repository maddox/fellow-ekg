"""Client tests against a fake kettle on localhost. Never touches the real device."""

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from fellow_ekg import EKGClient, EKGCommandError, EKGConnectionError

KNOWN = {
    "temp": ["tempr min 20.0 max 21.0 av 20.5"],
    "state": ["mode: IDLE"],
    "heaton": [],
    "heatoff": [],
}


@pytest.fixture
async def kettle():
    received: list[str] = []

    async def cli(request: web.Request) -> web.Response:
        cmd = request.query.get("cmd", "")
        received.append(cmd)
        body = f"<form></form>I (1) Cli: cmd len {len(cmd)}: '{cmd}'\n"
        if cmd in KNOWN:
            body += "".join(f"I (2) Cli: {line}\n" for line in KNOWN[cmd])
        else:
            body += f"I (2) Cli: cannot find command '{cmd}'\n"
        return web.Response(text=body, content_type="text/html")

    async def root(request: web.Request) -> web.Response:
        return web.Response(text="<h1>EKG</h1>Current version: 1.2.5CL CLI<br>", content_type="text/html")

    app = web.Application()
    app.router.add_get("/cli", cli)
    app.router.add_get("/", root)
    server = TestServer(app)
    await server.start_server()
    client = EKGClient(server.host, port=server.port)
    yield client, received
    await client.close()
    await server.close()


async def test_reads(kettle):
    client, received = kettle
    assert (await client.get_firmware_info()).version == "1.2.5CL CLI"
    assert (await client.get_temperature()).average == 20.5
    assert (await client.get_state()).values == {"mode": "IDLE"}
    assert received == ["temp", "state"]


async def test_heat_on_off(kettle):
    client, received = kettle
    await client.heat_on()
    await client.heat_off()
    assert received == ["heaton", "heatoff"]
    assert client._heat_off_task is None


async def test_heat_watchdog_turns_heater_off(kettle):
    client, received = kettle
    await client.heat_on(max_seconds=0.05)
    await asyncio.sleep(0.2)
    assert received == ["heaton", "heatoff"]


async def test_unknown_command(kettle):
    client, _ = kettle
    with pytest.raises(EKGCommandError):
        await client.command("bogus")


async def test_unreachable():
    async with EKGClient("127.0.0.1", port=1, timeout=1) as client:
        with pytest.raises(EKGConnectionError):
            await client.get_temperature()
