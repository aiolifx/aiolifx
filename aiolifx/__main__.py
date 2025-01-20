#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This application is an example on how to use aiolifx
#
# Copyright (c) 2016 François Wautier
# Copyright (c) 2022 Michael Farrell <micolous+git@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies
# or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
from enum import Enum
import asyncio as aio

import click
import aiolifx as alix
from functools import partial
from time import sleep
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.validator import EmptyInputValidator

UDP_BROADCAST_PORT = 56700


# Simple bulb control frpm console
class bulbs:
    """A simple class with a register and unregister methods"""

    def __init__(self):
        self.bulbs = []
        self.boi = None  # bulb of interest

    def register(self, bulb):
        global opts
        bulb.get_label()
        bulb.get_location()
        bulb.get_version()
        bulb.get_group()
        bulb.get_wififirmware()
        bulb.get_hostfirmware()
        self.bulbs.append(bulb)
        self.bulbs.sort(key=lambda x: x.label or x.mac_addr)
        if opts["extra"]:
            bulb.register_callback(lambda y: print("Unexpected message: %s" % str(y)))

    def unregister(self, bulb):
        idx = 0
        for x in list([y.mac_addr for y in self.bulbs]):
            if x == bulb.mac_addr:
                del self.bulbs[idx]
                break
            idx += 1


class DeviceFeatures(Enum):
    INFO = "Info"
    FIRMWARE = "Firmware"
    WIFI = "Wifi"
    UPTIME = "Uptime"
    POWER = "Power"
    WHITE = "White"
    COLOR = "Color"
    PULSE = "Pulse"
    HEV_CYCLE = "HEV Cycle"
    HEV_CONFIGURATION = "HEV Configuration"
    MULTIZONE_FIRMWARE_EFFECT = "Get Multizone Firmware Effect"
    MULTIZONE_FIRMWARE_EFFECT_START_STOP = "Start/Stop Firmware Effect"
    MATRIX_FIRMWARE_EFFECT = "Get Matrix Firmware Effect"
    MATRIX_FIRMWARE_EFFECT_START_STOP = "Start/Stop Firmware Effect"
    RELAYS = "Relays"
    BUTTONS = "Buttons"
    BUTTON_CONFIG = "Button Config"
    REBOOT = "Reboot"


def get_features(device):
    base_options = [
        DeviceFeatures.INFO,
        DeviceFeatures.FIRMWARE,
        DeviceFeatures.WIFI,
        DeviceFeatures.UPTIME,
        DeviceFeatures.REBOOT,
    ]
    features = []
    if alix.aiolifx.products_dict[device].max_kelvin != None:
        features.extend([DeviceFeatures.POWER, DeviceFeatures.WHITE])
    if alix.aiolifx.products_dict[device].color is True:
        features.extend([DeviceFeatures.COLOR, DeviceFeatures.PULSE])
    if alix.aiolifx.products_dict[device].hev is True:
        features.extend([DeviceFeatures.HEV_CYCLE, DeviceFeatures.HEV_CONFIGURATION])
    if alix.aiolifx.products_dict[device].multizone is True:
        features.extend(
            [
                DeviceFeatures.MULTIZONE_FIRMWARE_EFFECT,
                DeviceFeatures.MULTIZONE_FIRMWARE_EFFECT_START_STOP,
            ]
        )
    if alix.aiolifx.products_dict[device].matrix is True:
        features.extend(
            [
                DeviceFeatures.MATRIX_FIRMWARE_EFFECT,
                DeviceFeatures.MATRIX_FIRMWARE_EFFECT_START_STOP,
            ]
        )
    if alix.aiolifx.products_dict[device].relays is True:
        features.append(DeviceFeatures.RELAYS)
    if alix.aiolifx.products_dict[device].buttons is True:
        features.extend([DeviceFeatures.BUTTONS, DeviceFeatures.BUTTON_CONFIG])
    features.extend(base_options)
    return features


async def get_device(devices):
    device_choices = [
        *[Choice(device.mac_addr, name=device.label) for device in devices],
        Choice("back", name="❌ Quit"),
    ]
    device_mac_addr = await inquirer.fuzzy(
        message="Select a device", choices=device_choices
    ).execute_async()
    device = next(
        (device for device in devices if device.mac_addr == device_mac_addr), None
    )
    return device


async def get_feature(device):
    features = get_features(device.product)
    features_choices = [
        *[Choice(feature, name=feature.value) for feature in features],
        (Choice("back", name="❌ Go back to device selection")),
    ]
    option = await inquirer.fuzzy(
        message="Select an option", choices=features_choices
    ).execute_async()
    if option == "back":
        return None
    return option


async def readin():
    while True:
        device = await get_device(MyBulbs.bulbs)
        if device is None:
            break
        feature = await get_feature(device)
        if feature is None:  # if going back
            continue
        if feature == DeviceFeatures.POWER:
            power_level = await inquirer.select(
                message="Select a power level", choices=["On", "Off"]
            ).execute_async()
            device.set_power(power_level.lower())
        elif feature == DeviceFeatures.WHITE:
            brightness = await inquirer.number(
                "Brightness (0 - 100)",
                replace_mode=True,
                min_allowed=0,
                max_allowed=100,
                validate=EmptyInputValidator(),
            ).execute_async()
            while True:
                kelvin = await inquirer.number(
                    "Kelvin (1500 - 9000)",
                    min_allowed=0,
                    max_allowed=9000,
                    validate=EmptyInputValidator(),
                ).execute_async()
                if int(kelvin) < 1500:
                    print("Kelvin must be greater than 1500")
                    continue
                break
            device.set_color(
                [
                    58275,
                    0,
                    int(round((float(brightness) * 65365.0) / 100.0)),
                    float(kelvin),
                ]
            )
        elif feature == DeviceFeatures.COLOR:
            hue = await inquirer.number(
                "Hue (0 - 360)",
                replace_mode=True,
                min_allowed=0,
                max_allowed=360,
                validate=EmptyInputValidator(),
            ).execute_async()
            saturation = await inquirer.number(
                "Saturation (0 - 100)",
                replace_mode=True,
                min_allowed=0,
                max_allowed=100,
                validate=EmptyInputValidator(),
            ).execute_async()
            brightness = await inquirer.number(
                "Brightness (0 - 100)",
                replace_mode=True,
                min_allowed=0,
                max_allowed=100,
                validate=EmptyInputValidator(),
            ).execute_async()
            device.set_color(
                [
                    int(round((float(hue) * 65535.0) / 360.0)),
                    int(round((float(saturation) * 65535.0) / 100.0)),
                    int(round((float(brightness) * 65535.0) / 100.0)),
                    3500,
                ]
            )
            device = None

        elif feature == DeviceFeatures.INFO:
            print(device.device_characteristics_str("    "))
            print(device.device_product_str("    "))
            device = None
        elif feature == DeviceFeatures.FIRMWARE:
            print(device.device_firmware_str("   "))
            device = None
        elif feature == DeviceFeatures.WIFI:
            mypartial = partial(device.device_radio_str)
            device.get_wifiinfo(callb=lambda x, y: print("\n" + mypartial(y)))
            device = None
        elif feature == DeviceFeatures.UPTIME:
            mypartial = partial(device.device_time_str)
            device.get_hostinfo(callb=lambda x, y: print("\n" + mypartial(y)))
            device = None
        elif feature == DeviceFeatures.PULSE:
            hue = await inquirer.number(
                "Hue (0 - 360)",
                replace_mode=True,
                min_allowed=0,
                max_allowed=360,
                validate=EmptyInputValidator(),
            ).execute_async()
            saturation = await inquirer.number(
                "Saturation (0 - 100)",
                replace_mode=True,
                min_allowed=0,
                max_allowed=100,
                validate=EmptyInputValidator(),
            ).execute_async()
            brightness = await inquirer.number(
                "Brightness (0 - 100)",
                replace_mode=True,
                min_allowed=0,
                max_allowed=100,
                validate=EmptyInputValidator(),
            ).execute_async()
            device.set_waveform(
                {
                    "color": [
                        int(round((float(hue) * 65535.0) / 360.0)),
                        int(round((float(saturation) * 65535.0) / 100.0)),
                        int(round((float(brightness) * 65535.0) / 100.0)),
                        3500,
                    ],
                    "transient": 1,
                    "period": 100,
                    "cycles": 30,
                    "skew_ratio": 0,
                    "waveform": 3,
                }
            )
            device = None
        elif feature == DeviceFeatures.HEV_CYCLE:
            device.get_hev_cycle(
                callb=lambda _, r: print(
                    f"\nHEV: duration={r.duration}, "
                    f"remaining={r.remaining}, "
                    f"last_power={r.last_power}"
                )
            )
            device.get_last_hev_cycle_result(
                callb=lambda _, r: print(f"\nHEV result: {r.result_str}")
            )
            set_duration = await inquirer.confirm(
                message="Set duration?", default=False
            ).execute_async()
            if set_duration:
                duration = await inquirer.number(
                    "Duration (seconds)",
                    replace_mode=True,
                    min_allowed=0,
                    validate=EmptyInputValidator(),
                ).execute_async()
                enable = duration >= 0
                if enable:
                    print(f"Running HEV cycle for {duration} second(s)")
                else:
                    print(f"Aborting HEV cycle")
                    duration = 0
                device.set_hev_cycle(
                    enable=enable,
                    duration=duration,
                    callb=lambda _, r: print(
                        f"\nHEV: duration={r.duration}, "
                        f"remaining={r.remaining}, "
                        f"last_power={r.last_power}"
                    ),
                )

            device = None
        elif feature == DeviceFeatures.MATRIX_FIRMWARE_EFFECT:

            print("Getting current firmware effect state from matrix device")
            device.get_tile_effect(
                callb=lambda _, r: print(
                    f"\nCurrent effect={r.effect_str}"
                    f"\nSpeed={r.speed/1000 if getattr(r, 'speed', None) is not None else 0}"
                    f"\nDuration={r.duration/1000000000 if getattr(r, 'duration', None) is not None else 0:4f}"
                    f"\nSky type={r.sky_type_str}"
                    f"\nCloud saturation min={r.cloud_saturation_min}"
                    f"\nCloud saturation max={r.cloud_saturation_max}"
                )
            )
            device = None
        elif feature == DeviceFeatures.MATRIX_FIRMWARE_EFFECT_START_STOP:

            effect = await inquirer.fuzzy(
                message="Effect",
                choices=["Off", "Morph", "Flame", "Sky"],
            ).execute_async()

            if effect.lower() == "sky":
                sky_type = await inquirer.fuzzy(
                    message="Sky Type", choices=["Sunrise", "Sunset", "Clouds"]
                ).execute_async()
                e = alix.aiolifx.TileEffectType[effect.upper()].value
                st = alix.TileEffectSkyType[sky_type.upper()].value
                sp = 50
            else:
                e = alix.aiolifx.TileEffectType[effect.upper()].value
                st = None
                sp = 3

            device.set_tile_effect(effect=e, speed=sp, sky_type=st)
            device = None
        elif feature == DeviceFeatures.MULTIZONE_FIRMWARE_EFFECT:

            print("Getting current firmware effect state from multizone device")
            device.get_multizone_effect(
                callb=lambda _, r: print(
                    f"\nCurrent effect={r.effect_str}"
                    f"\nSpeed={r.speed/1000 if getattr(r, 'speed', None) is not None else 0}"
                    f"\nDuration={r.duration/1000000000 if getattr(r, 'duration', None) is not None else 0:4f}"
                    f"\nDirection={r.direction_str}"
                )
            )
            device = None
        elif feature == DeviceFeatures.MULTIZONE_FIRMWARE_EFFECT_START_STOP:

            effect = await inquirer.fuzzy(
                message="Effect",
                choices=["Off", "Move"],
            ).execute_async()

            if effect.lower() == "off":
                device.set_multizone_effect(effect=0)
            else:
                direction = await inquirer.fuzzy(
                    message="Direction",
                    choices=["Left", "Right"],
                ).execute_async()

                e = alix.aiolifx.MultiZoneEffectType[effect.upper()].value
                d = alix.aiolifx.MultiZoneDirection[direction.upper()].value
                device.set_multizone_effect(effect=e, speed=3, direction=d)
            device = None
        elif feature == DeviceFeatures.HEV_CONFIGURATION:
            # Get current state
            print("Getting current HEV configuration")
            device.get_hev_configuration(
                callb=lambda _, r: print(
                    f"\nHEV: indication={r.indication}, " f"duration={r.duration}"
                )
            )

            set_hev_configuration = await inquirer.confirm(
                message="Set HEV configuration?", default=False
            ).execute_async()
            if set_hev_configuration:
                indication = await inquirer.confirm(
                    message="Indication?", default=False
                ).execute_async()
                duration = await inquirer.number(
                    "Duration (seconds)",
                    replace_mode=True,
                    min_allowed=0,
                    validate=EmptyInputValidator(),
                ).execute_async()
                print(
                    f"Configuring default HEV cycle with "
                    f"{'' if indication else 'no '}indication for "
                    f"{duration} second(s)"
                )
                device.set_hev_configuration(
                    indication=indication,
                    duration=duration,
                    callb=lambda _, r: print(
                        f"\nHEV: indication={r.indication}, " f"duration={r.duration}"
                    ),
                )
            device = None
        elif feature == DeviceFeatures.RELAYS:
            callback = lambda x, statePower: print(
                # +1 to use 1-indexing
                f"\nRelay {statePower.relay_index + 1}: {'On' if statePower.level == 65535 else 'Off'}"
            )
            device.get_rpower(callb=callback)
            await aio.sleep(
                0.5
            )  # to wait for the callback to be called. TODO: use await
            should_set_relay_state = await inquirer.confirm(
                message="Set relay state?", default=False
            ).execute_async()
            if should_set_relay_state:
                relay_index = await inquirer.number(
                    "Relay index",
                    replace_mode=True,
                    min_allowed=1,
                    max_allowed=4,
                    validate=EmptyInputValidator(),
                ).execute_async()
                relay_index = int(relay_index) - 1  # Convert to 0-indexing
                relay_state = await inquirer.select(
                    "Relay state", choices=["On", "Off"]
                ).execute_async()
                set_rpower = partial(device.set_rpower, relay_index, callb=callback)
                set_rpower(relay_state.lower() == "on")
                await aio.sleep(
                    0.5
                )  # to wait for the callback to be called. TODO: use await
            feature = None
        elif feature == DeviceFeatures.BUTTONS:

            def callback(x, buttonResponse):
                def get_action_name(action_index):
                    if action_index == 0:
                        return "Single Press"
                    elif action_index == 1:
                        return "Double Press"
                    elif action_index == 2:
                        return "Long Press"
                    else:
                        # To present 1-indexing to users
                        return f"Action {action_index + 1}"

                buttons_str = ""
                for button_index, button in enumerate(
                    buttonResponse.buttons[: buttonResponse.buttons_count]
                ):
                    buttons_str += f"\tButton {button_index + 1}:\n"
                    # At the moment, LIFX app only supports single, double and long press
                    MAX_ACTIONS = 3
                    for action_index, action in enumerate(
                        button["button_actions"][:MAX_ACTIONS]
                    ):
                        buttons_str += (
                            f"\t\t{get_action_name(action_index)}\n"
                            + f"\t\t\tGesture: {action['button_gesture']}\n"
                            + f"\t\t\t{action['button_target_type']}\n"
                            + f"\t\t\t{action['button_target']}\n"
                        )
                return print(
                    f"Count: {buttonResponse.count}\n"
                    + f"Index: {buttonResponse.index}\n"
                    + f"Buttons Count: {buttonResponse.buttons_count}\n"
                    + f"Buttons:\n{buttons_str}"
                )

            device.get_button(callback)
            await aio.sleep(0.5)
        elif feature == DeviceFeatures.BUTTON_CONFIG:

            def callback(x, buttonConfig):

                def get_backlight_str(backlight):

                    backlight_color = {
                        "hue": int(round(360 * (backlight["hue"] / 65535))),
                        "saturation": int(
                            round(100 * (backlight["saturation"] / 65535))
                        ),
                        "brightness": int(
                            round(100 * (backlight["brightness"] / 65535))
                        ),
                        "kelvin": backlight["kelvin"],
                    }
                    return (
                        f"\n\tHue: {backlight_color['hue']},\n"
                        + f"\tSaturation: {backlight_color['saturation']}\n"
                        + f"\tBrightness: {backlight_color['brightness']}\n"
                        + f"\tKelvin (used if Hue is 0): {backlight_color['kelvin']}"
                    )

                backlight_on_color_str = get_backlight_str(
                    buttonConfig.backlight_on_color
                )
                backlight_off_color_str = get_backlight_str(
                    buttonConfig.backlight_off_color
                )

                return print(
                    f"Haptic Duration (ms): {buttonConfig.haptic_duration_ms}\nBacklight on color: {backlight_on_color_str}\nBacklight off color: {backlight_off_color_str}"
                )

            device.get_button_config(callback)
            await aio.sleep(0.5)
            should_set_button_config = await inquirer.confirm(
                message="Set button config?", default=False
            ).execute_async()
            if should_set_button_config:
                haptic_duration_ms = await inquirer.number(
                    "Haptic duration (ms)",
                    replace_mode=True,
                    default=30,
                    min_allowed=0,
                    max_allowed=1000,
                    validate=EmptyInputValidator(),
                ).execute_async()

                async def get_backlight_color():
                    color_set_mode = await inquirer.rawlist(
                        message="Set backlight via kelvin or color (hue, saturation)?",
                        choices=["Kelvin", "Color"],
                    ).execute_async()
                    # Switch accepts the actual kelvin value as the input
                    kelvin = 4500
                    hue = 0
                    saturation = 0
                    if color_set_mode == "Kelvin":
                        while True:
                            kelvin = await inquirer.number(
                                "Kelvin (1500 - 9000)",
                                min_allowed=0,
                                max_allowed=9000,
                                validate=EmptyInputValidator(),
                            ).execute_async()
                            if int(kelvin) < 1500 or int(kelvin) > 9000:
                                print("Kelvin must be greater within 1500 and 9000")
                                continue
                            break
                    else:
                        hue = await inquirer.number(
                            "Hue (0 - 360)",
                            min_allowed=0,
                            max_allowed=360,
                            validate=EmptyInputValidator(),
                        ).execute_async()
                        saturation = await inquirer.number(
                            "Saturation (0 - 100)",
                            min_allowed=0,
                            max_allowed=100,
                            validate=EmptyInputValidator(),
                        ).execute_async()
                    brightness = await inquirer.number(
                        "Brightness (0 - 100)",
                        min_allowed=0,
                        max_allowed=100,
                        validate=EmptyInputValidator(),
                    ).execute_async()
                    return {
                        "hue": int(round(65535 * (int(hue) / 360))),
                        "saturation": int(round(65535 * (int(saturation) / 100))),
                        "brightness": int(round(65535 * (int(brightness) / 100))),
                        "kelvin": int(kelvin),
                    }

                print("Backlight on color")
                backlight_on_color = await get_backlight_color()
                print("Backlight off color")
                backlight_off_color = await get_backlight_color()

                device.set_button_config(
                    haptic_duration_ms,
                    backlight_on_color,
                    backlight_off_color,
                    callback,
                )
                await aio.sleep(0.5)
        elif feature == DeviceFeatures.REBOOT:
            # Reboot bulb
            print(
                "Rebooting bulb in 3 seconds. If the bulb is on, it will flicker off and back on as it reboots."
            )
            print("Hit CTRL-C within 3 seconds to to quit without rebooting the bulb.")
            sleep(3)
            device.set_reboot()
            print("Bulb rebooted.")
            feature = None
    return


async def amain():
    global MyBulbs

    # Avoid any asyncio error message
    await aio.sleep(0)

    MyBulbs = bulbs()
    loop = aio.get_event_loop()
    discovery = alix.LifxDiscovery(loop, MyBulbs)
    try:
        discovery.start()
        print("Starting")
        # Wait to discover bulbs
        await aio.sleep(2)
        print("Use Ctrl-C to quit")
        print("Start typing or use arrow keys to navigate, and enter to select.")
        await readin()
    finally:
        discovery.cleanup()


@click.command(help="Track and interact with Lifx light bulbs.")
@click.option(
    "-6",
    "--ipv6prefix",
    default=None,
    help="Connect to Lifx using IPv6 with given /64 prefix (Do not end with colon unless you have less than 64bits).",
)
@click.option(
    "-x",
    "--extra",
    is_flag=True,
    default=False,
    help="Print unexpected messages.",
)
def cli(ipv6prefix, extra):
    global opts
    opts = {"ipv6prefix": ipv6prefix, "extra": extra}
    try:
        aio.run(amain())
    except KeyboardInterrupt:
        print("\nExiting at user's request.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    cli()
