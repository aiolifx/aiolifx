# unpack.py
# Author: Meghan Clark

from .msgtypes import *
import binascii


# Creates a LIFX Message out of packed binary data
# If the message type is not one of the officially released ones above, it will create just a Message out of it
# If it's not in the LIFX protocol format, uhhhhh...we'll put that on a to-do list.
def unpack_lifx_message(packed_message):
    header_str = packed_message[0:HEADER_SIZE_BYTES]
    payload_str = packed_message[HEADER_SIZE_BYTES:]

    size = struct.unpack("H", header_str[0:2])[0]
    flags = struct.unpack("H", header_str[2:4])[0]
    origin = (flags >> 14) & 3
    tagged = (flags >> 13) & 1
    addressable = (flags >> 12) & 1
    protocol = flags & 4095
    source_id = struct.unpack("I", header_str[4:8])[0]
    target_addr = ":".join(
        [("%02x" % b) for b in struct.unpack("B" * 6, header_str[8:14])]
    )
    response_flags = struct.unpack("B", header_str[22:23])[0]
    ack_requested = response_flags & 2
    response_requested = response_flags & 1
    seq_num = struct.unpack("B", header_str[23:24])[0]
    message_type = struct.unpack("H", header_str[32:34])[0]

    message = None
    if message_type == MSG_IDS[GetService]:
        message = GetService(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateService]:
        service = struct.unpack("B", payload_str[0:1])[0]
        port = struct.unpack("I", payload_str[1:5])[0]
        payload = {"service": service, "port": port}
        message = StateService(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetHostInfo]:
        message = GetHostInfo(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateHostInfo]:
        signal = struct.unpack("f", payload_str[0:4])[0]
        tx = struct.unpack("I", payload_str[4:8])[0]
        rx = struct.unpack("I", payload_str[8:12])[0]
        reserved1 = struct.unpack("h", payload_str[12:14])[0]
        payload = {"signal": signal, "tx": tx, "rx": rx, "reserved1": reserved1}
        message = StateHostInfo(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetHostFirmware]:
        message = GetHostFirmware(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateHostFirmware]:
        build = struct.unpack("Q", payload_str[0:8])[0]
        reserved1 = struct.unpack("Q", payload_str[8:16])[0]
        version = struct.unpack("I", payload_str[16:20])[0]
        payload = {"build": build, "reserved1": reserved1, "version": version}
        message = StateHostFirmware(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetWifiInfo]:
        message = GetWifiInfo(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateWifiInfo]:
        signal = struct.unpack("f", payload_str[0:4])[0]
        tx = struct.unpack("I", payload_str[4:8])[0]
        rx = struct.unpack("I", payload_str[8:12])[0]
        reserved1 = struct.unpack("h", payload_str[12:14])[0]
        payload = {"signal": signal, "tx": tx, "rx": rx, "reserved1": reserved1}
        message = StateWifiInfo(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetWifiFirmware]:
        message = GetWifiFirmware(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateWifiFirmware]:
        build = struct.unpack("Q", payload_str[0:8])[0]
        reserved1 = struct.unpack("Q", payload_str[8:16])[0]
        version = struct.unpack("I", payload_str[16:20])[0]
        payload = {"build": build, "reserved1": reserved1, "version": version}
        message = StateWifiFirmware(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetPower]:
        message = GetPower(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[SetPower]:
        power_level = struct.unpack("H", payload_str[0:2])[0]
        payload = {"power_level": power_level}
        message = SetPower(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StatePower]:
        power_level = struct.unpack("H", payload_str[0:2])[0]
        payload = {"power_level": power_level}
        message = StatePower(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetLabel]:
        message = GetLabel(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[SetLabel]:
        label = binascii.unhexlify(
            "".join(
                [
                    "%2.2x" % (b & 0x000000FF)
                    for b in struct.unpack("b" * 32, payload_str[0:32])
                ]
            )
        )
        payload = {"label": label}
        message = SetLabel(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateLabel]:
        label = binascii.unhexlify(
            "".join(
                [
                    "%2.2x" % (b & 0x000000FF)
                    for b in struct.unpack("b" * 32, payload_str[0:32])
                ]
            )
        )
        payload = {"label": label}
        message = StateLabel(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetLocation]:
        message = GetLocation(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateLocation]:
        location = [b for b in struct.unpack("B" * 16, payload_str[0:16])]
        label = binascii.unhexlify(
            "".join(
                [
                    "%2.2x" % (b & 0x000000FF)
                    for b in struct.unpack("b" * 32, payload_str[16:48])
                ]
            )
        )
        updated_at = struct.unpack("Q", payload_str[48:56])[0]
        payload = {"location": location, "label": label, "updated_at": updated_at}
        message = StateLocation(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetGroup]:
        message = GetGroup(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateGroup]:
        group = [b for b in struct.unpack("B" * 16, payload_str[0:16])]
        label = binascii.unhexlify(
            "".join(
                [
                    "%2.2x" % (b & 0x000000FF)
                    for b in struct.unpack("b" * 32, payload_str[16:48])
                ]
            )
        )
        updated_at = struct.unpack("Q", payload_str[48:56])[0]
        payload = {"group": group, "label": label, "updated_at": updated_at}
        message = StateGroup(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetVersion]:
        message = GetVersion(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateVersion]:
        vendor = struct.unpack("I", payload_str[0:4])[0]
        product = struct.unpack("I", payload_str[4:8])[0]
        version = struct.unpack("I", payload_str[8:12])[0]
        payload = {"vendor": vendor, "product": product, "version": version}
        message = StateVersion(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetInfo]:
        message = GetInfo(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateInfo]:
        time = struct.unpack("Q", payload_str[0:8])[0]
        uptime = struct.unpack("Q", payload_str[8:16])[0]
        downtime = struct.unpack("Q", payload_str[16:24])[0]
        payload = {"time": time, "uptime": uptime, "downtime": downtime}
        message = StateInfo(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[Acknowledgement]:
        message = Acknowledgement(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[EchoRequest]:
        byte_array_len = len(payload_str)
        byte_array = [
            b
            for b in struct.unpack("B" * byte_array_len, payload_str[0:byte_array_len])
        ]
        payload = {"byte_array": byte_array}
        message = EchoRequest(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[EchoResponse]:
        byte_array_len = len(payload_str)
        byte_array = [
            b
            for b in struct.unpack("B" * byte_array_len, payload_str[0:byte_array_len])
        ]
        payload = {"byte_array": byte_array}
        message = EchoResponse(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightGet]:
        message = LightGet(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightSetColor]:
        color = struct.unpack("H" * 4, payload_str[0:8])
        duration = struct.unpack("I", payload_str[8:12])[0]
        payload = {"color": color, "duration": duration}
        message = LightSetColor(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightState]:
        color = struct.unpack("H" * 4, payload_str[0:8])
        reserved1 = struct.unpack("H", payload_str[8:10])[0]
        power_level = struct.unpack("H", payload_str[10:12])[0]
        label = binascii.unhexlify(
            "".join(
                [
                    "%2.2x" % (b & 0x000000FF)
                    for b in struct.unpack("b" * 32, payload_str[12:44])
                ]
            )
        )
        reserved2 = struct.unpack("Q", payload_str[44:52])[0]
        payload = {
            "color": color,
            "reserved1": reserved1,
            "power_level": power_level,
            "label": label,
            "reserved2": reserved2,
        }
        message = LightState(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightGetPower]:
        message = LightGetPower(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightSetPower]:
        power_level = struct.unpack("H", payload_str[0:2])[0]
        duration = struct.unpack("I", payload_str[2:6])[0]
        payload = {"power_level": power_level, "duration": duration}
        message = LightSetPower(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightStatePower]:
        power_level = struct.unpack("H", payload_str[0:2])[0]
        payload = {"power_level": power_level}
        message = LightStatePower(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightGetInfrared]:  # 120
        message = LightGetInfrared(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightStateInfrared]:  # 121
        infrared_brightness = struct.unpack("H", payload_str[0:2])[0]
        payload = {"infrared_brightness": infrared_brightness}
        message = LightStateInfrared(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[LightSetInfrared]:  # 122
        infrared_brightness = struct.unpack("H", payload_str[0:2])[0]
        payload = {"infrared_brightness": infrared_brightness}
        message = LightSetInfrared(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetHevCycle]:  # 142
        message = GetHevCycle(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[SetHevCycle]:  # 143
        enable, duration = struct.unpack("<BI", payload_str[:5])
        payload = {"enable": enable == 1, "duration": duration}
        message = SetHevCycle(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateHevCycle]:  # 144
        duration, remaining, last_power = struct.unpack("<IIB", payload_str[:9])
        payload = {
            "duration": duration,
            "remaining": remaining,
            "last_power": last_power == 1,
        }
        message = StateHevCycle(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetHevCycleConfiguration]:  # 145
        message = GetHevCycleConfiguration(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[SetHevCycleConfiguration]:  # 146
        indication, duration = struct.unpack("<BI", payload_str[:5])
        payload = {"indication": indication == 1, "duration": duration}
        message = SetHevCycleConfiguration(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateHevCycleConfiguration]:  # 147
        indication, duration = struct.unpack("<BI", payload_str[:5])
        payload = {"indication": indication == 1, "duration": duration}
        message = StateHevCycleConfiguration(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[GetLastHevCycleResult]:  # 148
        message = GetLastHevCycleResult(
            target_addr, source_id, seq_num, {}, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateLastHevCycleResult]:  # 149
        (result,) = struct.unpack("<B", payload_str[:1])
        payload = {"result": result}
        message = StateLastHevCycleResult(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[MultiZoneStateZone]:  # 503
        count = struct.unpack("c", payload_str[0:1])[0]
        count = ord(count)  # 8 bit
        index = struct.unpack("c", payload_str[1:2])[0]
        index = ord(index)  # 8 bit
        color = struct.unpack("H" * 4, payload_str[2:10])
        payload = {"count": count, "index": index, "color": color}
        message = MultiZoneStateZone(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[MultiZoneStateMultiZone]:  # 506
        count = struct.unpack("c", payload_str[0:1])[0]
        count = ord(count)  # 8 bit
        index = struct.unpack("c", payload_str[1:2])[0]
        index = ord(index)  # 8 bit
        colors = []
        for i in range(8):
            color = struct.unpack("H" * 4, payload_str[2 + (i * 8) : 10 + (i * 8)])
            colors.append(color)
        payload = {"count": count, "index": index, "color": colors}
        message = MultiZoneStateMultiZone(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[MultiZoneGetMultiZoneEffect]:  # 507
        _, effect, _, speed, duration, _, _, _, direction, _, _ = struct.unpack(
            "<IBHIQIIBBBB", payload_str[:31]
        )
        payload = {
            "effect": effect,
            "speed": speed,
            "duration": duration,
            "direction": direction,
        }
        message = MultiZoneGetMultiZoneEffect(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[MultiZoneSetMultiZoneEffect]:  # 508
        _, effect, _, speed, duration, _, _, _, direction, _, _ = struct.unpack(
            "<IBHIQIIBBBB", payload_str[:31]
        )
        payload = {
            "effect": effect,
            "speed": speed,
            "duration": duration,
            "direction": direction,
        }
        message = MultiZoneSetMultiZoneEffect(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[MultiZoneStateMultiZoneEffect]:  # 509
        (
            instanceid,
            effect,
            _,
            speed,
            duration,
            _,
            _,
        ) = struct.unpack("<IBHIQII", payload_str[:27])
        direction = struct.unpack("I", payload_str[31:35])[0]
        payload = {
            "instanceid": instanceid,
            "effect": effect,
            "speed": speed,
            "duration": duration,
            "direction": direction,
        }
        message = MultiZoneStateMultiZoneEffect(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[MultiZoneStateExtendedColorZones]:  # 512
        zones_count = struct.unpack("H", payload_str[0:2])[0]
        zone_index = struct.unpack("H", payload_str[2:4])[0]
        colors_count = struct.unpack("B", payload_str[4:5])[0]
        colors = []
        for i in range(82):
            color = struct.unpack("H" * 4, payload_str[5 + (i * 8) : 13 + (i * 8)])
            colors.append(color)

        payload = {
            "zones_count": zones_count,
            "zone_index": zone_index,
            "colors_count": colors_count,
            "colors": colors,
        }
        message = MultiZoneStateExtendedColorZones(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[TileGetDeviceChain]:  # 701
        message = TileGetDeviceChain(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[TileStateDeviceChain]:  # 702
        start_index = struct.unpack("B", payload_str[0:1])[0]
        tile_devices_count = struct.unpack(
            "B", payload_str[len(payload_str) - 1 : len(payload_str)]
        )[0]

        tile_devices = []
        for i in range(tile_devices_count):
            tile_devices.append(getTile(payload_str[1 + (i * 55) : 55 + (i * 55)]))

        payload = {
            "start_index": start_index,
            "tile_devices": tile_devices,
            "tile_devices_count": tile_devices_count,
        }
        message = TileStateDeviceChain(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[TileGet64]:  # 707
        tile_index = struct.unpack("B", payload_str[0:1])[0]
        length = struct.unpack("B", payload_str[1:2])[0]
        x = struct.unpack("B", payload_str[3:4])[0]
        y = struct.unpack("B", payload_str[4:5])[0]
        width = struct.unpack("B", payload_str[5:6])[0]
        payload = {
            "tile_index": tile_index,
            "length": length,
            "x": x,
            "y": y,
            "width": width,
        }
        message = TileGet64(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[TileState64]:  # 711
        tile_index = struct.unpack("B", payload_str[0:1])[0]
        x = struct.unpack("B", payload_str[2:3])[0]
        y = struct.unpack("B", payload_str[3:4])[0]
        width = struct.unpack("B", payload_str[4:5])[0]
        colors = []
        for i in range(64):
            color = struct.unpack("H" * 4, payload_str[5 + (i * 8) : 13 + (i * 8)])
            colors.append(color)

        payload = {
            "tile_index": tile_index,
            "x": x,
            "y": y,
            "width": width,
            "colors": colors,
        }
        message = TileState64(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[TileSet64]:  # 715
        tile_index = struct.unpack("B", payload_str[0:1])[0]
        length = struct.unpack("B", payload_str[1:2])[0]
        x = struct.unpack("B", payload_str[3:4])[0]
        y = struct.unpack("B", payload_str[4:5])[0]
        width = struct.unpack("B", payload_str[5:6])[0]
        duration = struct.unpack("I", payload_str[6:10])[0]
        colors = []
        for i in range(64):
            color = struct.unpack("H" * 4, payload_str[10 + (i * 8) : 18 + (i * 8)])
            colors.append(color)
        payload = {
            "tile_index": tile_index,
            "length": length,
            "x": x,
            "y": y,
            "width": width,
            "duration": duration,
            "colors": colors,
        }
        message = TileSet64(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[TileStateTileEffect]:  # 720
        instanceid = struct.unpack("I", payload_str[1:5])[0]
        effect = struct.unpack("B", payload_str[5:6])[0]
        speed = struct.unpack("I", payload_str[6:10])[0]
        duration = struct.unpack("Q", payload_str[10:18])[0]
        sky_type = struct.unpack("B", payload_str[26:27])[0]
        cloud_saturation_min = struct.unpack("B", payload_str[30:31])[0]
        cloud_saturation_max = struct.unpack("B", payload_str[34:35])[0]
        palette_count = struct.unpack("B", payload_str[58:59])[0]
        palette = []
        for i in range(16):
            color = struct.unpack("H" * 4, payload_str[59 + (i * 8) : 67 + (i * 8)])
            palette.append(color)

        payload = {
            "instanceid": instanceid,
            "effect": effect,
            "speed": speed,
            "duration": duration,
            "sky_type": sky_type,
            "cloud_saturation_min": cloud_saturation_min,
            "cloud_saturation_max": cloud_saturation_max,
            "palette_count": palette_count,
            "palette": palette,
        }
        message = TileStateTileEffect(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateRPower]:  # 818
        relay_index = struct.unpack("B", payload_str[:1])[0]
        level = struct.unpack(">H", payload_str[1:])[0]
        payload = {"relay_index": relay_index, "level": level}
        message = StateRPower(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateButton]:  # 907
        count = struct.unpack("B", payload_str[:1])[0]
        index = struct.unpack("B", payload_str[1:2])[0]
        buttons_count = struct.unpack("B", payload_str[2:3])[0]

        # always an array of 8 buttons
        buttons = []
        for i in range(8):
            # each button is 101 bytes
            button_bytes = payload_str[3 + (i * 101) : 104 + (i * 101)]
            actions_count = struct.unpack("B", button_bytes[:1])[0]
            # each button has 5 actions, size 100 bytes each
            button_actions = []
            for j in range(5):
                button_action_bytes = button_bytes[1 + (j * 20) : 21 + (j * 20)]

                button_gesture = struct.unpack("H", button_action_bytes[:2])[0]
                button_gesture_enum = ButtonGesture(button_gesture)

                button_target_type = struct.unpack("H", button_action_bytes[2:4])[0]
                button_target_type_enum = ButtonTargetType(button_target_type)

                button_target = button_action_bytes[4:]
                button_target_properties = {
                    "type": button_target_type_enum,
                }
                if button_target_type_enum == ButtonTargetType.RELAYS:
                    button_target_properties["relays_count"] = struct.unpack(
                        "B", button_target[:1]
                    )[0]
                    button_target_properties["relays"] = struct.unpack(
                        "B" * 15, button_target[1:]
                    )
                elif button_target_type_enum == ButtonTargetType.DEVICE:
                    button_target_properties["serial"] = struct.unpack(
                        "B" * 6, button_target[:6]
                    )
                    button_target_properties["reserved"] = struct.unpack(
                        "B" * 10, button_target[6:]
                    )
                elif button_target_type_enum == ButtonTargetType.LOCATION:
                    button_target_properties["location_id"] = struct.unpack(
                        "B" * 16, button_target[:16]
                    )
                elif button_target_type_enum == ButtonTargetType.GROUP:
                    button_target_properties["group_id"] = struct.unpack(
                        "B" * 16, button_target[:16]
                    )
                elif button_target_type_enum == ButtonTargetType.SCENE:
                    button_target_properties["scene_id"] = struct.unpack(
                        "B" * 16, button_target[:16]
                    )
                elif button_target_type_enum == ButtonTargetType.DEVICE_RELAYS:
                    button_target_properties["serial"] = struct.unpack(
                        "B" * 6, button_target[:6]
                    )
                    button_target_properties["relays_count"] = struct.unpack(
                        "B", button_target[6:7]
                    )[0]
                    button_target_properties["relays"] = struct.unpack(
                        "B" * 9, button_target[7:]
                    )
                button_action = {
                    "button_gesture": button_gesture_enum,
                    "button_target_type": button_target_type_enum,
                    "button_target": button_target_properties,
                }
                button_actions.append(button_action)
            button = {
                "actions_count": actions_count,
                "button_actions": button_actions,
            }
            buttons.append(button)

        payload = {
            "count": count,
            "index": index,
            "buttons_count": buttons_count,
            "buttons": buttons,
        }
        message = StateButton(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )

    elif message_type == MSG_IDS[StateButtonConfig]:  # 911
        haptic_duration_ms = struct.unpack("H", payload_str[0:2])[0]

        backlight_on_color_values = payload_str[2:10]
        backlight_on_color = getBacklightColor(backlight_on_color_values)

        backlight_off_color_values = payload_str[10:18]
        backlight_off_color = getBacklightColor(backlight_off_color_values)

        payload = {
            "haptic_duration_ms": haptic_duration_ms,
            "backlight_on_color": backlight_on_color,
            "backlight_off_color": backlight_off_color,
        }

        message = StateButtonConfig(
            target_addr, source_id, seq_num, payload, ack_requested, response_requested
        )
    else:
        message = Message(
            message_type,
            target_addr,
            source_id,
            seq_num,
            ack_requested,
            response_requested,
        )

    message.size = size
    message.origin = origin
    message.tagged = tagged
    message.addressable = addressable
    message.protocol = protocol
    message.source_id = source_id
    message.header = header_str
    message.payload = payload_str
    message.packed_message = packed_message

    return message


class ButtonGesture(Enum):
    NONE = 0
    PRESS = 1
    HOLD = 2
    PRESS_PRESS = 3
    PRESS_HOLD = 4
    HOLD_HOLD = 5


class ButtonTargetType(Enum):
    RESERVED = 0
    RESERVED_1 = 1
    RELAYS = 2
    DEVICE = 3
    LOCATION = 4
    GROUP = 5
    SCENE = 6
    DEVICE_RELAYS = 7


def getTile(payload_str):
    accel_meas_x = struct.unpack("h", payload_str[0:2])[0]
    accel_meas_y = struct.unpack("h", payload_str[2:4])[0]
    accel_meas_z = struct.unpack("h", payload_str[4:6])[0]
    # 6:8
    user_x = struct.unpack("f", payload_str[8:12])[0]
    user_y = struct.unpack("f", payload_str[12:16])[0]
    width = struct.unpack("B", payload_str[16:17])[0]
    height = struct.unpack("B", payload_str[17:18])[0]
    # 18:19
    device_version_vendor = struct.unpack("I", payload_str[19:23])[0]
    device_version_product = struct.unpack("I", payload_str[23:27])[0]
    # 27:31
    firmware_build = struct.unpack("Q", payload_str[31:39])[0]
    # 39:47
    firmware_version_minor = struct.unpack("H", payload_str[47:49])[0]
    firmware_version_major = struct.unpack("H", payload_str[49:51])[0]
    # 51:55

    return {
        "accel_meas_x": accel_meas_x,
        "accel_meas_y": accel_meas_y,
        "accel_meas_z": accel_meas_z,
        "user_x": user_x,
        "user_y": user_y,
        "width": width,
        "height": height,
        "device_version_vendor": device_version_vendor,
        "device_version_product": device_version_product,
        "firmware_build": firmware_build,
        "firmware_version_minor": firmware_version_minor,
        "firmware_version_major": firmware_version_major,
    }


def getBacklightColor(payload_str):
    hue = struct.unpack("H", payload_str[:2])[0]
    saturation = struct.unpack("H", payload_str[2:4])[0]
    brightness = struct.unpack("H", payload_str[4:6])[0]
    kelvin = struct.unpack("H", payload_str[6:8])[0]

    return {
        "hue": hue,
        "saturation": saturation,
        "brightness": brightness,
        "kelvin": kelvin,
    }
