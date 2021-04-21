from common.util import Load
from sip.SipEndpoint import SipEndpoint
from sip.SipFlows import basic_call
from itertools import cycle

sipsm_address = ("localhost", 9999)
number_of_subs = 500
a_subs = [SipEndpoint("30210881" + str(x).zfill(4)) for x in range(int(number_of_subs/2))]
b_subs = [SipEndpoint("30210882" + str(x).zfill(4)) for x in range(int(number_of_subs/2), number_of_subs)]


def flow(pool_a, pool_b):
    a = next(pool_a)
    b = next(pool_b)
    basic_call(a, b, duration=8)


def register(subs, expiration=3600):
    for a in subs:
        a.register(expiration)


def connect(subs, sip_server_address, transport="tcp"):
    local_address = ("127.0.0.1", 0)
    for a in subs:
        a.connect(local_address, sip_server_address, transport)


if __name__ == "__main__":
    a_sides = cycle(a_subs)
    b_sides = cycle(b_subs)
    all_subs = a_subs + b_subs
    connect(all_subs, sipsm_address)
    try:
        register(all_subs)
        test = Load(flow, a_sides, b_sides, interval=1, quantity=1, duration=10)
        test.start()
        test.monitor()
    finally:
        # unregister
        register(all_subs, 0)
