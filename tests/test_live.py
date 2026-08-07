"""Opt-in tests against real devices on the local network.

These are skipped unless the corresponding environment variables are set:

    AIOLIFX_LIVE_HOST / AIOLIFX_LIVE_MAC
        An IPv4 (WiFi) device to test against.
    AIOLIFX_LIVE_HOST6 / AIOLIFX_LIVE_MAC6
        An IPv6 (e.g. Thread, via a border router) device to test against.

Example:
    AIOLIFX_LIVE_HOST6=fd12:3456:789a:1:2:3:4:5 \
    AIOLIFX_LIVE_MAC6=d0:73:d5:01:02:03 pytest tests/test_live.py
"""

import asyncio
import os
import socket

import pytest

from aiolifx.connection import LIFXConnection


async def _check_device(host, mac, family):
    conn = LIFXConnection(host, mac)
    await conn.async_setup()
    try:
        sock = conn.transport.get_extra_info("socket")
        assert sock.family == family
        event = asyncio.Event()
        conn.device.get_label(callb=lambda dev, resp: event.set())
        await asyncio.wait_for(event.wait(), timeout=5)
        assert conn.device.label
    finally:
        conn.async_stop()


@pytest.mark.skipif(
    not (os.environ.get("AIOLIFX_LIVE_HOST") and os.environ.get("AIOLIFX_LIVE_MAC")),
    reason="AIOLIFX_LIVE_HOST/AIOLIFX_LIVE_MAC not set",
)
async def test_live_ipv4_device():
    await _check_device(
        os.environ["AIOLIFX_LIVE_HOST"],
        os.environ["AIOLIFX_LIVE_MAC"],
        socket.AF_INET,
    )


@pytest.mark.skipif(
    not (os.environ.get("AIOLIFX_LIVE_HOST6") and os.environ.get("AIOLIFX_LIVE_MAC6")),
    reason="AIOLIFX_LIVE_HOST6/AIOLIFX_LIVE_MAC6 not set",
)
async def test_live_ipv6_device():
    await _check_device(
        os.environ["AIOLIFX_LIVE_HOST6"],
        os.environ["AIOLIFX_LIVE_MAC6"],
        socket.AF_INET6,
    )
