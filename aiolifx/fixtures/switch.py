from dataclasses import dataclass
from functools import partial
from aiolifx.fixtures.base_fixture import BaseFixture, RootFixture
from aiolifx.fixtures.device_features import DeviceFeatures

from aiolifx.msgtypes import (
    GetButton,
    GetButtonConfig,
    GetRPower,
    SetButtonConfig,
    SetRPower,
    StateButton,
    StateButtonConfig,
    StateRPower,
)

MAX_UNSIGNED_16_BIT_INTEGER_VALUE = int("0xFFFF", 16)


@dataclass
class SwitchMixin(RootFixture, BaseFixture):
    capabilities = [
        DeviceFeatures.RELAYS,
        DeviceFeatures.BUTTONS,
        DeviceFeatures.BUTTON_CONFIG,
    ]

    # Only used by a Lifx Switch. Will be populated with either True or False for each relay index if `get_rpower` called.
    # At the moment we assume the switch to be 4 relays. This will likely work with the 2 relays switch as well, but only the first two values
    # in this array will contain useful data.
    relays_power = [None, None, None, None]
    # Only used by a Lifx switch. Will be populated with an object containing the `haptic_duration_ms`, `backlight_on_color` and `backlight_off_color`
    button_config = None
    # Only used by a Lifx switch. Will be populated with an object containing `count`, `index`, `buttons_count` and `buttons`
    button = None

    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        super().__init__(req_with_resp, req_with_ack, fire_and_forget)

    def get_rpower(self, relay_index=None, callb=None):
        """Method will get the power state of all relays; or a single relay if value provided.

        :param relay_index: The index of the relay to check power state for. If not provided, will loop through 4 relays
        :type relay_index: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        mypartial = partial(self.resp_set_rpower)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        if relay_index is not None:
            payload = {"relay_index": relay_index}
            response = self.req_with_resp(
                GetRPower, StateRPower, payload, callb=mycallb
            )
        else:
            for relay_index in range(4):
                payload = {"relay_index": relay_index}
                response = self.req_with_resp(
                    GetRPower, StateRPower, payload, callb=mycallb
                )
        return self.relays_power

    def set_rpower(self, relay_index, is_on, callb=None, rapid=False):
        """Sets relay power for a given relay index

        :param relay_index: The relay on the switch starting from 0.
        :type relay_index: int
        :param on: Whether the relay is on or not
        :type is_on: bool
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :param rapid: Whether to ask for ack (False) or not (True). Default False
        :type rapid: bool
        :returns: None
        :rtype: None
        """
        level = 0
        if is_on:
            level = MAX_UNSIGNED_16_BIT_INTEGER_VALUE

        payload = {"relay_index": relay_index, "level": level}
        mypartial = partial(self.resp_set_rpower, relay_index=relay_index, level=level)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        if not rapid:
            self.req_with_resp(SetRPower, StateRPower, payload, callb=mycallb)
        else:
            self.fire_and_forget(SetRPower, payload)

    def resp_set_rpower(self, resp, relay_index=None, level=None):
        """Default callback for get_rpower/set_rpower"""
        if relay_index != None and level != None:
            self.relays_power[relay_index] = level == MAX_UNSIGNED_16_BIT_INTEGER_VALUE
        elif resp:
            # Current models of the LIFX switch do not have dimming capability, so the two valid values are 0 for off (False) and 65535 for on (True).
            self.relays_power[resp.relay_index] = (
                resp.level == MAX_UNSIGNED_16_BIT_INTEGER_VALUE
            )

    def get_button(self, callb=None):
        """Method will get the state of all buttons

        :param relay_index: The index of the relay to check power state for. If not provided, will loop through 4 relays
        :type relay_index: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        mypartial = partial(self.resp_get_button)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        payload = {}
        response = self.req_with_resp(GetButton, StateButton, payload, callb=mycallb)

    def set_button(self, callb=None, rapid=False):
        raise Exception(
            "SetButton isn't yet implemented as you can only set button actions to the same values as the LIFX app (ie you can't add custom callbacks), making it not that useful. Feel free to implement if you need this :)"
        )
        """ Sets button

            :param callb: Callable to be used when the response is received.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """

        payload = {}
        mypartial = partial(self.resp_get_button)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        if not rapid:
            self.req_with_resp(SetButton, StateButton, payload, callb=mycallb)
        else:
            self.fire_and_forget(SetButton, payload)

    def resp_get_button(self, resp):
        """Default callback for get_button/set_button"""
        self.button = {
            "count": resp.count,
            "index": resp.index,
            "buttons_count": resp.buttons_count,
            "buttons": resp.buttons,
        }

    def get_button_config(self, callb=None):
        """Method will get the button config

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        mypartial = partial(self.resp_get_button_config)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        response = self.req_with_resp(
            GetButtonConfig, StateButtonConfig, {}, callb=mycallb
        )

    def set_button_config(
        self,
        haptic_duration_ms: int,
        backlight_on_color,
        backlight_off_color,
        callb=None,
        rapid=False,
    ):
        """Sets button config

        :param haptic_duration_ms: How many milliseconds the haptic vibration when the button is pressed should last
        :type haptic_duration_ms: int
        :param backlight_on_color: The color the backlight should be when a button is on
        :type backlight_on_color: { "hue": int, "saturation": int, "brightness": int, "kelvin": int }
        :param backlight_off_color: The color the backlight should be when a button is off
        :type backlight_off_color: { "hue": int, "saturation": int, "brightness": int, "kelvin": int }
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :param rapid: Whether to ask for ack (False) or not (True). Default False
        :type rapid: bool
        :returns: None
        :rtype: None
        """

        payload = {
            "haptic_duration_ms": haptic_duration_ms,
            "backlight_on_color": backlight_on_color,
            "backlight_off_color": backlight_off_color,
        }
        mypartial = partial(
            self.resp_get_button_config,
            haptic_duration_ms=haptic_duration_ms,
            backlight_on_color=backlight_on_color,
            backlight_off_color=backlight_off_color,
        )
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        if not rapid:
            self.req_with_resp(
                SetButtonConfig, StateButtonConfig, payload, callb=mycallb
            )
        else:
            self.fire_and_forget(SetButtonConfig, payload)

    def resp_get_button_config(
        self,
        resp,
        haptic_duration_ms=None,
        backlight_on_color=None,
        backlight_off_color=None,
    ):
        """Default callback for get_button_config/set_button_config"""
        if (
            haptic_duration_ms != None
            and backlight_on_color != None
            and backlight_off_color != None
        ):
            self.button_config = {
                "haptic_duration_ms": haptic_duration_ms,
                "backlight_on_color": backlight_on_color,
                "backlight_off_color": backlight_off_color,
            }
        elif resp:
            self.button_config = {
                "haptic_duration_ms": resp.haptic_duration_ms,
                "backlight_on_color": resp.backlight_on_color,
                "backlight_off_color": resp.backlight_off_color,
            }
