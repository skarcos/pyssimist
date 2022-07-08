import logging.handlers
import logging.config
import os
import sys
from time import sleep

sys.path.append(os.path.join("..", ".."))
from common.tc_logging import LOG_CONFG
from common.util import Load, next_available_sip, make_available_sip
from sip.SipEndpoint import SipEndpoint
from common.view import SipEndpointView, LoadWindow
from sip.SipFlows import basic_call
from itertools import cycle
import yappi


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
    # local_address = ("172.25.255.137", 0)
    count = 0
    try:
        os.mkdir("log")
    except:
        pass

    for a in subs:
        count += 1
        local_address = ("10.4.253.13", 65535 - count)
        try:
            a.connect(local_address, sip_server_address, transport)
            a_logger = logging.getLogger(a.number)
            a.link.logger = a_logger
            a_logger.setLevel("INFO")
            handler = logging.handlers.RotatingFileHandler(os.path.join("log", a.number + ".txt"), mode="w",
                                                           maxBytes=10000, backupCount=5)
            handler.setLevel("INFO")
            a_logger.addHandler(handler)
        except OSError:
            a.busy = True
            if type(a) is SipEndpointView:
                a.colour("red")


def main():
    a_sides = cycle(a_subs)
    b_sides = cycle(b_subs)
    all_subs = a_subs + b_subs
    connect(all_subs, sipsm_address)
    try:
        register(all_subs)
        test = Load(flow, a_sides, b_sides, interval=0.1, quantity=5, duration=200)
        print("TEST STARTING")
        test.start()
        print("TEST STARTED")
        test.monitor()
    finally:
        # unregister
        register(all_subs, 0)


if __name__ == "__main__":
    # logging.config.dictConfig(LOG_CONFG)
    sipsm_address = ("10.9.65.195", 5060)
    number_of_subs = 1000
    GUI = True
    # yappi.start()
    if not GUI:
        a_subs = [SipEndpoint("15616920" + str(x).zfill(3)) for x in range(int(number_of_subs / 2))]
        b_subs = [SipEndpoint("15616920" + str(x).zfill(3)) for x in range(int(number_of_subs / 2), number_of_subs)]
        main()
    else:
        view = LoadWindow()
        a_subs = [SipEndpointView(view, "15616920" + str(x).zfill(3)) for x in range(int(number_of_subs / 2))]
        b_subs = [SipEndpointView(view, "15616920" + str(x).zfill(3)) for x in
                  range(int(number_of_subs / 2), number_of_subs)]
        view.start(main)

    # yappi.get_func_stats().print_all()
    #
    # yappi.get_thread_stats().print_all()