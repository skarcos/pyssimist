from client import TCPClient
import util
message={"A":'''\
OPTIONS sip:{dest_ip}:{dest_port};transport={transport} SIP/2.0
Call-ID: {callId}
CSeq: 1 OPTIONS
To: <sip:{dest_ip}:{dest_port}>
From: <sip:{user}@{sourceIP}:{sourcePort}>;tag=snl_{fromTag}
User-Agent: OpenScape Voice V9R0
Content-Length: 0
Max-Forwards: 70
Via: SIP/2.0/TCP {sourceIP}:{sourcePort};branch={viaBranch}

'''.replace("\n","\r\n"),
         "B":'''\
SIP/2.0 200 OK
Call-ID: {any}
CSeq: 1 OPTIONS
From: <sip:survivabilityprovider@10.5.111.100>;tag=2002523463
To: <sip:sipserver@10.5.111.56:5161;transport=TLS>;tag=SEC11-a70050a-a70050a-1-4BW18Fm8vXem
Via: SIP/2.0/TLS 10.5.111.100:5061;branch=z9hG4bK8081.221dd174bcecbac6d9b3928928ff8171.0;i=1
Via: SIP/2.0/TCP 10.5.111.100;branch=z9hG4bK83973b84
Via: SIP/2.0/TLS 10.5.111.100:5161;branch=z9hG4bK349799b9
Content-Length: 0'''
}

parameters={"dest_ip":"192.168.1.70",
            "dest_port":9999,
            "transport":"tcp",
            "callId":util.randomCallID(),
            "user":"3021005533",
            "fromTag":util.randomFromTag(),
            "sourceIP":util.getLocalIP(),
            "sourcePort":50003,
            "viaBranch":util.randomBranch()
            }

m=message["A"].format(**parameters)
print(m)

C=TCPClient(parameters["sourceIP"],parameters["sourcePort"])
C.connect(parameters["dest_ip"],parameters["dest_port"])
C.send(m)

C.waitForData()
