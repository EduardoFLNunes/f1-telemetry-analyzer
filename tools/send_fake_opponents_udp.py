import argparse
import json
import math
import socket
import time


def build_payload(start_time, car_count, track):
    now = time.time()
    elapsed = now - start_time
    cars = []
    for index in range(car_count):
        car_id = index + 1
        angle = elapsed * (0.35 + index * 0.08) + index * 2.0
        radius = 80.0 + index * 18.0
        cars.append(
            {
                "carId": car_id,
                "driverName": "Fake Opponent %s" % car_id,
                "carModel": "debug_car",
                "isPlayer": False,
                "isAI": True,
                "worldPosition": {
                    "x": math.cos(angle) * radius,
                    "y": 0.0,
                    "z": math.sin(angle) * radius,
                },
                "speedKmh": 130.0 + math.sin(angle) * 35.0,
                "yaw": angle + math.pi / 2.0,
                "splinePosition": (elapsed * 0.02 + index * 0.12) % 1.0,
                "lap": int(elapsed // 90.0) + 1,
                "lapTime": elapsed % 90.0,
                "racePosition": car_id + 1,
                "status": "on_track",
            }
        )

    return {
        "type": "opponents_snapshot",
        "timestamp": now,
        "sessionTime": elapsed,
        "playerCarId": 0,
        "track": track,
        "cars": cars,
    }


def main():
    parser = argparse.ArgumentParser(description="Send fake opponents telemetry snapshots over UDP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--hz", type=float, default=20.0)
    parser.add_argument("--cars", type=int, default=3)
    parser.add_argument("--track", default="ks_interlagos")
    args = parser.parse_args()

    interval = 1.0 / max(args.hz, 1.0)
    car_count = max(args.cars, 0)
    start_time = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Sending fake opponents to %s:%s at %.1f Hz" % (args.host, args.port, args.hz))
    try:
        while True:
            payload = build_payload(start_time, car_count, args.track)
            sock.sendto(json.dumps(payload).encode("utf-8"), (args.host, args.port))
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
