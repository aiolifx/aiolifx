from dataclasses import dataclass
from math import floor
from functools import partial
from aiolifx.fixtures.base_fixture import RootFixture, BaseFixture

from aiolifx.fixtures.device_features import DeviceFeatures

from aiolifx.msgtypes import (
    LightGet,
    LightGetPower,
    LightSetColor,
    LightSetPower,
    LightSetWaveform,
    LightSetWaveformOptional,
    LightState,
    LightStatePower,
)

MAX_UNSIGNED_16_BIT_INTEGER_VALUE = int("0xFFFF", 16)


@dataclass
class LightMixin(RootFixture, BaseFixture):
    capabilities = [
        DeviceFeatures.INFO,
        DeviceFeatures.FIRMWARE,
        DeviceFeatures.WIFI,
        DeviceFeatures.UPTIME,
        DeviceFeatures.REBOOT,
        DeviceFeatures.POWER,
        DeviceFeatures.WHITE,
    ]
    color = None
    zones_count: int = 1
    effect = {"effect": None}

    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        super().__init__(req_with_resp, req_with_ack, fire_and_forget)

    def get_power(self, callb=None):
        """Convenience method to request the power status from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        if self.power_level is None:
            response = self.req_with_resp(LightGetPower, LightStatePower, callb=callb)
        return self.power_level

    def set_power(self, value, callb=None, duration=0, rapid=False):
        """Convenience method to set the power status of the device

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The new state
            :type value: str/bool/int
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
        on = [True, 1, "on"]
        off = [False, 0, "off"]
        if value in on:
            myvalue = MAX_UNSIGNED_16_BIT_INTEGER_VALUE
        else:
            myvalue = 0
        mypartial = partial(self.resp_set_lightpower, power_level=myvalue)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)
        if not rapid:
            response = self.req_with_ack(
                LightSetPower,
                {"power_level": myvalue, "duration": duration},
                callb=mycallb,
            )
        else:
            response = self.fire_and_forget(
                LightSetPower,
                {"power_level": myvalue, "duration": duration},
                num_repeats=1,
            )
            self.power_level = myvalue
            if callb:
                callb(self, None)

    # Here lightpower because LightStatePower message will give lightpower
    def resp_set_lightpower(self, resp, power_level=None):
        """Default callback for set_power"""
        if power_level is not None:
            self.power_level = power_level
        elif resp:
            self.power_level = resp.power_level

    # value should be a dictionary with the the following keys: transient, color, period, cycles, skew_ratio, waveform
    def set_waveform(self, value, callb=None, rapid=False):
        """Convenience method to animate the light, a dictionary with the the following
        keys: transient, color, period, cycles, skew_ratio, waveform

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The animation parameter.
            :type value:
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
        if "color" in value and len(value["color"]) == 4:
            if rapid:
                self.fire_and_forget(LightSetWaveform, value, num_repeats=1)
            else:
                self.req_with_ack(LightSetWaveform, value, callb=callb)

    # value should be a dictionary with the the following keys:
    # transient, color, period, cycles, skew_ratio, waveform, set_hue, set_saturation, set_brightness, set_kelvin
    def set_waveform_optional(self, value, callb=None, rapid=False):
        """Convenience method to animate the light, a dictionary with the the following
        keys: transient, color, period, cycles, skew_ratio, waveform, set_hue, set_saturation, set_brightness, set_kelvin

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The animation parameter.
            :type value:
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
        if "color" in value and len(value["color"]) == 4:
            if rapid:
                self.fire_and_forget(LightSetWaveformOptional, value, num_repeats=1)
            else:
                self.req_with_ack(LightSetWaveformOptional, value, callb=callb)

    # LightGet, color, power_level, label
    def get_color(self, callb=None):
        """Convenience method to request the colour status from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        response = self.req_with_resp(LightGet, LightState, callb=callb)
        return self.color

    # color is [Hue, Saturation, Brightness, Kelvin], duration in ms
    def set_color(self, value, callb=None, duration=0, rapid=False):
        """Convenience method to set the colour status of the device

        This method will send a LightSetColor message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

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
        if len(value) == 4:
            mypartial = partial(self.resp_set_light, color=value)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)
            # try:
            if rapid:
                self.fire_and_forget(
                    LightSetColor, {"color": value, "duration": duration}, num_repeats=1
                )
                self.resp_set_light(None, color=value)
                if callb:
                    callb(self, None)
            else:
                self.req_with_ack(
                    LightSetColor, {"color": value, "duration": duration}, callb=mycallb
                )
            # except WorkflowException as e:
            # print(e)

    # Here light because LightState message will give light
    def resp_set_light(self, resp, color=None):
        """Default callback for set_color"""
        if color:
            self.color = color
        elif resp:
            self.power_level = resp.power_level
            self.color = resp.color
            self.label = resp.label.decode().replace("\x00", "")

    # def get_accesspoint(self, callb=None):
    #     """Convenience method to request the access point available

    #     This method will do nothing unless a call back is passed to it.

    #     :param callb: Callable to be used when the response is received. If not set,
    #                   self.resp_set_label will be used.
    #     :type callb: callable
    #     :returns: None
    #     :rtype: None
    #     """
    #     response = self.req_with_resp(GetAccessPoint, StateAccessPoint, callb=callb)
    #     return None

    # def __str__(self):
    #     indent = "  "
    #     s = self.device_characteristics_str(indent)
    #     s += indent + "Color (HSBK): {}\n".format(self.color)
    #     s += indent + self.device_firmware_str(indent)
    #     s += indent + self.device_product_str(indent)
    #     # s += indent + self.device_time_str(indent)
    #     # s += indent + self.device_radio_str(indent)
    #     return s
