import sys
import traceback
from copy import copy
from threading import Timer

from os import path
sys.path.append(path.join("..", ".."))

from common.tc_logging import debug, warning
from sip.SipParser import parseBytes
from common import util
from sip.messages import message
from sip.SipEndpoint import SipEndpoint
from time import sleep
from itertools import cycle


def notify_after_subscribe(sip_ep, subscribe_dialog):
    # cd = dict(subscribe_dialog)
    # subscribe = sip_ep.get_last_message_in(cd)
    # cd["to_tag"] = util.randomTag()
    cd = sip_ep.reply(message_string=message["200_OK_1"], dialog=subscribe_dialog).get_dialog()

    notify_dialog = {"Call-ID": cd["Call-ID"],
                     "from_tag": cd["to_tag"],
                     "to_tag": cd["from_tag"]}
    # subscribe.set_dialog_from(notify_dialog)
    # sip_ep.save_message(subscribe)
    sip_ep.send(message_string=message["Notify_terminated_1"], expected_response="200 OK", dialog=notify_dialog)


def register_primary(sip_ep, secondary_numbers,expiration_in_seconds=360):
    sip_ep.re_register_timer = Timer(expiration_in_seconds/2, register_primary, (sip_ep, secondary_numbers, expiration_in_seconds))
    sip_ep.re_register_timer.start()
    sip_ep.parameters["expires"] = expiration_in_seconds
    sip_ep.parameters["primary"] = sip_ep.number
    sip_ep.parameters["primary_port"] = sip_ep.port
    if not sip_ep.parameters["epid"]:
        sip_ep.parameters["epid"] = "SC" + util.randStr(6)
    debug("Sent register from "+sip_ep.number)
    sip_ep.send_new(message_string=message["Register_primary"], expected_response="200 OK")
    debug("Got 200OK to register from " + sip_ep.number)
    if not sip_ep.secondary_lines:
        # first registration
        for n in secondary_numbers:
            line = SipEndpoint(n)
            line.use_link(sip_ep.link)
            sip_ep.secondary_lines.append(line)

    for line in sip_ep.secondary_lines:
        sleep(0.1)
        register_secondary(sip_ep, line)

    subscribe_primary(sip_ep)
    for line in sip_ep.secondary_lines:
        try:
            subscribe_secondary(line)
            line.registered = True
        except:
            debug(traceback.format_exc())
            raise
        debug("Subscribed " + line.number + " on " + sip_ep.number)
    sip_ep.registered = True


def subscribe_primary(sip_ep):
    sip_ep.send_new(message_string=message["Subscribe_secondary"], expected_response="200 OK")
    sip_ep.waitForMessage("NOTIFY").get_dialog()
    sip_ep.reply(message_string=message["200_OK_1"])
    subscribe_dialog = sip_ep.waitForMessage("SUBSCRIBE").get_dialog()
    notify_after_subscribe(sip_ep, subscribe_dialog)
    sleep(2)


def register_secondary(primary, line, expiration_in_seconds=360):
    line.parameters["expires"] = expiration_in_seconds
    line.parameters["primary"] = primary.number
    line.parameters["primary_port"] = primary.port
    retry_count = 10
    for _ in range(retry_count):
        try:
            line.send_new(message_string=message["Register_secondary"], expected_response="200 OK")
            debug("Registered " + line.number + " on " + primary.number)
            break
        except AssertionError:
            sleep(2)


def subscribe_secondary(line):
    line.send_new(message_string=message["Subscribe_secondary"], expected_response="200 OK")
    for msg in line.wait_for_messages("NOTIFY", "SUBSCRIBE"):
        msg_type = msg.get_status_or_method()
        if msg_type == "NOTIFY":
            line.reply(message_string=message["200_OK_1"])
        elif msg_type == "SUBSCRIBE":
            notify_after_subscribe(line, msg.get_dialog())


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
    sip_ep.re_register_timer.cancel()


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


def setup(A, B, secondaryNumbers, user_address_pool, call_taker_address_pool, registration_expiration=360):
    B.connect(next(call_taker_address_pool),
              (params2["psap_thig_ip"],
               params2["psap_thig_port"]),
              params2["transport"])

    # Semi-Ugly way to handle OPTIONS messages from OSV when we don't shut down correctly :TODO
    B.link.register_for_event(("OPTIONS", {}, message["200_OK_1"]))

    try:
        register_primary(B, secondaryNumbers, expiration_in_seconds=registration_expiration)
    except:
        B.registered = False
        #debug(traceback.format_exc())
        traceback.print_exc()

    A.connect(next(user_address_pool),
              (params1["orig_osv_sipsm_ip"],
               params1["orig_osv_sipsm_port"]),
              params1["transport"])
    A.link.register_for_event(("OPTIONS", {}, message["200_OK_1"]))

    try:
        A.register(expiration_in_seconds=registration_expiration, re_register_time=registration_expiration/2)
    except:
        A.registered = False
        debug(traceback.format_exc())


def wait_for_call(B, c_index):
    C = B.secondary_lines[c_index]
    debug(C.number + " waiting for calls from device " + B.number)
    invite_dialogs = {}
    while not B.shutdown:
        try:
            # wait for any of the following messages
            inmessage = B.wait_for_message(["INVITE", "ACK", "CANCEL", "BYE", "NOTIFY", "SUBSCRIBE", "200 OK"])

            inmessage_type = inmessage.get_status_or_method()
            to_number = inmessage["To"].split("@")[0].split(":")[1]
            line = [a for a in [B]+B.secondary_lines if a.number == to_number][0]
            line.set_dialog(inmessage.get_dialog())
            line.set_transaction(inmessage.get_transaction())
            line.save_message(inmessage)

            if inmessage_type == "INVITE":
                line.reply(message["Trying_1"])
                line.reply(message["Ringing_1"])
                if line is C:
                    if not C.registered:
                        warning("Line {}@{}:{} is not registered".format(C.number, C.ip, C.port))
                    line.reply(message["200_OK_SDP_1"])
                    print(C.number,"on",B.number,"picked up call from",inmessage["From"].split("<")[0])
                else:
                    invite_dialogs[line.number] = inmessage.get_dialog()

            elif inmessage_type in ("ACK", "200 OK"):
                # Should we make sure all expected ACK have been received?
                continue

            elif inmessage_type == "CANCEL":
                line.reply(message["200_OK_1"])
                line.send(message["487_Request_Terminated"], dialog=invite_dialogs[line.number])
                invite_dialogs.pop(line.number)

            elif inmessage_type in ("BYE", "NOTIFY"):
                line.reply(message["200_OK_1"])

            elif inmessage_type == "SUBSCRIBE":
                notify_after_subscribe(line, inmessage.get_dialog())
                # line.reply(message["200_OK_1"])
                # line.send(message_string=message["Notify_terminated_1"])

            else:
                raise Exception("Unexpected message received: " + inmessage_type)

        except TimeoutError:
            continue

        except:
            debug("ERROR on B side: device "+B.number)
            debug(traceback.format_exc())
            continue

    debug(B.number + " exited")


def flow(users, secondary_numbers):
    A = next(users)
    dial_number = next(secondary_numbers)
    try:

        print("{} will dial {}".format(A.number, dial_number))
        debug(A.number + "Sends invite to " + dial_number)
        A.send_new(dial_number, message["Invite_SDP_1"])
        debug(A.number + "Waiting 200 OK to INVITE from " + dial_number)
        A.waitForMessage("200 OK", ignore_messages=["100 Trying", "180 Ringing"])
        A.send(message["Ack_1"])

        sleep(params1["call_duration"])

        A.send(message["Bye_1"], expected_response="200 OK")

        debug("SUCCESSFUL CALL: {} to {} ".format(A.number, dial_number))
    except KeyboardInterrupt:
        print("Stopping test")
        raise
    except:
        debug("FAILED CALL on A side: {} to {} ".format(A.number, dial_number))
        debug(traceback.format_exc())


def tear_down(A, B):
    A.unregister()
    unregister_primary(B)


if __name__ == "__main__":

    number_of_call_takers = 10
    number_of_secondary_lines = 10
    number_of_users = 10

    params1 = {"orig_osv_sipsm_ip": "10.5.42.44", "orig_osv_sipsm_port": 5060, "transport": "TCP", "call_duration": 10}

    params2 = {"psap_thig_ip": "10.0.26.20", "psap_thig_port": 5060, "transport": "TCP"}

    user_numbers = ("3021023" + str(i) for i in range(10010, 10010 + number_of_users))
    call_taker_numbers = ("3021069" + str(i) for i in range(60210, 60210 + number_of_call_takers))
    secondary_numbers = ["911"+str(i) for i in range(90, 90 + number_of_secondary_lines)]

    users = [SipEndpoint(a) for a in user_numbers]
    call_takers = [SipEndpoint(b) for b in call_taker_numbers]
    secondary_lines = range(number_of_secondary_lines)

    user_pool = util.pool(users, lambda x: x.registered)
    #call_taker_pool = util.pool(call_takers, lambda x: x.registered)
    secondary_line_pool = cycle(secondary_numbers)

    user_port_pool = (("10.5.45.19", port)
                      for port in
                      range(13000, 13000+number_of_users))

    call_taker_ip_pool = (("10.5.45."+str(i), 5566)
                          for i in
                          range(20, 20+number_of_call_takers))
    agentThreads = []

    try:
        for user, call_taker in zip(users, call_takers):
            setup(user, call_taker, secondary_numbers, user_port_pool, call_taker_ip_pool, 3600)
            sleep(0.5)

        for call_taker, secondary_line in zip(call_takers, secondary_lines):
            call_taker.shutdown = False
            agentThreads.append(util.serverThread(wait_for_call, call_taker, secondary_line))
            sleep(0.1)

        test = util.Load(flow,
                         user_pool,
                         secondary_line_pool,
                         duration=5*60*60,
                         quantity=1,
                         interval=2)
        test.start()
        test.monitor()
    finally:
        for user, call_taker in zip(users, call_takers):
            call_taker.shutdown = True
            tear_down(user, call_taker)

        for thread in agentThreads:
            thread.result()
