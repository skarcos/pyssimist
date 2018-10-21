message={"Options_1":'''\
OPTIONS sip:{dest_ip}:{dest_port};transport={transport} SIP/2.0
Call-ID: {callId}
CSeq: 1 OPTIONS
To: <sip:{dest_ip}:{dest_port}>
From: <sip:{user}@{source_ip}:{source_port}>;tag=snl_{fromTag}
User-Agent: OpenScape Voice V9R0
Content-Length: 0
Max-Forwards: 70
Via: SIP/2.0/TCP {source_ip}:{source_port};branch={viaBranch}

''',
         "Register_1":'''\
REGISTER sip:{dest_ip}:{dest_port};transport={transport} SIP/2.0
Call-ID: {callId}
CSeq: 1 REGISTER
To: <sip:{user}@{dest_ip}:{dest_port}>
From: "{user}" <sip:{user}@{dest_ip}:{dest_port}>;tag=snl_{fromTag}
User-Agent: Python tools
Content-Length: 0
Max-Forwards: 70
Via: SIP/2.0/TCP {source_ip}:{source_port};branch={viaBranch}
Accept: application/dls-contact-me
Supported: X-Siemens-Proxy-State
Contact: "{user}" <sip:{user}@{source_ip}:{source_port};transport={transport}>;expires={expires}
''',
         "Register_2":'''\
REGISTER sip:{dest_ip}:{dest_port};transport={transport} SIP/2.0
Call-ID: {callId}
CSeq: 1 REGISTER
To: <sip:{user}@{dest_ip}:{dest_port}>
From: "{user}" <sip:{user}@{dest_ip}:{dest_port}>;tag=snl_{fromTag};epid={epid}
User-Agent: Python tools
Content-Length: 0
Max-Forwards: 70
Via: SIP/2.0/TCP {source_ip}:{source_port};branch={viaBranch}
Accept: application/dls-contact-me
Supported: X-Siemens-Proxy-State
Contact: "{user}" <sip:{user}@{source_ip}:{source_port};transport={transport}>;expires={expires}
''',
         "Invite_SDP_1":'''\
INVITE sip:{userB}@{dest_ip}:{dest_port};transport={transport} SIP/2.0
Via: SIP/2.0/{transport} {source_ip}:{source_port};branch={viaBranch}
From: {userA} <sip:{userA}@{dest_ip}:{dest_port}>;tag={fromTag}
To: <sip:{userB}@{dest_ip}:{dest_port};transport={transport}>
Contact: <sip:{userA}@{source_ip}:{source_port};transport={transport}>
Content-Type: application/sdp
Call-ID: {callId}
CSeq: 1 INVITE
Max-Forwards: 70
Content-Length: {bodyLength}

v=0
o=Anomymous {userA} 1234567890 IN IP4 {source_ip}
s=SIGMA is the best
c=IN IP4 {source_ip}
t=0 0
m=audio 6006 RTP/AVP 8 0 3
a=rtpmap:8 PCMA/8000
a=rtpmap:0 PCMU/8000
a=rtpmap:3 GSM/8000
m=video 6008 RTP/AVP 40
a=rtpmap:40 H263-1998/90000
''',
         "Trying_1":'''\
SIP/2.0 100 Trying
Call-ID: Will be overwritten by incoming INVITE
CSeq: Will be overwritten by incoming INVITE
From: Will be overwritten by incoming INVITE
To: Will be overwritten by incoming INVITE
Via: Will be overwritten by incoming INVITE
Content-Length: 0
''',
         "Ringing_1":'''\
SIP/2.0 180 Ringing
Call-ID: Will be overwritten by incoming INVITE
CSeq: Will be overwritten by incoming INVITE
From: Will be overwritten by incoming INVITE
To: Will be overwritten by incoming INVITE and a tag will be added
Via: Will be overwritten by incoming INVITE
Contact: sip:{userB}@{source_ip}:{source_port};transport={transport}
Content-Length: 0
''',
         "200_OK_SDP_1":'''\
SIP/2.0 200 OK
Contact: <sip:{userB}@{source_ip}:{source_port};transport={transport}>
Call-ID: Will be overwritten by incoming INVITE
CSeq: Will be overwritten by incoming INVITE
From: Will be overwritten by incoming INVITE
To: Will be overwritten by incoming INVITE and a tag will be added
Via: Will be overwritten by incoming INVITE
Content-Type: application/sdp
Content-Length: {bodyLength}

v=0
o=Anomymous {userB} 1234567890 IN IP4 {source_ip}
s=SIGMA is the best
c=IN IP4 {source_ip}
t=0 0
m=audio 6006 RTP/AVP 8 0 3
a=rtpmap:8 PCMA/8000
a=rtpmap:0 PCMU/8000
a=rtpmap:3 GSM/8000
m=video 6008 RTP/AVP 40
a=rtpmap:40 H263-1998/90000
''',
         "Ack_1":'''\
ACK sip:{userB}@{dest_ip}:{dest_port};transport={transport};maddr={dest_ip} SIP/2.0
CSeq: 1 ACK
Via: SIP/2.0/{transport} {source_ip}:{source_port};branch={viaBranch}
To: Same as initial INVITE
From: Same as initial INVITE
Call-ID: Same as initial INVITE
Max-Forwards: 70
Content-Length: 0
''',
         "Bye_1":'''\
BYE sip:{userB}@10.2.0.22:5060;transport=tcp;maddr=10.2.0.22 SIP/2.0
Call-ID: Same as initial INVITE
CSeq: 2 BYE
Via: SIP/2.0/{transport} {source_ip}:{source_port};branch={viaBranch}
To: Same as initial INVITE
From: Same as initial INVITE
Max-Forwards: 70
Content-Length: 0
''',
         "200_OK_1":'''\
SIP/2.0 200 OK
Content-Length: 0
Call-ID: Will be overwritten by incoming BYE
CSeq: Will be overwritten by incoming BYE
From: Will be overwritten by incoming BYE
To: Will be overwritten by incoming BYE
Via: Will be overwritten by incoming BYE
'''
}
