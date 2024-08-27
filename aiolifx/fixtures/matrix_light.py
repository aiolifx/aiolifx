from dataclasses import dataclass
from functools import partial
from math import floor
from aiolifx.fixtures.base_fixture import BaseFixture
from aiolifx.fixtures.device_features import DeviceFeatures
from aiolifx.msgtypes import (
    TileEffectSkyType,
    TileEffectType,
    TileGetTileEffect,
    TileStateTileEffect,
    TileSetTileEffect,
)


# matrix devices: Tile, Candle, Path, Spot, Ceiling
@dataclass
class MatrixLightMixin(BaseFixture):
    DEVICE_FEATURES = (
        DeviceFeatures.MATRIX_FIRMWARE_EFFECT,
        DeviceFeatures.MATRIX_FIRMWARE_EFFECT_START_STOP,
    )
    tile_devices = []
    tile_devices_count = 0
    tile_device_width = 0

    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        super().__init__(req_with_resp, req_with_ack, fire_and_forget)

    def get_tile_effect(self, callb=None):
        """Convenience method to get the currently running effect on a Tile or Candle.

        The value returned is the previously known state of the effect. Use a callback
        to get the actual current state.

        :param callb: callable to be used when a response is received. If not set,
                      self.resp_set_tileeffect will be used.
        :type callb: callable
        :returns: current effect details as a dictionary
        :rtype: dict
        """
        response = self.req_with_resp(
            TileGetTileEffect, TileStateTileEffect, callb=callb
        )
        return self.effect

    def set_tile_effect(
        self,
        effect=0,
        speed=None,
        sky_type=None,
        cloud_saturation_min=None,
        cloud_saturation_max=None,
        palette=[],
        callb=None,
        rapid=False,
    ):
        """Convenience method to start or stop a firmware effect on matrix devices.

        A palette of up to 16 HSBK tuples can be provided for the MORPH effect, otherwise
        it will use the same Exciting theme used by the LIFX smart phone app.

        :param effect: 0/Off, 2/Morph, 3/Flame, 5/Sky (LIFX Ceiling only)
        :type effect: int/str
        :param speed: time in seconds for one cycle of the effect to travel the length of the device
        :type speed: int
        :param sky_type: only used by Sky effect on LIFX ceiling
        :type sky_type: int/str
        :param cloud_saturation_min: only used by Sky effect on LIFX ceiling
        :type cloud_saturation_min: int
        :param cloud_saturation_max: only used by Sky effect on LIFX ceiling
        :type cloud_saturation_max: int
        :param palette: a list of up to 16 HSBK tuples to use for the Morph effect
        :type palette: list[tuple(hue, saturation, brightness, kelvin)]
        :param callb: a callback to use when the response is received
        :type callb: callable
        :param rapid: whether to request an acknowledgement or not
        :type rapid: bool
        :returns: None
        :rtype: None
        """

        # Exciting theme
        default_morph_palette = [
            (0, 65535, 65535, 3500),
            (7282, 65535, 65535, 3500),
            (10923, 65535, 65535, 3500),
            (22209, 65535, 65535, 3500),
            (43509, 65535, 65535, 3500),
            (49334, 65535, 65535, 3500),
            (53521, 65535, 65535, 3500),
        ]

        typ = effect
        if type(effect) == str:
            typ = TileEffectType[effect.upper()].value
        elif type(effect) == int:
            typ = effect if effect in [e.value for e in TileEffectType] else 0

        if typ is TileEffectType.SKY.value:
            speed = floor(speed * 1000) if speed is not None else 50000

            if sky_type is None:
                sky_type = TileEffectSkyType.CLOUDS.value
            elif type(sky_type) == str:
                sky_type = TileEffectSkyType[sky_type.upper()].value
            elif type(sky_type) == int:
                sky_type = (
                    sky_type if sky_type in [e.value for e in TileEffectSkyType] else 2
                )

            if cloud_saturation_min is None:
                cloud_saturation_min = 50
            if cloud_saturation_max is None:
                cloud_saturation_max = 180

        else:
            sky_type = 0
            cloud_saturation_min = 0
            cloud_saturation_max = 0

            if speed is None:
                speed = 3
            if len(palette) == 0 and typ is TileEffectType.MORPH.value:
                palette = default_morph_palette
            if len(palette) > 16:
                palette = palette[:16]

            speed = floor(speed * 1000) if 0 < speed <= 60 else 3000

        palette_count = len(palette)
        payload = {
            "type": typ,
            "speed": speed,
            "duration": 0,
            "sky_type": sky_type,
            "cloud_saturation_min": cloud_saturation_min,
            "cloud_saturation_max": cloud_saturation_max,
            "palette_count": palette_count,
            "palette": palette,
        }

        if rapid:
            self.fire_and_forget(TileSetTileEffect, payload)
        else:
            self.req_with_ack(TileSetTileEffect, payload, callb=callb)

    def resp_set_tiletileeffect(self, resp):
        """Default callback for get_tile_effect and set_tile_effect"""
        if resp:
            self.effect = {"effect": TileEffectType(resp.effect).name.upper()}

            if resp.effect != 0:
                self.effect["speed"] = resp.speed / 1000
                self.effect["duration"] = (
                    0.0
                    if resp.duration == 0
                    else float(f"{resp.duration/1000000000:4f}")
                )
                if resp.effect == TileEffectType.SKY.value:
                    self.effect["sky_type"] = TileEffectSkyType(
                        resp.sky_type
                    ).name.upper()
                    self.effect["cloud_saturation_min"] = resp.cloud_saturation_min
                    self.effect["cloud_saturation_max"] = resp.cloud_saturation_max

                self.effect["palette_count"] = resp.palette_count
                self.effect["palette"] = resp.palette
