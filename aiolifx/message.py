# message.py
# Author: Meghan Clark

import struct
import binascii
import sys

BROADCAST_MAC = "00:00:00:00:00:00"
BROADCAST_SOURCE_ID = 0

HEADER_SIZE_BYTES = 36


class Message(object):
    def __init__(
        self,
        msg_type,
        target_addr,
        source_id,
        seq_num,
        ack_requested=False,
        response_requested=False,
    ):

        # Frame
        self.frame_format = ["<H", "<H", "<L"]
        self.size = None  # 16 bits/uint16
        self.origin = 0  # 2 bits/uint8, must be zero
        self.tagged = (
            1 if target_addr == BROADCAST_MAC else 0
        )  # 1 bit/bool, also must be one if getservice
        self.addressable = 1  # 1 bit/bool, must be one
        self.protocol = 1024  # 12 bits/uint16
        self.source_id = source_id  # 32 bits/uint32, unique ID set by client. If zero, broadcast reply requested. If non-zero, unicast reply requested.

        # Frame Address
        self.frame_addr_format = ["<Q", "<BBBBBB", "<B", "<B"]
        self.target_addr = target_addr  # 64 bits/uint64, either single MAC address or all zeroes for broadcast.
        self.reserved = 0  # 48 bits/uint8 x 6, all zero
        self.reserved = 0  # 6 bits, all zero
        self.ack_requested = 1 if ack_requested else 0  # 1 bit/bool, 1 = yes
        self.response_requested = 1 if response_requested else 0  # 1 bit/bool, 1 = yes
        self.seq_num = seq_num  # 8 bits/uint8, wraparound

        # Protocol Header
        self.protocol_header_format = ["<Q", "<H", "<H"]
        self.reserved = 0  # 64 bits/uint64, all zero
        self.message_type = msg_type  # 16 bits/uint16
        self.reserved = 0  # 16 bits/uint16, all zero

        self.payload_fields = []  # tuples of ("label", value)

        self._packed_message = None

    @property
    def packed_message(self):
        if self._packed_message is None:
            self._packed_message = self.generate_packed_message()
        return self._packed_message

    @packed_message.setter
    def packed_message(self, value):
        self._packed_message = value

    def generate_packed_message(self):
        self.payload = self.get_payload()
        self.header = self.get_header()
        packed_message = self.header + self.payload
        return packed_message

    # frame (and thus header) needs to be generated after payload (for size field)
    def get_header(self):
        if self.size == None:
            self.size = self.get_msg_size()
        frame_addr = self.get_frame_addr()
        frame = self.get_frame()
        protocol_header = self.get_protocol_header()
        header = frame + frame_addr + protocol_header
        return header

    # Default: No payload unless method overridden
    def get_payload(self):
        return struct.pack("")

    def get_frame(self):
        size_format = self.frame_format[0]
        flags_format = self.frame_format[1]
        source_id_format = self.frame_format[2]
        size = struct.pack(size_format, self.size)
        flags = struct.pack(
            flags_format,
            ((self.origin & 0b11) << 14)
            | ((self.tagged & 0b1) << 13)
            | ((self.addressable & 0b1) << 12)
            | (self.protocol & 0b111111111111),
        )
        source_id = struct.pack(source_id_format, self.source_id)
        frame = size + flags + source_id
        return frame

    def get_frame_addr(self):
        mac_addr_format = self.frame_addr_format[0]
        reserved_48_format = self.frame_addr_format[1]
        response_flags_format = self.frame_addr_format[2]
        seq_num_format = self.frame_addr_format[3]
        mac_addr = struct.pack(mac_addr_format, convert_MAC_to_int(self.target_addr))
        reserved_48 = struct.pack(reserved_48_format, *([self.reserved] * 6))
        response_flags = struct.pack(
            response_flags_format,
            ((self.reserved & 0b111111) << 2)
            | ((self.ack_requested & 0b1) << 1)
            | (self.response_requested & 0b1),
        )
        seq_num = struct.pack(seq_num_format, self.seq_num)
        frame_addr = mac_addr + reserved_48 + response_flags + seq_num
        return frame_addr

    def get_protocol_header(self):
        reserved_64_format = self.protocol_header_format[0]
        message_type_format = self.protocol_header_format[1]
        reserved_16_format = self.protocol_header_format[2]
        reserved_64 = struct.pack(reserved_64_format, self.reserved)
        message_type = struct.pack(message_type_format, self.message_type)
        reserved_16 = struct.pack(reserved_16_format, self.reserved)
        protocol_header = reserved_64 + message_type + reserved_16
        return protocol_header

    def get_msg_size(self):
        payload_size_bytes = len(self.payload)
        return HEADER_SIZE_BYTES + payload_size_bytes

    def __str__(self):
        indent = "  "
        s = self.__class__.__name__ + "\n"
        s += indent + "Size: {}\n".format(self.size)
        s += indent + "Origin: {}\n".format(self.origin)
        s += indent + "Tagged: {}\n".format(self.tagged)
        s += indent + "Protocol: {}\n".format(self.protocol)
        s += indent + "Source ID: {}\n".format(self.source_id)
        s += indent + "Target MAC Address: {}\n".format(self.target_addr)
        s += indent + "Ack Requested: {}\n".format(self.ack_requested)
        s += indent + "Response Requested: {}\n".format(self.response_requested)
        s += indent + "Seq Num: {}\n".format(self.seq_num)
        s += indent + "Message Type: {}\n".format(self.message_type)
        s += indent + "Payload:"
        for field in self.payload_fields:
            s += "\n" + indent * 2 + "{}: {}".format(field[0], field[1])
        if len(self.payload_fields) == 0:
            s += "\n" + indent * 2 + "<empty>"
        s += "\n"
        s += indent + "Bytes:\n"
        s += indent * 2 + str(
            [
                hex(b)
                for b in struct.unpack(
                    "B" * (len(self.packed_message)), self.packed_message
                )
            ]
        )
        s += "\n"
        return s


# reverses bytes for little endian, then converts to int
def convert_MAC_to_int(addr):
    reverse_bytes_str = addr.split(":")
    reverse_bytes_str.reverse()
    addr_str = "".join(reverse_bytes_str)
    return int(addr_str, 16)


def little_endian(bs):
    return bytes(reversed(bs.bytes))
