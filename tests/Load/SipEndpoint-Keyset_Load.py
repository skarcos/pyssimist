import sys
from copy import copy
from threading import Timer

from os import path
sys.path.append(path.join("..", ".."))

from common.tc_logging import debug
from sip.SipParser import parseBytes
from common import util
from sip.messages import message
from sip.SipEndpoint import SipEndpoint
from time import sleep
from itertools import cycle


def notify_after_subscribe(sip_ep, notify_dialog):
    cd = dict(notify_dialog)
    subscribe = sip_ep.get_last_message_in(cd)
    cd["to_tag"] = util.randomTag()
    sip_ep.reply(message_string=message["200_OK_1"], dialog=cd)
    cd = sip_ep.current_dialog
    notify_dialog = {"Call-ID": cd["Call-ID"],
                     "from_tag": cd["to_tag"],
                     "to_tag": cd["from_tag"]}
    subscribe.set_dialog_from(notify_dialog)
    sip_ep.save_message(subscribe)
    sip_ep.send(message_string=message["Notify_terminated_1"], expected_response="200 OK", dialog=notify_dialog)


def register_primary(sip_ep, expiration_in_seconds=360):
    sip_ep.parameters["expires"] = expiration_in_seconds
    sip_ep.parameters["primary"] = sip_ep.number
    sip_ep.parameters["primary_port"] = sip_ep.port
    if not sip_ep.parameters["epid"]:
        sip_ep.parameters["epid"] = "SC" + util.randStr(6)
    sip_ep.send_new(message_string=message["Register_primary"], expected_response="200 OK")
    sip_ep.send_new(message_string=message["Subscribe_secondary"], expected_response="200 OK")
    subscribe_dialog = sip_ep.waitForMessage("NOTIFY").get_dialog()
    #subscribe_dialog = sip_ep.current_dialog
    sip_ep.reply(message_string=message["200_OK_1"])
    notify_dialog = sip_ep.waitForMessage("SUBSCRIBE").get_dialog()
    notify_after_subscribe(sip_ep, notify_dialog)
    sip_ep.link.register_for_event(("SUBSCRIBE", {}, message["200_OK_1"]))
    sip_ep.link.register_for_event(("NOTIFY", subscribe_dialog, message["200_OK_1"]))
    sip_ep.link.register_for_event(("CANCEL", {}, ""))

def register_secondary(primary, line, expiration_in_seconds=360):
    line.parameters["expires"] = expiration_in_seconds
    line.parameters["primary"] = primary.number
    line.parameters["primary_port"] = primary.port
    line.send_new(message_string=message["Register_secondary"], expected_response="200 OK", ignore_messages=["SUBSCRIBE"])
    line.send_new(message_string=message["Subscribe_secondary"], expected_response="200 OK")
    subscribe_dialog = line.waitForMessage("NOTIFY").get_dialog()
    # subscribe_dialog = line.current_dialog
    line.reply(message_string=message["200_OK_1"])
    #line.waitForMessage("SUBSCRIBE")
    #line.reply(message_string=message["200_OK_1"])
    # notify_after_subscribe(line)
    line.link.register_for_event(("NOTIFY", subscribe_dialog, message["200_OK_1"]))
    line.link.register_for_event(("SUBSCRIBE", {}, message["200_OK_1"]))
    #line.link.register_for_event(("CANCEL", {}, ""))


def unregister_primary(sip_ep):
    for line in sip_ep.secondary_lines:
        unregister_secondary(sip_ep, line)
    sip_ep.parameters["expires"] = 0
    sip_ep.parameters["primary"] = sip_ep.number
    sip_ep.parameters["primary_port"] = sip_ep.port
    sip_ep.send_new(message_string=message["Register_primary"])
#    sip_ep.waitForMessage("NOTIFY")
#    sip_ep.reply(message_string=message["200_OK_1"])
#    sip_ep.send_new(message_string=message["Subscribe_secondary"], expected_response="200 OK")
#     for msg in sip_ep.wait_for_messages("SUBSCRIBE", "200 OK"):
#         if msg == "SUBSCRIBE":
#             sip_ep.reply(message_string=message["200_OK_1"])
    sip_ep.wait_for_message("200 OK")


def unregister_secondary(primary, line):
    line.parameters["expires"] = 0
    line.parameters["primary"] = primary.number
    line.parameters["primary_port"] = primary.port
    line.send_new(message_string=message["Register_secondary"])
#    line.waitForMessage("NOTIFY")
#    line.reply(message_string=message["200_OK_1"])
#    line.send_new(message_string=message["Subscribe_secondary"], expected_response="200 OK")
    line.waitForMessage("200 OK")
    # line.waitForMessage("SUBSCRIBE")
    # line.reply(message_string=message["200_OK_1"])


def add_keyset_line(primary, line_dn):
    line = SipEndpoint(line_dn)
    line.use_link(primary.link)
    register_secondary(primary, line)
    primary.secondary_lines.append(line)
    return line


def handle_notify(sip_ep):
    """ Handle NOTIFY messages and restore previous dialog """
    current_dialog = copy(sip_ep.current_dialog)
    current_transaction = copy(sip_ep.current_transaction)
    sip_ep.waitForMessage("NOTIFY")
    sip_ep.reply(message_string=message["200_OK_1"])
    sip_ep.set_dialog(current_dialog)
    sip_ep.set_transaction(current_transaction)


def setup(A, B, secondaryNumbers, user_address_pool, call_taker_address_pool):
    A.connect(next(user_address_pool),
              (params1["orig_osv_sipsm_ip"],
               params1["orig_osv_sipsm_port"]),
              params1["transport"])
    A.link.register_for_event(("OPTIONS", {}, message["200_OK_1"]))

    B.connect(next(call_taker_address_pool),
              (params2["psap_thig_ip"],
               params2["psap_thig_port"]),
              params2["transport"])

    # Semi-Ugly way to handle OPTIONS messages from OSV when we don't shut down correctly :TODO
    B.link.register_for_event(("OPTIONS", {}, message["200_OK_1"]))

    A.register()
    register_primary(B)


    for n in secondaryNumbers:
        print("Adding", n, "to", B.number)
        add_keyset_line(B, n)
        sleep(0.5)

    # Will handle Notify messages that
    # B.link.register_for_event(("NOTIFY", {}, message["200_OK_1"]))

    # Reregister timer
    Timer(300.0, setup, args=[A, B, secondaryNumbers, user_address_pool, call_taker_address_pool]).start()


def flow(users, call_taker_pool, call_takers, secondary_numbers):

    A = next(users)
    B = next(call_taker_pool)
    line_appearance_index = next(secondary_numbers)
    C = B.secondary_lines[line_appearance_index]
    all_device_appearances = [device.secondary_lines[line_appearance_index] for device in call_takers]
    appearance_invite_dialogs = {}

    print("{} will dial {} and device {} will pickup".format(A.number, C.number, B.number))

    A.send_new(C, message["Invite_SDP_1"])
    invite = C.waitForMessage("INVITE")
    assert "sip:" + C.number + "@" in invite["To"]
    C.reply(message["Trying_1"])
    C.reply(message["Ringing_1"])

    invited_lines = []

    for appearance in all_device_appearances:
        if appearance is not C:
            try:
                dialog = appearance.waitForMessage("INVITE", timeout=0.1).get_dialog()
                appearance.reply(message["Trying_1"])
                appearance.reply(message["Ringing_1"])
                invited_lines.append((appearance, dialog))
            except TimeoutError:
                pass

    A.waitForMessage("180 Ringing", ignore_messages="100 Trying")
    C.reply(message["200_OK_SDP_1"])

    A.waitForMessage("200 OK")
    A.send(message["Ack_1"])

    C.waitForMessage("ACK")

    for appearance, dialog in invited_lines:
        try:
            appearance.set_dialog(dialog)
            appearance.waitForMessage("CANCEL")
            appearance.reply(message["200_OK_1"])
            appearance.send(message["487_Request_terminated"], dialog=dialog)
            appearance.waitForMessage("ACK")
        except TimeoutError:
            # Is it OK if some lines that got invite don't get CANCEL? Maybe if they get busy meanwhile.
            pass

    sleep(params1["call_duration"])

    A.send(message["Bye_1"], expected_response="200 OK")

    C.waitForMessage("BYE")
    C.reply(message["200_OK_1"])
    debug("SUCCESSFUL CALL: {} dial {} device {} pickup".format(A.number, C.number, B.number))


def tear_down(A, B):
    A.unregister()
    unregister_primary(B)


if __name__ == "__main__":

    number_of_call_takers = 10
    number_of_secondary_lines = 10
    number_of_users = 10

    params1 = {"orig_osv_sipsm_ip": "10.5.42.44", "orig_osv_sipsm_port": 5060, "transport": "TCP", "call_duration": 8}

    params2 = {"psap_thig_ip": "10.0.26.20", "psap_thig_port": 5060, "transport": "TCP"}

    user_numbers = ("3021023" + str(i) for i in range(10010, 10010 + number_of_users))
    call_taker_numbers = ("3021069" + str(i) for i in range(60210, 60210 + number_of_call_takers))
    secondaryNumbers = ["911"+str(i) for i in range(90, 90 + number_of_secondary_lines)]

    users = [SipEndpoint(a) for a in user_numbers]
    call_takers = [SipEndpoint(b) for b in call_taker_numbers]
    secondary_lines = range(number_of_secondary_lines)

    user_pool = cycle(users)
    call_taker_pool = cycle(call_takers)
    secondary_line_pool = cycle(secondary_lines)

    user_port_pool = (("10.5.45.19", port)
                       for port in
                       range(13000, 13000+number_of_users))

    call_taker_ip_pool = (("10.5.45."+str(i), 5566)
                          for i in
                          range(20, 20+number_of_call_takers))

    try:
        for user, call_taker in zip(users, call_takers):
            setup(user, call_taker, secondaryNumbers, user_port_pool, call_taker_ip_pool)
            sleep(0.5)

        # flow(user_pool, call_taker_pool, call_takers, secondary_line_pool)
        # sleep(15)
        # flow(user_pool, call_taker_pool, call_takers, secondary_line_pool)

        test = util.Load(flow,
                         user_pool,
                         call_taker_pool,
                         call_takers,
                         secondary_line_pool,
                         duration=-1,
                         quantity=1,
                         interval=2)
        test.start()
        test.monitor()
    finally:
        for user, call_taker in zip(users, call_takers):
            tear_down(user, call_taker)

