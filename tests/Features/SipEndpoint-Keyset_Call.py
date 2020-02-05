import sys
from copy import copy

from os import path
sys.path.append(path.join("..", ".."))
from sip.messages import message
from sip.SipEndpoint import SipEndpoint
from time import sleep


def register_primary(sip_ep, expiration_in_seconds=360):
    sip_ep.parameters["expires"] = expiration_in_seconds
    sip_ep.parameters["primary"] = sip_ep.number
    sip_ep.parameters["primary_port"] = sip_ep.port
    sip_ep.send_new(message_string=message["Register_primary"], expected_response="200 OK")
    sip_ep.send_new(message_string=message["Subscribe_secondary"], expected_response="200 OK")
    sip_ep.waitForMessage("NOTIFY")
    sip_ep.reply(message_string=message["200_OK_1"])
    sip_ep.waitForMessage("SUBSCRIBE")
    sip_ep.reply(message_string=message["200_OK_1"])


def register_secondary(primary, line, expiration_in_seconds=360):
    line.parameters["expires"] = expiration_in_seconds
    line.parameters["primary"] = primary.number
    line.parameters["primary_port"] = primary.port
    line.send_new(message_string=message["Register_secondary"], expected_response="200 OK")
    line.send_new(message_string=message["Subscribe_secondary"], expected_response="200 OK")
    line.waitForMessage("NOTIFY")
    line.reply(message_string=message["200_OK_1"])
    line.waitForMessage("SUBSCRIBE")
    line.reply(message_string=message["200_OK_1"])


def add_keyset_line(primary, line_dn):
    line = SipEndpoint(line_dn)
    line.use_link(primary.link)
    register_secondary(primary, line)


def handle_notify(sip_ep):
    """ Handle NOTIFY messages and restore previous dialog """
    current_dialog = copy(sip_ep.current_dialog)
    current_transaction = copy(sip_ep.current_transaction)
    sip_ep.waitForMessage("NOTIFY")
    sip_ep.reply(message_string=message["200_OK_1"])
    sip_ep.set_dialog(current_dialog)
    sip_ep.set_transaction(current_transaction)


if __name__ == "__main__":
    params1 = {"orig_osv_sipsm_ip": "10.5.42.44",
               "orig_osv_sipsm_port": 5060,
               "local_ip": "10.5.45.19",
               "local_port": 13000,
               "transport": "tcp",
               "call_duration": 8}

    params2 = {"psap_thig_ip": "10.0.26.20",
               "psap_thig_port": 5060,
               "local_ip": "10.5.45.20",
               "local_port": 13001,
               "transport": "tcp"}

    A = SipEndpoint("302102310010")
    B = SipEndpoint("302106960219")

    A.connect((params1["local_ip"], params1["local_port"]), (params1["orig_osv_sipsm_ip"], params1["orig_osv_sipsm_port"]),
              params1["transport"])

    B.connect((params2["local_ip"], params2["local_port"]), (params2["psap_thig_ip"], params2["psap_thig_port"]),
              params2["transport"])

    A.unregister()
    B.unregister()

    A.register()
    register_primary(B)
    add_keyset_line(B,"91190")

    A.send_new(B, message["Invite_SDP_1"], expected_response="Trying")
    B.waitForMessage("INVITE")
    B.reply(message["Trying_1"])
    B.reply(message["Ringing_1"])

    handle_notify(B)

    A.waitForMessage("180 Ringing")
    B.reply(message["200_OK_SDP_1"])
    B.waitForMessage("ACK")
    A.waitForMessage("200 OK")
    A.send(message["Ack_1"])

    handle_notify(B)

    sleep(params1["call_duration"])

    A.send(message["Bye_1"], expected_response="200 OK")


    B.waitForMessage("BYE")
    B.reply(message["200_OK_1"])

    handle_notify(B)

    A.unregister()
    B.unregister()

    handle_notify(B)
