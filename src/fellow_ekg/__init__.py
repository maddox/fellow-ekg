"""Async local client for the Fellow EKG Pro kettle."""

from .client import EKGClient
from .discovery import SERVICE_TYPE, DiscoveredKettle, async_discover, kettle_from_service_info
from .exceptions import EKGCommandError, EKGConnectionError, EKGError
from .models import EKGState, FirmwareInfo, Temperature
from .parser import parse_cli_output, parse_firmware_info, parse_state, parse_temperature

__all__ = [
    "SERVICE_TYPE",
    "DiscoveredKettle",
    "async_discover",
    "kettle_from_service_info",
    "EKGClient",
    "EKGCommandError",
    "EKGConnectionError",
    "EKGError",
    "EKGState",
    "FirmwareInfo",
    "Temperature",
    "parse_cli_output",
    "parse_firmware_info",
    "parse_state",
    "parse_temperature",
]
