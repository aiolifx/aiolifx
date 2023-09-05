from dataclasses import dataclass
from functools import partial
from math import floor
from typing import Dict, List, Union
from aiolifx.fixtures.base_fixture import RootFixture, BaseFixture
from aiolifx.fixtures.device_features import DeviceFeatures
from aiolifx.msgtypes import (
    MultiZoneDirection,
    MultiZoneEffectType,
    MultiZoneGetColorZones,
    MultiZoneGetExtendedColorZones,
    MultiZoneGetMultiZoneEffect,
    MultiZoneSetColorZones,
    MultiZoneSetExtendedColorZones,
    MultiZoneSetMultiZoneEffect,
    MultiZoneStateExtendedColorZones,
    MultiZoneStateMultiZone,
    MultiZoneStateMultiZoneEffect,
    TileEffectType,
    TileGetTileEffect,
    TileSetTileEffect,
    TileStateTileEffect,
)


@dataclass
class MultizoneLightMixin(RootFixture, BaseFixture):
    capabilities = [
        DeviceFeatures.MULTIZONE_FIRMWARE_EFFECT,
        DeviceFeatures.MULTIZONE_FIRMWARE_EFFECT_START_STOP,
    ]

    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        super().__init__(req_with_resp, req_with_ack, fire_and_forget)

    # Multizone
    def get_color_zones(self, start_index, end_index=None, callb=None):
        """Convenience method to request the state of colour by zones from the device

        This method will request the information from the device and request that callb
        be executed when a response is received.

            :param start_index: Index of the start of the zone of interest
            :type start_index: int
            :param end_index: Index of the end of the zone of interest. By default start_index+7
            :type end_index: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: None
            :rtype: None
        """
        if end_index is None:
            end_index = start_index + 7
        args = {
            "start_index": start_index,
            "end_index": end_index,
        }
        self.req_with_resp(
            MultiZoneGetColorZones, MultiZoneStateMultiZone, payload=args, callb=callb
        )

    def set_color_zones(
        self,
        start_index,
        end_index,
        color,
        duration=0,
        apply=1,
        callb=None,
        rapid=False,
    ):
        """Convenience method to set the colour status zone of the device

        This method will send a MultiZoneSetColorZones message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param start_index: Index of the start of the zone of interest
            :type start_index: int
            :param end_index: Index of the end of the zone of interest. By default start_index+7
            :type end_index: int
            :param apply: Indicates if the colour change is to be applied or memorized. Default: 1
            :type apply: int
            :param value: The new state, a dictionary onf int with 4 keys Hue, Saturation, Brightness, Kelvin
            :type value: dict
            :param duration: The duration, in seconds, of the power state transition.
            :type duration: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """
        if len(color) == 4:
            args = {
                "start_index": start_index,
                "end_index": end_index,
                "color": color,
                "duration": duration,
                "apply": apply,
            }

            mypartial = partial(self.resp_set_multizonemultizone, args=args)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)

            if rapid:
                self.fire_and_forget(MultiZoneSetColorZones, args, num_repeats=1)
                mycallb(self, None)
            else:
                self.req_with_ack(MultiZoneSetColorZones, args, callb=mycallb)

    # A multi-zone MultiZoneGetColorZones returns MultiZoneStateMultiZone -> multizonemultizone
    def resp_set_multizonemultizone(self, resp: MultiZoneStateMultiZone, args=None):
        """Default callback for get-color_zones/set_color_zones"""
        if args:
            if self.color_zones:
                for i in range(args["start_index"], args["end_index"] + 1):
                    self.color_zones[i] = args["color"]
        elif resp:
            if self.color_zones is None:
                self.color_zones = [None] * resp.count
            try:
                for i in range(resp.index, min(resp.index + 8, resp.count)):
                    if i > len(self.color_zones) - 1:
                        self.color_zones += [resp.color[i - resp.index]] * (
                            i - len(self.color_zones)
                        )
                        self.color_zones.append(resp.color[i - resp.index])
                    else:
                        self.color_zones[i] = resp.color[i - resp.index]
            except:
                # I guess this should not happen but...
                pass

    def get_multizone_effect(self, callb=None):
        """Convenience method to get the currently running firmware effect on the device.

        The value returned is the previously known state of the device. Use a callback
        to get the current state of the device.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_multizonemultizoneeffect will be used.
        :type callb: callable
        :returns: current effect details as a dictionary
        :rtype: dict
        """
        response = self.req_with_resp(
            MultiZoneGetMultiZoneEffect, MultiZoneStateMultiZoneEffect, callb=callb
        )
        return self.effect

    def set_multizone_effect(
        self, effect=0, speed=3, direction=0, callb=None, rapid=False
    ):
        """Convenience method to start or stop the Move firmware effect on multizone devices.

        Compatible devices include LIFX Z, Lightstrip and Beam and can be identified by
        checking if products_dict[device.product].multizone is True. Multizone devices
        only have one firmware effect named "MOVE". The effect can be started and stopped
        without the device being powered on. The effect will not be visible if the
        device is a single uniform color.

        Sending a set_power(0) to the device while the effect is running does not stop the effect.
        Physically powering off the device will stop the effect. And the device.


        :param effect: 0/Off, 1/Move
        :type effect: int
        :param speed: time in seconds for one cycle of the effect to travel the length of the device
        :type speed: float
        :param direction: 0/Right, 1/Left
        :type direction: int
        """

        typ = effect
        if type(effect) == str:
            typ = MultiZoneEffectType[effect.upper()].value
        elif type(effect) == int:
            typ = effect if effect in [e.value for e in MultiZoneEffectType] else 0

        speed = floor(speed * 1000) if 0 < speed <= 60 else 3000

        if type(direction) == str:
            direction = MultiZoneDirection[direction.upper()].value
        elif type(direction) == int:
            direction = (
                direction if direction in [d.value for d in MultiZoneDirection] else 0
            )

        payload = {
            "type": typ,
            "speed": speed,
            "duration": 0,
            "direction": direction,
        }

        if rapid:
            self.fire_and_forget(MultiZoneSetMultiZoneEffect, payload)
        else:
            self.req_with_ack(MultiZoneSetMultiZoneEffect, payload, callb=callb)

    def resp_set_multizonemultizoneeffect(self, resp):
        """Default callback for get_multizone_effect"""

        if resp:
            self.effect = {"effect": MultiZoneEffectType(resp.effect).name.upper()}

            if resp.effect != 0:
                self.effect["speed"] = resp.speed / 1000
                self.effect["duration"] = (
                    0.0
                    if resp.duration == 0
                    else float(f"{self.effect['duration'] / 1000000000:4f}")
                )
                self.effect["direction"] = MultiZoneDirection(
                    resp.direction
                ).name.capitalize()

    def get_extended_color_zones(self, callb=None):
        """
        Convenience method to request the state of all zones of a multizone device
        in a single request.

        The device must have the extended_multizone feature to use this method.

        This method will request the information from the device and request that callb
        be executed when a response is received.

        :param callb: Callable to be used when the response is received. If not set,
                    self.resp_set_multizonemultizoneextendedcolorzones will be used.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        self.req_with_resp(
            MultiZoneGetExtendedColorZones,
            MultiZoneStateExtendedColorZones,
            callb=callb,
        )

    def set_extended_color_zones(
        self,
        colors,
        colors_count,
        zone_index=0,
        duration=0,
        apply=1,
        callb=None,
        rapid=False,
    ):
        """
        Convenience method to set the state of all zones on a multizone device in
        a single request.

        The device must have the extended_multizone feature to use this method.
        There must be 82 color tuples in the colors list regardless of how many
        zones the device has. Use the colors_count parameter to specify the number
        of colors from the colors list that should be applied to the device and
        use the zone_index parameter to specify the starting zone.

        :param colors List of color dictionaries with HSBK keys
        :type colors List[dict[str, int]]
        :param colors_count How many color values in the color list to apply to the device
        :type colors_count int
        :param zone_index Which zone to start applying the colors from (default 0)
        :type zone_index int
        :param duration duration in seconds to apply the colors (default 0)
        :type duration int
        :param apply whether to apply the colors or buffer the new value (default 1 or apply)
        :type apply int
        :param callb Callback function to invoke when the response is received
        :type callb Callable
        :returns None
        :rtype None
        """
        if len(colors) == 82:
            args = {
                "duration": duration,
                "apply": apply,
                "zone_index": zone_index,
                "colors_count": colors_count,
                "colors": colors,
            }
            mypartial = partial(self.resp_set_multizoneextendedcolorzones, args=args)

            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)

            if rapid:
                self.fire_and_forget(
                    MultiZoneSetExtendedColorZones, args, num_repeats=1
                )
                mycallb(self, None)
            else:
                self.req_with_ack(MultiZoneSetExtendedColorZones, args, callb=mycallb)

    def resp_set_multizoneextendedcolorzones(self, resp, args=None):
        """Default callback for get_extended_color_zones"""
        if args:
            if self.color_zones:
                for i in range(args["zone_index"], args["colors_count"]):
                    self.color_zones[i] = args["colors"][i]

        elif resp:
            self.zones_count = resp.zones_count
            self.color_zones = resp.colors[resp.zone_index : resp.colors_count]

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

    def set_tile_effect(self, effect=0, speed=3, palette=None, callb=None, rapid=False):
        """Convenience method to start or stop a firmware effect on matrix devices.

        A palette of up to 16 HSBK tuples can be provided for the MORPH effect, otherwise
        it will use the same Exciting theme used by the LIFX smart phone app.

        :param effect: 0/Off, 2/Morph, 3/Flame
        :type effect: int/str
        :param speed: time in seconds for one cycle of the effect to travel the length of the device
        :type speed: int
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
        default_tile_palette = [
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

        speed = floor(speed * 1000) if 0 < speed <= 60 else 3000
        if palette is None:
            palette = default_tile_palette
        if len(palette) > 16:
            palette = palette[:16]
        palette_count = len(palette)

        payload = {
            "type": typ,
            "speed": speed,
            "duration": 0,
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
                    else float(f"{self.effect['duration']/1000000000:4f}")
                )
                self.effect["palette_count"] = resp.palette_count
                self.effect["palette"] = resp.palette
