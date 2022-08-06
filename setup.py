#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import setuptools

version = "0.8.2"

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aiolifx",
    packages=["aiolifx"],
    version=version,
    author="François Wautier",
    author_email="francois@wautier.eu",
    description="API for local communication with LIFX devices over a LAN with asyncio.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="http://github.com/frawau/aiolifx",
    keywords=["lifx", "light", "automation"],
    license="MIT",
    install_requires=[
        "bitstring",
        "ifaddr",
    ],
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # Pick your license as you wish (should match "license" above)
        "License :: OSI Approved :: MIT License",
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        "Programming Language :: Python :: 3",
    ],
    entry_points={"console_scripts": ["aiolifx=aiolifx.__main__:main"]},
    python_requires=">=3.4",
    zip_safe=False,
)
