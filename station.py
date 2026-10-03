import threading

COMPARTMENTS_PER_BOARD = 3
SENSOR_SIDES = ["A", "B", "C", "D"]

# Populated automatically as boards report in over CAN - no need to list
# board IDs by hand. See can_driver.py's receiver thread.
station = {}
station_lock = threading.Lock()

station_meta = {
    "name": "Battery Swapping Station",
    "firmware": "1.1.0",
    "company": "Your Company Name",
}


def global_compartment(board, local_compartment):
    """Board 1 -> compartments 1,2,3. Board 2 -> 4,5,6. Board 3 -> 7,8,9. etc."""
    return (board - 1) * COMPARTMENTS_PER_BOARD + local_compartment


def board_and_local(global_compartment_num):
    """Inverse of global_compartment() - needed to address a relay command
    back to the right board+local compartment over CAN."""
    board = (global_compartment_num - 1) // COMPARTMENTS_PER_BOARD + 1
    local = (global_compartment_num - 1) % COMPARTMENTS_PER_BOARD + 1
    return board, local


def ensure_compartment(board, local_compartment):
    """Create this compartment's entry the first time we ever hear from its
    board - this is what makes board 2 showing up automatically produce
    compartments 4/5/6 with no manual configuration."""
    g = global_compartment(board, local_compartment)

    if g not in station:
        station[g] = {
            "board": board,
            "localCompartment": local_compartment,
            "door": "UNKNOWN",
            "doorRelay": "OFF",
            "smpsRelay": "OFF",
            "battery": "NO",
            "lastSeen": 0,
            "sensors": {side: {"temperature": 0.0, "present": 0} for side in SENSOR_SIDES},
        }

    return g
