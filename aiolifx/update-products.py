#!/usr/bin/env python3

from urllib.request import urlopen
import json
import pprint

json = json.load(
    urlopen("https://raw.githubusercontent.com/LIFX/products/master/products.json")
)

product_map = {}
features_map = {}

for product in json[0]["products"]:
    product_id = product["pid"]

    product_map[product_id] = product["name"]

    features = product["features"]

    for upgrade in product["upgrades"]:
        features.update(upgrade["features"])

    if "temperature_range" in features:
        features["min_kelvin"] = features["temperature_range"][0]
        features["max_kelvin"] = features["temperature_range"][1]
        del features["temperature_range"]

    features_map[product_id] = features

output = "product_map = {products}\n\nfeatures_map = {features}\n".format(
    products=pprint.pformat(product_map, indent=4),
    features=pprint.pformat(features_map, indent=4),
)

print(output)
