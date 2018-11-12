"""\
Purpose: Define reusable SIP Flows
Initial Version: Costas Skarakis 11/11/2018
"""
from sip.messages import message


def register(sip_ep, expiration_in_seconds=360):
    """ Register a SIP endpoint """
    sip_ep.parameters["expires"] = expiration_in_seconds
    sip_ep.send_new(message_string=message["Register_1"], expected_response="200 OK")


def unregister(sip_ep):
    """ Un-Register a SIP endpoint """
    register(sip_ep, expiration_in_seconds=0)