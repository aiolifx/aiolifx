from dataclasses import dataclass
from aiolifx.fixtures.color_light import ColorLightMixin
from aiolifx.fixtures.hev_light import HevLightMixin
from aiolifx.fixtures.light import LightMixin
from aiolifx.fixtures.multizone_light import MultizoneLightMixin
from aiolifx.fixtures.switch import SwitchMixin
from aiolifx.fixtures.matrix_light import MatrixLightMixin
from aiolifx.products import products_dict


class Light(LightMixin):
    pass


class ColorLight(LightMixin, ColorLightMixin):
    pass


class MultizoneLight(LightMixin, ColorLightMixin, MultizoneLightMixin):
    pass


class HevLight(LightMixin, HevLightMixin):
    pass

class MatrixLight(LightMixin, MatrixLightMixin):
    DEVICE_FEATURES = LightMixin.DEVICE_FEATURES + MatrixLightMixin.DEVICE_FEATURES

class Switch(SwitchMixin):
    pass


def get_fixture(product_id, req_with_resp, req_with_ack, fire_and_forget):
    product = products_dict[product_id]
    if product.relays and product.buttons:
        return Switch(req_with_resp, req_with_ack, fire_and_forget)
    if product.multizone and product.extended_multizone:
        return MultizoneLight(req_with_resp, req_with_ack, fire_and_forget)
    if product.color:
        return ColorLight(req_with_resp, req_with_ack, fire_and_forget)
    if product.infrared and product.hev:
        return HevLight(req_with_resp, req_with_ack, fire_and_forget)
    if product.max_kelvin and product.min_kelvin:
        return Light(req_with_resp, req_with_ack, fire_and_forget)
    elif product.matrix:
        return MatrixLight(req_with_resp, req_with_ack, fire_and_forget)
    raise Exception(f"{product} doesn't exist")
        
