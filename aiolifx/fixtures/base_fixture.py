from dataclasses import dataclass

from aiolifx.fixtures.device_features import DeviceFeatures


# An interface ensuring every fixture has a capabilities list
class RootFixture:
    capabilities = [
        DeviceFeatures.INFO,
        DeviceFeatures.FIRMWARE,
        DeviceFeatures.WIFI,
        DeviceFeatures.UPTIME,
        DeviceFeatures.REBOOT
    ]
    pass


class DeviceMeta(type):
    def __init__(cls, name, bases, attrs):
        cls.capabilities = []

        for base in bases:
            if hasattr(base, "capabilities"):
                cls.capabilities.extend(base.capabilities)

        # This loops through the attributes of each subclass and adds them to the base capabilities list
        for attr in attrs.items():
            if attr[0] == "capabilities":
                cls.capabilities.extend(attr[1])
        super().__init__(name, bases, attrs)


@dataclass
class BaseFixture(metaclass=DeviceMeta):
    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        self.req_with_resp = req_with_resp
        self.req_with_ack = req_with_ack
        self.fire_and_forget = fire_and_forget
        return
