import os
import sys
from time import sleep

sys.path.append(os.path.join("..", ".."))
from common.tc_logging import info, logger
from common.util import Load
from sip.SipEndpoint import SipEndpoint
from sip.SipFlows import basic_call
from itertools import cycle

sipsm_address = ("10.2.23.102", 5060)
number_of_subs = 400
a_subs = [SipEndpoint("302108810" + str(x).zfill(3)) for x in range(int(number_of_subs / 2))]
b_subs = [SipEndpoint("302108811" + str(x).zfill(3)) for x in range(int(number_of_subs / 2), number_of_subs)]
logger.setLevel("INFO")


def flow(pool_a, pool_b):
    a = next(pool_a)
    b = next(pool_b)
    basic_call(a, b, duration=8)


def register(subs, expiration=3600):
    failed_subs = []
    for a in subs:
        try:
            a.register(expiration)
            sleep(0.1)
            info("{}egistered {}".format(["R", "Unr"][expiration == 0], a.number))
        except:
            failed_subs.append(a.number)
    if failed_subs:
        print("Failed to register:", "\n".join(failed_subs))


def connect(subs, sip_server_address, transport="tcp"):
    # local_address = ("172.25.255.96", 0)
    count = 0
    for a in subs:
        count += 1
        local_address = ("172.25.255.96", 65535 - count)
        a.connect(local_address, sip_server_address, transport)


if __name__ == "__main__":
    a_sides = cycle(a_subs)
    b_sides = cycle(b_subs)
    all_subs = a_subs + b_subs
    connect(all_subs, sipsm_address)
    try:
        register(all_subs)
        test = Load(flow, a_sides, b_sides, interval=1, quantity=40, duration=300)
        test.start()
        test.monitor()
    finally:
        # unregister
        register(all_subs, 0)
