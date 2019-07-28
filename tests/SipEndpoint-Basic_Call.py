import sys
sys.path.append("..")
from sip.messages import message
from sip.SipEndpoint import SipEndpoint
from time import sleep


if __name__ == "__main__":

    params = {"sipsm_ip": "10.2.28.54",
              "sipsm_port": 5060,
              "local_ip": "10.5.45.19",
              "base_local_port": 13000,
              "number_of_endpoints": 2,
              "transport": "tcp",
              "call_duration": 8}

    sip_server_address = (params["sipsm_ip"], params["sipsm_port"])

    # ConnectionPool = [("10.2.31.5", 13001), ("10.2.31.5", 13001)]u
    ConnectionPool = [(params["local_ip"], params["base_local_port"]+i) for i in range(params["number_of_endpoints"])]

    A = SipEndpoint("302108810001")
    B = SipEndpoint("302108810002")

    A.connect(ConnectionPool[0], sip_server_address, params["transport"])
    B.connect(ConnectionPool[1], sip_server_address, params["transport"])


    A.register()
    B.register()

    A.send_new(B, message["Invite_SDP_1"], expected_response="Trying")
    B.waitForMessage("INVITE")
    B.reply(message["Trying_1"])
    B.reply(message["Ringing_1"])
    A.waitForMessage("180 Ringing")
    B.reply(message["200_OK_SDP_1"])
    B.waitForMessage("ACK")
    A.waitForMessage("200 OK")
    A.send(message["Ack_1"])

    sleep(params["call_duration"])

    A.send(message["Bye_1"], expected_response="200 OK")
    B.waitForMessage("BYE")
    B.reply(message["200_OK_1"])

    A.unregister()
    B.unregister()