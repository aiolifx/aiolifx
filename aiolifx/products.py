from typing import List
from .products_defs import product_map, features_map


class Product:
    def __init__(
        self,
        id: int,
        name: str,
        buttons: bool,
        chain: bool,
        color: bool,
        extended_multizone: bool,
        hev: bool,
        infrared: bool,
        matrix: bool,
        multizone: bool,
        relays: bool,
        max_kelvin: int,
        min_kelvin: int,
        min_ext_mz_firmware: int,
        min_ext_mz_firmware_components: List[int],
        temperature_range: None,
    ):
        self.id = id
        self.name = name
        self.buttons = buttons
        self.chain = chain
        self.color = color
        self.extended_multizone = extended_multizone
        self.hev = hev
        self.infrared = infrared
        self.matrix = matrix
        self.multizone = multizone
        self.relays = relays
        self.max_kelvin = max_kelvin
        self.min_kelvin = min_kelvin
        self.min_ext_mz_firmware = min_ext_mz_firmware
        self.min_ext_mz_firmware_components = min_ext_mz_firmware_components
        self.temperature_range = temperature_range

    def __str__(self):
        return (
            f"Product(id={self.id}, "
            f"name='{self.name}', "
            f"buttons={self.buttons}, "
            f"chain={self.chain}, "
            f"color={self.color}, "
            f"extended_multizone={self.extended_multizone}, "
            f"hev={self.hev}, "
            f"infrared={self.infrared}, "
            f"matrix={self.matrix}, "
            f"multizone={self.multizone}, "
            f"relays={self.relays}, "
            f"max_kelvin={self.max_kelvin}, "
            f"min_kelvin={self.min_kelvin}, "
            f"min_ext_mz_firmware={self.min_ext_mz_firmware}, "
            f"min_ext_mz_firmware_components={self.min_ext_mz_firmware_components}, "
            f"temperature_range={self.temperature_range})"
        )


def create_product_dict(product_map, features_map):
    products_dict = {}
    for product_id, product_name in product_map.items():
        features = features_map[product_id]
        products_dict[product_id] = Product(
            id=product_id,
            name=product_name,
            buttons=features.get("buttons"),
            chain=features.get("chain"),
            color=features.get("color"),
            extended_multizone=features.get("extended_multizone"),
            hev=features.get("hev"),
            infrared=features.get("infrared"),
            matrix=features.get("matrix"),
            multizone=features.get("multizone"),
            relays=features.get("relays"),
            max_kelvin=features.get("max_kelvin"),
            min_kelvin=features.get("min_kelvin"),
            min_ext_mz_firmware=features.get("min_ext_mz_firmware"),
            min_ext_mz_firmware_components=features.get(
                "min_ext_mz_firmware_components"
            ),
            temperature_range=features.get("temperature_range"),
        )
    return products_dict


products_dict = create_product_dict(product_map, features_map)
