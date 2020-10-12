"""\
Purpose:
Initial Version: Costas Skarakis 7/11/2020  
"""
import re

from common.server import SipServer
from sip.SipEndpoint import SipEndpoint
from sip.SipMessage import get_user_from_message
from sip.messages import message
import sip.SipFlows as sip_flows
import time


def reg_user(sip_server, register_message, expiration_in_seconds=360):
    user, address = get_user_from_message(register_message, header="Contact").split("@")
    # replacement to overcome localhost silliness
    address = address.replace("localhost", "127.0.0.1")
    sip_server.set_parameter("expires", expiration_in_seconds)
    sip_server.reply(address, message["200_OK_1"])
    sip_server.registered_addresses[user] = address


def b2b_uas(sip_server, invite):
    a = get_user_from_message(invite, header="Contact")
    b = get_user_from_message(invite)
    leg_a_dialog = invite.get_dialog()
    a_user, a_address = a.split("@")
    b_user = b.split("@")[0]
    b_address = sip_server.registered_addresses[b_user]
    if not sip_server.is_registered(a):
        sip_server.reply(message["403_Forbidden"])
    if not sip_server.is_registered(b):
        sip_server.reply(message["404_Not_Found"])
    sip_server.reply(a_address, message["Trying_1"])

    invite_b = sip_server.send_new(b_address, b_user, invite.contents())
    leg_b_dialog = invite_b.get_dialog()
    sip_server.wait_for_message("100 Trying")
    b_ringing = sip_server.wait_for_message("180 Ringing", dialog=leg_b_dialog)
    sip_server.send(a_address, b_ringing.contents(), dialog=leg_a_dialog)



if __name__ == "__main__":

    HOST, PORT = "localhost", 9999
    MockSIPTCP = SipServer(HOST, PORT)
    MockSIPTCP.serve_in_background()
    A = SipEndpoint("121242124")
    B = SipEndpoint("121242125")
    SipMock = MockSIPTCP
    SipMock.on("REGISTER", reg_user)
    SipMock.on("INVITE", b2b_uas)

    A.connect(("localhost", 6666),
              (HOST, PORT),
              "tcp")
    # B.use_link(A.link)
    B.connect(("localhost", 6667),
              (HOST, PORT),
              "tcp")

    A.register()
    B.register()
    sip_flows.basic_call(A, B, duration=10)
    # A.send(SipMock, message["Register_1"])
    # B.wait_for_message("REGISTER")
    # B.reply(message["200_OK_1"])
    # A.wait_for_message("200 OK")
    # A.send_new(B, message["Invite_SDP_1"])
    # B.wait_for_message("INVITE")
    # B.reply(message["200_OK_SDP_1"])
    # A.wait_for_message("200 OK")
    # B.send(message["Bye_1"])
    # A.wait_for_message("BYE")
    # # unfortunately our server is not a real sip server yet so there may be some
    # # inconsistencies in the dialog elements. Either that or we should make our message pool better
    # last_dialog = A.reply(message["200_OK_1"]).get_dialog()
    # B.wait_for_message("200 OK", dialog=last_dialog)


    MockSIPTCP.shutdown()
