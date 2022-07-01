import asyncio

from .aiolifx import UDP_BROADCAST_PORT, Light


class AwaitAioLIFX:
    """Wait for an aiolifx callback and return the message."""

    def __init__(self):
        """Initialize the wrapper."""
        self.message = None
        self.event = asyncio.Event()

    def callback(self, bulb, message):
        """Handle responses."""
        self.message = message
        self.event.set()

    async def wait(self, method):
        """Call an aiolifx method and wait for its response."""
        self.message = None
        self.event.clear()
        method(callb=self.callback)

        await self.event.wait()
        return self.message


class LIFXConnection:
    """Manage a connection to a LIFX device."""

    def __init__(self, host, mac):
        """Init the connection."""
        self.host = host
        self.mac = mac
        self.device = None
        self.transport = None

    async def async_setup(self):
        """Ensure we are connected."""
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: Light(loop, self.mac, self.host),
            remote_addr=(self.host, UDP_BROADCAST_PORT),
        )

    def async_stop(self):
        """Close the transport."""
        assert self.transport is not None
        self.transport.close()
