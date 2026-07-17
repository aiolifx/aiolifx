"""Tests for LifxDiscovery address family and remote address selection."""

import asyncio
import socket

from aiolifx.aiolifx import UDP_BROADCAST_PORT, LifxDiscovery
from aiolifx.message import BROADCAST_MAC
from aiolifx.msgtypes import StateService

MAC = "d0:73:d5:01:02:03"
SOURCE_ID = 12345


class RecordingLoop:
    """Stand-in loop that records create_datagram_endpoint arguments."""

    def __init__(self):
        self.endpoints = []

    def create_datagram_endpoint(self, factory, **kwargs):
        self.endpoints.append(kwargs)

        async def coro():
            return None, factory()

        return coro()


def state_service_packet(mac_addr=MAC, port=UDP_BROADCAST_PORT):
    """Build the wire format of a device's StateService discovery answer."""
    return StateService(
        mac_addr, SOURCE_ID, seq_num=0, payload={"service": 1, "port": port}
    ).generate_packed_message()


def make_discovery(loop, **kwargs):
    discovery = LifxDiscovery(loop, parent=None, **kwargs)
    return discovery


class TestDatagramReceived:
    async def test_ipv4_response_uses_af_inet(self):
        loop = RecordingLoop()
        discovery = make_discovery(loop)
        discovery.datagram_received(
            state_service_packet(), ("192.168.1.50", UDP_BROADCAST_PORT)
        )
        await asyncio.sleep(0)
        assert len(loop.endpoints) == 1
        endpoint = loop.endpoints[0]
        assert endpoint["family"] == socket.AF_INET
        assert endpoint["remote_addr"] == ("192.168.1.50", UDP_BROADCAST_PORT)
        light = discovery.lights[MAC]
        assert light.ip_addr == "192.168.1.50"
        assert light.port == UDP_BROADCAST_PORT

    async def test_ipv6_response_uses_af_inet6(self):
        # A discovery answer arriving over IPv6 comes with a 4-tuple
        # address and must be connected back to with an IPv6 socket.
        loop = RecordingLoop()
        discovery = make_discovery(loop)
        ipv6 = "fd12:3456:789a:1:2:3:4:5"
        discovery.datagram_received(
            state_service_packet(), (ipv6, UDP_BROADCAST_PORT, 0, 0)
        )
        await asyncio.sleep(0)
        endpoint = loop.endpoints[0]
        assert endpoint["family"] == socket.AF_INET6
        assert endpoint["remote_addr"] == (ipv6, UDP_BROADCAST_PORT)
        assert discovery.lights[MAC].ip_addr == ipv6

    async def test_ipv6prefix_uses_eui64_link_local(self):
        loop = RecordingLoop()
        discovery = make_discovery(loop, ipv6prefix="fe80::")
        discovery.datagram_received(
            state_service_packet(), ("192.168.1.50", UDP_BROADCAST_PORT)
        )
        await asyncio.sleep(0)
        endpoint = loop.endpoints[0]
        assert endpoint["family"] == socket.AF_INET6
        remote_ip = endpoint["remote_addr"][0]
        assert remote_ip == "fe80::d273:d5ff:fe01:0203"
        # The synthesized address must be parseable.
        socket.inet_pton(socket.AF_INET6, remote_ip)

    async def test_broadcast_mac_ignored(self):
        loop = RecordingLoop()
        discovery = make_discovery(loop)
        discovery.datagram_received(
            state_service_packet(mac_addr=BROADCAST_MAC),
            ("192.168.1.50", UDP_BROADCAST_PORT),
        )
        await asyncio.sleep(0)
        assert loop.endpoints == []
        assert discovery.lights == {}

    async def test_custom_service_port_preserved(self):
        loop = RecordingLoop()
        discovery = make_discovery(loop)
        discovery.datagram_received(
            state_service_packet(port=56701), ("192.168.1.50", UDP_BROADCAST_PORT)
        )
        await asyncio.sleep(0)
        assert loop.endpoints[0]["remote_addr"] == ("192.168.1.50", 56701)

    async def test_rediscovery_updates_address_of_unregistered_light(self):
        # A known but unregistered light rediscovered at a new address
        # must be reconnected to that address with the matching family.
        loop = RecordingLoop()
        discovery = make_discovery(loop)
        discovery.datagram_received(
            state_service_packet(), ("192.168.1.50", UDP_BROADCAST_PORT)
        )
        await asyncio.sleep(0)
        light = discovery.lights[MAC]
        assert not light.registered
        discovery.datagram_received(
            state_service_packet(), ("192.168.1.99", UDP_BROADCAST_PORT)
        )
        await asyncio.sleep(0)
        assert discovery.lights[MAC] is light
        assert light.ip_addr == "192.168.1.99"
        assert len(loop.endpoints) == 2
        assert loop.endpoints[1]["family"] == socket.AF_INET
        assert loop.endpoints[1]["remote_addr"] == ("192.168.1.99", UDP_BROADCAST_PORT)

    async def test_rediscovery_of_registered_light_is_ignored(self):
        loop = RecordingLoop()
        discovery = make_discovery(loop)
        discovery.datagram_received(
            state_service_packet(), ("192.168.1.50", UDP_BROADCAST_PORT)
        )
        await asyncio.sleep(0)
        light = discovery.lights[MAC]
        light.registered = True
        discovery.datagram_received(
            state_service_packet(), ("192.168.1.99", UDP_BROADCAST_PORT)
        )
        await asyncio.sleep(0)
        assert light.ip_addr == "192.168.1.50"
        assert len(loop.endpoints) == 1
