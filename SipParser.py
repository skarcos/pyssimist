import re
from SipMessage import SipMessage

ENCODING="utf8"
MANDATORY_REQUEST_HEADERS=set(("To", "From", "CSeq", "Call-ID", "Max-Forwards","Via"))

def buildMessage(message,parameters):
    tString=message.strip().format(**parameters)
    bString=bytes(tString.replace("\n","\r\n")+2*"\r\n",encoding=ENCODING)
    sipMessage=parseBytes(bString)
    return sipMessage

def parseBytes(bString,sep="\r\n",encoding=ENCODING):
    #header and body are separated by an empty line
    header,body=bString.decode(encoding).split(sep+sep,maxsplit=1)
    header_lines=header.split(sep)
    request_or_response=header_lines[0]
    headers={}
    
    for line in header_lines[1:]:
        k,v=line.split(":",maxsplit=1)
        headers[str(k).strip()]=v.strip()

    #print (headers.keys())
    message=SipMessage(headers,body)
    # add more elements depending if it is a request or a responses
    resP=re.match(r"^SIP/\d\.?\d? (\d+ .*)$",request_or_response,re.I)
    if resP:
        message.type="Response"
        message.status=resP.group(1)
        message.status_line=request_or_response
    else:
        reqP=re.match(r"^(\w+) \S+ SIP/\d\.?\d?$",request_or_response,re.I)
        if not reqP:
            raise Exception ("Not a valdid request or response.. or parse logic error", request_or_response)
            #return None

        # make sure all mandatory headers are present
        missing_headers=MANDATORY_REQUEST_HEADERS.difference(set(headers.keys()))
        if missing_headers:
            raise Exception ("Mandatory headers missing",missing_headers)
            #return None
        message.type="Request"
        message.request_line=request_or_response
        message.method=reqP.group(1)
    #TODO: Implement body parsing
    return message

if __name__=="__main__":
    m=b'SIP/2.0 403 Forbidden\r\nWarning: 399 10.2.0.22 "Originating Endpoint is not configured or registered on system. Check provisioning of 3021005533, , 10.2.31.5, 10.2.0.24."\r\nCall-ID: 5bc4d2b1lKza5n\r\nCSeq: 1 OPTIONS\r\nTo: <sip:10.2.0.24:5060>\r\nFrom: <sip:3021005533@10.2.31.5:50080>;tag=snl_5bc4d2b14Y\r\nContent-Length: 0\r\nVia: SIP/2.0/TCP 10.2.31.5:50080;branch=5bc4d2b1cswcPR1cq4nQ\r\n\r\n'
    n=b'SIP/2.0 400 Bad Request\r\nWarning: 399 10.2.0.22 "Request mandatory header is missing or incorrect. Mandatory Header CSEQ-Method mismatch."\r\nVia: SIP/2.0/TCP 10.2.31.5:5080;branch=5bc619b78AKFDlh5mRGL\r\nFrom: "3021005533" <sip:3021005533@10.2.0.22:5060>;tag=snl_5bc619b7OD;epid=SCD0n\r\nCSeq: 1 OPTIONS\r\nCall-ID: 5bc619b7TTYmPW\r\nTo: <sip:10.2.0.22:5060>;tag=snl_PT47YjDdJE\r\nContent-Length: 0\r\n\r\n'
    s=parseBytes(n)
    print(s)
    i='''
INVITE sip:302108100501@10.2.31.5:4745;transport=tcp SIP/2.0
To: <sip:302108100501@10.2.31.5>
From: "Line00001" <sip:00001@10.2.0.22>;tag=snl_sWw2Lh4Inl
Call-ID: SEC11-600020a-700020a-1-23K8za03bXNI
CSeq: 1235 INVITE
Contact: <sip:00001@10.2.0.22:5060;transport=tcp;maddr=10.2.0.22>
Via: SIP/2.0/TCP 10.2.0.22:5060;branch=z9hG4bKSEC-600020a-700020a-1-e9B4b9825u
Accept-Language: en;q=0.0
Alert-Info: <Bellcore-dr1>
Allow: REGISTER, INVITE, ACK, BYE, CANCEL, NOTIFY, REFER, INFO
P-Asserted-Identity: "Line00001" <sip:00001@10.2.0.22>
Session-Expires: 1800;refresher=uac
Min-SE: 1800
Supported: timer
Date: Tue, 16 Oct 2018 19:01:31 GMT
Max-Forwards: 69
Content-Type: application/sdp
Content-Length: 0

v=0
o=Anomymous 302108100001 1234567890 IN IP4 10.2.31.5
s=SIGMA is the best
c=IN IP4 10.2.31.5
t=0 0
m=audio 6006 RTP/AVP 8 0 3
a=rtpmap:8 PCMA/8000
a=rtpmap:0 PCMU/8000
a=rtpmap:3 GSM/8000
m=video 6008 RTP/AVP 40
a=rtpmap:40 H263-1998/90000
'''
    j=buildMessage(i,{})
    print(j)
