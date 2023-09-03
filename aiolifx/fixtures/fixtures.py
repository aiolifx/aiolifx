from aiolifx.fixtures.color_light import ColorLightMixin
from aiolifx.fixtures.hev_light import HevLightMixin
from aiolifx.fixtures.light import LightMixin
from aiolifx.fixtures.multizone_light import MultizoneLightMixin
from aiolifx.fixtures.switch import SwitchMixin
from aiolifx.fixtures.matrix_light import MatrixLightMixin
from aiolifx.products import products_dict

class Light(LightMixin):
    DEVICE_FEATURES = LightMixin.DEVICE_FEATURES
    pass

class ColorLight(LightMixin, ColorLightMixin):
    DEVICE_FEATURES = LightMixin.DEVICE_FEATURES + ColorLightMixin.DEVICE_FEATURES
    pass
            

class MultizoneLight(LightMixin, ColorLightMixin, MultizoneLightMixin):
    DEVICE_FEATURES = LightMixin.DEVICE_FEATURES + ColorLightMixin.DEVICE_FEATURES + MultizoneLightMixin.DEVICE_FEATURES
    pass

class HevLight(LightMixin, HevLightMixin):
    DEVICE_FEATURES = LightMixin.DEVICE_FEATURES + HevLightMixin.DEVICE_FEATURES
    pass

class MatrixLight(LightMixin, MatrixLightMixin):
    DEVICE_FEATURES = LightMixin.DEVICE_FEATURES + MatrixLightMixin.DEVICE_FEATURES

class Switch(SwitchMixin):
    DEVICE_FEATURES = SwitchMixin.DEVICE_FEATURES
    pass

def get_fixture(product_id, req_with_resp, req_with_ack, fire_and_forget):
    product = products_dict[product_id]
    if product.relays and product.buttons:
        return Switch(req_with_resp, req_with_ack, fire_and_forget)
    elif product.multizone and product.extended_multizone:
        return MultizoneLight(req_with_resp, req_with_ack, fire_and_forget)
    elif product.color:
        return ColorLight(req_with_resp, req_with_ack, fire_and_forget)
    elif product.infrared and product.hev:
        return HevLight(req_with_resp, req_with_ack, fire_and_forget)
    elif product.max_kelvin and product.min_kelvin:
        return Light(req_with_resp, req_with_ack, fire_and_forget)
    elif product.matrix:
        return MatrixLight(req_with_resp, req_with_ack, fire_and_forget)
    else:
        raise Exception(f"{product} doesn't exist")
        