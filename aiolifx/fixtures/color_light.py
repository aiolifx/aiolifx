from dataclasses import dataclass
from functools import partial
from aiolifx.fixtures.base_fixture import BaseFixture
from aiolifx.fixtures.device_features import DeviceFeatures
from aiolifx.msgtypes import LightGet, LightSetColor, LightState


@dataclass
class ColorLightMixin(BaseFixture):
    DEVICE_FEATURES = (
        DeviceFeatures.COLOR,
        DeviceFeatures.PULSE
    )
    
    color = None
    color_zones = None

    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        super().__init__(req_with_resp, req_with_ack, fire_and_forget)

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