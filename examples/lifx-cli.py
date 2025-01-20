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
import sys
import asyncio as aio
import aiolifx as alix
from time import sleep
from functools import partial
from enum import Enum


# Simple bulb control frpm console
class bulbs:
    """A simple class with a register and  unregister methods"""

    def __init__(self):
        self.bulbs = []
        self.boi = None  # bulb of interest

    def register(self, bulb):
        bulb.get_label()
        bulb.get_location()
        bulb.get_version()
        bulb.get_group()
        bulb.get_wififirmware()
        bulb.get_hostfirmware()
        self.bulbs.append(bulb)
        self.bulbs.sort(key=lambda x: x.label or x.mac_addr)

    def unregister(self, bulb):
        idx = 0
        for x in list([y.mac_addr for y in self.bulbs]):
            if x == bulb.mac_addr:
                del self.bulbs[idx]
                break
            idx += 1


class BulbOptions(Enum):
    BACK = 0
    POWER = 1
    WHITE = 2
    COLOUR = 3
    INFO = 4
    FIRMWARE = 5
    WIFI = 6
    UPTIME = 7
    PULSE = 8
    HEV_CYCLE_OR_FIRMWARE_EFFECT = 9
    HEV_CONFIGURATION_OR_FIRMWARE_EFFECT_START_STOP = 10
    RELAYS = 11
    BUTTON = 12
    BUTTON_CONFIG = 13
    REBOOT = 99


def readin():
    """Reading from stdin and displaying menu"""

    selection = sys.stdin.readline().strip("\n")
    MyBulbs.bulbs.sort(key=lambda x: x.label or x.mac_addr)
    lov = [x for x in selection.split(" ") if x != ""]
    if lov:
        if MyBulbs.boi:
            # try:
            if True:
                if int(lov[0]) == BulbOptions.BACK.value:
                    MyBulbs.boi = None
                elif int(lov[0]) == BulbOptions.POWER.value:
                    if len(lov) > 1:
                        MyBulbs.boi.set_power(lov[1].lower() in ["1", "on", "true"])
                        MyBulbs.boi = None
                    else:
                        print("Error: For power you must indicate on or off\n")
                elif int(lov[0]) == BulbOptions.WHITE.value:
                    if len(lov) > 2:
                        try:
                            MyBulbs.boi.set_color(
                                [
                                    58275,
                                    0,
                                    int(round((float(lov[1]) * 65365.0) / 100.0)),
                                    int(round(float(lov[2]))),
                                ]
                            )

                            MyBulbs.boi = None
                        except:
                            print(
                                "Error: For white brightness (0-100) and temperature (2500-9000) must be numbers.\n"
                            )
                    else:
                        print(
                            "Error: For white you must indicate brightness (0-100) and temperature (2500-9000)\n"
                        )
                elif int(lov[0]) == BulbOptions.COLOUR.value:
                    if len(lov) > 3:
                        try:
                            MyBulbs.boi.set_color(
                                [
                                    int(round((float(lov[1]) * 65535.0) / 360.0)),
                                    int(round((float(lov[2]) * 65535.0) / 100.0)),
                                    int(round((float(lov[3]) * 65535.0) / 100.0)),
                                    3500,
                                ]
                            )
                            MyBulbs.boi = None
                        except:
                            print(
                                "Error: For colour hue (0-360), saturation (0-100) and brightness (0-100)) must be numbers.\n"
                            )
                    else:
                        print(
                            "Error: For colour you must indicate hue (0-360), saturation (0-100) and brightness (0-100))\n"
                        )

                elif int(lov[0]) == BulbOptions.INFO.value:
                    print(MyBulbs.boi.device_characteristics_str("    "))
                    print(MyBulbs.boi.device_product_str("    "))
                    MyBulbs.boi = None
                elif int(lov[0]) == BulbOptions.FIRMWARE.value:
                    print(MyBulbs.boi.device_firmware_str("   "))
                    MyBulbs.boi = None
                elif int(lov[0]) == BulbOptions.WIFI.value:
                    mypartial = partial(MyBulbs.boi.device_radio_str)
                    MyBulbs.boi.get_wifiinfo(
                        callb=lambda x, y: print("\n" + mypartial(y))
                    )
                    MyBulbs.boi = None
                elif int(lov[0]) == BulbOptions.UPTIME.value:
                    mypartial = partial(MyBulbs.boi.device_time_str)
                    MyBulbs.boi.get_hostinfo(
                        callb=lambda x, y: print("\n" + mypartial(y))
                    )
                    MyBulbs.boi = None
                elif int(lov[0]) == BulbOptions.PULSE.value:
                    if len(lov) > 3:
                        try:
                            print(
                                "Sending {}".format(
                                    [
                                        int(round((float(lov[1]) * 65535.0) / 360.0)),
                                        int(round((float(lov[2]) * 65535.0) / 100.0)),
                                        int(round((float(lov[3]) * 65535.0) / 100.0)),
                                        3500,
                                    ]
                                )
                            )
                            MyBulbs.boi.set_waveform(
                                {
                                    "color": [
                                        int(round((float(lov[1]) * 65535.0) / 360.0)),
                                        int(round((float(lov[2]) * 65535.0) / 100.0)),
                                        int(round((float(lov[3]) * 65535.0) / 100.0)),
                                        3500,
                                    ],
                                    "transient": 1,
                                    "period": 100,
                                    "cycles": 30,
                                    "skew_ratio": 0,
                                    "waveform": 0,
                                }
                            )
                            MyBulbs.boi = None
                        except:
                            print(
                                "Error: For pulse hue (0-360), saturation (0-100) and brightness (0-100)) must be numbers.\n"
                            )
                    else:
                        print(
                            "Error: For pulse you must indicate hue (0-360), saturation (0-100) and brightness (0-100))\n"
                        )
                elif int(lov[0]) == BulbOptions.HEV_CYCLE_OR_FIRMWARE_EFFECT.value:
                    if (
                        alix.aiolifx.products_dict[MyBulbs.boi.product].hev is True
                    ):  # HEV cycle
                        if len(lov) == 1:
                            # Get current state
                            print("Getting current HEV state")
                            MyBulbs.boi.get_hev_cycle(
                                callb=lambda _, r: print(
                                    f"\nHEV: duration={r.duration}, "
                                    f"remaining={r.remaining}, "
                                    f"last_power={r.last_power}"
                                )
                            )
                            MyBulbs.boi.get_last_hev_cycle_result(
                                callb=lambda _, r: print(
                                    f"\nHEV result: {r.result_str}"
                                )
                            )

                        elif len(lov) == 2:
                            duration = int(lov[1])
                            enable = duration >= 0
                            if enable:
                                print(f"Running HEV cycle for {duration} second(s)")
                            else:
                                print(f"Aborting HEV cycle")
                                duration = 0
                            MyBulbs.boi.set_hev_cycle(
                                enable=enable,
                                duration=duration,
                                callb=lambda _, r: print(
                                    f"\nHEV: duration={r.duration}, "
                                    f"remaining={r.remaining}, "
                                    f"last_power={r.last_power}"
                                ),
                            )
                        else:
                            print("Error: maximum 1 argument for HEV cycle")
                        MyBulbs.boi = None
                    elif (
                        alix.aiolifx.products_dict[MyBulbs.boi.product].multizone
                        is True
                    ):  # Multizone firmware effect
                        print(
                            "Getting current firmware effect state from multizone device"
                        )
                        MyBulbs.boi.get_multizone_effect(
                            callb=lambda _, r: print(
                                f"\nCurrent effect={r.effect_str}"
                                f"\nSpeed={r.speed / 1000 if getattr(r, 'speed', None) is not None else 0}"
                                f"\nDuration={r.duration / 1000000000 if getattr(r, 'duration', None) is not None else 0:4f}"
                                f"\nDirection={r.direction_str}"
                            )
                        )
                        MyBulbs.boi = None

                elif (
                    int(lov[0])
                    == BulbOptions.HEV_CONFIGURATION_OR_FIRMWARE_EFFECT_START_STOP.value
                ):
                    if (
                        alix.aiolifx.products_dict[MyBulbs.boi.product].hev is True
                    ):  # HEV cycle configuration
                        if len(lov) == 1:
                            # Get current state
                            print("Getting current HEV configuration")
                            MyBulbs.boi.get_hev_configuration(
                                callb=lambda _, r: print(
                                    f"\nHEV: indication={r.indication}, "
                                    f"duration={r.duration}"
                                )
                            )

                        elif len(lov) == 3:
                            indication = bool(int(lov[1]))
                            duration = int(lov[2])
                            print(
                                f"Configuring default HEV cycle with "
                                f"{'' if indication else 'no '}indication for "
                                f"{duration} second(s)"
                            )
                            MyBulbs.boi.set_hev_configuration(
                                indication=indication,
                                duration=duration,
                                callb=lambda _, r: print(
                                    f"\nHEV: indication={r.indication}, "
                                    f"duration={r.duration}"
                                ),
                            )
                        else:
                            print("Error: 0 or 2 arguments for HEV config")
                        MyBulbs.boi = None
                    elif (
                        alix.aiolifx.products_dict[MyBulbs.boi.product].multizone
                        is True
                    ):  # Start/stop firmware effect
                        can_set = True
                        if len(lov) == 3:
                            effect = str(lov[1])
                            direction = str(lov[2])

                            if effect.lower() not in ["off", "move"]:
                                print("Error: effect parameter must be 'off' or 'move'")
                                can_set = False
                            if direction.lower() not in ["left", "right"]:
                                print(
                                    "Error: direction parameter must be 'right' or 'left"
                                )
                                can_set = False

                            if can_set:
                                e = alix.aiolifx.MultiZoneEffectType[
                                    effect.upper()
                                ].value
                                d = alix.aiolifx.MultiZoneDirection[
                                    direction.upper()
                                ].value
                                MyBulbs.boi.set_multizone_effect(
                                    effect=e, speed=3, direction=d
                                )

                        elif len(lov) == 2:
                            MyBulbs.boi.set_multizone_effect(effect=0)

                        else:
                            print(
                                "Error: need to provide effect and direction parameters."
                            )

                        MyBulbs.boi = None

                elif int(lov[0]) == BulbOptions.RELAYS.value:

                    def callback(x, statePower):
                        return print(
                            f"Relay {statePower.relay_index + 1}: {'On' if statePower.level == 65535 else 'Off'}"
                        )  # +1 to use 1-indexing

                    if alix.aiolifx.features_map[MyBulbs.boi.product]["relays"] is True:
                        # If user provides relay index as second param AND a third param off or on
                        if len(lov) == 3:
                            # -1 to use 1-indexing
                            relay_index = int(lov[1]) - 1
                            on = [True, 1, "on"]
                            off = [False, 0, "off"]
                            set_power = partial(
                                MyBulbs.boi.set_rpower, relay_index, callb=callback
                            )
                            if lov[2] in on:
                                set_power(True)
                            elif lov[2] in off:
                                set_power(False)
                            else:
                                values_list = ", ".join(
                                    [str(x) for lst in [on, off] for x in lst]
                                )
                                print(
                                    f"Argument not known. Use one of these values: {values_list}"
                                )
                        # User has provided a relay index but isn't trying to set the value
                        elif len(lov) == 2:
                            # -1 to use 1-indexing
                            relay_index = int(lov[1]) - 1
                            MyBulbs.boi.get_rpower(relay_index, callb=callback)
                        else:  # User hasn't provided a relay index so wants all values
                            MyBulbs.boi.get_rpower(callb=callback)
                    else:
                        print(
                            "This device isn't a switch and therefore doesn't have relays"
                        )

                elif int(lov[0]) == BulbOptions.BUTTON.value:
                    if alix.aiolifx.features_map[MyBulbs.boi.product]["relays"] is True:

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
                                buttons_str += f"Button {button_index + 1}:\n"
                                # At the moment, LIFX app only supports single, double and long press
                                MAX_ACTIONS = 3
                                for action_index, action in enumerate(
                                    button["button_actions"][:MAX_ACTIONS]
                                ):
                                    buttons_str += (
                                        f"\t{get_action_name(action_index)}\n"
                                        + f"\t\tGesture: {action['button_gesture']}\n"
                                        + f"\t\t{action['button_target_type']}\n"
                                        + f"\t\t{action['button_target']}\n"
                                    )
                            return print(
                                f"Count: {buttonResponse.count}\n"
                                + f"Index: {buttonResponse.index}\n"
                                + f"Buttons Count: {buttonResponse.buttons_count}\n"
                                + f"Buttons:\n{buttons_str}"
                            )

                        MyBulbs.boi.get_button(callback)

                elif int(lov[0]) == BulbOptions.BUTTON_CONFIG.value:
                    if alix.aiolifx.features_map[MyBulbs.boi.product]["relays"] is True:

                        def callback(x, buttonConfig):
                            backlight_on_color = {
                                "hue": int(
                                    round(
                                        360
                                        * (
                                            buttonConfig.backlight_on_color["hue"]
                                            / 65535
                                        )
                                    )
                                ),
                                "saturation": int(
                                    round(
                                        100
                                        * (
                                            buttonConfig.backlight_on_color[
                                                "saturation"
                                            ]
                                            / 65535
                                        )
                                    )
                                ),
                                "brightness": int(
                                    round(
                                        100
                                        * (
                                            buttonConfig.backlight_on_color[
                                                "brightness"
                                            ]
                                            / 65535
                                        )
                                    )
                                ),
                                "kelvin": buttonConfig.backlight_on_color["kelvin"],
                            }
                            backlight_on_color_str = f"hue: {backlight_on_color['hue']}, saturation: {backlight_on_color['saturation']}, brightness: {backlight_on_color['brightness']}, kelvin: {backlight_on_color['kelvin']}"
                            backlight_off_color = {
                                "hue": int(
                                    round(
                                        360
                                        * (
                                            buttonConfig.backlight_off_color["hue"]
                                            / 65535
                                        )
                                    )
                                ),
                                "saturation": int(
                                    round(
                                        100
                                        * (
                                            buttonConfig.backlight_off_color[
                                                "saturation"
                                            ]
                                            / 65535
                                        )
                                    )
                                ),
                                "brightness": int(
                                    round(
                                        100
                                        * (
                                            buttonConfig.backlight_off_color[
                                                "brightness"
                                            ]
                                            / 65535
                                        )
                                    )
                                ),
                                "kelvin": buttonConfig.backlight_off_color["kelvin"],
                            }
                            backlight_off_color_str = f"hue: {backlight_off_color['hue']}, saturation: {backlight_off_color['saturation']}, brightness: {backlight_off_color['brightness']}, kelvin: {backlight_off_color['kelvin']}"
                            return print(
                                f"Haptic Duration (ms): {buttonConfig.haptic_duration_ms}\nBacklight on color: {backlight_on_color_str}\nBacklight off color: {backlight_off_color_str}"
                            )

                        if len(lov) == 10:
                            haptic_duration_ms = int(lov[1])

                            # Switch accepts the actual kelvin value as the input
                            def get_kelvin(input):
                                if input < 1500 or input > 9000:
                                    print("Kelvin must be between 1500 and 9000")
                                    return 1500
                                return input

                            backlight_on_color = {
                                "hue": int(round(65535 * (int(lov[2]) / 360))),
                                "saturation": int(round(65535 * (int(lov[3]) / 100))),
                                "brightness": int(round(65535 * (int(lov[4]) / 100))),
                                "kelvin": get_kelvin(int(lov[5])),
                            }
                            backlight_off_color = {
                                "hue": int(round(65535 * (int(lov[6]) / 360))),
                                "saturation": int(round(65535 * (int(lov[7]) / 100))),
                                "brightness": int(round(65535 * (int(lov[8]) / 100))),
                                "kelvin": get_kelvin(int(lov[9])),
                            }
                            MyBulbs.boi.set_button_config(
                                haptic_duration_ms,
                                backlight_on_color,
                                backlight_off_color,
                                callback,
                            )
                        elif len(lov) > 1:
                            print(
                                "Error: Format should be: <haptic_duration_ms> <backlight_on_color_hue> (0-360) <backlight_on_color_saturation> (0-100) <backlight_on_color_brightness> (0-100) <backlight_on_color_kelvin> (2500-9000) <backlight_off_color_hue> (0-360) <backlight_off_color_saturation> (0-100) <backlight_off_color_brightness> (0-100) <backlight_off_color_kelvin> (2500-9000)"
                            )
                        else:
                            MyBulbs.boi.get_button_config(callback)

                elif int(lov[0]) == 99:
                    # Reboot bulb
                    print(
                        "Rebooting bulb in 3 seconds. If the bulb is on, it will flicker off and back on as it reboots."
                    )
                    print(
                        "Hit CTRL-C within 3 seconds to to quit without rebooting the bulb."
                    )
                    sleep(3)
                    MyBulbs.boi.set_reboot()
                    print("Bulb rebooted.")
            # except:
            # print ("\nError: Selection must be a number.\n")
        else:
            try:
                if int(lov[0]) > 0:
                    if int(lov[0]) <= len(MyBulbs.bulbs):
                        MyBulbs.boi = MyBulbs.bulbs[int(lov[0]) - 1]
                    else:
                        print("\nError: Not a valid selection.\n")

            except:
                print("\nError: Selection must be a number.\n")

    if MyBulbs.boi:
        print("Select Function for {}:".format(MyBulbs.boi.label))
        print(f"\t[{BulbOptions.POWER.value}]\tPower (0 or 1)")
        print(f"\t[{BulbOptions.WHITE.value}]\tWhite (Brightness Temperature)")
        print(f"\t[{BulbOptions.COLOUR.value}]\tColour (Hue Saturation Brightness)")
        print(f"\t[{BulbOptions.INFO.value}]\tInfo")
        print(f"\t[{BulbOptions.FIRMWARE.value}]\tFirmware")
        print(f"\t[{BulbOptions.WIFI.value}]\tWifi")
        print(f"\t[{BulbOptions.UPTIME.value}]\tUptime")
        print(f"\t[{BulbOptions.PULSE.value}]\tPulse")
        if alix.aiolifx.products_dict[MyBulbs.boi.product].hev is True:
            print(
                f"\t[{BulbOptions.HEV_CYCLE_OR_FIRMWARE_EFFECT.value}]\tHEV cycle (duration, or -1 to stop)"
            )
            print(
                f"\t[{BulbOptions.HEV_CONFIGURATION_OR_FIRMWARE_EFFECT_START_STOP.value}]\tHEV configuration (indication, duration)"
            )
        if alix.aiolifx.products_dict[MyBulbs.boi.product].multizone is True:
            print(
                f"\t[{BulbOptions.HEV_CYCLE_OR_FIRMWARE_EFFECT.value}]\tGet firmware effect status"
            )
            print(
                f"\t[{BulbOptions.HEV_CONFIGURATION_OR_FIRMWARE_EFFECT_START_STOP.value}]\tStart or stop firmware effect ([off/move] [right|left])"
            )
        if alix.aiolifx.products_dict[MyBulbs.boi.product].relays is True:
            print(
                f"\t[{BulbOptions.RELAYS.value}]\tRelays; optionally followed by relay number (beginning at 1); optionally followed by `on` or `off` to set the value"
            )
            print(f"\t[{BulbOptions.BUTTON.value}]\tButton")
            print(
                f"\t[{BulbOptions.BUTTON_CONFIG.value}]\tButton Config. Optionally followed by <haptic_duration_ms> <backlight_on_color_hue> (0-360; if not 0, kelvin is ignored) <backlight_on_color_saturation> (0-100) <backlight_on_color_brightness> (0-100) <backlight_on_color_kelvin> (2500-9000) <backlight_off_color_hue> (0-360; if not 0, kelvin is ignored) <backlight_off_color_saturation> (0-100) <backlight_off_color_brightness> (0-100) <backlight_off_color_kelvin> (2500-9000)"
            )
        print(
            f"\t[{BulbOptions.REBOOT.value}]\tReboot the bulb (indicated by a reboot blink)"
        )
        print("")
        print(f"\t[{BulbOptions.BACK.value}]\tBack to bulb selection")
    else:
        idx = 1
        print("Select Bulb:")
        for x in MyBulbs.bulbs:
            print("\t[{}]\t{}".format(idx, x.label or x.mac_addr))
            idx += 1
    print("")
    print("Your choice: ", end="", flush=True)


async def scan(loop, discovery):
    scanner = alix.LifxScan(loop)
    ips = await scanner.scan()
    print('Hit "Enter" to start')
    print("Use Ctrl-C to quit")
    if not ips:
        print("LIFX controller not found!")
        return

    discovery.start(listen_ip=ips[0])


MyBulbs = bulbs()
loop = aio.get_event_loop()
discovery = alix.LifxDiscovery(loop, MyBulbs)

try:
    loop.add_reader(sys.stdin, readin)
    loop.create_task(scan(loop, discovery))
    loop.run_forever()
except:
    pass
finally:
    discovery.cleanup()
    loop.remove_reader(sys.stdin)
    loop.close()
