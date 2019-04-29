"""\
Purpose: Define reusable SIP Flows
Initial Version: Costas Skarakis 11/11/2018
"""
from sip.messages import message
from time import sleep


def register(sip_ep, expiration_in_seconds=360):
    """ Register a SIP endpoint """
    sip_ep.parameters["expires"] = expiration_in_seconds
    sip_ep.send_new(message_string=message["Register_1"], expected_response="200 OK")


def unregister(sip_ep):
    """ Un-Register a SIP endpoint """
    register(sip_ep, expiration_in_seconds=0)


def basic_call(A, B, duration=2):
    """ Basic SIP Call flow between two SIP Endpoints
    A calls B. B answers. A hangs up after the duration.

    :A: The caller
    :B: The callee
    :duration: The duration of the call
    """
    A.send_new(B, message["Invite_SDP_1"], expected_response="Trying")
    B.waitForMessage("INVITE")
    B.reply(message["Trying_1"])
    B.reply(message["Ringing_1"])
    A.waitForMessage("180 Ringing")
    B.reply(message["200_OK_SDP_1"])
    B.waitForMessage("ACK")
    A.waitForMessage("200 OK")
    A.send(message["Ack_1"])

    sleep(duration)

    A.send(message["Bye_1"], expected_response="200 OK")
    B.waitForMessage("BYE")
    B.reply(message["200_OK_1"])