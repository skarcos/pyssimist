import re
from SipMessage import SipMessage

ENCODING="utf8"
MANDATORY_REQUEST_HEADERS=set(("To", "From", "CSeq", "Call-ID", "Max-Forwards","Via"))

def prepareMessage(message,parameters):
    tString=message.format(**parameters)
    bString=bytes(tString.replace("\n","\r\n"),encoding=ENCODING)
    sipMessage=parseBytes(bString)
    return sipMessage.message()

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
    resP=re.match(r"^SIP/\d\.?\d? (\d+ \w+)$",request_or_response,re.I)
    if resP:
        message.type="Response"
        message.status=resP.group(1)
        message.status_line=request_or_response
    else:
        reqP=re.match(r"^(\w+) \S+ SIP/\d\.?\d?$",request_or_response,re.I)
        if not reqP:
            return None

        # make sure all mandatory headers are present
        missing_headers=MANDATORY_REQUEST_HEADERS.difference(set(headers.keys()))
        if missing_headers:
            print("Mandatory headers missing",missing_headers)
            return None
        message.type="Request"
        message.request_line=request_or_response
        message.method=reqP.group(1)
    #TODO: Implement body parsing
    return message

if __name__=="__main__":
    m=b'SIP/2.0 403 Forbidden\r\nWarning: 399 10.2.0.22 "Originating Endpoint is not configured or registered on system. Check provisioning of 3021005533, , 10.2.31.5, 10.2.0.24."\r\nCall-ID: 5bc4d2b1lKza5n\r\nCSeq: 1 OPTIONS\r\nTo: <sip:10.2.0.24:5060>\r\nFrom: <sip:3021005533@10.2.31.5:50080>;tag=snl_5bc4d2b14Y\r\nContent-Length: 0\r\nVia: SIP/2.0/TCP 10.2.31.5:50080;branch=5bc4d2b1cswcPR1cq4nQ\r\n\r\n'
    s=parseBytes(m)
    print(s)
