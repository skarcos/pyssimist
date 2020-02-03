import sys
sys.path.append("..")
from sip.messages import message
from sip.SipEndpoint import SipEndpoint
from time import sleep


if __name__ == "__main__":

    params = {"sipsm_ip": "10.2.28.54",
              "sipsm_port": 5060, # usually 5061 for tls
              "local_ip": "10.4.253.10",
              "base_local_port": 13000,
              "number_of_endpoints": 2,
              "transport": "tcp", # Any of udp, tcp or tls. Don't forget to change sipsm_port for tls
              "certificate": None, # Leave empty for TLS with no certificate validation
              #"certificate": "root.pem", 
              "subject_name": "localhost", # parameter related to tls only
              "call_duration": 8}

# For OSV TSL has been verified with the following conditions:
# 1) Install UNSProotca64.rpm and download any of root.pem, client.pem and server.pem from OSV to the test directory. Set "certificate" to appropriate filename. Set subject_name to "localhost". 
#    or
# 2) Set certificate to None
#
# In general a valid certificate is needed. For the value of "subject_name" search for "Subject Alternative Name" in output of 'openssl x509 -text -in <the certificate you will use>'

    sip_server_address = (params["sipsm_ip"], params["sipsm_port"])

    ConnectionPool = [(params["local_ip"], params["base_local_port"]+i) for i in range(params["number_of_endpoints"])]

    A = SipEndpoint("302108810001")
    B = SipEndpoint("302108810002")

    A.connect(ConnectionPool[0], 
              sip_server_address, 
              params["transport"], 
              certificate=params["certificate"], 
              subject_name=params["subject_name"])
              
    B.connect(ConnectionPool[1], 
              sip_server_address, 
              params["transport"], 
              certificate=params["certificate"],
              subject_name=params["subject_name"])


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