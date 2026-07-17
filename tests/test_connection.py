"""Tests for unicast device connections over IPv4 and IPv6.

Thread-connected LIFX devices have no IPv4 address and are reachable only
via IPv6 through a Thread border router, so the unicast connection path
must work for both address families. These tests run a minimal fake LIFX
device on the loopback interface and exercise the full request/response
message flow through Light/Device.
"""

import asyncio
import socket

import pytest

from aiolifx.aiolifx import UDP_BROADCAST_PORT, Light, address_family
from aiolifx.connection import LIFXConnection
from aiolifx.msgtypes import (
    GetHostFirmware,
    GetLabel,
    StateHostFirmware,
    StateLabel,
)
from aiolifx.unpack import unpack_lifx_message

MAC = "d0:73:d5:01:02:03"


def _ipv6_loopback_available():
    if not socket.has_ipv6:
        return False
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.bind(("::1", 0))
        sock.close()
        return True
    except OSError:
        return False


requires_ipv6 = pytest.mark.skipif(
    not _ipv6_loopback_available(), reason="IPv6 loopback not available"
)


class FakeLifxDevice(asyncio.DatagramProtocol):
    """Minimal LIFX device answering label and firmware requests."""

    def __init__(self, label=b"Fake Bulb"):
        self.label = label
        self.transport = None
        self.requests = []

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        request = unpack_lifx_message(data)
        self.requests.append(request)
        if isinstance(request, GetLabel):
            reply = StateLabel(
                request.target_addr,
                request.source_id,
                request.seq_num,
                {"label": self.label},
            )
        elif isinstance(request, GetHostFirmware):
            reply = StateHostFirmware(
                request.target_addr,
                request.source_id,
                request.seq_num,
                {"build": 0, "reserved1": 0, "version": (4 << 16) | 200},
            )
        else:
            return
        self.transport.sendto(reply.generate_packed_message(), addr)


async def _start_fake_device(host):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        FakeLifxDevice, family=address_family(host), local_addr=(host, 0)
    )
    port = transport.get_extra_info("sockname")[1]
    return transport, protocol, port


async def _connect_light(host, port):
    """Connect a Light the same way LIFXConnection.async_setup does."""
    loop = asyncio.get_running_loop()
    transport, light = await loop.create_datagram_endpoint(
        lambda: Light(loop, MAC, host, port),
        family=address_family(host),
        remote_addr=(host, port),
    )
    return transport, light


async def _get_label(light):
    event = asyncio.Event()
    light.get_label(callb=lambda dev, resp: event.set())
    await asyncio.wait_for(event.wait(), timeout=5)
    return light.label


class TestLIFXConnection:
    async def test_ipv4_socket_family(self):
        conn = LIFXConnection("127.0.0.1", MAC)
        await conn.async_setup()
        try:
            sock = conn.transport.get_extra_info("socket")
            assert sock.family == socket.AF_INET
            assert conn.transport.get_extra_info("peername") == (
                "127.0.0.1",
                UDP_BROADCAST_PORT,
            )
        finally:
            conn.async_stop()

    @requires_ipv6
    async def test_ipv6_socket_family(self):
        conn = LIFXConnection("::1", MAC)
        await conn.async_setup()
        try:
            sock = conn.transport.get_extra_info("socket")
            assert sock.family == socket.AF_INET6
            assert conn.transport.get_extra_info("peername")[:2] == (
                "::1",
                UDP_BROADCAST_PORT,
            )
        finally:
            conn.async_stop()

    @requires_ipv6
    async def test_ipv6_device_attributes(self):
        conn = LIFXConnection("::1", MAC)
        await conn.async_setup()
        try:
            assert conn.device.ip_addr == "::1"
            assert conn.device.mac_addr == MAC
        finally:
            conn.async_stop()


class TestRequestResponse:
    async def test_ipv4_label_round_trip(self):
        server_transport, server, port = await _start_fake_device("127.0.0.1")
        transport, light = await _connect_light("127.0.0.1", port)
        try:
            assert await _get_label(light) == "Fake Bulb"
        finally:
            transport.close()
            server_transport.close()

    @requires_ipv6
    async def test_ipv6_label_round_trip(self):
        server_transport, server, port = await _start_fake_device("::1")
        transport, light = await _connect_light("::1", port)
        try:
            assert await _get_label(light) == "Fake Bulb"
        finally:
            transport.close()
            server_transport.close()

    @requires_ipv6
    async def test_ipv6_firmware_round_trip(self):
        server_transport, server, port = await _start_fake_device("::1")
        transport, light = await _connect_light("::1", port)
        try:
            event = asyncio.Event()
            light.get_hostfirmware(callb=lambda dev, resp: event.set())
            await asyncio.wait_for(event.wait(), timeout=5)
            assert light.host_firmware_version == "4.200"
        finally:
            transport.close()
            server_transport.close()

    @requires_ipv6
    async def test_ipv6_multiple_requests_share_connection(self):
        server_transport, server, port = await _start_fake_device("::1")
        transport, light = await _connect_light("::1", port)
        try:
            assert await _get_label(light) == "Fake Bulb"
            event = asyncio.Event()
            light.get_hostfirmware(callb=lambda dev, resp: event.set())
            await asyncio.wait_for(event.wait(), timeout=5)
            assert light.host_firmware_version == "4.200"
            assert len(server.requests) == 2
        finally:
            transport.close()
            server_transport.close()
