#!/usr/bin/env python3

from urllib.request import urlopen
import json
import pprint

json = json.load(urlopen('https://raw.githubusercontent.com/LIFX/products/master/products.json'))

product_map = {}
features_map = {}

kelvin_range = {
    10: [2700, 6500],
    11: [2700, 6500],
    50: [1500, 4000],
    51: [2700, 2700],
    60: [1500, 4000],
    61: [2700, 2700],
}
default_kelvin = [2500, 9000]

for product in json[0]['products']:
    product_id = product['pid']

    product_map[product_id] = product['name']

    features = product['features']
    whites = kelvin_range.get(product_id, default_kelvin)
    features['min_kelvin'] = whites[0]
    features['max_kelvin'] = whites[1]

    features_map[product_id] = features

output = "product_map = {products}\n\nfeatures_map = {features}\n".format(
    products=pprint.pformat(product_map, indent=4),
    features=pprint.pformat(features_map, indent=4),
)

print(output)
