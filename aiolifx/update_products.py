#!/usr/bin/env python3

import requests
import json
import pprint


product_map = {}
features_map = {}
for url in ["https://raw.githubusercontent.com/LIFX/products/master/products.json"]:
    resp = requests.get(url)
    lifxp = json.loads(resp.text)
    defaults = lifxp[0]["defaults"]

    for product in lifxp[0]["products"]:
        product_id = product["pid"]

        product_map[product_id] = product["name"]

        features = {}
        for feature in defaults:
            if feature in product["features"]:
                features[feature] = product["features"][feature]
            else:
                features[feature] = defaults[feature]

        for upgrade in product.get("upgrades", []):
            features.update(upgrade["features"])

        if features["temperature_range"] is not None:
            features["min_kelvin"] = features["temperature_range"][0]
            features["max_kelvin"] = features["temperature_range"][1]
            del features["temperature_range"]

        if "min_ext_mz_firmware" in product["features"]:
            features["min_ext_mz_firmware"] = product["features"]["min_ext_mz_firmware"]

        if "min_ext_mz_firmware_components" in product["features"]:
            features["min_ext_mz_firmware_components"] = product["features"][
                "min_ext_mz_firmware_components"
            ]

        features_map[product_id] = features

    output = "product_map = {products}\n\nfeatures_map = {features}\n".format(
        products=pprint.pformat(product_map, indent=4),
        features=pprint.pformat(features_map, indent=4),
    )

print(output)
