"""\
Purpose:
Initial Version: Costas Skarakis 7/11/2020  
"""
import os
import sys

sys.path.append(os.path.join("..", ".."))

from common.server import SipServer
from sip.SipMessage import get_user_from_message
from sip.messages import message
from sip.SipParser import buildMessage
import time
from common.tc_logging import logger

CONFERENCE_ID = "112215"

message_moved = '''\
SIP/2.0 302 Moved Temporarily
Contact: <sip:{conf_id}@{source_ip}:{source_port};transport={transport}>;isFocus
Allow: INVITE, ACK, BYE, CANCEL, NOTIFY, INFO, UPDATE, OPTIONS, SUBSCRIBE, REFER
Reason: SIP;cause=302;text="Moved+Temporarily"
User-Agent: MediaServer Mock
Content-Length: 0'''


# def reg_user(sip_server, register_message, expiration_in_seconds=360):
#     user, address = get_user_from_message(register_message, header="Contact").split("@")
#     # replacement to overcome localhost silliness
#     address = address.replace("localhost", "127.0.0.1")
#     sip_server.set_parameter("expires", expiration_in_seconds)
#     register_200 = buildMessage(message["200_OK_1"])
#     register_200.make_response_to(register_message)
#     register_200["Contact"] = register_message["Contact"]
#     sip_server.reply_to(register_message, register_200.contents())
#     sip_server.registered_addresses[user] = address


def msbf_receive_invite(sip_server, invite):
    if any("sip:" + CONFERENCE_ID + "@" in invite[h] for h in invite.headers):
        ms_establish(sip_server, invite)
    else:
        msbf_redirect(sip_server, invite)


def msbf_redirect(sip_server, invite):
    sip_server.reply_to(invite, message_moved)
    sip_server.wait_for_message("ACK")


def ms_establish(sip_server, invite):
    # a = get_user_from_message(invite, header="Contact")
    # b = get_user_from_message(invite)
    a_user, a_address = get_user_from_message(invite, header="From").split("@")
    b_user, b_address = get_user_from_message(invite, header="Contact").split("@")

    # b_user = b.split("@")[0]
    # b_address = sip_server.registered_addresses[b_user]
    sip_server.reply_to(invite, message["Trying_1"])

    sip_server.set_parameter("userB", b_user)
    sip_server.set_parameter("userA", a_user)
    invite_b = buildMessage(message["Invite_SDP_1"], sip_server.sip_endpoint.parameters)
    invite_b.request_line = invite.request_line
    invite_b["X-Siemens-Call-Type"] = "Conference-Aware-BtoBUA"
    invite_b["To"] = invite["To"]
    contact_with_conf_id = buildMessage(message_moved, sip_server.sip_endpoint.parameters)["Contact"]
    invite_b["Contact"] = contact_with_conf_id
    invite_b["Route"] = "<" + contact_with_conf_id.split("<")[1].split(";")[0] + ";lr>"
    # invite_b.body = invite.body
    sip_server.send_new(b_address, b_user, invite_b.contents())

    time.sleep(0.5)
    b_ringing = sip_server.wait_for_message("180 Ringing", ignore_messages=["100 Trying"])
    leg_b_dialog = b_ringing.get_dialog()

    time.sleep(0.5)
    a_ringing = sip_server.reply_to(invite, b_ringing.contents())
    leg_a_dialog = a_ringing.get_dialog()

    time.sleep(2)
    b_ok_invite = sip_server.wait_for_message("200 OK", dialog=leg_b_dialog)
    b_ok_invite["Contact"] = invite_b["Contact"]
    sip_server.reply_to(invite, b_ok_invite.contents())

    time.sleep(0.5)
    sip_server.reply_to(b_ok_invite, message["Ack_1"])

    time.sleep(0.5)
    sip_server.wait_for_message("ACK", dialog=leg_a_dialog)
    sip_server.active_calls.append((leg_a_dialog, leg_b_dialog))


def b2b_uas_terminate(sip_server, bye):
    leg_a_dialog = bye.get_dialog()
    leg_b_dialog = sip_server.get_active_call(dialog=leg_a_dialog)
    if not leg_b_dialog:
        # try reversed tags in case b side hung up
        leg_a_dialog = {"Call-ID": leg_a_dialog["Call-ID"],
                        "to_tag": leg_a_dialog["from_tag"],
                        "from_tag": leg_a_dialog["to_tag"]}
        leg_b_dialog = sip_server.get_active_call(dialog=leg_a_dialog)
        if not leg_b_dialog:
            sip_server.reply_to(bye, message["481_Transaction_does_not_exist"])
            return
        else:
            leg_b_dialog_new = {"Call-ID": leg_b_dialog["Call-ID"],
                                "to_tag": leg_b_dialog["from_tag"],
                                "from_tag": leg_b_dialog["to_tag"]}
            sip_server.links.append((leg_b_dialog_new, sip_server.get_dialog_link(leg_b_dialog)))
            leg_b_dialog = leg_b_dialog_new

    sip_server.send(leg_b_dialog, message["Bye_1"])
    sip_server.reply_to(bye, message["200_OK_1"])

    time.sleep(0.5)
    sip_server.wait_for_message("200 OK", dialog=leg_b_dialog)


if __name__ == "__main__":
    logger.setLevel("DEBUG")
    HOST, PORT = "0.0.0.0", 15060
    MSBF = SipServer(HOST, PORT, "tcp")
    MSBF.set_parameter("conf_id", CONFERENCE_ID)
    MSBF.serve_in_background()
    MSBF.on("INVITE", msbf_receive_invite)
    MSBF.on("BYE", b2b_uas_terminate)
