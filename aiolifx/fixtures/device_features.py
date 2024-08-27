from enum import Enum


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