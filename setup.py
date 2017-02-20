#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from setuptools import setup

setup(name='aiolifx',
      version='0.4.0',
      description='API for local communication with LIFX devices over a LAN.',
      url='http://github.com/frawau/aiolifx',
      author='François Wautier',
      author_email='francois@wautier.eu',
      license='MIT',
      packages=['aiolifx'],
      install_requires=[
        "bitstring",
        "asyncio"
        ],
      zip_safe=False,
          # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5'
    ])