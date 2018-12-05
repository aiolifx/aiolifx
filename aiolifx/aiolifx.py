#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# This application is simply a bridge application for Lifx bulbs.
#
# Copyright (c) 2016 François Wautier
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
from .message import BROADCAST_MAC, BROADCAST_SOURCE_ID
from .msgtypes import *
from .products import *
from .unpack import unpack_lifx_message
from functools import partial
import time, random, datetime, socket, ifaddr

# A couple of constants
LISTEN_IP = "0.0.0.0"
UDP_BROADCAST_IP = "255.255.255.255"
UDP_BROADCAST_PORT = 56700
DEFAULT_TIMEOUT=0.5 # How long to wait for an ack or response
DEFAULT_ATTEMPTS=3  # How many time shou;d we try to send to the bulb`
DISCOVERY_INTERVAL=180
DISCOVERY_STEP=5

def mac_to_ipv6_linklocal(mac,prefix="fe80::"):
    """ Translate a MAC address into an IPv6 address in the prefixed network.

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
    mac_value = int(mac.translate(str.maketrans(dict([(x,None) for x in [" ",".",":","-"]]))),16)
    # Split out the bytes that slot into the IPv6 address
    # XOR the most significant byte with 0x02, inverting the
    # Universal / Local bit
    high2 = mac_value >> 32 & 0xffff ^ 0x0200
    high1 = mac_value >> 24 & 0xff
    low1 = mac_value >> 16 & 0xff
    low2 = mac_value & 0xffff
    return prefix+':{:04x}:{:02x}ff:fe{:02x}:{:04x}'.format(
        high2, high1, low1, low2)

def nanosec_to_hours(ns):
    """Convert nanoseconds to hours

        :param ns: Number of nanoseconds
        :type ns: into
        :returns: ns/(1000000000.0*60*60)
        :rtype: int
    """
    return ns/(1000000000.0*60*60)

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
        self.source_id = random.randint(0, (2**32)-1)
        #Default callback for unexpected messages
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
        self.lastmsg=datetime.datetime.now()

    def seq_next(self):
        """Method to return the next sequence value to use in messages.

            :returns: next number in sequensce (modulo 128)
            :rtype: int
        """
        self.seq = ( self.seq + 1 ) % 128
        return self.seq

    #
    #                            Protocol Methods
    #

    def connection_made(self, transport):
        """Method run when the connection to the lamp is established
        """
        self.transport = transport
        self.register()

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
        self.lastmsg=datetime.datetime.now()
        if response.seq_num in self.message:
            response_type,myevent,callb = self.message[response.seq_num]
            if type(response) == response_type:
                if response.source_id == self.source_id:
                    if "State" in response.__class__.__name__:
                        setmethod="resp_set_"+response.__class__.__name__.replace("State","").lower()
                        if setmethod in dir(self) and callable(getattr(self,setmethod)):
                            getattr(self,setmethod)(response)
                    if callb:
                        callb(self,response)
                    myevent.set()
                del(self.message[response.seq_num])
            elif type(response) == Acknowledgement:
                pass
            else:
                del(self.message[response.seq_num])
        elif self.default_callb:
            self.default_callb(response)

    def register(self):
        """Proxy method to register the device with the parent.
        """
        if not self.registered:
            self.registered = True
            if self.parent:
                self.parent.register(self)

    def unregister(self):
        """Proxy method to unregister the device with the parent.
        """
        if self.registered:
            #Only if we have not received any message recently.
            if datetime.datetime.now()-datetime.timedelta(seconds=self.unregister_timeout) > self.lastmsg:
                self.registered = False
                if self.parent:
                    self.parent.unregister(self)

    def cleanup(self):
        """Method to call to cleanly terminate the connection to the device.
        """
        if self.transport:
            self.transport.close()
            self.transport = None
        if self.task:
            self.task.cancel()
            self.task = None

    #
    #                            Workflow Methods
    #

    async def fire_sending(self,msg,num_repeats):
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
        while(sent_msg_count < num_repeats):
            if self.transport:
                self.transport.sendto(msg.packed_message)
            sent_msg_count += 1
            await aio.sleep(sleep_interval) # Max num of messages device can handle is 20 per second.

    # Don't wait for Acks or Responses, just send the same message repeatedly as fast as possible
    def fire_and_forget(self, msg_type, payload={}, timeout_secs=None, num_repeats=None):
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
        msg = msg_type(self.mac_addr, self.source_id, seq_num=0, payload=payload, ack_requested=False, response_requested=False)
        xx=self.loop.create_task(self.fire_sending(msg,num_repeats))
        return True


    async def try_sending(self,msg,timeout_secs, max_attempts):
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
            if msg.seq_num not in self.message: return
            event = aio.Event()
            self.message[msg.seq_num][1]= event
            attempts += 1
            if self.transport:
                self.transport.sendto(msg.packed_message)
            try:
                myresult = await aio.wait_for(event.wait(),timeout_secs)
                break
            except Exception as inst:
                if attempts >= max_attempts:
                    if msg.seq_num in self.message:
                        callb = self.message[msg.seq_num][2]
                        if callb:
                            callb(self, None)
                        del(self.message[msg.seq_num])
                    #It's dead Jim
                    self.unregister()

    # Usually used for Set messages
    def req_with_ack(self, msg_type, payload, callb = None, timeout_secs=None, max_attempts=None):
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
        msg = msg_type(self.mac_addr, self.source_id, seq_num=self.seq_next(), payload=payload, ack_requested=True, response_requested=False)
        self.message[msg.seq_num]=[Acknowledgement,None,callb]
        xx=self.loop.create_task(self.try_sending(msg,timeout_secs, max_attempts))
        return True

    # Usually used for Get messages, or for state confirmation after Set (hence the optional payload)
    def req_with_resp(self, msg_type, response_type, payload={}, callb = None, timeout_secs=None, max_attempts=None):
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
        msg = msg_type(self.mac_addr, self.source_id, seq_num=self.seq_next(), payload=payload, ack_requested=False, response_requested=True)
        self.message[msg.seq_num]=[response_type,None,callb]
        xx=self.loop.create_task(self.try_sending(msg,timeout_secs, max_attempts))
        return True

    # Not currently implemented, although the LIFX LAN protocol supports this kind of workflow natively
    def req_with_ack_resp(self, msg_type, response_type, payload, callb = None, timeout_secs=None, max_attempts=None):
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
        msg = msg_type(self.mac_addr, self.source_id, seq_num=self.seq_next(), payload=payload, ack_requested=True, response_requested=True)
        self.message[msg.seq_num]=[response_type,None,callb]
        xx=self.loop.create_task(self.try_sending(msg,timeout_secs, max_attempts))
        return True


    #
    #                            Attribute Methods
    #
    def get_label(self,callb=None):
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
            mypartial=partial(self.resp_set_label)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetLabel, StateLabel, callb=mycallb )
        return self.label

    def set_label(self, value,callb=None):
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
        mypartial=partial(self.resp_set_label,label=value)
        if callb:
            self.req_with_ack(SetLabel, {"label": value},lambda x,y:(mypartial(y),callb(x,y)) )
        else:
            self.req_with_ack(SetLabel, {"label": value},lambda x,y:mypartial(y) )

    def resp_set_label(self, resp, label=None):
        """Default callback for get_label/set_label
        """
        if label:
            self.label=label
        elif resp:
            self.label=resp.label.decode().replace("\x00", "")

    def get_location(self,callb=None):
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
            mypartial=partial(self.resp_set_location)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetLocation, StateLocation,callb=mycallb )
        return self.location

    #def set_location(self, value,callb=None):
        #mypartial=partial(self.resp_set_location,location=value)
        #if callb:
            #self.req_with_ack(SetLocation, {"location": value},lambda x,y:(mypartial(y),callb(x,y)) )
        #else:
            #self.req_with_ack(SetLocation, {"location": value},lambda x,y:mypartial(y) )

    def resp_set_location(self, resp, location=None):
        """Default callback for get_location/set_location
        """
        if location:
            self.location=location
        elif resp:
            self.location=resp.label.decode().replace("\x00", "")
            #self.resp_set_label(resp)


    def get_group(self,callb=None):
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
            mypartial=partial(self.resp_set_group)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetGroup, StateGroup, callb=callb )
        return self.group

    #Not implemented. Why?
    #def set_group(self, value,callb=None):
        #if callb:
            #self.req_with_ack(SetGroup, {"group": value},lambda x,y:(partial(self.resp_set_group,group=value)(y),callb(x,y)) )
        #else:
            #self.req_with_ack(SetGroup, {"group": value},lambda x,y:partial(self.resp_set_group,group=value)(y) )

    def resp_set_group(self, resp, group=None):
        """Default callback for get_group/set_group
        """
        if group:
            self.group=group
        elif resp:
            self.group=resp.label.decode().replace("\x00", "")


    def get_power(self,callb=None):
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
            response = self.req_with_resp(GetPower, StatePower, callb=callb )
        return self.power_level

    def set_power(self, value,callb=None,rapid=False):
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
        mypartial=partial(self.resp_set_power,power_level=value)
        if callb:
            mycallb=lambda x,y:(mypartial(y),callb(x,y))
        else:
            mycallb=lambda x,y:mypartial(y)
        if value in on and not rapid:
            response = self.req_with_ack(SetPower, {"power_level": 65535},mycallb)
        elif value in off and not rapid:
            response = self.req_with_ack(SetPower, {"power_level": 0},mycallb)
        elif value in on and rapid:
            response = self.fire_and_forget(SetPower, {"power_level": 65535})
            self.power_level=65535
        elif value in off and rapid:
            response = self.fire_and_forget(SetPower, {"power_level": 0})
            self.power_level=0

    def resp_set_power(self, resp, power_level=None):
        """Default callback for get_power/set_power
        """
        if power_level is not None:
            self.power_level=power_level
        elif resp:
            self.power_level=resp.power_level


    def get_wififirmware(self,callb=None):
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
            mypartial=partial(self.resp_set_wififirmware)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetWifiFirmware, StateWifiFirmware,mycallb )
        return (self.wifi_firmware_version,self.wifi_firmware_build_timestamp)

    def resp_set_wififirmware(self, resp):
        """Default callback for get_wififirmware
        """
        if resp:
            self.wifi_firmware_version = float(str(str(resp.version >> 16) + "." + str(resp.version & 0xff)))
            self.wifi_firmware_build_timestamp = resp.build

    #Too volatile to be saved
    def get_wifiinfo(self,callb=None):
        """Convenience method to request the wifi info from the device

        This will request the information from the device and request that callb be executed
        when a response is received. The is no  default callback

            :param callb: Callable to be used when the response is received. If not set,
                        self.resp_set_label will be used.
            :type callb: callable
            :returns: None
            :rtype: None
        """
        response = self.req_with_resp(GetWifiInfo, StateWifiInfo,callb=callb )
        return None


    def get_hostfirmware(self,callb=None):
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
            mypartial=partial(self.resp_set_hostfirmware)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetHostFirmware, StateHostFirmware,mycallb )
        return (self.host_firmware_version,self.host_firmware_build_timestamp)

    def resp_set_hostfirmware(self, resp):
        """Default callback for get_hostfirmware
        """
        if resp:
            self.host_firmware_version = float(str(str(resp.version >> 16) + "." + str(resp.version & 0xff)))
            self.host_firmware_build_timestamp = resp.build

    #Too volatile to be saved
    def get_hostinfo(self,callb=None):
        """Convenience method to request the device info from the device

        This will request the information from the device and request that callb be executed
        when a response is received. The is no  default callback

        :param callb: Callable to be used when the response is received. If not set,
                      self.resp_set_label will be used.
        :type callb: callable
        :returns: None
        :rtype: None
        """
        response = self.req_with_resp(GetInfo, StateInfo,callb=callb )
        return None

    def get_version(self,callb=None):
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
            mypartial=partial(self.resp_set_version)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetVersion, StateVersion,callb=mycallb )
        return (self.host_firmware_version,self.host_firmware_build_timestamp)

    def resp_set_version(self, resp):
        """Default callback for get_version
        """
        if resp:
            self.vendor = resp.vendor
            self.product = resp.product
            self.version = resp.version

    #
    #                            Formating
    #
    def device_characteristics_str(self, indent):
        """Convenience to string method.
        """
        s = "{}\n".format(self.label)
        s += indent + "MAC Address: {}\n".format(self.mac_addr)
        s += indent + "IP Address: {}\n".format(self.ip_addr)
        s += indent + "Port: {}\n".format(self.port)
        s += indent + "Power: {}\n".format(str_map(self.power_level))
        s += indent + "Location: {}\n".format(self.location)
        s += indent + "Group: {}\n".format(self.group)
        return s

    def device_firmware_str(self, indent):
        """Convenience to string method.
        """
        host_build_ns = self.host_firmware_build_timestamp
        host_build_s = datetime.datetime.utcfromtimestamp(host_build_ns/1000000000) if host_build_ns != None else None
        wifi_build_ns = self.wifi_firmware_build_timestamp
        wifi_build_s = datetime.datetime.utcfromtimestamp(wifi_build_ns/1000000000) if wifi_build_ns != None else None
        s = "Host Firmware Build Timestamp: {} ({} UTC)\n".format(host_build_ns, host_build_s)
        s += indent + "Host Firmware Build Version: {}\n".format(self.host_firmware_version)
        s += indent + "Wifi Firmware Build Timestamp: {} ({} UTC)\n".format(wifi_build_ns, wifi_build_s)
        s += indent + "Wifi Firmware Build Version: {}\n".format(self.wifi_firmware_version)
        return s

    def device_product_str(self, indent):
        """Convenience to string method.
        """
        s = "Vendor: {}\n".format(self.vendor)
        s += indent + "Product: {}\n".format((self.product and product_map[self.product]) or "Unknown")
        s += indent + "Version: {}\n".format(self.version)
        return s

    def device_time_str(self, resp, indent="  "):
        """Convenience to string method.
        """
        time = resp.time
        uptime = resp.uptime
        downtime = resp.downtime
        time_s = datetime.datetime.utcfromtimestamp(time/1000000000) if time != None else None
        uptime_s = round(nanosec_to_hours(uptime), 2) if uptime != None else None
        downtime_s = round(nanosec_to_hours(downtime), 2) if downtime != None else None
        s = "Current Time: {} ({} UTC)\n".format(time, time_s)
        s += indent + "Uptime (ns): {} ({} hours)\n".format(uptime, uptime_s)
        s += indent + "Last Downtime Duration +/-5s (ns): {} ({} hours)\n".format(downtime, downtime_s)
        return s

    def device_radio_str(self, resp, indent="  "):
        """Convenience to string method.
        """
        signal = resp.signal
        tx = resp.tx
        rx = resp.rx
        s = "Wifi Signal Strength (mW): {}\n".format(signal)
        s += indent + "Wifi TX (bytes): {}\n".format(tx)
        s += indent + "Wifi RX (bytes): {}\n".format(rx)
        return s

    def register_callback(self,callb):
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
        self.infrared_brightness = None

    def get_power(self,callb=None):
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
            response = self.req_with_resp(LightGetPower, LightStatePower, callb=callb )
        return self.power_level

    def set_power(self, value,callb=None,duration=0,rapid=False):
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
            myvalue = 65535
        else:
            myvalue = 0
        mypartial=partial(self.resp_set_lightpower,power_level=myvalue)
        if callb:
            mycallb=lambda x,y:(mypartial(y),callb(x,y))
        else:
            mycallb=lambda x,y:mypartial(y)
        if not rapid:
            response = self.req_with_ack(LightSetPower, {"power_level": myvalue, "duration": duration},callb=mycallb)
        else:
            response = self.fire_and_forget(LightSetPower, {"power_level": myvalue, "duration": duration}, num_repeats=1)
            self.power_level=myvalue
            if callb:
                callb(self,None)

    #Here lightpower because LightStatePower message will give lightpower
    def resp_set_lightpower(self, resp, power_level=None):
        """Default callback for set_power
        """
        if power_level is not None:
            self.power_level=power_level
        elif resp:
            self.power_level=resp.power_level

    # LightGet, color, power_level, label
    def get_color(self,callb=None):
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
            mypartial=partial(self.resp_set_light,color=value)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            #try:
            if rapid:
                self.fire_and_forget(LightSetColor, {"color": value, "duration": duration}, num_repeats=1)
                self.resp_set_light(None,color=value)
                if callb:
                    callb(self,None)
            else:
                self.req_with_ack(LightSetColor, {"color": value, "duration": duration},callb=mycallb)
            #except WorkflowException as e:
                #print(e)

    #Here light because LightState message will give light
    def resp_set_light(self, resp, color=None):
        """Default callback for set_color
        """
        if color:
            self.color=color
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
        self.req_with_resp(MultiZoneGetColorZones, MultiZoneStateMultiZone, payload=args, callb=callb)

    def set_color_zones(self, start_index, end_index, color, duration=0, apply=1, callb=None, rapid=False):
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

            mypartial=partial(self.resp_set_multizonemultizone, args=args)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)

            if rapid:
                self.fire_and_forget(MultiZoneSetColorZones, args, num_repeats=1)
                mycallb(self, None)
            else:
                self.req_with_ack(MultiZoneSetColorZones, args, callb=mycallb)

    # A multi-zone MultiZoneGetColorZones returns MultiZoneStateMultiZone -> multizonemultizone
    def resp_set_multizonemultizone(self, resp, args=None):
        """Default callback for get-color_zones/set_color_zones
        """
        if args:
            if self.color_zones:
                for i in range(args["start_index"], args["end_index"]+1):
                    self.color_zones[i] = args["color"]
        elif resp:
            if self.color_zones is None:
                self.color_zones = [None] * resp.count
            for i in range(resp.index, min(resp.index+8, resp.count)):
                self.color_zones[i] = resp.color[i-resp.index]

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
    def get_infrared(self,callb=None):
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
        response = self.req_with_resp(LightGetInfrared, LightStateInfrared,callb=callb)
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
        mypartial=partial(self.resp_set_infrared,infrared_brightness=infrared_brightness)
        if callb:
            mycallb=lambda x,y:(mypartial(y),callb(x,y))
        else:
            mycallb=lambda x,y:mypartial(y)
        if rapid:
            self.fire_and_forget(LightSetInfrared, {"infrared_brightness": infrared_brightness}, num_repeats=1)
            self.resp_set_infrared(None,infrared_brightness=infrared_brightness)
            if callb:
                callb(self,None)
        else:
            self.req_with_ack(LightSetInfrared, {"infrared_brightness": infrared_brightness}, callb=mycallb)

    #Here infrared because StateInfrared message will give infrared
    def resp_set_infrared(self, resp, infrared_brightness=None):
        """Default callback for set_infrared/get_infrared
        """
        if infrared_brightness is not None:
            self.infrared_brightness = infrared_brightness
        elif resp:
            self.infrared_brightness = resp.infrared_brightness

    def __str__(self):
        indent = "  "
        s = self.device_characteristics_str(indent)
        s += indent + "Color (HSBK): {}\n".format(self.color)
        s += indent + self.device_firmware_str(indent)
        s += indent + self.device_product_str(indent)
        #s += indent + self.device_time_str(indent)
        #s += indent + self.device_radio_str(indent)
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

    def __init__(self, loop, parent=None, ipv6prefix=None, discovery_interval=DISCOVERY_INTERVAL, discovery_step=DISCOVERY_STEP, broadcast_ip=UDP_BROADCAST_IP):
        self.lights = {} #Known devices indexed by mac addresses
        self.parent = parent #Where to register new devices
        self.transport = None
        self.loop = loop
        self.task = None
        self.source_id = random.randint(0, (2**32)-1)
        self.ipv6prefix = ipv6prefix
        self.discovery_interval = discovery_interval
        self.discovery_step = discovery_step
        self.discovery_countdown = 0
        self.broadcast_ip = broadcast_ip

    def start(self, listen_ip=LISTEN_IP, listen_port=0):
        """Start discovery task."""
        coro = self.loop.create_datagram_endpoint(
            lambda: self, local_addr=(listen_ip, listen_port))

        self.task = self.loop.create_task(coro)
        return self.task

    def connection_made(self, transport):
        """Method run when the UDP broadcast server is started
        """
        #print('started')
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

        if type(response) == StateService and response.service == 1: # only look for UDP services
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
            lambda: light, family=family, remote_addr=(remote_ip, remote_port))

        light.task = self.loop.create_task(coro)

    def discover(self):
        """Method to send a discovery message
        """
        if self.transport:
            if self.discovery_countdown <= 0:
                self.discovery_countdown = self.discovery_interval
                msg = GetService(BROADCAST_MAC, self.source_id, seq_num=0, payload={}, ack_requested=False, response_requested=True)
                self.transport.sendto(msg.generate_packed_message(), (self.broadcast_ip, UDP_BROADCAST_PORT))
            else:
                self.discovery_countdown -= self.discovery_step
            self.loop.call_later(self.discovery_step, self.discover)

    def register(self,alight):
        """Proxy method to register the device with the parent.
        """
        if self.parent:
            self.parent.register(alight)

    def unregister(self,alight):
        """Proxy method to unregister the device with the parent.
        """
        if self.parent:
            self.parent.unregister(alight)

    def cleanup(self):
        """Method to call to cleanly terminate the connection to the device.
        """
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
        ips = [ip.ip for adapter in ifaddr.get_adapters() for ip in adapter.ips if ip.is_IPv4]

        if not ips:
            return []

        tasks = []
        discoveries = []
        for ip in ips:
            manager = ScanManager(ip)
            lifx_discovery = LifxDiscovery(self.loop, manager)
            discoveries.append(lifx_discovery)
            lifx_discovery.start(listen_ip=ip)
            tasks.append(self.loop.create_task(manager.lifx_ip()))

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
