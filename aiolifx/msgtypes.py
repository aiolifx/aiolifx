# msgtypes.py
# Author: Meghan Clark
#    Edited for python3 by François Wautier

# To Do: Validate that args are within required ranges, types, etc. In particular: Color [0-65535, 0-65535, 0-65535, 2500-9000], Power Level (must be 0 OR 65535)
# Need to look into assert-type frameworks or something, there has to be a tool for that.
# Also need to make custom errors possibly, though tool may have those.

from curses import color_content
from .message import Message, BROADCAST_MAC, HEADER_SIZE_BYTES, little_endian
import bitstring
from enum import Enum
import random
import sys
import struct

##### DEVICE MESSAGES #####


class GetService(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        target_addr = BROADCAST_MAC
        super(GetService, self).__init__(
            MSG_IDS[GetService],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateService(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.service = payload["service"]
        self.port = payload["port"]
        super(StateService, self).__init__(
            MSG_IDS[StateService],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Service", self.service))
        self.payload_fields.append(("Port", self.port))
        service = little_endian(bitstring.pack("uint:8", self.service))
        port = little_endian(bitstring.pack("uint:32", self.port))
        payload = service + port
        return payload


class GetHostInfo(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetHostInfo, self).__init__(
            MSG_IDS[GetHostInfo],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateHostInfo(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.signal = payload["signal"]
        self.tx = payload["tx"]
        self.rx = payload["rx"]
        self.reserved1 = payload["reserved1"]
        super(StateHostInfo, self).__init__(
            MSG_IDS[StateHostInfo],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Signal (mW)", self.signal))
        self.payload_fields.append(("TX (bytes since on)", self.tx))
        self.payload_fields.append(("RX (bytes since on)", self.rx))
        self.payload_fields.append(("Reserved", self.reserved1))
        signal = little_endian(bitstring.pack("float:32", self.signal))
        tx = little_endian(bitstring.pack("uint:32", self.tx))
        rx = little_endian(bitstring.pack("uint:32", self.rx))
        reserved1 = little_endian(bitstring.pack("int:16", self.reserved1))
        payload = signal + tx + rx + reserved1
        return payload


class GetHostFirmware(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetHostFirmware, self).__init__(
            MSG_IDS[GetHostFirmware],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateHostFirmware(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.build = payload["build"]
        self.reserved1 = payload["reserved1"]
        self.version = payload["version"]
        super(StateHostFirmware, self).__init__(
            MSG_IDS[StateHostFirmware],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Timestamp of Build", self.build))
        self.payload_fields.append(("Reserved", self.reserved1))
        self.payload_fields.append(("Version", self.version))
        build = little_endian(bitstring.pack("uint:64", self.build))
        reserved1 = little_endian(bitstring.pack("uint:64", self.reserved1))
        version = little_endian(bitstring.pack("uint:32", self.version))
        payload = build + reserved1 + version
        return payload


class GetWifiInfo(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetWifiInfo, self).__init__(
            MSG_IDS[GetWifiInfo],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateWifiInfo(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.signal = payload["signal"]
        self.tx = payload["tx"]
        self.rx = payload["rx"]
        self.reserved1 = payload["reserved1"]
        super(StateWifiInfo, self).__init__(
            MSG_IDS[StateWifiInfo],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Signal (mW)", self.signal))
        self.payload_fields.append(("TX (bytes since on)", self.tx))
        self.payload_fields.append(("RX (bytes since on)", self.rx))
        self.payload_fields.append(("Reserved", self.reserved1))
        signal = little_endian(bitstring.pack("float:32", self.signal))
        tx = little_endian(bitstring.pack("uint:32", self.tx))
        rx = little_endian(bitstring.pack("uint:32", self.rx))
        reserved1 = little_endian(bitstring.pack("int:16", self.reserved1))
        payload = signal + tx + rx + reserved1
        return payload


class GetWifiFirmware(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetWifiFirmware, self).__init__(
            MSG_IDS[GetWifiFirmware],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateWifiFirmware(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.build = payload["build"]
        self.reserved1 = payload["reserved1"]
        self.version = payload["version"]
        super(StateWifiFirmware, self).__init__(
            MSG_IDS[StateWifiFirmware],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Timestamp of Build", self.build))
        self.payload_fields.append(("Reserved", self.reserved1))
        self.payload_fields.append(("Version", self.version))
        build = little_endian(bitstring.pack("uint:64", self.build))
        reserved1 = little_endian(bitstring.pack("uint:64", self.reserved1))
        version = little_endian(bitstring.pack("uint:32", self.version))
        payload = build + reserved1 + version
        return payload


class GetPower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetPower, self).__init__(
            MSG_IDS[GetPower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class SetPower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.power_level = payload["power_level"]
        super(SetPower, self).__init__(
            MSG_IDS[SetPower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Power", self.power_level))
        power_level = little_endian(bitstring.pack("uint:16", self.power_level))
        payload = power_level
        return payload


class StatePower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.power_level = payload["power_level"]
        super(StatePower, self).__init__(
            MSG_IDS[StatePower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Power", self.power_level))
        power_level = little_endian(bitstring.pack("uint:16", self.power_level))
        payload = power_level
        return payload


class GetLabel(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetLabel, self).__init__(
            MSG_IDS[GetLabel],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class SetLabel(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.label = payload["label"]
        super(SetLabel, self).__init__(
            MSG_IDS[SetLabel],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Label", self.label))
        field_len_bytes = 32
        label = b"".join(
            little_endian(bitstring.pack("uint:8", ord(c))) for c in self.label
        )
        padding = b"".join(
            little_endian(bitstring.pack("uint:8", 0))
            for i in range(field_len_bytes - len(self.label))
        )
        payload = label + padding
        return payload


class StateLabel(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.label = payload["label"]
        super(StateLabel, self).__init__(
            MSG_IDS[StateLabel],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Label", self.label))
        field_len_bytes = 32
        label = b"".join(little_endian(bitstring.pack("uint:8", c)) for c in self.label)
        padding = b"".join(
            little_endian(bitstring.pack("uint:8", 0))
            for i in range(field_len_bytes - len(self.label))
        )
        payload = label + padding
        return payload


class GetVersion(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetVersion, self).__init__(
            MSG_IDS[GetVersion],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateVersion(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.vendor = payload["vendor"]
        self.product = payload["product"]
        self.version = payload["version"]
        super(StateVersion, self).__init__(
            MSG_IDS[StateVersion],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Vendor", self.vendor))
        self.payload_fields.append(("Reserved", self.product))
        self.payload_fields.append(("Version", self.version))
        vendor = little_endian(bitstring.pack("uint:32", self.vendor))
        product = little_endian(bitstring.pack("uint:32", self.product))
        version = little_endian(bitstring.pack("uint:32", self.version))
        payload = vendor + product + version
        return payload


class GetInfo(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetInfo, self).__init__(
            MSG_IDS[GetInfo],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateInfo(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.time = payload["time"]
        self.uptime = payload["uptime"]
        self.downtime = payload["downtime"]
        super(StateInfo, self).__init__(
            MSG_IDS[StateInfo],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Current Time", self.time))
        self.payload_fields.append(("Uptime (ns)", self.uptime))
        self.payload_fields.append(
            ("Last Downtime Duration (ns) (5 second error)", self.downtime)
        )
        time = little_endian(bitstring.pack("uint:64", self.time))
        uptime = little_endian(bitstring.pack("uint:64", self.uptime))
        downtime = little_endian(bitstring.pack("uint:64", self.downtime))
        payload = time + uptime + downtime
        return payload


class GetLocation(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetLocation, self).__init__(
            MSG_IDS[GetLocation],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateLocation(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.location = payload["location"]
        self.label = payload["label"]
        self.updated_at = payload["updated_at"]
        super(StateLocation, self).__init__(
            MSG_IDS[StateLocation],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Location ", self.location))
        self.payload_fields.append(("Label ", self.label))
        self.payload_fields.append(("Updated At ", self.updated_at))
        location = b"".join(
            little_endian(bitstring.pack("uint:8", b)) for b in self.location
        )
        label = b"".join(little_endian(bitstring.pack("uint:8", c)) for c in self.label)
        label_padding = b"".join(
            little_endian(bitstring.pack("uint:8", 0))
            for i in range(32 - len(self.label))
        )
        label += label_padding
        updated_at = little_endian(bitstring.pack("uint:64", self.updated_at))
        payload = location + label + updated_at
        return payload


class GetGroup(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetGroup, self).__init__(
            MSG_IDS[GetGroup],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateGroup(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.group = payload["group"]
        self.label = payload["label"]
        self.updated_at = payload["updated_at"]
        super(StateGroup, self).__init__(
            MSG_IDS[StateGroup],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Group ", self.group))
        self.payload_fields.append(("Label ", self.label))
        self.payload_fields.append(("Updated At ", self.updated_at))
        group = b"".join(little_endian(bitstring.pack("uint:8", b)) for b in self.group)
        label = b"".join(little_endian(bitstring.pack("uint:8", c)) for c in self.label)
        label_padding = b"".join(
            little_endian(bitstring.pack("uint:8", 0))
            for i in range(32 - len(self.label))
        )
        label += label_padding
        updated_at = little_endian(bitstring.pack("uint:64", self.updated_at))
        payload = group + label + updated_at
        return payload


class SetReboot(Message):
    def __init__(
        self,
        target_addr: str,
        source_id: str,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ) -> None:
        """Initialise a SetReboot packet."""
        super(SetReboot, self).__init__(
            MSG_IDS[SetReboot],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class Acknowledgement(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(Acknowledgement, self).__init__(
            MSG_IDS[Acknowledgement],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class EchoRequest(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.byte_array = payload["byte_array"]
        super(EchoRequest, self).__init__(
            MSG_IDS[EchoRequest],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        field_len = 64
        self.payload_fields.append(("Byte Array", self.byte_array))
        byte_array = b"".join(
            little_endian(bitstring.pack("uint:8", b)) for b in self.byte_array
        )
        byte_array_len = len(byte_array)
        if byte_array_len < field_len:
            byte_array += b"".join(
                little_endian(bitstring.pack("uint:8", 0))
                for i in range(field_len - byte_array_len)
            )
        elif byte_array_len > field_len:
            byte_array = byte_array[:field_len]
        payload = byte_array
        return payload


class EchoResponse(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.byte_array = payload["byte_array"]
        super(EchoResponse, self).__init__(
            MSG_IDS[EchoResponse],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Byte Array", self.byte_array))
        byte_array = b"".join(
            little_endian(bitstring.pack("uint:8", b)) for b in self.byte_array
        )
        payload = byte_array
        return payload


##### LIGHT MESSAGES #####


class LightGet(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(LightGet, self).__init__(
            MSG_IDS[LightGet],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class LightSetColor(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.color = payload["color"]
        self.duration = payload["duration"]
        super(LightSetColor, self).__init__(
            MSG_IDS[LightSetColor],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        reserved_8 = little_endian(bitstring.pack("uint:8", self.reserved))
        color = b"".join(
            little_endian(bitstring.pack("uint:16", field)) for field in self.color
        )
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        payload = reserved_8 + color + duration
        payloadUi = " ".join("{:02x}".format(c) for c in payload)
        return payload


class LightSetWaveform(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.transient = payload["transient"]
        self.color = payload["color"]
        self.period = payload["period"]
        self.cycles = payload["cycles"]
        self.skew_ratio = payload["skew_ratio"]
        self.waveform = payload["waveform"]
        super(LightSetWaveform, self).__init__(
            MSG_IDS[LightSetWaveform],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        reserved_8 = little_endian(bitstring.pack("uint:8", self.reserved))
        transient = little_endian(bitstring.pack("uint:8", self.transient))
        color = b"".join(
            little_endian(bitstring.pack("uint:16", field)) for field in self.color
        )
        period = little_endian(bitstring.pack("uint:32", self.period))
        cycles = little_endian(bitstring.pack("float:32", self.cycles))
        skew_ratio = little_endian(bitstring.pack("int:16", self.skew_ratio))
        waveform = little_endian(bitstring.pack("uint:8", self.waveform))
        payload = (
            reserved_8 + transient + color + period + cycles + skew_ratio + waveform
        )

        payloadUi = " ".join("{:02x}".format(c) for c in payload)
        return payload


class LightSetWaveformOptional(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.transient = payload["transient"]
        self.color = payload["color"]
        self.period = payload["period"]
        self.cycles = payload["cycles"]
        self.skew_ratio = payload["skew_ratio"]
        self.waveform = payload["waveform"]
        self.set_hue = payload["set_hue"]
        self.set_saturation = payload["set_saturation"]
        self.set_brightness = payload["set_brightness"]
        self.set_kelvin = payload["set_kelvin"]
        super(LightSetWaveformOptional, self).__init__(
            MSG_IDS[LightSetWaveformOptional],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        reserved_8 = little_endian(bitstring.pack("uint:8", self.reserved))
        transient = little_endian(bitstring.pack("uint:8", self.transient))
        color = b"".join(
            little_endian(bitstring.pack("uint:16", field)) for field in self.color
        )
        period = little_endian(bitstring.pack("uint:32", self.period))
        cycles = little_endian(bitstring.pack("float:32", self.cycles))
        skew_ratio = little_endian(bitstring.pack("int:16", self.skew_ratio))
        waveform = little_endian(bitstring.pack("uint:8", self.waveform))
        set_hue = little_endian(bitstring.pack("uint:8", self.set_hue))
        set_saturation = little_endian(bitstring.pack("uint:8", self.set_saturation))
        set_brightness = little_endian(bitstring.pack("uint:8", self.set_brightness))
        set_kelvin = little_endian(bitstring.pack("uint:8", self.set_kelvin))
        payload = (
            reserved_8
            + transient
            + color
            + period
            + cycles
            + skew_ratio
            + waveform
            + set_hue
            + set_saturation
            + set_brightness
            + set_kelvin
        )

        payloadUi = " ".join("{:02x}".format(c) for c in payload)
        return payload


class LightState(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.color = payload["color"]
        self.reserved1 = payload["reserved1"]
        self.power_level = payload["power_level"]
        self.label = payload["label"]
        self.reserved2 = payload["reserved2"]
        super(LightState, self).__init__(
            MSG_IDS[LightState],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Color (HSBK)", self.color))
        self.payload_fields.append(("Reserved", self.reserved1))
        self.payload_fields.append(("Power Level", self.power_level))
        self.payload_fields.append(("Label", self.label))
        self.payload_fields.append(("Reserved", self.reserved2))
        color = b"".join(
            little_endian(bitstring.pack("uint:16", field)) for field in self.color
        )
        reserved1 = little_endian(bitstring.pack("int:16", self.reserved1))
        power_level = little_endian(bitstring.pack("uint:16", self.power_level))
        label = self.label.ljust(32, b"\0")
        reserved2 = little_endian(bitstring.pack("uint:64", self.reserved1))
        payload = color + reserved1 + power_level + label + reserved2
        return payload


class LightGetPower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(LightGetPower, self).__init__(
            MSG_IDS[LightGetPower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class LightSetPower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.power_level = payload["power_level"]
        self.duration = payload["duration"]
        super(LightSetPower, self).__init__(
            MSG_IDS[LightSetPower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        power_level = little_endian(bitstring.pack("uint:16", self.power_level))
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        payload = power_level + duration
        return payload


class LightStatePower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.power_level = payload["power_level"]
        super(LightStatePower, self).__init__(
            MSG_IDS[LightStatePower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Power Level", self.power_level))
        power_level = little_endian(bitstring.pack("uint:16", self.power_level))
        payload = power_level
        return payload


##### INFRARED MESSAGES #####


class LightGetInfrared(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(LightGetInfrared, self).__init__(
            MSG_IDS[LightGetInfrared],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class LightStateInfrared(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.infrared_brightness = payload["infrared_brightness"]
        super(LightStateInfrared, self).__init__(
            MSG_IDS[LightStateInfrared],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Infrared Brightness", self.infrared_brightness))
        infrared_brightness = little_endian(
            bitstring.pack("uint:16", self.infrared_brightness)
        )
        payload = infrared_brightness
        return payload


class LightSetInfrared(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.infrared_brightness = payload["infrared_brightness"]
        super(LightSetInfrared, self).__init__(
            MSG_IDS[LightSetInfrared],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        infrared_brightness = little_endian(
            bitstring.pack("uint:16", self.infrared_brightness)
        )
        payload = infrared_brightness
        return payload


##### HEV (LIFX Clean) MESSAGES #####
# https://lan.developer.lifx.com/docs/hev-light-control
class GetHevCycle(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetHevCycle, self).__init__(
            MSG_IDS[GetHevCycle],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class SetHevCycle(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.enable = payload["enable"]
        self.duration = payload["duration"]
        super(SetHevCycle, self).__init__(
            MSG_IDS[SetHevCycle],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        enable = little_endian(bitstring.pack("uint:8", self.enable))
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        payload = enable + duration
        return payload


class StateHevCycle(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.duration = payload["duration"]
        self.remaining = payload["remaining"]
        self.last_power = payload["last_power"]
        super(StateHevCycle, self).__init__(
            MSG_IDS[StateHevCycle],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        remaining = little_endian(bitstring.pack("uint:32", self.remaining))
        last_power = little_endian(bitstring.pack("uint:8", self.last_power))
        payload = duration + remaining + last_power
        return payload


class GetHevCycleConfiguration(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetHevCycleConfiguration, self).__init__(
            MSG_IDS[GetHevCycleConfiguration],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class SetHevCycleConfiguration(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.indication = payload["indication"]
        self.duration = payload["duration"]
        super(SetHevCycleConfiguration, self).__init__(
            MSG_IDS[SetHevCycleConfiguration],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        indication = little_endian(bitstring.pack("uint:8", self.indication))
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        payload = indication + duration
        return payload


class StateHevCycleConfiguration(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.indication = payload["indication"]
        self.duration = payload["duration"]
        super(StateHevCycleConfiguration, self).__init__(
            MSG_IDS[StateHevCycleConfiguration],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        indication = little_endian(bitstring.pack("uint:8", self.indication))
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        payload = indication + duration
        return payload


class GetLastHevCycleResult(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetLastHevCycleResult, self).__init__(
            MSG_IDS[GetLastHevCycleResult],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class StateLastHevCycleResult(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.result = payload["result"]
        super(StateLastHevCycleResult, self).__init__(
            MSG_IDS[StateLastHevCycleResult],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        result = little_endian(bitstring.pack("uint:8", self.result))
        return result

    @property
    def result_str(self):
        return LAST_HEV_CYCLE_RESULT.get(self.result, "UNKNOWN")


##### MULTIZONE MESSAGES #####


class MultiZoneStateMultiZone(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.count = payload["count"]
        self.index = payload["index"]
        self.color = payload["color"]
        super(MultiZoneStateMultiZone, self).__init__(
            MSG_IDS[MultiZoneStateMultiZone],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Count", self.count))
        self.payload_fields.append(("Index", self.index))
        self.payload_fields.append(("Color (HSBK)", self.color))
        count = little_endian(bitstring.pack("uint:8", self.count))
        index = little_endian(bitstring.pack("uint:8", self.index))
        payload = count + index
        for color in self.color:
            payload += b"".join(
                little_endian(bitstring.pack("uint:16", field)) for field in color
            )
        return payload


class MultiZoneStateZone(Message):  # 503
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.count = payload["count"]
        self.index = payload["index"]
        self.color = payload["color"]
        super(MultiZoneStateZone, self).__init__(
            MSG_IDS[MultiZoneStateZone],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Count", self.count))
        self.payload_fields.append(("Index", self.index))
        self.payload_fields.append(("Color (HSBK)", self.color))
        count = little_endian(bitstring.pack("uint:8", self.count))
        index = little_endian(bitstring.pack("uint:8", self.index))
        color = b"".join(
            little_endian(bitstring.pack("uint:16", field)) for field in self.color
        )
        payload = count + index + color
        return payload


class MultiZoneSetColorZones(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.start_index = payload["start_index"]
        self.end_index = payload["end_index"]
        self.color = payload["color"]
        self.duration = payload["duration"]
        self.apply = payload["apply"]
        super(MultiZoneSetColorZones, self).__init__(
            MSG_IDS[MultiZoneSetColorZones],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        start_index = little_endian(bitstring.pack("uint:8", self.start_index))
        end_index = little_endian(bitstring.pack("uint:8", self.end_index))
        color = b"".join(
            little_endian(bitstring.pack("uint:16", field)) for field in self.color
        )
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        apply = little_endian(bitstring.pack("uint:8", self.apply))
        payload = start_index + end_index + color + duration + apply
        return payload


class MultiZoneGetColorZones(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.start_index = payload["start_index"]
        self.end_index = payload["end_index"]
        super(MultiZoneGetColorZones, self).__init__(
            MSG_IDS[MultiZoneGetColorZones],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        start_index = little_endian(bitstring.pack("uint:8", self.start_index))
        end_index = little_endian(bitstring.pack("uint:8", self.end_index))
        payload = start_index + end_index
        return payload


class MultiZoneGetMultiZoneEffect(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(MultiZoneGetMultiZoneEffect, self).__init__(
            MSG_IDS[MultiZoneGetMultiZoneEffect],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class MultiZoneSetMultiZoneEffect(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.instanceid = random.randrange(1, 1 << 32)
        self.type = payload["type"]
        self.speed = payload["speed"]
        self.duration = payload["duration"]
        self.direction = payload["direction"]
        super(MultiZoneSetMultiZoneEffect, self).__init__(
            MSG_IDS[MultiZoneSetMultiZoneEffect],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        instanceid = little_endian(bitstring.pack("uint:32", self.instanceid))
        type = little_endian(bitstring.pack("uint:8", self.type))
        reserved6 = little_endian(bitstring.pack("int:16", 2))
        speed = little_endian(bitstring.pack("uint:32", self.speed))
        duration = little_endian(bitstring.pack("uint:64", self.duration))
        reserved7 = little_endian(bitstring.pack("int:32", 4))
        reserved8 = little_endian(bitstring.pack("int:32", 4))
        parameter1 = little_endian(bitstring.pack("uint:32", 4))
        direction = little_endian(bitstring.pack("uint:32", self.direction))
        parameter3 = little_endian(bitstring.pack("uint:32", 4))

        payload = (
            instanceid
            + type
            + reserved6
            + speed
            + duration
            + reserved7
            + reserved8
            + parameter1
            + direction
            + parameter3 * 6
        )
        return payload


class MultiZoneStateMultiZoneEffect(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.instanceid = payload["instanceid"]
        self.effect = payload["effect"]
        self.speed = payload["speed"]
        self.duration = payload["duration"]
        self.direction = payload["direction"]

        super(MultiZoneStateMultiZoneEffect, self).__init__(
            MSG_IDS[MultiZoneStateMultiZoneEffect],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append("Instance ID", self.instanceid)
        self.payload_fields.append("Effect", self.effect)
        self.payload_fields.append("Speed", self.speed)
        self.payload_fields.append("Duration", self.duration)
        self.payload_fields.append("Direction", self.direction)
        instanceid = little_endian(bitstring.pack("uint:32", self.instanceid))
        effect = little_endian(bitstring.pack("uint:8", self.effect))
        speed = little_endian(bitstring.pack("uint:32", self.speed))
        duration = little_endian(bitstring.pack("uint:64", self.duration))
        parameter1 = b"".join(little_endian(bitstring.pack("uint:8", 8)))
        direction = b"".join(
            little_endian(bitstring.pack("uint:8", c)) for c in self.direction
        )
        direction_padding = b"".join(
            little_endian(bitstring.pack("uint:8", 0))
            for i in range(8 - len(self.direction))
        )
        direction += direction_padding
        parameter3 = b"".join(little_endian(bitstring.pack("uint:8", 8)))
        parameter4 = b"".join(little_endian(bitstring.pack("uint:8", 8)))
        payload = (
            instanceid
            + effect
            + speed
            + duration
            + parameter1
            + direction
            + parameter3
            + parameter4
        )

        return payload

    @property
    def effect_str(self):
        return MultiZoneEffectType(self.effect).name.upper()

    @property
    def direction_str(self):
        return MultiZoneDirection(self.direction).name.lower()


class MultiZoneSetExtendedColorZones(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.duration = payload["duration"]
        self.apply = payload["apply"]
        self.zone_index = payload["zone_index"]
        self.colors_count = payload["colors_count"]
        self.colors = payload["colors"]
        super(MultiZoneSetExtendedColorZones, self).__init__(
            MSG_IDS[MultiZoneSetExtendedColorZones],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        apply = little_endian(bitstring.pack("uint:8", self.apply))
        zone_index = little_endian(bitstring.pack("uint:16", self.zone_index))
        colors_count = little_endian(bitstring.pack("uint:8", self.colors_count))
        payload = duration + apply + zone_index + colors_count
        for color in self.colors:
            payload += b"".join(
                little_endian(bitstring.pack("uint:16", field)) for field in color
            )
        return payload


class MultiZoneGetExtendedColorZones(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(MultiZoneGetExtendedColorZones, self).__init__(
            MSG_IDS[MultiZoneGetExtendedColorZones],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class MultiZoneStateExtendedColorZones(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.zones_count = payload["zones_count"]
        self.zone_index = payload["zone_index"]
        self.colors_count = payload["colors_count"]
        self.colors = payload["colors"]
        super(MultiZoneStateExtendedColorZones, self).__init__(
            MSG_IDS[MultiZoneStateExtendedColorZones],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Zones Count", self.zones_count))
        self.payload_fields.append(("Zone Index", self.zone_index))
        self.payload_fields.append(("Colors count", self.colors_count))
        self.payload_fields.append(("Colors", self.colors))
        zones_count = little_endian(bitstring.pack("uint:16", self.zones_count))
        zone_index = little_endian(bitstring.pack("uint:16", self.zone_index))
        colors_count = little_endian(bitstring.pack("uint:8", self.colors_count))
        payload = zones_count + zone_index + colors_count
        for color in self.colors:
            payload += b"".join(
                little_endian(bitstring.pack("uint:16", field)) for field in color
            )
        return payload


class TileGetDeviceChain(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(TileGetDeviceChain, self).__init__(
            MSG_IDS[TileGetDeviceChain],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class TileStateDeviceChain(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.start_index = payload["start_index"]
        self.tile_devices = [tile_device for tile_device in payload["tile_devices"]]
        self.tile_devices_count = payload["tile_devices_count"]
        super(TileStateDeviceChain, self).__init__(
            MSG_IDS[TileStateDeviceChain],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Start Index", self.start_index))
        self.payload_fields.append(("Devices", self.tile_devices))
        self.payload_fields.append(("Devices Count", self.tile_devices_count))

        start_index = little_endian(bitstring.pack("uint:8", self.start_index))
        tile_devices = b""
        for tile_device in self.tile_devices:
            tile_devices += b"".join(
                little_endian(bitstring.pack("int:16", tile_device["accel_meas_x"])),
                little_endian(bitstring.pack("int:16", tile_device["accel_meas_y"])),
                little_endian(bitstring.pack("int:16", tile_device["accel_meas_z"])),
                little_endian(bitstring.pack("float", tile_device["user_x"])),
                little_endian(bitstring.pack("float", tile_device["user_y"])),
                little_endian(bitstring.pack("uint:8", tile_device["width"])),
                little_endian(bitstring.pack("uint:8", tile_device["height"])),
                little_endian(
                    bitstring.pack("uint:32", tile_device["device_version_vendor"])
                ),
                little_endian(
                    bitstring.pack("uint:32", tile_device["device_version_product"])
                ),
                little_endian(bitstring.pack("uint:64", tile_device["firmware_build"])),
                little_endian(
                    bitstring.pack("uint:16", tile_device["firmware_version_minor"])
                ),
                little_endian(
                    bitstring.pack("uint:16", tile_device["firmware_version_major"])
                ),
            )
        tile_devices_count = little_endian(
            bitstring.pack("uint:8", self.tile_devices_count)
        )

        payload = start_index + tile_devices + tile_devices_count
        return payload


class TileGet64(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.tile_index = payload["tile_index"]
        self.length = payload["length"]
        self.x = payload["x"]
        self.y = payload["y"]
        self.width = payload["width"]
        super(TileGet64, self).__init__(
            MSG_IDS[TileGet64],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        tile_index = little_endian(bitstring.pack("uint:8", self.tile_index))
        length = little_endian(bitstring.pack("uint:8", self.length))
        reserved = little_endian(bitstring.pack("uint:8", 0))
        x = little_endian(bitstring.pack("uint:8", self.x))
        y = little_endian(bitstring.pack("uint:8", self.y))
        width = little_endian(bitstring.pack("uint:8", self.width))
        payload = tile_index + length + reserved + x + y + width
        return payload


class TileSet64(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.tile_index = payload["tile_index"]
        self.length = payload["length"]
        self.x = payload["x"]
        self.y = payload["y"]
        self.width = payload["width"]
        self.duration = payload["duration"]
        self.colors = payload["colors"]
        super(TileSet64, self).__init__(
            MSG_IDS[TileSet64],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        tile_index = little_endian(bitstring.pack("uint:8", self.tile_index))
        length = little_endian(bitstring.pack("uint:8", self.length))
        reserved = little_endian(bitstring.pack("int:8", 0))
        x = little_endian(bitstring.pack("uint:8", self.x))
        y = little_endian(bitstring.pack("uint:8", self.y))
        width = little_endian(bitstring.pack("uint:8", self.width))
        duration = little_endian(bitstring.pack("uint:32", self.duration))
        payload = tile_index + length + reserved + x + y + width + duration
        for color in self.colors:
            payload += b"".join(
                little_endian(bitstring.pack("uint:16", field)) for field in color
            )
        return payload


class TileState64(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.tile_index = payload["tile_index"]
        self.x = payload["x"]
        self.y = payload["y"]
        self.width = payload["width"]
        self.colors = payload["colors"]
        super(TileState64, self).__init__(
            MSG_IDS[TileState64],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Tile Index", self.tile_index))
        self.payload_fields.append(("x", self.x))
        self.payload_fields.append(("y", self.y))
        self.payload_fields.append(("width", self.width))

        tile_index = little_endian(bitstring.pack("uint:8", self.tile_index))
        x = little_endian(bitstring.pack("uint:8", self.x))
        y = little_endian(bitstring.pack("uint:8", self.y))
        width = little_endian(bitstring.pack("uint:8", self.width))
        payload = tile_index + x + y + width

        for color in self.colors:
            payload += b"".join(
                little_endian(bitstring.pack("uint:16", field)) for field in color
            )
        return payload


class TileGetTileEffect(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(TileGetTileEffect, self).__init__(
            MSG_IDS[TileGetTileEffect],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class TileSetTileEffect(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.instanceid = random.randrange(1, 1 << 32)
        self.type = payload["type"]
        self.speed = payload["speed"]
        self.duration = payload["duration"]
        self.sky_type = payload["sky_type"]
        self.cloud_saturation_min = payload["cloud_saturation_min"]
        self.cloud_saturation_max = payload["cloud_saturation_max"]
        self.palette_count = payload["palette_count"]
        self.palette = payload["palette"]
        super(TileSetTileEffect, self).__init__(
            MSG_IDS[TileSetTileEffect],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        reserved = little_endian(bitstring.pack("int:8", 0))
        instanceid = little_endian(bitstring.pack("uint:32", self.instanceid))
        type = little_endian(bitstring.pack("uint:8", self.type))
        speed = little_endian(bitstring.pack("uint:32", self.speed))
        duration = little_endian(bitstring.pack("uint:64", self.duration))
        sky_type = little_endian(bitstring.pack("uint:8", self.sky_type))
        cloud_saturation_min = little_endian(
            bitstring.pack("uint:8", self.cloud_saturation_min)
        )
        cloud_saturation_max = little_endian(
            bitstring.pack("uint:8", self.cloud_saturation_max)
        )
        palette_count = little_endian(bitstring.pack("uint:8", self.palette_count))
        payload = (
            reserved * 2
            + instanceid
            + type
            + speed
            + duration
            + reserved * 8
            + sky_type
            + reserved * 3
            + cloud_saturation_min
            + reserved * 3
            + cloud_saturation_max
            + reserved * 23
            + palette_count
        )
        for color in self.palette:
            payload += b"".join(
                little_endian(bitstring.pack("uint:16", field)) for field in color
            )

        return payload


class TileStateTileEffect(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.instanceid = payload["instanceid"]
        self.effect = payload["effect"]
        self.speed = payload["speed"]
        self.duration = payload["duration"]
        self.sky_type = payload["sky_type"]
        self.cloud_saturation_min = payload["cloud_saturation_min"]
        self.cloud_saturation_max = payload["cloud_saturation_max"]
        self.palette_count = payload["palette_count"]
        self.palette = payload["palette"]
        super(TileStateTileEffect, self).__init__(
            MSG_IDS[TileStateTileEffect],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append("Instance ID", self.instanceid)
        self.payload_fields.append("Effect", self.effect)
        self.payload_fields.append("Speed", self.speed)
        self.payload_fields.append("Duration", self.duration)
        self.payload_fields.append("Sky Type", self.sky_type)
        self.payload_fields.append("Cloud Saturation Min", self.cloud_saturation_min)
        self.payload_fields.append("Cloud Saturation Max", self.cloud_saturation_max)
        self.payload_fields.append("Palette Count", self.palette_count)
        self.payload_fields.append("Palette", self.palette)
        instanceid = little_endian(bitstring.pack("uint:32", self.instanceid))
        effect = little_endian(bitstring.pack("uint:8", self.effect))
        speed = little_endian(bitstring.pack("uint:32", self.speed))
        duration = little_endian(bitstring.pack("uint:64", self.duration))
        sky_type = little_endian(bitstring.pack("uint:8", self.sky_type))
        cloud_saturation_min = little_endian(
            bitstring.pack("uint:8", self.cloud_saturation_min)
        )
        cloud_saturation_max = little_endian(
            bitstring.pack("uint:8", self.cloud_saturation_max)
        )
        palette_count = little_endian(bitstring.pack("uint:8", self.palette_count))
        payload = (
            instanceid
            + effect
            + speed
            + duration
            + sky_type
            + cloud_saturation_min
            + cloud_saturation_max
            + palette_count
        )
        for color in self.palette:
            payload += b"".join(
                little_endian(bitstring.pack("uint:16", field)) for field in color
            )

        return payload

    @property
    def effect_str(self):
        return TileEffectType(self.effect).name.upper()

    @property
    def sky_type_str(self):
        if self.effect == TileEffectType.SKY.value:
            return TileEffectSkyType(self.sky_type).name.upper()
        return "NONE"


##### RELAY (SWITCH) MESSAGES #####
##### https://lan.developer.lifx.com/docs/the-lifx-switch #####


class GetRPower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        self.relay_index = payload["relay_index"]
        super(GetRPower, self).__init__(
            MSG_IDS[GetRPower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Relay Index", self.relay_index))
        relay_index = little_endian(bitstring.pack("uint:8", self.relay_index))
        payload = relay_index
        return payload


class SetRPower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.relay_index = payload["relay_index"]
        self.level = payload["level"]
        super(SetRPower, self).__init__(
            MSG_IDS[SetRPower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Relay Index", self.relay_index))
        self.payload_fields.append(("Level", self.level))
        relay_index = little_endian(bitstring.pack("uint:8", self.relay_index))
        level = little_endian(bitstring.pack("uint:16", self.level))
        payload = relay_index + level
        return payload


class StateRPower(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.relay_index = payload["relay_index"]
        self.level = payload["level"]
        super(StateRPower, self).__init__(
            MSG_IDS[StateRPower],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("Relay Index", self.relay_index))
        self.payload_fields.append(("Level", self.level))
        relay_index = little_endian(bitstring.pack("uint:8", self.relay_index))
        level = little_endian(bitstring.pack("uint:32", self.level))
        payload = relay_index + level
        return payload


##### SWITCH BUTTON MESSAGES #####
##### https://github.com/LIFX/public-protocol/blob/main/protocol.yml#L472-L541 #####


class GetButton(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetButton, self).__init__(
            MSG_IDS[GetButton],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class SetButton(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        super(SetButton, self).__init__(
            MSG_IDS[SetButton],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )
        raise Exception("Not implemented")

    def get_payload(self):
        raise Exception("Not implemented")


class StateButton(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.count = payload["count"]
        self.index = payload["index"]
        self.buttons_count = payload["buttons_count"]
        self.buttons = payload["buttons"]
        super(StateButton, self).__init__(
            MSG_IDS[StateButton],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class GetButtonConfig(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload={},
        ack_requested=False,
        response_requested=False,
    ):
        super(GetButtonConfig, self).__init__(
            MSG_IDS[GetButtonConfig],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


class SetButtonConfig(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.haptic_duration_ms = payload["haptic_duration_ms"]
        self.backlight_on_color = payload["backlight_on_color"]
        self.backlight_off_color = payload["backlight_off_color"]
        super(SetButtonConfig, self).__init__(
            MSG_IDS[SetButtonConfig],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    def get_payload(self):
        self.payload_fields.append(("haptic_duration_ms", self.haptic_duration_ms))
        self.payload_fields.append(("backlight_on_color", self.backlight_on_color))
        self.payload_fields.append(("backlight_off_color", self.backlight_off_color))
        haptic_duration_ms = little_endian(
            bitstring.pack("uint:16", self.haptic_duration_ms)
        )

        hue = self.backlight_on_color["hue"]
        saturation = self.backlight_on_color["saturation"]
        brightness = self.backlight_on_color["brightness"]
        kelvin = self.backlight_on_color["kelvin"]

        backlight_on_color = (
            little_endian(bitstring.pack("uint:16", hue))
            + little_endian(bitstring.pack("uint:16", saturation))
            + little_endian(bitstring.pack("uint:16", brightness))
            + little_endian(bitstring.pack("uint:16", kelvin))
        )

        hue = self.backlight_off_color["hue"]
        saturation = self.backlight_off_color["saturation"]
        brightness = self.backlight_off_color["brightness"]
        kelvin = self.backlight_off_color["kelvin"]

        backlight_off_color = (
            little_endian(bitstring.pack("uint:16", hue))
            + little_endian(bitstring.pack("uint:16", saturation))
            + little_endian(bitstring.pack("uint:16", brightness))
            + little_endian(bitstring.pack("uint:16", kelvin))
        )

        payload = haptic_duration_ms + backlight_on_color + backlight_off_color
        return payload


class StateButtonConfig(Message):
    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.haptic_duration_ms = payload["haptic_duration_ms"]
        self.backlight_on_color = payload["backlight_on_color"]
        self.backlight_off_color = payload["backlight_off_color"]
        super(StateButtonConfig, self).__init__(
            MSG_IDS[StateButtonConfig],
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )


MSG_IDS = {
    GetService: 2,
    StateService: 3,
    GetHostInfo: 12,
    StateHostInfo: 13,
    GetHostFirmware: 14,
    StateHostFirmware: 15,
    GetWifiInfo: 16,
    StateWifiInfo: 17,
    GetWifiFirmware: 18,
    StateWifiFirmware: 19,
    GetPower: 20,
    SetPower: 21,
    StatePower: 22,
    GetLabel: 23,
    SetLabel: 24,
    StateLabel: 25,
    GetVersion: 32,
    StateVersion: 33,
    GetInfo: 34,
    StateInfo: 35,
    SetReboot: 38,
    Acknowledgement: 45,
    GetLocation: 48,
    StateLocation: 50,
    GetGroup: 51,
    StateGroup: 53,
    EchoRequest: 58,
    EchoResponse: 59,
    LightGet: 101,
    LightSetColor: 102,
    LightSetWaveform: 103,
    LightState: 107,
    LightGetPower: 116,
    LightSetPower: 117,
    LightStatePower: 118,
    LightSetWaveformOptional: 119,
    LightGetInfrared: 120,
    LightStateInfrared: 121,
    LightSetInfrared: 122,
    GetHevCycle: 142,
    SetHevCycle: 143,
    StateHevCycle: 144,
    GetHevCycleConfiguration: 145,
    SetHevCycleConfiguration: 146,
    StateHevCycleConfiguration: 147,
    GetLastHevCycleResult: 148,
    StateLastHevCycleResult: 149,
    MultiZoneSetColorZones: 501,
    MultiZoneGetColorZones: 502,
    MultiZoneStateZone: 503,
    MultiZoneStateMultiZone: 506,
    MultiZoneGetMultiZoneEffect: 507,
    MultiZoneSetMultiZoneEffect: 508,
    MultiZoneStateMultiZoneEffect: 509,
    MultiZoneSetExtendedColorZones: 510,
    MultiZoneGetExtendedColorZones: 511,
    MultiZoneStateExtendedColorZones: 512,
    TileGetDeviceChain: 701,
    TileStateDeviceChain: 702,
    TileGet64: 707,
    TileState64: 711,
    TileSet64: 715,
    TileGetTileEffect: 718,
    TileSetTileEffect: 719,
    TileStateTileEffect: 720,
    GetRPower: 816,
    SetRPower: 817,
    StateRPower: 818,
    GetButton: 905,
    SetButton: 906,
    StateButton: 907,
    GetButtonConfig: 909,
    SetButtonConfig: 910,
    StateButtonConfig: 911,
}

SERVICE_IDS = {1: "UDP", 2: "reserved", 3: "reserved", 4: "reserved"}

STR_MAP = {65535: "On", 0: "Off", None: "Unknown"}

ZONE_MAP = {0: "NO_APPLY", 1: "APPLY", 2: "APPLY_ONLY"}

LAST_HEV_CYCLE_RESULT = {
    0: "SUCCESS",
    1: "BUSY",
    2: "INTERRUPTED_BY_RESET",
    3: "INTERRUPTED_BY_HOMEKIT",
    4: "INTERRUPTED_BY_LAN",
    5: "INTERRUPTED_BY_CLOUD",
    255: "NONE",
}

TILE_EFFECT_SKY_PALETTE = {
    0: "SKY",
    1: "NIGHT_SKY",
    2: "DAWN_SKY",
    3: "DAWN_SUN",
    4: "FULL_SUN",
    5: "FINAL_SUN",
}


class Button:
    def __init__(self, data):
        self.actions = []
        self.actions_count = data[0]
        for i in range(0, self.actions_count):
            self.actions.append(ButtonAction(data[1 + i * 20 : 1 + (i + 1) * 20]))

    def get_payload(self):
        payload = little_endian(bitstring.pack("uint:8", self.actions_count))
        for action in self.actions:
            payload += action.get_payload()
        return payload


class ButtonAction:
    def __init__(self, data):
        self.gesture = ButtonGesture(data[0] + data[1] * 256)
        self.target_type = ButtonTargetType(data[2] + data[3] * 256)
        if self.target_type == ButtonTargetType.RELAYS:
            self.target = ButtonTargetRelays(data[4:])
        elif self.target_type == ButtonTargetType.DEVICE:
            self.target = ButtonTargetDevice(data[4:])
        elif self.target_type == ButtonTargetType.DEVICE_RELAYS:
            self.target = ButtonTargetDeviceRelays(data[4:])
        else:
            self.target = None

    def get_payload(self):
        payload = little_endian(bitstring.pack("uint:16", self.gesture.value))
        payload += little_endian(bitstring.pack("uint:16", self.target_type.value))
        if self.target_type == ButtonTargetType.RELAYS:
            payload += little_endian(bitstring.pack("uint:8", self.target.relays_count))
            for relay in self.target.relays:
                payload += little_endian(bitstring.pack("uint:8", relay))
        elif self.target_type == ButtonTargetType.DEVICE:
            payload += self.target.serial
            payload += self.target.reserved
        elif self.target_type == ButtonTargetType.DEVICE_RELAYS:
            payload += self.target.serial
            payload += little_endian(bitstring.pack("uint:8", self.target.relays_count))
            for relay in self.target.relays:
                payload += little_endian(bitstring.pack("uint:8", relay))
        return payload


class ButtonTargetRelays:
    def __init__(self, data):
        self.relays_count = data[0]
        self.relays = data[1 : 1 + self.relays_count]


class ButtonTargetDevice:
    def __init__(self, data):
        self.serial = data[0:6]
        self.reserved = data[6:16]


class ButtonTargetDeviceRelays:
    def __init__(self, data):
        self.serial = data[0:6]
        self.relays_count = data[6]
        self.relays = data[7 : 7 + self.relays_count]


class ButtonGesture(Enum):
    PRESS = 1
    HOLD = 2
    PRESS_PRESS = 3
    PRESS_HOLD = 4
    HOLD_HOLD = 5


class ButtonTargetType(Enum):
    RELAYS = 2
    DEVICE = 3
    LOCATION = 4
    GROUP = 5
    SCENE = 6
    DEVICE_RELAYS = 7


class MultiZoneEffectType(Enum):
    OFF = 0
    MOVE = 1
    RESERVED1 = 2
    RESERVED2 = 3


class MultiZoneDirection(Enum):
    RIGHT = 0
    LEFT = 1
    BACKWARD = 0
    FORWARD = 1


class TileEffectType(Enum):
    OFF = 0
    RESERVED1 = 1
    MORPH = 2
    FLAME = 3
    RESERVED2 = 4
    SKY = 5


class TileEffectSkyType(Enum):
    SUNRISE = 0
    SUNSET = 1
    CLOUDS = 2


def str_map(key):
    string_representation = "Unknown"
    if key == None:
        string_representation = "Unknown"
    elif type(key) == type(0):
        if key > 0 and key <= 65535:
            string_representation = "On"
        elif key == 0:
            string_representation = "Off"
    return string_representation
