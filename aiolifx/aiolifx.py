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
    # ip_addr is a streing with the ip address, either IPv4 or IPv6
    # port is the port we are connected to
    def __init__(self, loop, mac_addr, ip_addr, port, parent=None):
        self.loop = loop
        self.mac_addr = mac_addr
        self.port = port
        self.ip_addr = ip_addr
        self.parent = parent
        self.transport = None
        self.seq = 0
        # Key is the message sequence, value is (Response, Event, callb )
        self.message = {}
        self.source_id = random.randint(0, (2**32)-1)
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
        
    def seq_next(self):
        self.seq = ( self.seq + 1 ) % 128
        return self.seq
       
    #
    #                            Protocol Methods
    #
    
    def connection_made(self, transport):
        self.transport = transport
        if self.parent:
            self.parent.register(self)

    def datagram_received(self, data, addr):
        response = unpack_lifx_message(data)
        if response.seq_num in self.message:
            response_type,myevent,callb = self.message[response.seq_num]

            if type(response) == response_type:
                if response.origin == 1 and response.source_id == self.source_id:
                    self.ip_addr = addr
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
                

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        if self.parent:
            self.parent.unregister(self)
        
    #
    #                            Workflow Methods
    #
   

    async def fire_sending(self,msg,num_repeats):
        sent_msg_count = 0
        sleep_interval = 0.05 if num_repeats > 20 else 0
        while(sent_msg_count < num_repeats):
            self.transport.sendto(msg.packed_message)
            sent_msg_count += 1
            await aio.sleep(sleep_interval) # Max num of messages device can handle is 20 per second.

    # Don't wait for Acks or Responses, just send the same message repeatedly as fast as possible
    def fire_and_forget(self, msg_type, payload={}, timeout_secs=DEFAULT_TIMEOUT, num_repeats=DEFAULT_ATTEMPTS):
        msg = msg_type(self.mac_addr, self.source_id, seq_num=0, payload=payload, ack_requested=False, response_requested=False)
        xx=self.loop.create_task(self.fire_sending(msg,num_repeats))
        return True


    async def try_sending(self,msg,timeout_secs, max_attempts):
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
                pass
        if attempts >= max_attempts:
            if msg.seq_num in self.message:
                del(self.message[msg.seq_num])
            #It's dead Jim
            self.connection_lost(None)

    # Usually used for Set messages
    def req_with_ack(self, msg_type, payload, callb = None, timeout_secs=DEFAULT_TIMEOUT, max_attempts=DEFAULT_ATTEMPTS):
        msg = msg_type(self.mac_addr, self.source_id, seq_num=self.seq_next(), payload=payload, ack_requested=True, response_requested=False)
        self.message[msg.seq_num]=[Acknowledgement,None,callb]
        xx=self.loop.create_task(self.try_sending(msg,timeout_secs, max_attempts))
        return True
    
    # Usually used for Get messages, or for state confirmation after Set (hence the optional payload)
    def req_with_resp(self, msg_type, response_type, payload={}, callb = None, timeout_secs=DEFAULT_TIMEOUT, max_attempts=DEFAULT_ATTEMPTS):
        msg = msg_type(self.mac_addr, self.source_id, seq_num=self.seq_next(), payload=payload, ack_requested=False, response_requested=True) 
        self.message[msg.seq_num]=[response_type,None,callb]
        xx=self.loop.create_task(self.try_sending(msg,timeout_secs, max_attempts))
        return True
    
    # Not currently implemented, although the LIFX LAN protocol supports this kind of workflow natively
    def req_with_ack_resp(self, msg_type, response_type, payload, callb = None, timeout_secs=DEFAULT_TIMEOUT, max_attempts=DEFAULT_ATTEMPTS):
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
        else:
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
        else:
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
        else:
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
        else:
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
        self.vendor = resp.vendor
        self.product = resp.product
        self.version = resp.version
    
    #
    #                            Formating
    #
    def device_characteristics_str(self, indent):
        s = "{}\n".format(self.label)
        s += indent + "MAC Address: {}\n".format(self.mac_addr)
        s += indent + "IP Address: {}\n".format(self.ip_addr and self.ip_addr[0])
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



class Light(Device):
    
    def __init__(self, loop, mac_addr, ip_addr, port=56700, parent=None):
        mac_addr = mac_addr.lower()
        super(Light, self).__init__(loop, mac_addr, ip_addr, port, parent)
        self.color = None
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
        else:
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
        else:
            self.power_level = resp.power_level
            self.color = resp.color
            self.label = resp.label.decode().replace("\x00", "")
 
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
    def set_infrared(self, infrared_brightness, rapid=False):
        mypartial=partial(self.resp_set_infrared,color=value)
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

        
    #Here light because LightState message will give light
    def resp_set_infrared(self, resp, infrared_brightness=None):
        if infrared_brightness:
            self.infrared_brightness = infrared_brightness
        else:
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

    def __init__(self, loop, parent=None,retry_count=3,timeout=0.5,ipv6prefix=None,discovery_interval=180):
        self.lights = [] #Know devices mac addresses
        self.parent = parent #Where to register new devices
        self.transport = None
        self.light_tp = {}
        self.loop = loop
        self.bcast_count = retry_count
        self.retry_count = retry_count
        self.timeout = [timeout]*retry_count
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
        if type(response) == StateService and response.service == 1 : #Only look for UDP services
            #Discovered
            if response.target_addr not in self.lights and response.target_addr != BROADCAST_MAC:
                self.lights.append(response.target_addr)
                if self.ipv6prefix:
                    coro = self.loop.create_datagram_endpoint(
                        partial(Light,self.loop,response.target_addr, response.ip_addr, response.port, parent=self),
                        family = socket.AF_INET6, remote_addr=(mac_to_ipv6_linklocal(response.target_addr,self.ipv6prefix), response.port))
                else:
                    coro = self.loop.create_datagram_endpoint(
                        partial(Light,self.loop,response.target_addr, response.ip_addr, response.port,parent=self),
                        family = socket.AF_INET, remote_addr=(response.ip_addr, response.port))
                
                self.light_tp[response.target_addr] = self.loop.create_task(coro)
               
        elif type(response) == LightState and response.target_addr != BROADCAST_MAC:
            if response.target_addr not in self.lights :
                #looks like the lights are volunteering LigthState after booting 
                self.lights.append(response.target_addr)
                if self.ipv6prefix:
                    coro = self.loop.create_datagram_endpoint(
                        partial(Light,self.loop,response.target_addr, response.ip_addr, UDP_BROADCAST_PORT, parent=self),
                        family = socket.AF_INET6, remote_addr=(mac_to_ipv6_linklocal(response.target_addr,self.ipv6prefix), UDP_BROADCAST_PORT))
                else:
                    coro = self.loop.create_datagram_endpoint(
                        partial(Light,self.loop,response.target_addr, response.ip_addr, UDP_BROADCAST_PORT,parent=self),
                        family = socket.AF_INET, remote_addr=(response.ip_addr, UDP_BROADCAST_PORT))
                
                self.light_tp[response.target_addr] = self.loop.create_task(coro)
           

                
    def discover(self):
        msg = GetService(BROADCAST_MAC, self.source_id, seq_num=0, payload={}, ack_requested=False, response_requested=True)    
        self.transport.sendto(msg.generate_packed_message(), (UDP_BROADCAST_IP, UDP_BROADCAST_PORT ))
        self.bcast_count -= 1
        
        self.loop.call_later(self.timeout[0], self.discover)
        if len(self.timeout)>1:
            self.timeout=self.timeout[1:]
        else:
            self.timeout=[DISCOVERY_INTERVAL]
            
    def connection_lost(self,e):
        print ("Ooops lost connection")
        self.loop.close()
        
    def register(self,alight):
        if self.parent:
            self.parent.register(alight)
        
    def unregister(self,alight):
        try:
            self.lights.remove(alight.mac_addr)
        except:
            pass
        if alight.mac_addr in self.light_tp:
            self.light_tp[alight.mac_addr].cancel()
            del(self.light_tp[alight.mac_addr])
        if self.parent:
            self.parent.unregister(alight)
            
    def cleanup(self):
        try:
            self.lights.remove(alight.mac_addr)
        except:
            pass
        if alight.mac_addr in self.light_tp:
            self.light_tp[alight.mac_addr].cancel()
            del(self.light_tp[alight.mac_addr])

