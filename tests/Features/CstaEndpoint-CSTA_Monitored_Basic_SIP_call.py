import sys
from os import path
sys.path.append(path.join("..", ".."))
from sip.messages import message
from csta.CstaEndpoint import CstaEndpoint
from time import sleep
import sip.SipFlows as SipFlows

params = {"sipsm_ip": "10.2.28.54",
          "cstasm_ip": "10.2.28.60",
          "sipsm_port": 5060,
          "cstasm_port": 1040,
          "local_ip": "10.4.253.10",
          "base_local_port": 13000,
          "number_of_endpoints": 2,
          "transport": "tcp",
          "call_duration": 8}

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

A.start_new_incoming_event_thread(role="A")
B.start_new_incoming_event_thread(role="B")

SipFlows.basic_call(A, B)

A.unregister()
B.unregister()
