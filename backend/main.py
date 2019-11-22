#!/usr/bin/python3
from concurrent.futures.thread import ThreadPoolExecutor
import time
from db import Remote
from hardware import Sensor, Actuator
from utils import GracefulKiller
import config as cfg
import argparse

override = 0


def main(device_id, graceful):
    killer = GracefulKiller()
    remote = Remote(cfg.couchdb["host"], device_id, callback, graceful)
    sensor = Sensor(cfg.sensor_ports, cfg.debug)
    actuator = Actuator(cfg.relay_port, cfg.debug)
    remote.report_summary("auto", sensor.reading, actuator.closed)
    remote.report_summary("offline", [0, 0], False)
    with ThreadPoolExecutor() as executor:
        executor.submit(report_thread, remote, sensor, actuator, killer)

        try:
            sensor_stream = sensor.stream()
            for reading in sensor_stream:
                remote.report_datagrid(reading)
                if reading[0] > cfg.limit["h2s"][1] or reading[1] > cfg.limit["nh3"][1]:
                    actuator.closed = True
                elif reading[0] < cfg.limit["h2s"][0] and reading[0] < cfg.limit["nh3"][0]:
                    actuator.closed = False
                if killer.kill_now:
                    print("[SIGTERM]")
                    sensor_stream.close()
                    del sensor
                    del actuator
                    remote.__del__()
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("[KeyboardInterrupt]")
            killer.kill_now = True
    print("[-] Main end")


def callback(event, params):
    if event == "override":
        global override
        override = params[0]


def report_thread(remote, sensor, actuator, killer):
    while not killer.kill_now:
        if override == -1:
            override_status = "force_off"
        elif override == 1:
            override_status = "force_on"
        else:
            override_status = "auto"
        remote.report_summary(override_status, sensor.reading, actuator.closed)
        time.sleep(1)
    print("[-] report thread terminated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='IoT server for BrownSense.')
    parser.add_argument('id', metavar='id', type=int, help='device id')
    parser.add_argument('--no-graceful', dest='graceful', action='store_const',
                        const=False, default=True,
                        help='don\'t inform the backend when shutdown')
    args = parser.parse_args()
    main(args.id, args.graceful)