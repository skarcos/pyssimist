import sys
from os import path
sys.path.append(path.join("..", ".."))
from common.client import TCPClient
from sip.SipParser import parseBytes,prepareMessage
from sip.messages import message
from common import util

parameters={"dest_ip":"10.2.0.22",
            "dest_port":5060,
            "transport":"tcp",
            "callId": util.randomCallID(),
            "user":"302108100000",
            "fromTag": util.randomTag(),
            "sourceIP": util.getLocalIP(),
            "sourcePort":5080,
            "viaBranch": util.randomBranch(),
            "epid":"SC" + util.randHex(3),
            "expires":"360"
            }

# Open the connection
C=TCPClient(parameters["sourceIP"],parameters["sourcePort"])
C.connect(parameters["dest_ip"],parameters["dest_port"])

# Register
m=prepareMessage(message["Register_1"],parameters)
print(m)

C.send(m)

inmessage=C.waitForData()
response=parseBytes(inmessage)
print(response)
assert response.status=="200 OK"


# Unregister
parameters["expires"]="0"
m=prepareMessage(message["Register_1"],parameters)
print(m)

C.send(m)

inmessage=C.waitForData()
response=parseBytes(inmessage)
print(response)
assert response.status=="200 OK"

# Close the connection
#C.close()
# If I don't though, the socket remains open, else it goes into TIME_WAIT for 3 minutes
