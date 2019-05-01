import sys
sys.path.append("..")
from sip.messages import message
from csta.CstaEndpoint import CstaEndpoint
from time import sleep

params = {"sipsm_ip": "10.2.28.54",
          "cstasm_ip": "10.2.28.60",
          "sipsm_port": 5060,
          "cstasm_port": 1040,
          "local_ip": "10.2.31.5",
          "base_local_port": 13000,
          "number_of_endpoints": 2,
          "transport": "tcp",
          "call_duration": 8}

ClearConnection = '''<?xml version="1.0" encoding="UTF-8"?>
<ClearConnection
  xmlns="http://www.ecma.ch/standards/ecma-323/csta/ed2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="
      http://www.ecma.ch/standards/ecma-323/csta/ed2  file://localhost/X:/ips_bln/long_csta/ecma/clear-connection.xsd
  ">
  <connectionToBeCleared>
    <deviceID>{deviceID}</deviceID>
    <callID>{callID}</callID>
  </connectionToBeCleared>
</ClearConnection>
'''

sip_server_address = (params["sipsm_ip"], params["sipsm_port"])
csta_server_address = (params["cstasm_ip"], params["cstasm_port"])

ConnectionPool = [(params["local_ip"], params["base_local_port"]+i) for i in range(params["number_of_endpoints"])]

A = CstaEndpoint("302118840100")
B = CstaEndpoint("302118840101")

A.sip_connect(ConnectionPool[0], sip_server_address, params["transport"])
B.sip_connect(ConnectionPool[1], sip_server_address, params["transport"])

A.csta_connect(csta_server_address)
B.csta_connect(csta_server_address)

A.register()
B.register()

A.monitor_start()
B.monitor_start()

A.send_csta("MakeCall", B)
A.waitForCstaMessage("MakeCallResponse")

A.waitForMessage("INVITE")
A.send_sip(message["200_OK_SDP_1"])


B.waitForMessage("INVITE")
B.send_sip(message["Trying_1"])
B.send_sip(message["Ringing_1"])

A.waitForCstaMessage("ServiceInitiatedEvent")
A.waitForCstaMessage("OriginatedEvent")

B.send_sip(message["200_OK_SDP_1"])
B.waitForMessage("ACK")

A.waitForMessage("ACK")

A.waitForCstaMessage("DeliveredEvent")
B.waitForCstaMessage("DeliveredEvent")

A.waitForMessage("INVITE")
A.send_sip(message["200_OK_SDP_1"])

B.waitForMessage("INVITE")
B.send_sip(message["200_OK_SDP_1"])
B.waitForMessage("ACK")
A.waitForMessage("ACK")


A.waitForCstaMessage("EstablishedEvent")
B.waitForCstaMessage("EstablishedEvent")

sleep(2)

A.send_csta(ClearConnection)
A.waitForCstaMessage("ClearConnectionResponse")

A.waitForMessage("BYE")
A.reply(message["200_OK_1"])
B.waitForMessage("BYE")
B.reply(message["200_OK_1"])


A.waitForCstaMessage("ConnectionClearedEvent")
B.waitForCstaMessage("ConnectionClearedEvent")

A.unregister()
B.unregister()