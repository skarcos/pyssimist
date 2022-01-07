import logging.handlers
import logging.config
import os
import sys
from time import sleep

sys.path.append(os.path.join("..", ".."))
from common.tc_logging import LOG_CONFG
from common.util import Load
# from sip.SipEndpoint import SipEndpoint
from common.view import SipEndpointView, LoadWindow
from sip.SipFlows import basic_call
from itertools import cycle


def next_available_sip(sip_pool):
    """Find the next available sip endpoint from a pool of endpoints"""
    busy = True
    a = None
    while busy:
        a = next(sip_pool)
        busy = a.busy
    if type(a) is SipEndpointView:
        a.busy = True
        a.update_text()
        a.update_arrow()
        a.colour("green")
    return a


def make_available_sip(*sip_endpoints):
    for sip_endpoint in sip_endpoints:
        sip_endpoint.busy = False
        if type(sip_endpoint) is SipEndpointView:
            sip_endpoint.colour("yellow")


def flow(pool_a, pool_b):
    a = next_available_sip(pool_a)
    b = next_available_sip(pool_b)
    basic_call(a, b, duration=8)
    make_available_sip(a, b)


def register(subs, expiration=3600):
    failed_subs = []
    for a in subs:
        try:
            a.register(expiration)
            sleep(0.1)
            print("{}egistered {}".format(["R", "Unr"][expiration == 0], a.number))
        except:
            failed_subs.append(a.number)
    if failed_subs:
        print("Failed to register:", "\n".join(failed_subs))


def connect(subs, sip_server_address, transport="tcp"):
    # local_address = ("172.25.255.96", 0)
    count = 0
    try:
        os.mkdir("log")
    except:
        pass

    for a in subs:
        count += 1
        local_address = ("localhost", 65535 - count)
        a.connect(local_address, sip_server_address, transport)
        a_logger = logging.getLogger(a.number)
        a.link.logger = a_logger
        a_logger.setLevel("DEBUG")
        handler = logging.handlers.RotatingFileHandler(os.path.join("log", a.number + ".txt"), mode="w",
                                                       maxBytes=0, backupCount=5)
        a_logger.addHandler(handler)


def main():
    a_sides = cycle(a_subs)
    b_sides = cycle(b_subs)
    all_subs = a_subs + b_subs
    connect(all_subs, sipsm_address)
    try:
        register(all_subs)
        test = Load(flow, a_sides, b_sides, interval=1, quantity=3, duration=60)
        print("TEST STARTING")
        test.start()
        print("TEST STARTED")
        test.monitor()
    finally:
        # unregister
        register(all_subs, 0)


if __name__ == "__main__":
    sipsm_address = ("localhost", 9999)
    number_of_subs = 100
    view = LoadWindow()
    a_subs = [SipEndpointView(view, "302108810" + str(x).zfill(3)) for x in range(int(number_of_subs / 2))]
    b_subs = [SipEndpointView(view, "302108811" + str(x).zfill(3)) for x in
              range(int(number_of_subs / 2), number_of_subs)]
    logging.config.dictConfig(LOG_CONFG)
    view.start(main)
