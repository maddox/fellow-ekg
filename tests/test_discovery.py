from dataclasses import dataclass, field

from fellow_ekg.discovery import kettle_from_service_info


@dataclass
class FakeInfo:
    name: str = "EKG._ekg._tcp.local."
    server: str = "EKG-f0-73-3c.local."
    port: int = 8888
    addresses: list[str] = field(default_factory=lambda: ["fe80::1", "192.168.30.22"])

    def parsed_addresses(self):
        return self.addresses


def test_from_service_info():
    k = kettle_from_service_info(FakeInfo())
    assert k.name == "EKG"
    assert k.host == "192.168.30.22"
    assert k.mdns_port == 8888
    assert k.mac_suffix == "f0:73:3c"
    assert k.unique_id == "f0:73:3c"


def test_unexpected_hostname_falls_back_to_hostname_id():
    k = kettle_from_service_info(FakeInfo(server="kettle.local."))
    assert k.mac_suffix is None
    assert k.unique_id == "kettle.local."


def test_ipv6_only_is_skipped():
    assert kettle_from_service_info(FakeInfo(addresses=["fe80::1"])) is None
