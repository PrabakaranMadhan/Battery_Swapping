from ctypes import *
import threading
import time

from station import station, station_lock, ensure_compartment, global_compartment, board_and_local, SENSOR_SIDES

# ======================================================
# Waveshare / USB-CAN-B adapter bindings
# ======================================================

VCI_USBCAN2 = 4
STATUS_OK = 1

# Must match Config/can_config.h and can_protocol.h on every STM32 board exactly
CAN_ID_BOARD_SHIFT = 7
CAN_ID_MSGTYPE_SHIFT = 4
CAN_ID_COMPARTMENT_MASK = 0x0F

CAN_MSG_STATUS = 0x0
CAN_MSG_CMD_DOOR = 0x1
CAN_MSG_CMD_SMPS = 0x2
CAN_MSG_TEMP = 0x3

SIDE_BY_NUMBER = {1: "A", 2: "B", 3: "C", 4: "D"}


class VCI_INIT_CONFIG(Structure):
    _fields_ = [
        ("AccCode", c_uint),
        ("AccMask", c_uint),
        ("Reserved", c_uint),
        ("Filter", c_ubyte),
        ("Timing0", c_ubyte),
        ("Timing1", c_ubyte),
        ("Mode", c_ubyte)
    ]


class VCI_CAN_OBJ(Structure):
    _fields_ = [
        ("ID", c_uint),
        ("TimeStamp", c_uint),
        ("TimeFlag", c_ubyte),
        ("SendType", c_ubyte),
        ("RemoteFlag", c_ubyte),
        ("ExternFlag", c_ubyte),
        ("DataLen", c_ubyte),
        ("Data", c_ubyte * 8),
        ("Reserved", c_ubyte * 3)
    ]


canDLL = None


# ======================================================
# CAN ID helpers - must mirror can_config.h exactly
# ======================================================

def build_can_id(board, msgtype, local_compartment):
    return ((board & 0x0F) << CAN_ID_BOARD_SHIFT) | ((msgtype & 0x07) << CAN_ID_MSGTYPE_SHIFT) | (local_compartment & CAN_ID_COMPARTMENT_MASK)


def parse_can_id(can_id):
    board = (can_id >> CAN_ID_BOARD_SHIFT) & 0x0F
    msgtype = (can_id >> CAN_ID_MSGTYPE_SHIFT) & 0x07
    local_compartment = can_id & CAN_ID_COMPARTMENT_MASK
    return board, msgtype, local_compartment


def decode_temp(byte_hi, byte_lo):
    raw = (byte_hi << 8) | byte_lo
    if raw >= 0x8000:
        raw -= 0x10000  # sign-extend 16-bit
    return raw / 100.0


# ======================================================
# Initialize USB-CAN
# ======================================================

def init_can():
    global canDLL

    canDLL = cdll.LoadLibrary("./libcontrolcan.so")

    if canDLL.VCI_OpenDevice(VCI_USBCAN2, 0, 0) != STATUS_OK:
        raise Exception("Open Device Failed")

    cfg = VCI_INIT_CONFIG(0x80000008, 0xFFFFFFFF, 0, 0, 0x00, 0x1C, 0)

    if canDLL.VCI_InitCAN(VCI_USBCAN2, 0, 0, byref(cfg)) != STATUS_OK:
        raise Exception("CAN Init Failed")

    if canDLL.VCI_StartCAN(VCI_USBCAN2, 0, 0) != STATUS_OK:
        raise Exception("CAN Start Failed")

    print("===================================")
    print("USB-CAN Connected")
    print("CAN Started")
    print("===================================")


# ======================================================
# Receiver Thread
# ======================================================

def receiver():
    obj = VCI_CAN_OBJ()

    while True:
        ret = canDLL.VCI_Receive(VCI_USBCAN2, 0, 0, byref(obj), 1, 0)

        if ret > 0:
            board, msgtype, local_compartment = parse_can_id(obj.ID)

            if local_compartment < 1 or local_compartment > 3:
                continue  # not a valid compartment-addressed frame

            with station_lock:
                g = ensure_compartment(board, local_compartment)
                entry = station[g]

                if msgtype == CAN_MSG_STATUS and obj.DataLen >= 5:
                    data = list(obj.Data)
                    entry["door"] = "OPEN" if data[1] else "CLOSED"
                    entry["doorRelay"] = "ON" if data[2] else "OFF"
                    entry["smpsRelay"] = "ON" if data[3] else "OFF"
                    entry["battery"] = "YES" if data[4] else "NO"
                    entry["lastSeen"] = time.time()

                elif msgtype == CAN_MSG_TEMP and obj.DataLen >= 5:
                    data = list(obj.Data)
                    side = SIDE_BY_NUMBER.get(data[1])

                    if side:
                        entry["sensors"][side]["temperature"] = decode_temp(data[2], data[3])
                        entry["sensors"][side]["present"] = data[4]
                        entry["lastSeen"] = time.time()

        time.sleep(0.001)


def start_receiver():
    init_can()
    t = threading.Thread(target=receiver, daemon=True)
    t.start()
    print("CAN Receiver Started")


# ======================================================
# Send Command
# ======================================================

def send_command(msgtype, board, local_compartment, state):
    obj = VCI_CAN_OBJ()

    obj.ID = build_can_id(board, msgtype, local_compartment)
    obj.SendType = 0
    obj.RemoteFlag = 0
    obj.ExternFlag = 0
    obj.DataLen = 2

    obj.Data[0] = local_compartment
    obj.Data[1] = state

    ret = canDLL.VCI_Transmit(VCI_USBCAN2, 0, 0, byref(obj), 1)

    return ret == STATUS_OK


# ======================================================
# Helper APIs - take a GLOBAL compartment number, translate
# to the right board + local compartment for addressing
# ======================================================

def door(global_compartment_num, state):
    board, local = board_and_local(global_compartment_num)
    return send_command(CAN_MSG_CMD_DOOR, board, local, 1 if state else 0)


def smps(global_compartment_num, state):
    board, local = board_and_local(global_compartment_num)
    return send_command(CAN_MSG_CMD_SMPS, board, local, 1 if state else 0)
