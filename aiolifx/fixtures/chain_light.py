from dataclasses import dataclass
from functools import partial
from aiolifx.fixtures.base_fixture import BaseFixture
from aiolifx.fixtures.device_features import DeviceFeatures
from aiolifx.msgtypes import (
    TileGetDeviceChain,
    TileStateDeviceChain,
    TileGet64,
    TileState64,
    TileSet64,
)


# chain devices: Tile
@dataclass
class ChainLightMixin(BaseFixture):
    DEVICE_FEATURES = (
        DeviceFeatures.MATRIX_FIRMWARE_EFFECT,
        DeviceFeatures.MATRIX_FIRMWARE_EFFECT_START_STOP,
    )

    chain = {}
    chain_length = 0

    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        super().__init__(req_with_resp, req_with_ack, fire_and_forget)

    def get_device_chain(self, callb=None):
        """Convenience method to get the devices on a matrix chain.

        This method only works on LIFX matrix devices which include the Tile,
        Candle, Path, Spot and Ceiling.

        The LIFX protocol definition uses the terms tile and chain, even
        though the actual Tile product has been discontinued and is/was the
        only one to have more than one tile on the chain.

        This method populates the tile_devices, tile_devices_count and
        tile_device_width attributes of the corresponding Light object.

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        self.req_with_resp(TileGetDeviceChain, TileStateDeviceChain, callb=callb)

    def resp_set_tiledevicechain(self, resp):
        if resp:
            self.tile_devices = [tile_device for tile_device in resp.tile_devices]
            self.tile_devices_count = resp.tile_devices_count
            self.tile_device_width = self.tile_devices[0]["width"]

    def get64(self, tile_index=0, length=1, width=None, callb=None):
        """Convenience method to get the state of zones on tiles in a chain.

        This method populates returns the state of at least one but up to
        five tiles worth of zones, with up to 64 zones per tile. This is stored
        in the chain attribute of the Light which is an array that has the
        tile_index as the key and a list of 64 HSBK tuples as the value.

        :param tile_index: starting tile on the target chain
        :type tile_index: int
        :param length: how many tiles to target including the starting tile
        :type length: int
        :param width: how many zones per row on the target tile
        :type width: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :rtype: None
        """
        if width is None:
            if self.tile_device_width == 0:
                return
            width = self.tile_device_width

        length = 5

        for i in range(tile_index, length):
            args = {
                "tile_index": i,
                "length": 1,
                "x": 0,
                "y": 0,
                "width": width,
            }

            self.req_with_resp(
                msg_type=TileGet64, response_type=TileState64, payload=args, callb=callb
            )

    def resp_set_tile64(self, resp):
        if resp and isinstance(resp, TileState64):
            self.chain[resp.tile_index] = resp.colors
            self.chain_length = len(self.chain)

    def set64(
        self, tile_index=0, x=0, y=0, width=None, duration=0, colors=None, callb=None
    ):
        """Convenience method to set 64 colors on a tile.

        You can either provide the width of the target tile or
        use the get_device_chain method to retrieve the value
        from the target light. If the width is not provided,
        this method will return without sending a packet.

        The x and y parameters specify the row and column
        starting point from which to change the zones and
        the amount of colors provided will determine how many zones
        are changed.

        To change all zones to the same color, use the set_color
        method.

        Note this method does not return a response even if requested.

        :param tile_index: the starting tile in a chain to target
        :type tile_index: int
        :param x: the starting column to target on the target tile
        :type x: int
        :param y: the starting row to target on the target tile
        :type y: int
        :param width: how many zones per row on the target tile
        :type width: int
        :param duration: how long in seconds to transition to the new colors
        :type duration: int
        :param colors: up to 64 color tuples to apply to the target zones
        :type colors: list[tuple[int, float, float, int]]
        :rtype: None
        """

        if width is None:
            if self.tile_device_width == 0:
                return
            width = self.tile_device_width

        if len(colors) < 64:
            for _ in range(64 - len(colors)):
                colors.append((0, 0, 0, 3500))

        if len(colors) > 64:
            colors = colors[:64]

        payload = {
            "tile_index": tile_index,
            "length": 1,
            "x": x,
            "y": y,
            "width": width,
            "duration": duration * 1000,
            "colors": colors,
        }

        self.fire_and_forget(TileSet64, payload)