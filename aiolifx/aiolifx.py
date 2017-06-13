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
import time, random, datetime, socket

# A couple of constants
UDP_BROADCAST_IP = "255.255.255.255"
UDP_BROADCAST_PORT = 56700
DEFAULT_TIMEOUT=0.5 # How long to wait for an ack or response
DEFAULT_ATTEMPTS=3  # How many time shou;d we try to send to the bulb`
DISCOVERY_INTERVAL=180

def mac_to_ipv6_linklocal(mac,prefix):
    """ Translate a MAC address into an IPv6 address in the prefixed network"""

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
    return ns/(1000000000.0*60*60)

class Device(aio.DatagramProtocol):
    # mac_addr is a string, with the ":" and everything.
    # ip_addr is a string with the ip address
    # port is the port we are connected to
    def __init__(self, loop, mac_addr, ip_addr, port, parent=None):
        self.loop = loop
        self.mac_addr = mac_addr
        self.ip_addr = ip_addr
        self.port = port
        self.parent = parent
        self.registered = False
        self.retry_count = DEFAULT_ATTEMPTS
        self.timeout = DEFAULT_TIMEOUT
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
        self.lastmsg=datetime.datetime.now()-datetime.timedelta(seconds=600)
        
    def seq_next(self):
        self.seq = ( self.seq + 1 ) % 128
        return self.seq
       
    #
    #                            Protocol Methods
    #

    def connection_made(self, transport):
        self.transport = transport
        self.register()

    def datagram_received(self, data, addr):
        self.register()
        response = unpack_lifx_message(data)
        if response.seq_num in self.message:
            self.lastmsg=datetime.datetime.now()
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
        if not self.registered:
            self.registered = True
            if self.parent:
                self.parent.register(self)

    def unregister(self):
        if self.registered:
            #Only if we have not received any message recently.
            #On slower CPU, a race condition seem to sometime occur
            if datetime.datetime.now()-datetime.timedelta(seconds=DEFAULT_TIMEOUT) > self.lastmsg:
                self.registered = False
                if self.parent:
                    self.parent.unregister(self)

    def cleanup(self):
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
        if num_repeats is None:
            num_repeats = self.retry_count
        sent_msg_count = 0
        sleep_interval = 0.05
        while(sent_msg_count < num_repeats):
            self.transport.sendto(msg.packed_message)
            sent_msg_count += 1
            await aio.sleep(sleep_interval) # Max num of messages device can handle is 20 per second.

    # Don't wait for Acks or Responses, just send the same message repeatedly as fast as possible
    def fire_and_forget(self, msg_type, payload={}, timeout_secs=None, num_repeats=None):
        msg = msg_type(self.mac_addr, self.source_id, seq_num=0, payload=payload, ack_requested=False, response_requested=False)
        xx=self.loop.create_task(self.fire_sending(msg,num_repeats))
        return True


    async def try_sending(self,msg,timeout_secs, max_attempts):
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
        msg = msg_type(self.mac_addr, self.source_id, seq_num=self.seq_next(), payload=payload, ack_requested=True, response_requested=False)
        self.message[msg.seq_num]=[Acknowledgement,None,callb]
        xx=self.loop.create_task(self.try_sending(msg,timeout_secs, max_attempts))
        return True
    
    # Usually used for Get messages, or for state confirmation after Set (hence the optional payload)
    def req_with_resp(self, msg_type, response_type, payload={}, callb = None, timeout_secs=None, max_attempts=None):
        msg = msg_type(self.mac_addr, self.source_id, seq_num=self.seq_next(), payload=payload, ack_requested=False, response_requested=True) 
        self.message[msg.seq_num]=[response_type,None,callb]
        xx=self.loop.create_task(self.try_sending(msg,timeout_secs, max_attempts))
        return True
    
    # Not currently implemented, although the LIFX LAN protocol supports this kind of workflow natively
    def req_with_ack_resp(self, msg_type, response_type, payload, callb = None, timeout_secs=None, max_attempts=None):
        msg = msg_type(self.mac_addr, self.source_id, seq_num=self.seq_next(), payload=payload, ack_requested=True, response_requested=True) 
        self.message[msg.seq_num]=[response_type,None,callb]
        xx=self.loop.create_task(self.try_sending(msg,timeout_secs, max_attempts))
        return True
    
    
    #
    #                            Attribute Methods
    #
    def get_label(self,callb=None):
        if self.label is None:
            mypartial=partial(self.resp_set_label)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetLabel, StateLabel, callb=mycallb )
        return self.label
    
    def set_label(self, value,callb=None):
        if len(value) > 32:
            value = value[:32]
        mypartial=partial(self.resp_set_label,label=value)
        if callb:
            self.req_with_ack(SetLabel, {"label": value},lambda x,y:(mypartial(y),callb(x,y)) )
        else:
            self.req_with_ack(SetLabel, {"label": value},lambda x,y:mypartial(y) )
        
    def resp_set_label(self, resp, label=None):
        if label:
            self.label=label
        elif resp:
            self.label=resp.label.decode().replace("\x00", "") 

    def get_location(self,callb=None):
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
        if location:
            self.location=location
        elif resp:
            self.location=resp.label.decode().replace("\x00", "") 
            #self.resp_set_label(resp)
            
            
    def get_group(self,callb=None):
        if self.group is None:
            mypartial=partial(self.resp_set_group)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetGroup, StateGroup, callb=callb )
        return self.group
    
    #Not implemented. hy?
    #def set_group(self, value,callb=None):
        #if callb:
            #self.req_with_ack(SetGroup, {"group": value},lambda x,y:(partial(self.resp_set_group,group=value)(y),callb(x,y)) )
        #else:
            #self.req_with_ack(SetGroup, {"group": value},lambda x,y:partial(self.resp_set_group,group=value)(y) )
        
    def resp_set_group(self, resp, group=None):
        if group:
            self.group=group
        elif resp:
            self.group=resp.label.decode().replace("\x00", "")
            
            
    def get_power(self,callb=None):
        if self.power_level is None:
            response = self.req_with_resp(GetPower, StatePower, callb=callb )
        return self.power_level
    
    def set_power(self, value,callb=None,rapid=False):
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
        if power_level is not None:
            self.power_level=power_level
        elif resp:
            self.power_level=resp.power_level 
            
            
    def get_wififirmware(self,callb=None):
        if self.wifi_firmware_version is None:
            mypartial=partial(self.resp_set_wififirmware)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetWifiFirmware, StateWifiFirmware,mycallb )
        return (self.wifi_firmware_version,self.wifi_firmware_build_timestamp)
    
    def resp_set_wififirmware(self, resp):
        if resp:
            self.wifi_firmware_version = float(str(str(resp.version >> 16) + "." + str(resp.version & 0xff)))
            self.wifi_firmware_build_timestamp = resp.build
    
    #Too volatile to be saved
    def get_wifiinfo(self,callb=None):
        response = self.req_with_resp(GetWifiInfo, StateWifiInfo,callb=callb )
        return None
             
            
    def get_hostfirmware(self,callb=None):
        if self.host_firmware_version is None:
            mypartial=partial(self.resp_set_hostfirmware)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetHostFirmware, StateHostFirmware,mycallb )
        return (self.host_firmware_version,self.host_firmware_build_timestamp)
    
    def resp_set_hostfirmware(self, resp):
        if resp:
            self.host_firmware_version = float(str(str(resp.version >> 16) + "." + str(resp.version & 0xff)))
            self.host_firmware_build_timestamp = resp.build
    
    #Too volatile to be saved
    def get_hostinfo(self,callb=None):
        response = self.req_with_resp(GetInfo, StateInfo,callb=callb )
        return None
            
    def get_version(self,callb=None):
        if self.vendor is None:
            mypartial=partial(self.resp_set_version)
            if callb:
                mycallb=lambda x,y:(mypartial(y),callb(x,y))
            else:
                mycallb=lambda x,y:mypartial(y)
            response = self.req_with_resp(GetVersion, StateVersion,callb=mycallb )
        return (self.host_firmware_version,self.host_firmware_build_timestamp)
    
    def resp_set_version(self, resp):
        if resp:
            self.vendor = resp.vendor
            self.product = resp.product
            self.version = resp.version
    
    #
    #                            Formating
    #
    def device_characteristics_str(self, indent):
        s = "{}\n".format(self.label)
        s += indent + "MAC Address: {}\n".format(self.mac_addr)
        s += indent + "IP Address: {}\n".format(self.ip_addr)
        s += indent + "Port: {}\n".format(self.port)
        s += indent + "Power: {}\n".format(str_map(self.power_level))
        s += indent + "Location: {}\n".format(self.location)
        s += indent + "Group: {}\n".format(self.group)
        return s

    def device_firmware_str(self, indent):
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
        s = "Vendor: {}\n".format(self.vendor)
        s += indent + "Product: {}\n".format((self.product and product_map[self.product]) or "Unknown")
        s += indent + "Version: {}\n".format(self.version)
        return s
    
    def device_time_str(self, resp, indent="  "):
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
        signal = resp.signal
        tx = resp.tx
        rx = resp.rx
        s = "Wifi Signal Strength (mW): {}\n".format(signal)
        s += indent + "Wifi TX (bytes): {}\n".format(tx)
        s += indent + "Wifi RX (bytes): {}\n".format(rx)
        return s    

    def register_callback(self,callb):
        self.default_callb = callb

class Light(Device):
    
    def __init__(self, loop, mac_addr, ip_addr, port=UDP_BROADCAST_PORT, parent=None):
        mac_addr = mac_addr.lower()
        super(Light, self).__init__(loop, mac_addr, ip_addr, port, parent)
        self.color = None
        self.color_zones = None
        self.infrared_brightness = None

    def get_power(self,callb=None):
        if self.power_level is None:
            response = self.req_with_resp(LightGetPower, LightStatePower, callb=callb )
        return self.power_level
    
    def set_power(self, value,callb=None,duration=0,rapid=False):
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
        if power_level is not None:
            self.power_level=power_level
        elif resp:
            self.power_level=resp.power_level 
            
    # LightGet, color, power_level, label
    def get_color(self,callb=None):
        response = self.req_with_resp(LightGet, LightState, callb=callb)
        return self.color
   
    # color is [Hue, Saturation, Brightness, Kelvin], duration in ms
    def set_color(self, value, callb=None, duration=0, rapid=False):
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
        if color:
            self.color=color
        elif resp:
            self.power_level = resp.power_level
            self.color = resp.color
            self.label = resp.label.decode().replace("\x00", "")
 
    # Multizone
    def get_color_zones(self, start_index, end_index=None, callb=None):
        if end_index is None:
            end_index = start_index + 8
        args = {
            "start_index": start_index,
            "end_index": end_index,
        }
        self.req_with_resp(MultiZoneGetColorZones, MultiZoneStateMultiZone, payload=args, callb=callb)

    def set_color_zones(self, start_index, end_index, color, duration=0, apply=1, callb=None, rapid=False):
        if len(color) == 4:
            args = {
                "start_index": start_index,
                "end_index": end_index,
                "color": color,
                "duration": duration,
                "apply": apply,
            }

            if rapid:
                self.fire_and_forget(MultiZoneSetColorZones, args, callb=callb, num_repeats=1)
            else:
                self.req_with_ack(MultiZoneSetColorZones, args, callb=callb)

    # A multi-zone MultiZoneGetColorZones returns MultiZoneStateMultiZone -> multizonemultizone
    def resp_set_multizonemultizone(self, resp):
        if resp:
            if self.color_zones is None:
                self.color_zones = [None] * resp.count
            for i in range(0, 8):
                self.color_zones[resp.index + i] = resp.color[i]

    # value should be a dictionary with the the following keys: transient, color, period,cycles,duty_cycle,waveform
    def set_waveform(self, value, callb=None, rapid=False):
        if "color" in value and len(value["color"]) == 4:
            #try:
            if rapid:
                self.fire_and_forget(LightSetWaveform, value, callb=callb, num_repeats=1)
            else:
                self.req_with_ack(LightSetWaveform, value, callb=callb)
            #except WorkflowException as e:
                #print(e)

    # Infrared get maximum brightness, infrared_brightness
    def get_infrared(self,callb=None):
        response = self.req_with_resp(LightGetInfrared, LightStateInfrared,callb=callb)
        return self.infrared_brightness

    # Infrared set maximum brightness, infrared_brightness
    def set_infrared(self, infrared_brightness, callb=None, rapid=False):
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

    def __init__(self, loop, parent=None, ipv6prefix=None, discovery_interval=DISCOVERY_INTERVAL):
        self.lights = {} #Known devices indexed by mac addresses
        self.parent = parent #Where to register new devices
        self.transport = None
        self.loop = loop
        self.source_id = random.randint(0, (2**32)-1)
        self.ipv6prefix = ipv6prefix
        self.discovery_interval=discovery_interval

    def connection_made(self, transport):
        #print('started')
        self.transport = transport
        sock = self.transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.loop.call_soon(self.discover)

    def datagram_received(self, data, addr):
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

            # nothing changed, just register again
            if light.ip_addr == remote_ip and light.port == remote_port:
                light.register()
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
        if self.transport:
            msg = GetService(BROADCAST_MAC, self.source_id, seq_num=0, payload={}, ack_requested=False, response_requested=True)    
            self.transport.sendto(msg.generate_packed_message(), (UDP_BROADCAST_IP, UDP_BROADCAST_PORT ))
            self.loop.call_later(self.discovery_interval, self.discover)
            
    def register(self,alight):
        if self.parent:
            self.parent.register(alight)
        
    def unregister(self,alight):
        if self.parent:
            self.parent.unregister(alight)

    def cleanup(self):
        if self.transport:
            self.transport.close()
            self.transport = None
        for light in self.lights.values():
            light.cleanup()
        self.lights = {}
