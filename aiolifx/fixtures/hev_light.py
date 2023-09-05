from dataclasses import dataclass
from functools import partial
from aiolifx.fixtures.base_fixture import BaseFixture
from aiolifx.fixtures.device_features import DeviceFeatures
from aiolifx.msgtypes import (
    LAST_HEV_CYCLE_RESULT,
    GetHevCycle,
    GetHevCycleConfiguration,
    GetLastHevCycleResult,
    LightGetInfrared,
    LightSetInfrared,
    LightStateInfrared,
    SetHevCycle,
    SetHevCycleConfiguration,
    StateHevCycle,
    StateLastHevCycleResult,
)
from build.lib.aiolifx.msgtypes import StateHevCycleConfiguration


@dataclass
class HevLightMixin(BaseFixture):
    capabilities = [DeviceFeatures.HEV_CYCLE, DeviceFeatures.HEV_CONFIGURATION]
    infrared_brightness: int = 0
    hev_cycle = None
    hev_cycle_configuration = None
    last_hev_cycle_result = None

    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        super().__init__(req_with_resp, req_with_ack, fire_and_forget)

    # Infrared get maximum brightness, infrared_brightness
    def get_infrared(self, callb=None):
        """Convenience method to request the infrared brightness from the device

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
        response = self.req_with_resp(LightGetInfrared, LightStateInfrared, callb=callb)
        return self.infrared_brightness

    # Infrared set maximum brightness, infrared_brightness
    def set_infrared(self, infrared_brightness, callb=None, rapid=False):
        """Convenience method to set the infrared status of the device

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param infrared_brightness: The new state
            :type infrared_brightness: int
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
        mypartial = partial(
            self.resp_set_lightinfrared, infrared_brightness=infrared_brightness
        )
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)
        if rapid:
            self.fire_and_forget(
                LightSetInfrared,
                {"infrared_brightness": infrared_brightness},
                num_repeats=1,
            )
            self.resp_set_lightinfrared(None, infrared_brightness=infrared_brightness)
            if callb:
                callb(self, None)
        else:
            self.req_with_ack(
                LightSetInfrared,
                {"infrared_brightness": infrared_brightness},
                callb=mycallb,
            )

    # Here lightinfrared because LightStateInfrared message will give lightinfrared
    def resp_set_lightinfrared(self, resp, infrared_brightness=None):
        """Default callback for set_infrared/get_infrared"""
        if infrared_brightness is not None:
            self.infrared_brightness = infrared_brightness
        elif resp:
            self.infrared_brightness = resp.infrared_brightness

    def get_hev_cycle(self, callb=None):
        """Request the state of any running HEV cycle of the device.

        This method only works with LIFX Clean bulbs.

        This method will do nothing unless a call back is passed to it.

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        self.req_with_resp(GetHevCycle, StateHevCycle, callb=callb)

    def resp_set_hevcycle(self, resp):
        """Default callback for get_hev_cycle/set_hev_cycle"""
        if resp:
            self.hev_cycle = {
                "duration": resp.duration,
                "remaining": resp.remaining,
                "last_power": resp.last_power,
            }

    def set_hev_cycle(self, enable=True, duration=0, callb=None, rapid=False):
        """Immediately starts a HEV cycle on the device.

        This method only works with LIFX Clean bulbs.

        This method will send a SetHevCycle message to the device, and request
        callb be executed when an ACK is received.

        :param enable: If True, start the HEV cycle, otherwise abort.
        :type enable: bool
        :param duration: The duration, in seconds, of the HEV cycle. If 0,
                         use the default configuration on the bulb.
        :type duration: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :param rapid: Whether to ask for ack (False) or not (True). Default False
        :type rapid: bool
        :returns: None
        :rtype: None
        """
        if rapid:
            self.fire_and_forget(
                SetHevCycle,
                {"enable": int(enable), "duration": duration},
                num_repeats=1,
            )
            if callb:
                callb(self, None)
        else:
            self.req_with_resp(
                SetHevCycle,
                StateHevCycle,
                {"enable": int(enable), "duration": duration},
                callb=callb,
            )

    def get_hev_configuration(self, callb=None):
        """Requests the default HEV configuration of the device.

        This method only works with LIFX Clean bulbs.

        This method will do nothing unless a call back is passed to it.

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        self.req_with_resp(
            GetHevCycleConfiguration, StateHevCycleConfiguration, callb=callb
        )

    def resp_set_hevcycleconfiguration(self, resp):
        """Default callback for get_hev_cycle_configuration/set_hev_cycle_configuration"""
        if resp:
            self.hev_cycle_configuration = {
                "duration": resp.duration,
                "indication": resp.indication,
            }

    def set_hev_configuration(self, indication, duration, callb=None, rapid=False):
        """Sets the default HEV configuration of the device.

        This method only works with LIFX Clean bulbs.

        This method will send a SetHevCycleConfiguration message to the device,
        and request callb be executed when an ACK is received.

        :param indication: If True, show a short flashing indication when the
                           HEV cycle finishes.
        :type indication: bool
        :param duration: The duration, in seconds, of the HEV cycle.
        :type duration: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :param rapid: Whether to ask for ack (False) or not (True). Default False
        :type rapid: bool
        :returns: None
        :rtype: None
        """
        if rapid:
            self.fire_and_forget(
                SetHevCycleConfiguration,
                {"indication": int(indication), "duration": duration},
                num_repeats=1,
            )
            if callb:
                callb(self, None)
        else:
            self.req_with_resp(
                SetHevCycleConfiguration,
                StateHevCycleConfiguration,
                {"indication": int(indication), "duration": duration},
                callb=callb,
            )

    # Get last HEV cycle result
    def get_last_hev_cycle_result(self, callb=None):
        """Requests the result of the last HEV cycle of the device.

        This method only works with LIFX Clean bulbs.

        This method will do nothing unless a call back is passed to it.

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        self.req_with_resp(GetLastHevCycleResult, StateLastHevCycleResult, callb=callb)

    def resp_set_lasthevcycleresult(self, resp):
        if resp:
            self.last_hev_cycle_result = LAST_HEV_CYCLE_RESULT.get(resp.result)
