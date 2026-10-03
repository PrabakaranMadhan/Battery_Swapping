from flask import Flask, render_template, jsonify
import time

from station import station, station_lock, station_meta
from can_driver import start_receiver
import can_driver

app = Flask(__name__)

start_receiver()

ONLINE_TIMEOUT_SEC = 3


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    now = time.time()

    with station_lock:
        compartments = {}
        for g, v in station.items():
            entry = dict(v)
            entry["sensors"] = {side: dict(s) for side, s in v["sensors"].items()}
            entry["online"] = (now - v.get("lastSeen", 0)) < ONLINE_TIMEOUT_SEC
            compartments[g] = entry

    meta = dict(station_meta)
    meta["boardCount"] = len(set(c["board"] for c in compartments.values())) if compartments else 0
    meta["compartmentCount"] = len(compartments)

    return jsonify({"compartments": compartments, "meta": meta})


@app.route("/api/relay/door/<int:compartment>/<int:state>", methods=["POST"])
def relay_door(compartment, state):
    with station_lock:
        known = compartment in station
    if not known:
        return jsonify({"ok": False, "error": "unknown compartment"}), 400

    ok = can_driver.door(compartment, bool(state))
    return jsonify({"ok": ok})


@app.route("/api/relay/smps/<int:compartment>/<int:state>", methods=["POST"])
def relay_smps(compartment, state):
    with station_lock:
        known = compartment in station
    if not known:
        return jsonify({"ok": False, "error": "unknown compartment"}), 400

    ok = can_driver.smps(compartment, bool(state))
    return jsonify({"ok": ok})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
