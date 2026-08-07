import asyncio

from .aiolifx import UDP_BROADCAST_PORT, Light, address_family


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
            family=address_family(self.host),
            remote_addr=(self.host, UDP_BROADCAST_PORT),
        )

    def async_stop(self):
        """Close the transport, if any.

        Safe to call before setup, after a failed setup, or repeatedly,
        so callers can always clean up without masking a setup error.
        """
        if self.transport is None:
            return
        self.transport.close()
        self.transport = None
