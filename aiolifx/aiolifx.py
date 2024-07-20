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
from typing import Any, Coroutine, Optional, Set, Union
from aiolifx.fixtures.fixtures import ChainLight, MatrixLight, get_fixture, HevLight, ColorLight, MultizoneLight, Switch, Light
from .message import BROADCAST_MAC, BROADCAST_SOURCE_ID
from .msgtypes import *
from .products import *
from .unpack import unpack_lifx_message
from functools import partial
from math import floor
import random, datetime, socket, ifaddr
from dataclasses import dataclass, field


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

@dataclass
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

    loop: aio.AbstractEventLoop
    mac_addr: str
    ip_addr: str
    port: int
    parent: Any = None
    registered: bool = False
    retry_count: int = DEFAULT_ATTEMPTS
    timeout: float = DEFAULT_TIMEOUT
    unregister_timeout: float = DEFAULT_TIMEOUT
    transport: aio.DatagramTransport = None
    task: aio.Task = None
    seq: int = 0
    # Key is the message sequence, value is (Response, Event, callb )
    message: dict = field(default_factory=dict)
    source_id: int = random.randint(0, (2**32) - 1)
    # Default callback for unexpected messages
    default_callb: Any = None
    # And the rest
    label: str = None
    location: str = None
    group: str = None
    power_level: int = None
    vendor: str = None
    product: str = None
    version: str = None
    host_firmware_version: str = None
    host_firmware_build_timestamp: float = None
    wifi_firmware_version: str = None
    wifi_firmware_build_timestamp: float = None
    lastmsg: datetime = datetime.datetime.now()
    fixture: Optional[Union[Switch, MultizoneLight, ColorLight, HevLight, MatrixLight, ChainLight, Light]] = None

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
                        method = getattr(self, setmethod, None)
                        if method:
                            method(response)
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
        if not resp:
            return
        
        self.vendor = resp.vendor
        self.product = resp.product
        self.version = resp.version

        if not resp.product:
            return
        
        self.fixture = get_fixture(resp.product, self.req_with_resp, self.req_with_ack, self.fire_and_forget)


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

def lowercase(str):
    return str.lower()



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
            device = self.lights[mac_addr]

            # nothing to do
            if device.registered:
                return

            device.cleanup()
            device.ip_addr = remote_ip
            device.port = remote_port
        else:
            # newly discovered
            device = Device(self.loop, mac_addr, remote_ip, remote_port, parent=self)
            # print(device.product)
            # print(products_dict[device.product])
            self.lights[mac_addr] = device
            # if "max_kelvin" in products_dict[device.product]:
            #     print('is a light')
            #     self.lights[mac_addr] = device
            # else:
            #     print('isnt a light')
            

        coro = self.loop.create_datagram_endpoint(
            lambda: device, family=family, remote_addr=(remote_ip, remote_port)
        )

        device.task = aio.create_task(coro)

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
        alight.get_version()
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
