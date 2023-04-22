#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This application is simply a bridge application for Lifx bulbs.
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
import asyncio as aio
import logging
from typing import Any, Coroutine, Set
from .message import BROADCAST_MAC, BROADCAST_SOURCE_ID
from .msgtypes import *
from .products import *
from .unpack import unpack_lifx_message
from functools import partial
from math import floor
import time, random, datetime, socket, ifaddr

# prevent tasks from being garbage collected
_BACKGROUND_TASKS: Set[aio.Task] = set()

if sys.version_info[:2] < (3, 11):
    from async_timeout import timeout as asyncio_timeout
else:
    from asyncio import timeout as asyncio_timeout

# A couple of constants
LISTEN_IP = "0.0.0.0"
UDP_BROADCAST_IP = "255.255.255.255"
UDP_BROADCAST_PORT = 56700
DEFAULT_TIMEOUT = 0.5  # How long to wait for an ack or response
DEFAULT_ATTEMPTS = 3  # How many time shou;d we try to send to the bulb`
DISCOVERY_INTERVAL = 180
DISCOVERY_STEP = 5
MAX_UNSIGNED_16_BIT_INTEGER_VALUE = int("0xFFFF", 16)
_LOGGER = logging.getLogger(__name__)


def _create_background_task(coro: Coroutine) -> None:
    """Create a background task that will not be garbage collected."""
    global _BACKGROUND_TASKS
    task = aio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


def mac_to_ipv6_linklocal(mac, prefix="fe80::"):
    """Translate a MAC address into an IPv6 address in the prefixed network.

    This function calculates the EUI (Extended Unique Identifier) from the given
    MAC address and prepend the needed prefix to come up with a valid IPv6 address.
    The default prefix is the link local prefix defined by RFC 4291 .

        :param mac: the mac address of the device
        :type mac: str
        :param prefix: the IPv6 network prefix
        :type prefix: str
        :returns: IPv6 address
        :rtype: str

    """

    # Remove the most common delimiters; dots, dashes, etc.
    mac_value = int(
        mac.translate(str.maketrans(dict([(x, None) for x in [" ", ".", ":", "-"]]))),
        16,
    )
    # Split out the bytes that slot into the IPv6 address
    # XOR the most significant byte with 0x02, inverting the
    # Universal / Local bit
    high2 = mac_value >> 32 & 0xFFFF ^ 0x0200
    high1 = mac_value >> 24 & 0xFF
    low1 = mac_value >> 16 & 0xFF
    low2 = mac_value & 0xFFFF
    return prefix + ":{:04x}:{:02x}ff:fe{:02x}:{:04x}".format(high2, high1, low1, low2)


def nanosec_to_hours(ns):
    """Convert nanoseconds to hours

    :param ns: Number of nanoseconds
    :type ns: into
    :returns: ns/(1000000000.0*60*60)
    :rtype: int
    """
    return ns / (1000000000.0 * 60 * 60)


class Device(aio.DatagramProtocol):
    """Connection to a given Lifx device.

    :param loop: The asyncio loop being used
    :type loop: asyncio.AbstractEventLoop
    :param: mac_addr: The device MAC address aa:bb:cc:dd:ee:ff
    :type mac_addr: string
    :param ip_addr: The devie IP address (either IPv4 or IPv6)
    :type ip_addr: string
    :param port: The port used by the unicast connection
    :type port: into
    :param parent: Parent object with register/unregister methods
    :type parent: object
    :returns: an asyncio DatagramProtocol to handle communication with the device
    :rtype: DatagramProtocol
    """

    def __init__(self, loop, mac_addr, ip_addr, port, parent=None):
        self.loop = loop
        self.mac_addr = mac_addr
        self.ip_addr = ip_addr
        self.port = port
        self.parent = parent
        self.registered = False
        self.retry_count = DEFAULT_ATTEMPTS
        self.timeout = DEFAULT_TIMEOUT
        self.unregister_timeout = DEFAULT_TIMEOUT
        self.transport = None
        self.task = None
        self.seq = 0
        # Key is the message sequence, value is (Response, Event, callb )
        self.message = {}
        self.source_id = random.randint(0, (2**32) - 1)
        # Default callback for unexpected messages
        self.default_callb = None
        # And the rest
        self.label = None
        self.location = None
        self.group = None
        self.power_level = None
        self.vendor = None
        self.product = None
        self.version = None
        self.host_firmware_version = None
        self.host_firmware_build_timestamp = None
        self.wifi_firmware_version = None
        self.wifi_firmware_build_timestamp = None
        self.lastmsg = datetime.datetime.now()

    def seq_next(self):
        """Method to return the next sequence value to use in messages.

        :returns: next number in sequensce (modulo 128)
        :rtype: int
        """
        self.seq = (self.seq + 1) % 128
        return self.seq

    #
    #                            Protocol Methods
    #

    def connection_made(self, transport):
        """Method run when the connection to the lamp is established"""
        self.transport = transport
        self.register()

    def error_received(self, exc: Exception) -> None:
        """Method run when an error is received from the device.

        This method is called in rare conditions, when the transport (e.g. UDP)
        detects that a datagram could not be delivered to its recipient.
        In many conditions though, undeliverable datagrams will be silently dropped.
        """
        _LOGGER.debug("%s: Error received: %s", self.ip_addr, exc)
        # Clear the message queue since we know they are not going to be answered
        # and there is no point in waiting for them
        for entry in self.message.values():
            response_type, myevent, callb = entry
            if response_type != Acknowledgement:
                if callb:
                    callb(self, None)
                if myevent:
                    myevent.set()
        self.message.clear()

    def datagram_received(self, data, addr):
        """Method run when data is received from the device

        This method will unpack the data according to the LIFX protocol.
        If the message represents some state information, it will update
        the device state. Following that it will execute the callback corresponding
        to the message sequence number. If there is no sequence number, the
        default callback will be called.

            :param data: raw data
            :type data: bytestring
            :param addr: sender IP address 2-tuple for IPv4, 4-tuple for IPv6
            :type addr: tuple
        """
        self.register()
        response = unpack_lifx_message(data)
        self.lastmsg = datetime.datetime.now()
        if response.seq_num in self.message:
            response_type, myevent, callb = self.message[response.seq_num]
            if type(response) == response_type:
                if response.source_id == self.source_id:
                    if "State" in response.__class__.__name__:
                        setmethod = (
                            "resp_set_"
                            + response.__class__.__name__.replace("State", "").lower()
                        )
                        if setmethod in dir(self) and callable(
                            getattr(self, setmethod)
                        ):
                            getattr(self, setmethod)(response)
                    if callb:
                        callb(self, response)
                    myevent.set()
                del self.message[response.seq_num]
            elif type(response) == Acknowledgement:
                pass
            else:
                del self.message[response.seq_num]
        elif self.default_callb:
            self.default_callb(response)

    def register(self):
        """Proxy method to register the device with the parent."""
        if not self.registered:
            self.registered = True
            if self.parent:
                self.parent.register(self)

    def unregister(self):
        """Proxy method to unregister the device with the parent."""
        if self.registered:
            # Only if we have not received any message recently.
            if (
                datetime.datetime.now()
                - datetime.timedelta(seconds=self.unregister_timeout)
                > self.lastmsg
            ):
                self.registered = False
                if self.parent:
                    self.parent.unregister(self)

    def cleanup(self):
        """Method to call to cleanly terminate the connection to the device."""
        if self.transport:
            self.transport.close()
            self.transport = None
        if self.task:
            self.task.cancel()
            self.task = None

    #
    #                            Workflow Methods
    #

    async def fire_sending(self, msg, num_repeats):
        """Coroutine used to send message to the device when no response is needed.

        :param msg: Message to send
        :type msg: aiolifx.
        :param num_repeats: number of times the message is to be sent.
        :returns: The coroutine that can be scheduled to run
        :rtype: coroutine
        """
        if num_repeats is None:
            num_repeats = self.retry_count
        sent_msg_count = 0
        sleep_interval = 0.05
        while sent_msg_count < num_repeats:
            if self.transport:
                self.transport.sendto(msg.packed_message)
            sent_msg_count += 1
            await aio.sleep(
                sleep_interval
            )  # Max num of messages device can handle is 20 per second.

    # Don't wait for Acks or Responses, just send the same message repeatedly as fast as possible
    def fire_and_forget(
        self, msg_type, payload={}, timeout_secs=None, num_repeats=None
    ):
        """Method used to send message to the device when no response/ack is needed.

        :param msg_type: The type of the message to send, a subclass of aiolifx.Message
        :type msg_type: class
        :param payload: value to use when instantiating msg_type
        :type payload: dict
        :param timeout_secs: Not used. Present here only for consistency with other methods
        :type timeout_secs: None
        :param num_repeats: Number of times the message is to be sent.
        :type num_repeats: int
        :returns: Always True
        :rtype: bool
        """
        msg = msg_type(
            self.mac_addr,
            self.source_id,
            seq_num=0,
            payload=payload,
            ack_requested=False,
            response_requested=False,
        )
        _create_background_task(self.fire_sending(msg, num_repeats))
        return True

    async def try_sending(self, msg, timeout_secs, max_attempts):
        """Coroutine used to send message to the device when a response or ack is needed.

        This coroutine will try to send up to max_attempts time the message, waiting timeout_secs
        for an answer. If no answer is received, it will consider that the device is no longer
        accessible and will unregister it.

            :param msg: The message to send
            :type msg: aiolifx.Message
            :param timeout_secs: Number of seconds to wait for a response or ack
            :type timeout_secs: int
            :param max_attempts: .
            :type max_attempts: int
            :returns: a coroutine to be scheduled
            :rtype: coroutine
        """
        if timeout_secs is None:
            timeout_secs = self.timeout
        if max_attempts is None:
            max_attempts = self.retry_count

        attempts = 0
        while attempts < max_attempts:
            if msg.seq_num not in self.message:
                return
            event = aio.Event()
            self.message[msg.seq_num][1] = event
            attempts += 1
            if self.transport:
                self.transport.sendto(msg.packed_message)
            try:
                async with asyncio_timeout(timeout_secs):
                    await event.wait()
                break
            except Exception as inst:
                if attempts >= max_attempts:
                    if msg.seq_num in self.message:
                        callb = self.message[msg.seq_num][2]
                        if callb:
                            callb(self, None)
                        del self.message[msg.seq_num]
                    # It's dead Jim
                    self.unregister()

    # Usually used for Set messages
    def req_with_ack(
        self, msg_type, payload, callb=None, timeout_secs=None, max_attempts=None
    ):
        """Method to send a message expecting to receive an ACK.

        :param msg_type: The type of the message to send, a subclass of aiolifx.Message
        :type msg_type: class
        :param payload: value to use when instantiating msg_type
        :type payload: dict
        :param callb: A callback that will be executed when the ACK is received in datagram_received
        :type callb: callable
        :param timeout_secs: Number of seconds to wait for an ack
        :type timeout_secs: int
        :param max_attempts: .
        :type max_attempts: int
        :returns: True
        :rtype: bool
        """
        msg = msg_type(
            self.mac_addr,
            self.source_id,
            seq_num=self.seq_next(),
            payload=payload,
            ack_requested=True,
            response_requested=False,
        )
        self.message[msg.seq_num] = [Acknowledgement, None, callb]
        _create_background_task(self.try_sending(msg, timeout_secs, max_attempts))
        return True

    # Usually used for Get messages, or for state confirmation after Set (hence the optional payload)
    def req_with_resp(
        self,
        msg_type,
        response_type,
        payload={},
        callb=None,
        timeout_secs=None,
        max_attempts=None,
    ):
        """Method to send a message expecting to receive a response.

        :param msg_type: The type of the message to send, a subclass of aiolifx.Message
        :type msg_type: class
        :param response_type: The type of the response to expect, a subclass of aiolifx.Message
        :type response_type: class
        :param payload: value to use when instantiating msg_type
        :type payload: dict
        :param callb: A callback that will be executed when the response is received in datagram_received
        :type callb: callable
        :param timeout_secs: Number of seconds to wait for a response
        :type timeout_secs: int
        :param max_attempts: .
        :type max_attempts: int
        :returns: True
        :rtype: bool
        """
        msg = msg_type(
            self.mac_addr,
            self.source_id,
            seq_num=self.seq_next(),
            payload=payload,
            ack_requested=False,
            response_requested=True,
        )
        self.message[msg.seq_num] = [response_type, None, callb]
        _create_background_task(self.try_sending(msg, timeout_secs, max_attempts))
        return True

    # Not currently implemented, although the LIFX LAN protocol supports this kind of workflow natively
    def req_with_ack_resp(
        self,
        msg_type,
        response_type,
        payload,
        callb=None,
        timeout_secs=None,
        max_attempts=None,
    ):
        """Method to send a message expecting to receive both a response and an ack.

        :param msg_type: The type of the message to send, a subclass of aiolifx.Message
        :type msg_type: class
        :param payload: value to use when instantiating msg_type
        :type payload: dict
        :param callb: A callback that will be executed when the response is received in datagram_received
        :type callb: callable
        :param timeout_secs: Number of seconds to wait for a response
        :type timeout_secs: int
        :param max_attempts: .
        :type max_attempts: int
        :returns: True
        :rtype: bool
        """
        msg = msg_type(
            self.mac_addr,
            self.source_id,
            seq_num=self.seq_next(),
            payload=payload,
            ack_requested=True,
            response_requested=True,
        )
        self.message[msg.seq_num] = [response_type, None, callb]
        _create_background_task(self.try_sending(msg, timeout_secs, max_attempts))
        return True

    #
    #                            Attribute Methods
    #
    def get_label(self, callb=None):
        """Convenience method to request the label from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: The cached value
            :rtype: str
        """
        if self.label is None:
            mypartial = partial(self.resp_set_label)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)
            response = self.req_with_resp(GetLabel, StateLabel, callb=mycallb)
        return self.label

    def set_label(self, value, callb=None):
        """Convenience method to set the label of the device

        This method will send a SetLabel message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The new label
            :type value: str
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: None
            :rtype: None
        """
        if len(value) > 32:
            value = value[:32]
        mypartial = partial(self.resp_set_label, label=value)
        if callb:
            self.req_with_ack(
                SetLabel, {"label": value}, lambda x, y: (mypartial(y), callb(x, y))
            )
        else:
            self.req_with_ack(SetLabel, {"label": value}, lambda x, y: mypartial(y))

    def resp_set_label(self, resp, label=None):
        """Default callback for get_label/set_label"""
        if label:
            self.label = label
        elif resp:
            self.label = resp.label.decode().replace("\x00", "")

    def get_location(self, callb=None):
        """Convenience method to request the location from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: The cached value
            :rtype: str
        """
        if self.location is None:
            mypartial = partial(self.resp_set_location)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)
            response = self.req_with_resp(GetLocation, StateLocation, callb=mycallb)
        return self.location

    # def set_location(self, value,callb=None):
    # mypartial=partial(self.resp_set_location,location=value)
    # if callb:
    # self.req_with_ack(SetLocation, {"location": value},lambda x,y:(mypartial(y),callb(x,y)) )
    # else:
    # self.req_with_ack(SetLocation, {"location": value},lambda x,y:mypartial(y) )

    def resp_set_location(self, resp, location=None):
        """Default callback for get_location/set_location"""
        if location:
            self.location = location
        elif resp:
            self.location = resp.label.decode().replace("\x00", "")
            # self.resp_set_label(resp)

    def get_group(self, callb=None):
        """Convenience method to request the group from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: The cached value
            :rtype: str
        """
        if self.group is None:
            mypartial = partial(self.resp_set_group)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)
            response = self.req_with_resp(GetGroup, StateGroup, callb=callb)
        return self.group

    # Not implemented. Why?
    # def set_group(self, value,callb=None):
    # if callb:
    # self.req_with_ack(SetGroup, {"group": value},lambda x,y:(partial(self.resp_set_group,group=value)(y),callb(x,y)) )
    # else:
    # self.req_with_ack(SetGroup, {"group": value},lambda x,y:partial(self.resp_set_group,group=value)(y) )

    def resp_set_group(self, resp, group=None):
        """Default callback for get_group/set_group"""
        if group:
            self.group = group
        elif resp:
            self.group = resp.label.decode().replace("\x00", "")

    def get_power(self, callb=None):
        """Convenience method to request the power status from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        if self.power_level is None:
            response = self.req_with_resp(GetPower, StatePower, callb=callb)
        return self.power_level

    def set_power(self, value, callb=None, rapid=False):
        """Convenience method to set the power status of the device

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The new state
            :type value: str/bool/int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """
        on = [True, 1, "on"]
        off = [False, 0, "off"]
        mypartial = partial(self.resp_set_power, power_level=value)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)
        if value in on and not rapid:
            response = self.req_with_ack(
                SetPower,
                {"power_level": MAX_UNSIGNED_16_BIT_INTEGER_VALUE},
                callb=mycallb,
            )
        elif value in off and not rapid:
            response = self.req_with_ack(SetPower, {"power_level": 0}, callb=mycallb)
        elif value in on and rapid:
            response = self.fire_and_forget(
                SetPower, {"power_level": MAX_UNSIGNED_16_BIT_INTEGER_VALUE}
            )
            self.power_level = MAX_UNSIGNED_16_BIT_INTEGER_VALUE
        elif value in off and rapid:
            response = self.fire_and_forget(SetPower, {"power_level": 0})
            self.power_level = 0

    def resp_set_power(self, resp, power_level=None):
        """Default callback for get_power/set_power"""
        if power_level is not None:
            self.power_level = power_level
        elif resp:
            self.power_level = resp.power_level

    def get_wififirmware(self, callb=None):
        """Convenience method to request the wifi firmware info from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: The cached value (version, timestamp)
            :rtype: 2-tuple
        """
        if self.wifi_firmware_version is None:
            mypartial = partial(self.resp_set_wififirmware)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)
            response = self.req_with_resp(
                GetWifiFirmware, StateWifiFirmware, callb=mycallb
            )
        return (self.wifi_firmware_version, self.wifi_firmware_build_timestamp)

    def resp_set_wififirmware(self, resp):
        """Default callback for get_wififirmware"""
        if resp:
            self.wifi_firmware_version = float(
                str(str(resp.version >> 16) + "." + str(resp.version & 0xFF))
            )
            self.wifi_firmware_build_timestamp = resp.build

    # Too volatile to be saved
    def get_wifiinfo(self, callb=None):
        """Convenience method to request the wifi info from the device

        This will request the information from the device and request that callb be executed
        when a response is received. The is no  default callback

            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: None
            :rtype: None
        """
        response = self.req_with_resp(GetWifiInfo, StateWifiInfo, callb=callb)
        return None

    def get_hostfirmware(self, callb=None):
        """Convenience method to request the device firmware info from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: The cached value
        :rtype: str
        """
        if self.host_firmware_version is None:
            mypartial = partial(self.resp_set_hostfirmware)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)
            response = self.req_with_resp(
                GetHostFirmware, StateHostFirmware, callb=mycallb
            )

        return (self.host_firmware_version, self.host_firmware_build_timestamp)

    def resp_set_hostfirmware(self, resp):
        """Default callback for get_hostfirmware"""
        if resp:
            self.host_firmware_version = (
                str(resp.version >> 16) + "." + str(resp.version & 0xFFFF)
            )
            self.host_firmware_build_timestamp = resp.build

    # Too volatile to be saved
    def get_hostinfo(self, callb=None):
        """Convenience method to request the device info from the device

        This will request the information from the device and request that callb be executed
        when a response is received. The is no  default callback

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        response = self.req_with_resp(GetInfo, StateInfo, callb=callb)
        return None

    def set_reboot(self):
        """Convenience method to reboot the device

        This will send a magic reboot packet to the device which has the same effect
        as physically turning the device off and on again. Its uptime value will be
        reset and it will be rediscovered.

        There are no parameters or callbacks as the device immediately restarts with
        any response so it just returns True to indicate the packet was sent.
        """
        return self.fire_and_forget(SetReboot)

    def get_version(self, callb=None):
        """Convenience method to request the version from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: The cached value
            :rtype: str
        """
        if self.vendor is None:
            mypartial = partial(self.resp_set_version)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)
            response = self.req_with_resp(GetVersion, StateVersion, callb=mycallb)
        return (self.host_firmware_version, self.host_firmware_build_timestamp)

    def resp_set_version(self, resp):
        """Default callback for get_version"""
        if resp:
            self.vendor = resp.vendor
            self.product = resp.product
            self.version = resp.version

    #
    #                            Formating
    #
    def device_characteristics_str(self, indent):
        """Convenience to string method."""
        s = "{}\n".format(self.label)
        s += indent + "MAC Address: {}\n".format(self.mac_addr)
        s += indent + "IP Address: {}\n".format(self.ip_addr)
        s += indent + "Port: {}\n".format(self.port)
        s += indent + "Power: {}\n".format(str_map(self.power_level))
        s += indent + "Location: {}\n".format(self.location)
        s += indent + "Group: {}\n".format(self.group)
        return s

    def device_firmware_str(self, indent):
        """Convenience to string method."""
        host_build_ns = self.host_firmware_build_timestamp
        host_build_s = (
            datetime.datetime.utcfromtimestamp(host_build_ns / 1000000000)
            if host_build_ns != None
            else None
        )
        wifi_build_ns = self.wifi_firmware_build_timestamp
        wifi_build_s = (
            datetime.datetime.utcfromtimestamp(wifi_build_ns / 1000000000)
            if wifi_build_ns != None
            else None
        )
        s = "Host Firmware Build Timestamp: {} ({} UTC)\n".format(
            host_build_ns, host_build_s
        )
        s += indent + "Host Firmware Build Version: {}\n".format(
            self.host_firmware_version
        )
        s += indent + "Wifi Firmware Build Timestamp: {} ({} UTC)\n".format(
            wifi_build_ns, wifi_build_s
        )
        s += indent + "Wifi Firmware Build Version: {}\n".format(
            self.wifi_firmware_version
        )
        return s

    def device_product_str(self, indent):
        """Convenience to string method."""
        s = "Vendor: {}\n".format(self.vendor)
        s += indent + "Product: {}\n".format(
            (self.product and products_dict[self.product]) or "Unknown"
        )
        s += indent + "Version: {}\n".format(self.version)
        return s

    def device_time_str(self, resp, indent="  "):
        """Convenience to string method."""
        time = resp.time
        uptime = resp.uptime
        downtime = resp.downtime
        time_s = (
            datetime.datetime.utcfromtimestamp(time / 1000000000)
            if time != None
            else None
        )
        uptime_s = round(nanosec_to_hours(uptime), 2) if uptime != None else None
        downtime_s = round(nanosec_to_hours(downtime), 2) if downtime != None else None
        s = "Current Time: {} ({} UTC)\n".format(time, time_s)
        s += indent + "Uptime (ns): {} ({} hours)\n".format(uptime, uptime_s)
        s += indent + "Last Downtime Duration +/-5s (ns): {} ({} hours)\n".format(
            downtime, downtime_s
        )
        return s

    def device_radio_str(self, resp, indent="  "):
        """Convenience to string method."""
        signal = resp.signal
        tx = resp.tx
        rx = resp.rx
        s = "Wifi Signal Strength (mW): {}\n".format(signal)
        s += indent + "Wifi TX (bytes): {}\n".format(tx)
        s += indent + "Wifi RX (bytes): {}\n".format(rx)
        return s

    def register_callback(self, callb):
        """Method used to register a default call back to be called when data is received

        :param callb: The calllback to be executed.
        :type callb: callable

        """
        self.default_callb = callb


class Light(Device):
    """Connection to a given Lifx light device.

    :param loop: The asyncio loop being used
    :type loop: asyncio.AbstractEventLoop
    :param: mac_addr: The device MAC address aa:bb:cc:dd:ee:ff
    :type mac_addr: string
    :param ip_addr: The devie IP address (either IPv4 or IPv6)
    :type ip_addr: string
    :param port: The port used by the unicast connection
    :type port: into
    :param parent: Parent object with register/unregister methods
    :type parent: object
    :returns: an asyncio DatagramProtocol to handle communication with the device
    :rtype: DatagramProtocol
    """

    def __init__(self, loop, mac_addr, ip_addr, port=UDP_BROADCAST_PORT, parent=None):
        mac_addr = mac_addr.lower()
        super(Light, self).__init__(loop, mac_addr, ip_addr, port, parent)
        self.color = None
        self.color_zones = None
        self.zones_count = 1
        self.infrared_brightness = None
        self.hev_cycle = None
        self.hev_cycle_configuration = None
        self.last_hev_cycle_result = None
        self.effect = {"effect": None}
        # Only used by a Lifx Switch. Will be populated with either True or False for each relay index if `get_rpower` called.
        # At the moment we assume the switch to be 4 relays. This will likely work with the 2 relays switch as well, but only the first two values
        # in this array will contain useful data.
        self.relays_power = [None, None, None, None]
        # Only used by a Lifx switch. Will be populated with an object containing the `haptic_duration_ms`, `backlight_on_color` and `backlight_off_color`
        self.button_config = None
        # Only used by a Lifx switch. Will be populated with an object containing `count`, `index`, `buttons_count` and `buttons`
        self.button = None

    def get_power(self, callb=None):
        """Convenience method to request the power status from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        if self.power_level is None:
            response = self.req_with_resp(LightGetPower, LightStatePower, callb=callb)
        return self.power_level

    def set_power(self, value, callb=None, duration=0, rapid=False):
        """Convenience method to set the power status of the device

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The new state
            :type value: str/bool/int
            :param duration: The duration, in seconds, of the power state transition.
            :type duration: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """
        on = [True, 1, "on"]
        off = [False, 0, "off"]
        if value in on:
            myvalue = MAX_UNSIGNED_16_BIT_INTEGER_VALUE
        else:
            myvalue = 0
        mypartial = partial(self.resp_set_lightpower, power_level=myvalue)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)
        if not rapid:
            response = self.req_with_ack(
                LightSetPower,
                {"power_level": myvalue, "duration": duration},
                callb=mycallb,
            )
        else:
            response = self.fire_and_forget(
                LightSetPower,
                {"power_level": myvalue, "duration": duration},
                num_repeats=1,
            )
            self.power_level = myvalue
            if callb:
                callb(self, None)

    # Here lightpower because LightStatePower message will give lightpower
    def resp_set_lightpower(self, resp, power_level=None):
        """Default callback for set_power"""
        if power_level is not None:
            self.power_level = power_level
        elif resp:
            self.power_level = resp.power_level

    # LightGet, color, power_level, label
    def get_color(self, callb=None):
        """Convenience method to request the colour status from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        response = self.req_with_resp(LightGet, LightState, callb=callb)
        return self.color

    # color is [Hue, Saturation, Brightness, Kelvin], duration in ms
    def set_color(self, value, callb=None, duration=0, rapid=False):
        """Convenience method to set the colour status of the device

        This method will send a LightSetColor message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The new state, a dictionary onf int with 4 keys Hue, Saturation, Brightness, Kelvin
            :type value: dict
            :param duration: The duration, in seconds, of the power state transition.
            :type duration: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """
        if len(value) == 4:
            mypartial = partial(self.resp_set_light, color=value)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)
            # try:
            if rapid:
                self.fire_and_forget(
                    LightSetColor, {"color": value, "duration": duration}, num_repeats=1
                )
                self.resp_set_light(None, color=value)
                if callb:
                    callb(self, None)
            else:
                self.req_with_ack(
                    LightSetColor, {"color": value, "duration": duration}, callb=mycallb
                )
            # except WorkflowException as e:
            # print(e)

    # Here light because LightState message will give light
    def resp_set_light(self, resp, color=None):
        """Default callback for set_color"""
        if color:
            self.color = color
        elif resp:
            self.power_level = resp.power_level
            self.color = resp.color
            self.label = resp.label.decode().replace("\x00", "")

    # Multizone
    def get_color_zones(self, start_index, end_index=None, callb=None):
        """Convenience method to request the state of colour by zones from the device

        This method will request the information from the device and request that callb
        be executed when a response is received.

            :param start_index: Index of the start of the zone of interest
            :type start_index: int
            :param end_index: Index of the end of the zone of interest. By default start_index+7
            :type end_index: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: None
            :rtype: None
        """
        if end_index is None:
            end_index = start_index + 7
        args = {
            "start_index": start_index,
            "end_index": end_index,
        }
        self.req_with_resp(
            MultiZoneGetColorZones, MultiZoneStateMultiZone, payload=args, callb=callb
        )

    def set_color_zones(
        self,
        start_index,
        end_index,
        color,
        duration=0,
        apply=1,
        callb=None,
        rapid=False,
    ):
        """Convenience method to set the colour status zone of the device

        This method will send a MultiZoneSetColorZones message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param start_index: Index of the start of the zone of interest
            :type start_index: int
            :param end_index: Index of the end of the zone of interest. By default start_index+7
            :type end_index: int
            :param apply: Indicates if the colour change is to be applied or memorized. Default: 1
            :type apply: int
            :param value: The new state, a dictionary onf int with 4 keys Hue, Saturation, Brightness, Kelvin
            :type value: dict
            :param duration: The duration, in seconds, of the power state transition.
            :type duration: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """
        if len(color) == 4:
            args = {
                "start_index": start_index,
                "end_index": end_index,
                "color": color,
                "duration": duration,
                "apply": apply,
            }

            mypartial = partial(self.resp_set_multizonemultizone, args=args)
            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)

            if rapid:
                self.fire_and_forget(MultiZoneSetColorZones, args, num_repeats=1)
                mycallb(self, None)
            else:
                self.req_with_ack(MultiZoneSetColorZones, args, callb=mycallb)

    # A multi-zone MultiZoneGetColorZones returns MultiZoneStateMultiZone -> multizonemultizone
    def resp_set_multizonemultizone(self, resp, args=None):
        """Default callback for get-color_zones/set_color_zones"""
        if args:
            if self.color_zones:
                for i in range(args["start_index"], args["end_index"] + 1):
                    self.color_zones[i] = args["color"]
        elif resp:
            if self.color_zones is None:
                self.color_zones = [None] * resp.count
            try:
                for i in range(resp.index, min(resp.index + 8, resp.count)):
                    if i > len(self.color_zones) - 1:
                        self.color_zones += [resp.color[i - resp.index]] * (
                            i - len(self.color_zones)
                        )
                        self.color_zones.append(resp.color[i - resp.index])
                    else:
                        self.color_zones[i] = resp.color[i - resp.index]
            except:
                # I guess this should not happen but...
                pass

    def get_multizone_effect(self, callb=None):
        """Convenience method to get the currently running firmware effect on the device.

        The value returned is the previously known state of the device. Use a callback
        to get the current state of the device.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_multizonemultizoneeffect will be used.
        :type callb: callable
        :returns: current effect details as a dictionary
        :rtype: dict
        """
        response = self.req_with_resp(
            MultiZoneGetMultiZoneEffect, MultiZoneStateMultiZoneEffect, callb=callb
        )
        return self.effect

    def set_multizone_effect(
        self, effect=0, speed=3, direction=0, callb=None, rapid=False
    ):
        """Convenience method to start or stop the Move firmware effect on multizone devices.

        Compatible devices include LIFX Z, Lightstrip and Beam and can be identified by
        checking if products_dict[device.product].multizone is True. Multizone devices
        only have one firmware effect named "MOVE". The effect can be started and stopped
        without the device being powered on. The effect will not be visible if the
        device is a single uniform color.

        Sending a set_power(0) to the device while the effect is running does not stop the effect.
        Physically powering off the device will stop the effect. And the device.


        :param effect: 0/Off, 1/Move
        :type effect: int
        :param speed: time in seconds for one cycle of the effect to travel the length of the device
        :type speed: float
        :param direction: 0/Right, 1/Left
        :type direction: int
        """

        typ = effect
        if type(effect) == str:
            typ = MultiZoneEffectType[effect.upper()].value
        elif type(effect) == int:
            typ = effect if effect in [e.value for e in MultiZoneEffectType] else 0

        speed = floor(speed * 1000) if 0 < speed <= 60 else 3000

        if type(direction) == str:
            direction = MultiZoneDirection[direction.upper()].value
        elif type(direction) == int:
            direction = (
                direction if direction in [d.value for d in MultiZoneDirection] else 0
            )

        payload = {
            "type": typ,
            "speed": speed,
            "duration": 0,
            "direction": direction,
        }

        if rapid:
            self.fire_and_forget(MultiZoneSetMultiZoneEffect, payload)
        else:
            self.req_with_ack(MultiZoneSetMultiZoneEffect, payload, callb=callb)

    def resp_set_multizonemultizoneeffect(self, resp):
        """Default callback for get_multizone_effect"""

        if resp:
            self.effect = {"effect": MultiZoneEffectType(resp.effect).name.upper()}

            if resp.effect != 0:
                self.effect["speed"] = resp.speed / 1000
                self.effect["duration"] = (
                    0.0
                    if resp.duration == 0
                    else float(f"{self.effect['duration'] / 1000000000:4f}")
                )
                self.effect["direction"] = MultiZoneDirection(
                    resp.direction
                ).name.capitalize()

    def get_extended_color_zones(self, callb=None):
        """
        Convenience method to request the state of all zones of a multizone device
        in a single request.

        The device must have the extended_multizone feature to use this method.

        This method will request the information from the device and request that callb
        be executed when a response is received.

        :param callb: Callable to be used when the response is received. If not set,
                    self.resp_set_multizonemultizoneextendedcolorzones will be used.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        self.req_with_resp(
            MultiZoneGetExtendedColorZones,
            MultiZoneStateExtendedColorZones,
            callb=callb,
        )

    def set_extended_color_zones(
        self,
        colors,
        colors_count,
        zone_index=0,
        duration=0,
        apply=1,
        callb=None,
        rapid=False,
    ):
        """
        Convenience method to set the state of all zones on a multizone device in
        a single request.

        The device must have the extended_multizone feature to use this method.
        There must be 82 color tuples in the colors list regardless of how many
        zones the device has. Use the colors_count parameter to specify the number
        of colors from the colors list that should be applied to the device and
        use the zone_index parameter to specify the starting zone.

        :param colors List of color dictionaries with HSBK keys
        :type colors List[dict[str, int]]
        :param colors_count How many color values in the color list to apply to the device
        :type colors_count int
        :param zone_index Which zone to start applying the colors from (default 0)
        :type zone_index int
        :param duration duration in seconds to apply the colors (default 0)
        :type duration int
        :param apply whether to apply the colors or buffer the new value (default 1 or apply)
        :type apply int
        :param callb Callback function to invoke when the response is received
        :type callb Callable
        :returns None
        :rtype None
        """
        if len(colors) == 82:
            args = {
                "duration": duration,
                "apply": apply,
                "zone_index": zone_index,
                "colors_count": colors_count,
                "colors": colors,
            }
            mypartial = partial(self.resp_set_multizoneextendedcolorzones, args=args)

            if callb:
                mycallb = lambda x, y: (mypartial(y), callb(x, y))
            else:
                mycallb = lambda x, y: mypartial(y)

            if rapid:
                self.fire_and_forget(
                    MultiZoneSetExtendedColorZones, args, num_repeats=1
                )
                mycallb(self, None)
            else:
                self.req_with_ack(MultiZoneSetExtendedColorZones, args, callb=mycallb)

    def resp_set_multizoneextendedcolorzones(self, resp, args=None):
        """Default callback for get_extended_color_zones"""
        if args:
            if self.color_zones:
                for i in range(args["zone_index"], args["colors_count"]):
                    self.color_zones[i] = args["colors"][i]

        elif resp:
            self.zones_count = resp.zones_count
            self.color_zones = resp.colors[resp.zone_index : resp.colors_count]

    # value should be a dictionary with the the following keys: transient, color, period, cycles, skew_ratio, waveform
    def set_waveform(self, value, callb=None, rapid=False):
        """Convenience method to animate the light, a dictionary with the the following
        keys: transient, color, period, cycles, skew_ratio, waveform

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The animation parameter.
            :type value:
            :param duration: The duration, in seconds, of the power state transition.
            :type duration: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """
        if "color" in value and len(value["color"]) == 4:
            if rapid:
                self.fire_and_forget(LightSetWaveform, value, num_repeats=1)
            else:
                self.req_with_ack(LightSetWaveform, value, callb=callb)

    # value should be a dictionary with the the following keys:
    # transient, color, period, cycles, skew_ratio, waveform, set_hue, set_saturation, set_brightness, set_kelvin
    def set_waveform_optional(self, value, callb=None, rapid=False):
        """Convenience method to animate the light, a dictionary with the the following
        keys: transient, color, period, cycles, skew_ratio, waveform, set_hue, set_saturation, set_brightness, set_kelvin

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param value: The animation parameter.
            :type value:
            :param duration: The duration, in seconds, of the power state transition.
            :type duration: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """
        if "color" in value and len(value["color"]) == 4:
            if rapid:
                self.fire_and_forget(LightSetWaveformOptional, value, num_repeats=1)
            else:
                self.req_with_ack(LightSetWaveformOptional, value, callb=callb)

    # Infrared get maximum brightness, infrared_brightness
    def get_infrared(self, callb=None):
        """Convenience method to request the infrared brightness from the device

        This method will check whether the value has already been retrieved from the device,
        if so, it will simply return it. If no, it will request the information from the device
        and request that callb be executed when a response is received. The default callback
        will simply cache the value.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        response = self.req_with_resp(LightGetInfrared, LightStateInfrared, callb=callb)
        return self.infrared_brightness

    # Infrared set maximum brightness, infrared_brightness
    def set_infrared(self, infrared_brightness, callb=None, rapid=False):
        """Convenience method to set the infrared status of the device

        This method will send a SetPower message to the device, and request callb be executed
        when an ACK is received. The default callback will simply cache the value.

            :param infrared_brightness: The new state
            :type infrared_brightness: int
            :param duration: The duration, in seconds, of the power state transition.
            :type duration: int
            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """
        mypartial = partial(
            self.resp_set_lightinfrared, infrared_brightness=infrared_brightness
        )
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)
        if rapid:
            self.fire_and_forget(
                LightSetInfrared,
                {"infrared_brightness": infrared_brightness},
                num_repeats=1,
            )
            self.resp_set_lightinfrared(None, infrared_brightness=infrared_brightness)
            if callb:
                callb(self, None)
        else:
            self.req_with_ack(
                LightSetInfrared,
                {"infrared_brightness": infrared_brightness},
                callb=mycallb,
            )

    # Here lightinfrared because LightStateInfrared message will give lightinfrared
    def resp_set_lightinfrared(self, resp, infrared_brightness=None):
        """Default callback for set_infrared/get_infrared"""
        if infrared_brightness is not None:
            self.infrared_brightness = infrared_brightness
        elif resp:
            self.infrared_brightness = resp.infrared_brightness

    def get_hev_cycle(self, callb=None):
        """Request the state of any running HEV cycle of the device.

        This method only works with LIFX Clean bulbs.

        This method will do nothing unless a call back is passed to it.

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        if products_dict[self.product].hev is True:
            self.req_with_resp(GetHevCycle, StateHevCycle, callb=callb)

    def resp_set_hevcycle(self, resp):
        """Default callback for get_hev_cycle/set_hev_cycle"""
        if resp:
            self.hev_cycle = {
                "duration": resp.duration,
                "remaining": resp.remaining,
                "last_power": resp.last_power,
            }

    def set_hev_cycle(self, enable=True, duration=0, callb=None, rapid=False):
        """Immediately starts a HEV cycle on the device.

        This method only works with LIFX Clean bulbs.

        This method will send a SetHevCycle message to the device, and request
        callb be executed when an ACK is received.

        :param enable: If True, start the HEV cycle, otherwise abort.
        :type enable: bool
        :param duration: The duration, in seconds, of the HEV cycle. If 0,
                         use the default configuration on the bulb.
        :type duration: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :param rapid: Whether to ask for ack (False) or not (True). Default False
        :type rapid: bool
        :returns: None
        :rtype: None
        """
        if products_dict[self.product].hev is True:
            if rapid:
                self.fire_and_forget(
                    SetHevCycle,
                    {"enable": int(enable), "duration": duration},
                    num_repeats=1,
                )
                if callb:
                    callb(self, None)
            else:
                self.req_with_resp(
                    SetHevCycle,
                    StateHevCycle,
                    {"enable": int(enable), "duration": duration},
                    callb=callb,
                )

    def get_hev_configuration(self, callb=None):
        """Requests the default HEV configuration of the device.

        This method only works with LIFX Clean bulbs.

        This method will do nothing unless a call back is passed to it.

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        if products_dict[self.product].hev is True:
            self.req_with_resp(
                GetHevCycleConfiguration, StateHevCycleConfiguration, callb=callb
            )

    def resp_set_hevcycleconfiguration(self, resp):
        """Default callback for get_hev_cycle_configuration/set_hev_cycle_configuration"""
        if resp:
            self.hev_cycle_configuration = {
                "duration": resp.duration,
                "indication": resp.indication,
            }

    def set_hev_configuration(self, indication, duration, callb=None, rapid=False):
        """Sets the default HEV configuration of the device.

        This method only works with LIFX Clean bulbs.

        This method will send a SetHevCycleConfiguration message to the device,
        and request callb be executed when an ACK is received.

        :param indication: If True, show a short flashing indication when the
                           HEV cycle finishes.
        :type indication: bool
        :param duration: The duration, in seconds, of the HEV cycle.
        :type duration: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :param rapid: Whether to ask for ack (False) or not (True). Default False
        :type rapid: bool
        :returns: None
        :rtype: None
        """
        if products_dict[self.product].hev is True:
            if rapid:
                self.fire_and_forget(
                    SetHevCycleConfiguration,
                    {"indication": int(indication), "duration": duration},
                    num_repeats=1,
                )
                if callb:
                    callb(self, None)
            else:
                self.req_with_resp(
                    SetHevCycleConfiguration,
                    StateHevCycleConfiguration,
                    {"indication": int(indication), "duration": duration},
                    callb=callb,
                )

    # Get last HEV cycle result
    def get_last_hev_cycle_result(self, callb=None):
        """Requests the result of the last HEV cycle of the device.

        This method only works with LIFX Clean bulbs.

        This method will do nothing unless a call back is passed to it.

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        if products_dict[self.product].hev is True:
            self.req_with_resp(
                GetLastHevCycleResult, StateLastHevCycleResult, callb=callb
            )

    def resp_set_lasthevcycleresult(self, resp):
        if resp:
            self.last_hev_cycle_result = LAST_HEV_CYCLE_RESULT.get(resp.result)

    def get_tile_effect(self, callb=None):
        """Convenience method to get the currently running effect on a Tile or Candle.

        The value returned is the previously known state of the effect. Use a callback
        to get the actual current state.

        :param callb: callable to be used when a response is received. If not set,
                      self.resp_set_tileeffect will be used.
        :type callb: callable
        :returns: current effect details as a dictionary
        :rtype: dict
        """
        response = self.req_with_resp(
            TileGetTileEffect, TileStateTileEffect, callb=callb
        )
        return self.effect

    def set_tile_effect(self, effect=0, speed=3, palette=None, callb=None, rapid=False):
        """Convenience method to start or stop a firmware effect on matrix devices.

        A palette of up to 16 HSBK tuples can be provided for the MORPH effect, otherwise
        it will use the same Exciting theme used by the LIFX smart phone app.

        :param effect: 0/Off, 2/Morph, 3/Flame
        :type effect: int/str
        :param speed: time in seconds for one cycle of the effect to travel the length of the device
        :type speed: int
        :param palette: a list of up to 16 HSBK tuples to use for the Morph effect
        :type palette: list[tuple(hue, saturation, brightness, kelvin)]
        :param callb: a callback to use when the response is received
        :type callb: callable
        :param rapid: whether to request an acknowledgement or not
        :type rapid: bool
        :returns: None
        :rtype: None
        """

        # Exciting theme
        default_tile_palette = [
            (0, 65535, 65535, 3500),
            (7282, 65535, 65535, 3500),
            (10923, 65535, 65535, 3500),
            (22209, 65535, 65535, 3500),
            (43509, 65535, 65535, 3500),
            (49334, 65535, 65535, 3500),
            (53521, 65535, 65535, 3500),
        ]

        typ = effect
        if type(effect) == str:
            typ = TileEffectType[effect.upper()].value
        elif type(effect) == int:
            typ = effect if effect in [e.value for e in TileEffectType] else 0

        speed = floor(speed * 1000) if 0 < speed <= 60 else 3000
        if palette is None:
            palette = default_tile_palette
        if len(palette) > 16:
            palette = palette[:16]
        palette_count = len(palette)

        payload = {
            "type": typ,
            "speed": speed,
            "duration": 0,
            "palette_count": palette_count,
            "palette": palette,
        }
        if rapid:
            self.fire_and_forget(TileSetTileEffect, payload)
        else:
            self.req_with_ack(TileSetTileEffect, payload, callb=callb)

    def resp_set_tiletileeffect(self, resp):
        """Default callback for get_tile_effect and set_tile_effect"""
        if resp:
            self.effect = {"effect": TileEffectType(resp.effect).name.upper()}

            if resp.effect != 0:
                self.effect["speed"] = resp.speed / 1000
                self.effect["duration"] = (
                    0.0
                    if resp.duration == 0
                    else float(f"{self.effect['duration']/1000000000:4f}")
                )
                self.effect["palette_count"] = resp.palette_count
                self.effect["palette"] = resp.palette

    def get_rpower(self, relay_index=None, callb=None):
        """Method will get the power state of all relays; or a single relay if value provided.

        :param relay_index: The index of the relay to check power state for. If not provided, will loop through 4 relays
        :type relay_index: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        mypartial = partial(self.resp_set_rpower)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        if relay_index is not None:
            payload = {"relay_index": relay_index}
            response = self.req_with_resp(
                GetRPower, StateRPower, payload, callb=mycallb
            )
        else:
            for relay_index in range(4):
                payload = {"relay_index": relay_index}
                response = self.req_with_resp(
                    GetRPower, StateRPower, payload, callb=mycallb
                )
        return self.relays_power

    def set_rpower(self, relay_index, is_on, callb=None, rapid=False):
        """Sets relay power for a given relay index

        :param relay_index: The relay on the switch starting from 0.
        :type relay_index: int
        :param on: Whether the relay is on or not
        :type is_on: bool
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :param rapid: Whether to ask for ack (False) or not (True). Default False
        :type rapid: bool
        :returns: None
        :rtype: None
        """
        level = 0
        if is_on:
            level = MAX_UNSIGNED_16_BIT_INTEGER_VALUE

        payload = {"relay_index": relay_index, "level": level}
        mypartial = partial(self.resp_set_rpower, relay_index=relay_index, level=level)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        if not rapid:
            self.req_with_resp(SetRPower, StateRPower, payload, callb=mycallb)
        else:
            self.fire_and_forget(SetRPower, payload)

    def resp_set_rpower(self, resp, relay_index=None, level=None):
        """Default callback for get_rpower/set_rpower"""
        if relay_index != None and level != None:
            self.relays_power[relay_index] = level == MAX_UNSIGNED_16_BIT_INTEGER_VALUE
        elif resp:
            # Current models of the LIFX switch do not have dimming capability, so the two valid values are 0 for off (False) and 65535 for on (True).
            self.relays_power[resp.relay_index] = (
                resp.level == MAX_UNSIGNED_16_BIT_INTEGER_VALUE
            )

    def get_button(self, callb=None):
        """Method will get the state of all buttons

        :param relay_index: The index of the relay to check power state for. If not provided, will loop through 4 relays
        :type relay_index: int
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        mypartial = partial(self.resp_get_button)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        payload = {}
        response = self.req_with_resp(GetButton, StateButton, payload, callb=mycallb)

    def set_button(self, callb=None, rapid=False):
        raise Exception(
            "SetButton isn't yet implemented as you can only set button actions to the same values as the LIFX app (ie you can't add custom callbacks), making it not that useful. Feel free to implement if you need this :)"
        )
        """ Sets button

            :param callb: Callable to be used when the response is received.
            :type callb: callable
            :param rapid: Whether to ask for ack (False) or not (True). Default False
            :type rapid: bool
            :returns: None
            :rtype: None
        """

        payload = {}
        mypartial = partial(self.resp_get_button)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        if not rapid:
            self.req_with_resp(SetButton, StateButton, payload, callb=mycallb)
        else:
            self.fire_and_forget(SetButton, payload)

    def resp_get_button(self, resp):
        """Default callback for get_button/set_button"""
        self.button = {
            "count": resp.count,
            "index": resp.index,
            "buttons_count": resp.buttons_count,
            "buttons": resp.buttons,
        }

    def get_button_config(self, callb=None):
        """Method will get the button config

        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :returns: The cached value
        :rtype: int
        """
        mypartial = partial(self.resp_get_button_config)
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        response = self.req_with_resp(
            GetButtonConfig, StateButtonConfig, {}, callb=mycallb
        )

    def set_button_config(
        self,
        haptic_duration_ms: int,
        backlight_on_color,
        backlight_off_color,
        callb=None,
        rapid=False,
    ):
        """Sets button config

        :param haptic_duration_ms: How many milliseconds the haptic vibration when the button is pressed should last
        :type haptic_duration_ms: int
        :param backlight_on_color: The color the backlight should be when a button is on
        :type backlight_on_color: { "hue": int, "saturation": int, "brightness": int, "kelvin": int }
        :param backlight_off_color: The color the backlight should be when a button is off
        :type backlight_off_color: { "hue": int, "saturation": int, "brightness": int, "kelvin": int }
        :param callb: Callable to be used when the response is received.
        :type callb: callable
        :param rapid: Whether to ask for ack (False) or not (True). Default False
        :type rapid: bool
        :returns: None
        :rtype: None
        """

        payload = {
            "haptic_duration_ms": haptic_duration_ms,
            "backlight_on_color": backlight_on_color,
            "backlight_off_color": backlight_off_color,
        }
        mypartial = partial(
            self.resp_get_button_config,
            haptic_duration_ms=haptic_duration_ms,
            backlight_on_color=backlight_on_color,
            backlight_off_color=backlight_off_color,
        )
        if callb:
            mycallb = lambda x, y: (mypartial(y), callb(x, y))
        else:
            mycallb = lambda x, y: mypartial(y)

        if not rapid:
            self.req_with_resp(
                SetButtonConfig, StateButtonConfig, payload, callb=mycallb
            )
        else:
            self.fire_and_forget(SetButtonConfig, payload)

    def resp_get_button_config(
        self,
        resp,
        haptic_duration_ms=None,
        backlight_on_color=None,
        backlight_off_color=None,
    ):
        """Default callback for get_button_config/set_button_config"""
        if (
            haptic_duration_ms != None
            and backlight_on_color != None
            and backlight_off_color != None
        ):
            self.button_config = {
                "haptic_duration_ms": haptic_duration_ms,
                "backlight_on_color": backlight_on_color,
                "backlight_off_color": backlight_off_color,
            }
        elif resp:
            self.button_config = {
                "haptic_duration_ms": resp.haptic_duration_ms,
                "backlight_on_color": resp.backlight_on_color,
                "backlight_off_color": resp.backlight_off_color,
            }

    def get_accesspoint(self, callb=None):
        """Convenience method to request the access point available

        This method will do nothing unless a call back is passed to it.

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        response = self.req_with_resp(GetAccessPoint, StateAccessPoint, callb=callb)
        return None

    def __str__(self):
        indent = "  "
        s = self.device_characteristics_str(indent)
        s += indent + "Color (HSBK): {}\n".format(self.color)
        s += indent + self.device_firmware_str(indent)
        s += indent + self.device_product_str(indent)
        # s += indent + self.device_time_str(indent)
        # s += indent + self.device_radio_str(indent)
        return s


class LifxDiscovery(aio.DatagramProtocol):
    """UDP broadcast discovery for  Lifx device.

    The discovery object will bradcast a discovery message every discovery_interval second. Sometimes it
    may be necessary to speed up this process. So discovery uses self.discovery_countdown, initially
    set to discovery_interval. It will then sleep for discovery_step seconds and decrease discovery_countdown
    by that amount. When discovery_countdown is <= 0, discovery is triggered. To hasten the process, one can set
    discovery_countdown = 0.

        :param parent: Parent object to register/unregister discovered device
        :type parent: object
        :param loop: The asyncio loop being used
        :type loop: asyncio.AbstractEventLoop
        :param: ipv6prefix: ipv6 network prefix to use
        :type mipv6prefix: string
        :param discovery_interval: How often, in seconds, to broadcast a discovery messages
        :type discovery_interval: int
        :param discovery_step: How often, in seconds, will the discovery process check if it is time to broadcast
        :type discovery_step: int
        :returns: an asyncio DatagramProtocol to handle communication with the device
        :rtype: DatagramProtocol
    """

    def __init__(
        self,
        loop,
        parent=None,
        ipv6prefix=None,
        discovery_interval=DISCOVERY_INTERVAL,
        discovery_step=DISCOVERY_STEP,
        broadcast_ip=UDP_BROADCAST_IP,
    ):
        self.lights = {}  # Known devices indexed by mac addresses
        self.parent = parent  # Where to register new devices
        self.transport = None
        self.loop = loop
        self.task = None
        self.source_id = random.randint(0, (2**32) - 1)
        self.ipv6prefix = ipv6prefix
        self.discovery_interval = discovery_interval
        self.discovery_step = discovery_step
        self.discovery_countdown = 0
        self.broadcast_ip = broadcast_ip

    def start(self, listen_ip=LISTEN_IP, listen_port=0):
        """Start discovery task."""
        coro = self.loop.create_datagram_endpoint(
            lambda: self, local_addr=(listen_ip, listen_port)
        )

        self.task = aio.create_task(coro)
        return self.task

    def connection_made(self, transport):
        """Method run when the UDP broadcast server is started"""
        # print('started')
        self.transport = transport
        sock = self.transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.loop.call_soon(self.discover)

    def datagram_received(self, data, addr):
        """Method run when data is received from the devices

        This method will unpack the data according to the LIFX protocol.
        If a new device is found, the Light device will be created and started aa
        a DatagramProtocol and will be registered with the parent.

            :param data: raw data
            :type data: bytestring
            :param addr: sender IP address 2-tuple for IPv4, 4-tuple for IPv6
            :type addr: tuple
        """
        response = unpack_lifx_message(data)
        response.ip_addr = addr[0]

        mac_addr = response.target_addr
        if mac_addr == BROADCAST_MAC:
            return

        if (
            type(response) == StateService and response.service == 1
        ):  # only look for UDP services
            # discovered
            remote_port = response.port
        elif type(response) == LightState:
            # looks like the lights are volunteering LigthState after booting
            remote_port = UDP_BROADCAST_PORT
        else:
            return

        if self.ipv6prefix:
            family = socket.AF_INET6
            remote_ip = mac_to_ipv6_linklocal(mac_addr, self.ipv6prefix)
        else:
            family = socket.AF_INET
            remote_ip = response.ip_addr

        if mac_addr in self.lights:
            # rediscovered
            light = self.lights[mac_addr]

            # nothing to do
            if light.registered:
                return

            light.cleanup()
            light.ip_addr = remote_ip
            light.port = remote_port
        else:
            # newly discovered
            light = Light(self.loop, mac_addr, remote_ip, remote_port, parent=self)
            self.lights[mac_addr] = light

        coro = self.loop.create_datagram_endpoint(
            lambda: light, family=family, remote_addr=(remote_ip, remote_port)
        )

        light.task = aio.create_task(coro)

    def discover(self):
        """Method to send a discovery message"""
        if self.transport:
            if self.discovery_countdown <= 0:
                self.discovery_countdown = self.discovery_interval
                msg = GetService(
                    BROADCAST_MAC,
                    self.source_id,
                    seq_num=0,
                    payload={},
                    ack_requested=False,
                    response_requested=True,
                )
                self.transport.sendto(
                    msg.generate_packed_message(),
                    (self.broadcast_ip, UDP_BROADCAST_PORT),
                )
            else:
                self.discovery_countdown -= self.discovery_step
            self.loop.call_later(self.discovery_step, self.discover)

    def register(self, alight):
        """Proxy method to register the device with the parent."""
        if self.parent:
            self.parent.register(alight)

    def unregister(self, alight):
        """Proxy method to unregister the device with the parent."""
        if self.parent:
            self.parent.unregister(alight)

    def cleanup(self):
        """Method to call to cleanly terminate the connection to the device."""
        if self.transport:
            self.transport.close()
            self.transport = None
        if self.task:
            self.task.cancel()
            self.task = None
        for light in self.lights.values():
            light.cleanup()
        self.lights = {}


class LifxScan:
    """Scan all network interfaces for any active bulb."""

    def __init__(self, loop):
        """Initialize the scanner."""
        self.loop = loop

    async def scan(self, timeout=1):
        """Return a list of local IP addresses on interfaces with LIFX bulbs."""
        adapters = await self.loop.run_in_executor(None, ifaddr.get_adapters)
        ips = [
            ip.ip
            for adapter in ifaddr.get_adapters()
            for ip in adapter.ips
            if ip.is_IPv4
        ]

        if not ips:
            return []

        tasks = []
        discoveries = []
        for ip in ips:
            manager = ScanManager(ip)
            lifx_discovery = LifxDiscovery(self.loop, manager)
            discoveries.append(lifx_discovery)
            lifx_discovery.start(listen_ip=ip)
            tasks.append(aio.create_task(manager.lifx_ip()))

        (done, pending) = await aio.wait(tasks, timeout=timeout)

        for discovery in discoveries:
            discovery.cleanup()

        for task in pending:
            task.cancel()

        return [task.result() for task in done]


class ScanManager:
    """Temporary manager for discovering any bulb."""

    def __init__(self, ip):
        """Initialize the manager."""
        self._event = aio.Event()
        self.ip = ip

    async def lifx_ip(self):
        """Return our IP address when any device is discovered."""
        await self._event.wait()
        return self.ip

    def register(self, bulb):
        """Handle detected bulb."""
        self._event.set()

    def unregister(self, bulb):
        """Handle disappearing bulb."""
        pass
