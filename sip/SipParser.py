"""\
Purpose: Functions for parsing SIP messages and creating SipMessage objects
Initial Version: Costas Skarakis 11/11/2018
"""
import re
from sip.SipMessage import SipMessage

ENCODING = "utf8"
MANDATORY_REQUEST_HEADERS = {"To", "From", "CSeq", "Call-ID", "Max-Forwards"}
SPECIAL_CASE_HEADERS = {"Call-ID", "CSeq", "X-Siemens-OSS"}


def buildMessage(message, parameters={}):
    # remove whitespace from start and end TODO test this change on existing testcases
    message = re.sub("\n +", "\n", message)
    tString = message.strip().format(**parameters)
    # replace new lines
    bString = bytes(tString.replace("\n", "\r\n").replace("\r\r\n", "\r\n") + 2 * "\r\n", encoding=ENCODING)
    sipMessage = parseBytes(bString)
    return sipMessage


def parseBytes(bString, sep="\r\n", encoding=ENCODING):
    # header and body are separated by an empty line
    header, body = bString.decode(encoding).split(sep + sep, maxsplit=1)
    header_lines = header.split(sep)
    request_or_response = header_lines[0]
    headers = {}
    count = 0
    for line in header_lines[1:]:
        k, v = line.split(":", maxsplit=1)
        key = str(k).strip()
        if key in headers:
            count += 1
            key = key + "#{}".format(count)
        headers[key] = v.strip()

    # print (headers.keys())
    titled_headers = dict((h.title(), headers[h]) for h in headers)
    case_switched_headers = {}
    for h in titled_headers:
        case_switched_headers[h] = titled_headers[h]
        for special_h in SPECIAL_CASE_HEADERS:
            if h.capitalize() == special_h.capitalize():
                case_switched_headers.pop(h)
                case_switched_headers[special_h] = titled_headers[h]
                break
    message = SipMessage(case_switched_headers, body)
    # add more elements depending if it is a request or a responses
    resP = re.match(r"^SIP/\d\.?\d? (\d+ .*)$", request_or_response, re.I)
    if resP:
        message.type = "Response"
        message.status = resP.group(1)
        message.status_line = request_or_response
    else:
        reqP = re.match(r"^(\w+) \S+ SIP/\d\.?\d?$", request_or_response, re.I)
        if not reqP:
            raise Exception("Not a valid request or response.. or parse logic error", request_or_response)
            # return None

        # make sure all mandatory headers are present
        capital_mandatory_headers = set(h.capitalize() for h in MANDATORY_REQUEST_HEADERS)
        capital_message_headers = set(h.capitalize() for h in headers.keys())
        missing_headers = capital_mandatory_headers.difference(capital_message_headers)
        # missing_headers = MANDATORY_REQUEST_HEADERS.difference(set(headers.keys()))
        if missing_headers:
            raise Exception("Mandatory headers missing", missing_headers)
            # return None
        message.type = "Request"
        message.request_line = request_or_response
        message.method = reqP.group(1)
    # TODO: Implement body parsing
    return message


if __name__ == "__main__":
    m = b'SIP/2.0 403 Forbidden\r\nWarning: 399 10.2.0.22 "Originating Endpoint is not configured or registered on system. Check provisioning of 3021005533, , 10.2.31.5, 10.2.0.24."\r\nCall-ID: 5bc4d2b1lKza5n\r\nCSeq: 1 OPTIONS\r\nTo: <sip:10.2.0.24:5060>\r\nFrom: <sip:3021005533@10.2.31.5:50080>;tag=snl_5bc4d2b14Y\r\nContent-Length: 0\r\nVia: SIP/2.0/TCP 10.2.31.5:50080;branch=5bc4d2b1cswcPR1cq4nQ\r\n\r\n'
    n = b'SIP/2.0 400 Bad Request\r\nWarning: 399 10.2.0.22 "Request mandatory header is missing or incorrect. Mandatory Header CSEQ-Method mismatch."\r\nVia: SIP/2.0/TCP 10.2.31.5:5080;branch=5bc619b78AKFDlh5mRGL\r\nFrom: "3021005533" <sip:3021005533@10.2.0.22:5060>;tag=snl_5bc619b7OD;epid=SCD0n\r\nCSeq: 1 OPTIONS\r\nCall-ID: 5bc619b7TTYmPW\r\nTo: <sip:10.2.0.22:5060>;tag=snl_PT47YjDdJE\r\nContent-Length: 0\r\n\r\n'
    s = parseBytes(n)
    i = '''
   REGISTER sip:10.0.0.1:5060;transport=UDP SIP/2.0
   CSeq: 0 REGISTER
   Call-ID: 1253634160-1253634161-7867113566_SubA-1253634162
   From: 7867113566 <sip:7867113566@10.0.0.1>;epid=7867113566_SubA;tag=359368062
   To: 7867113566 <sip:7867113566@10.0.0.1>
   User-Agent: 
   Expires: 300
   Contact: <sip: 7867113566@10.0.0.2:3566;lr;transport=UDP>
   Via: SIP/2.0/UDP 10.0.0.2:3566;branch=z9hG4bK359368062.17428.1
   Via: SIP/2.0/UDP 10.0.0.3:3566;branch=z9hG4bK359368062.17428.1
   Via: SIP/2.0/UDP 10.0.0.2:3566;branch=z9hG4bK_STANDARD_reboot_with_Authen_Proxy_3-109_1253634158-1
   Route: <sip:7867113566@10.0.0.2:5060;lr;transport=UDP>
   Route: <sip:7867113566@10.0.0.3:5060;lr;transport=UDP>
   Path: <sip:10.0.0.2:5060;transport=UDP;lr>
   Max-Forwards: 70
   Content-Length: 0
'''
    j = buildMessage(i, {})
    s.make_response_to(j)
    x = '''SIP/2.0 202 Accepted
Via: SIP/2.0/TCP esrp.rnspn1.rnsp.california.ng911:5060;branch=z9hG4bKSEC-4d2a050a-4f2a050a-1-H666LTmfe6
record-route: <sip:10.5.42.58:50202;transport=tcp;gwIP=esrp.lane1.dc1.california.ng911~5060~tcp~tcp-5060-tls-5061;oss=bcf-10.09.00.00-1;ftag=snl_0qe665y4ZJ;lr>
contact: <sip:esrpn1@10.5.42.58:50202;transport=tls>
To: "esrpn1" <sip:esrpn1@esrp.lane1.dc1.california.ng911:5060>;tag=SEC11-20ea8c0-60ea8c0-1-w99HwH86Rdgx
From: <sip:rnspn1@esrp.rnspn1.rnsp.california.ng911:5060>;tag=snl_0qe665y4ZJ
X-Siemens-OSS: OpenScape SBC V10 R9.00.00-1/BCF/THIG
Date: Thu, 14 Jan 2021 08:57:17 GMT
call-id: SEC11-4d2a050a-4f2a050a-1-72tEETFIm13o
cseq: 1235 SUBSCRIBE
expires: 2811
content-length: 0'''
    y = '''NOTIFY sip:rnspn1@esrp.rnspn1.rnsp.california.ng911:5060;transport=tcp SIP/2.0
Via: SIP/2.0/TCP [fd00:10:2:8::4]:5061;branch=z9hG4bKdc13.38795be9c926ccdf9ce6c0ba3a91cee9.0;i=16
max-forwards: 69
contact: <sip:esrpn1@esrp.lane1.dc1.california.ng911:5060;transport=tcp>
to: "rnspn1" <sip:rnspn1@esrp.rnspn1.rnsp.california.ng911:5061;transport=tls>;tag=snl_0qe665y4ZJ
from: "esrpn1" <sip:esrpn1@esrp.lane1.dc1.california.ng911:5061;transport=tls>;tag=SEC11-20ea8c0-60ea8c0-1-w99HwH86Rdgx
Date: Thu, 14 Jan 2021 08:57:17 GMT
call-id: SEC11-4d2a050a-4f2a050a-1-72tEETFIm13o
cseq: 1 NOTIFY
content-type: application/vnd.nena.ElementState+xml
subscription-state: active;expires=2811
event: nena-ElementState
content-length: 220
X-Siemens-OSS: OpenScape SBC V10 R9.00.00-1/BCF/THIG

<?xml version="1.0" encoding="UTF-8" ?>
<?xml-stylesheet type="text/xsl" href="elementState.xsl"?>
<ElementState>
    <State>Normal</State>
    <Reason>The element is operating normally.</Reason>
</ElementState>'''
    # print(s.contents())
    ack = '''    ACK sip:302102433001@10.2.31.5:23001;transport=TCP SIP/2.0
    To: <sip:432001@10.2.31.5>;tag=605b7f97rxqy
    From: "Line31001" <sip:431001@10.3.28.112>;tag=snl_Pn97QmG639
    Call-ID: SEC11-6a1c030a-6b1c030a-1-38N4keA0mC7X
    CSeq: 1235 ACK
    Contact: <sip:431001@10.3.28.112:5060;transport=tcp;maddr=10.3.28.112>
    Via: SIP/2.0/TCP 10.3.28.112:5060;branch=z9hG4bKSEC-6a1c030a-6b1c030a-1-DIXL92Tf3A
    Allow: REGISTER, INVITE, ACK, BYE, CANCEL, NOTIFY, REFER, INFO
    Date: Wed, 24 Mar 2021 18:06:16 GMT
    Max-Forwards: 69
    Content-Length: 0'''
    bye = 'BYE sip:SUB_A_ext5@dest_ip:5060;transport=transport;maddr=dest_ip SIP/2.0\n' \
          'Max-Forwards: 70\n' \
          'From: "Line32001" <sip:SUB_B@local_ip:23001>;tag=SubC0-128_33b5341b194b49304833e5e8354c10e9-0\n' \
          'To: <sip:SUB_A_ext5@dest_ip>;tag=snl_6AL2CobU0a\n' \
          'Call-ID: SEC11-a7d980a-a7d980a-1-REgtx7XF0W45\n' \
          'Supported: timer\n' \
          'User-Agent: optiPoint 410_420/V7 V7 R0.11.0 M5T SIP Stack/4.0.24.24\n' \
          'CSeq: 1 BYE\n' \
          'Via: SIP/2.0/tcp local_ip:23001;branch=z9hG4bK1765806562.2480.1\n' \
          'Content-Length: 0\n' \
          '\n'
    ackm = buildMessage(ack, {})
    print(ackm.contents())
    byem = buildMessage(bye, {})
    print(byem.contents())
    byem.make_response_to(ackm)
    print(byem.contents())


