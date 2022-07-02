import asyncio

from .aiolifx import UDP_BROADCAST_PORT, Light


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
        self.transport, self.device = await loop.create_datagram_endpoint(
            lambda: Light(loop, self.mac, self.host),
            remote_addr=(self.host, UDP_BROADCAST_PORT),
        )

    def async_stop(self):
        """Close the transport."""
        assert self.transport is not None
        self.transport.close()
