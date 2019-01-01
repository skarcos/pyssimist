"""\
Purpose: Functions for parsing SIP messages and creating SipMessage objects
Initial Version: Costas Skarakis 11/11/2018
"""
import re
from _http.HttpMessage import HttpMessage

ENCODING = "utf8"

def buildMessage(message, parameters):
    # remove whitespace from start and end TODO test this change on existing testcases
    message = re.sub("\n +","\n",message)
    tString = message.strip().format(**parameters)
    # replace new lines
    bString = bytes(tString.replace("\n", "\r\n").replace("\r\r\n", "\r\n") + 2 * "\r\n", encoding=ENCODING)
    builtMessage = parseBytes(bString)
    return builtMessage


def parseBytes(bString, sep="\r\n", encoding=ENCODING):
    # header and body are separated by an empty line
    header, body = bString.decode(encoding).split(sep + sep, maxsplit=1)
    header_lines = header.split(sep)
    request_or_response = header_lines[0]
    headers = {}

    for line in header_lines[1:]:
        k, v = line.split(":", maxsplit=1)
        headers[str(k).strip()] = v.strip()

    # print (headers.keys())
    message = HttpMessage(headers, body)
    # add more elements depending if it is a request or a responses
    resP = re.match(r"^HTTP/\d\.?\d? (\d+ .*)$", request_or_response, re.I)
    if resP:
        message.type = "Response"
        message.status = resP.group(1)
        message.status_line = request_or_response
    else:
        reqP = re.match(r"^(\w+) \S+ HTTP/\d\.?\d?$", request_or_response, re.I)
        if not reqP:
            raise Exception("Not a valdid request or response.. or parse logic error", request_or_response)
            # return None

        # make sure all mandatory headers are present
#        missing_headers = MANDATORY_REQUEST_HEADERS.difference(set(headers.keys()))
#        if missing_headers:
#            raise Exception("Mandatory headers missing", missing_headers)
            # return None
        message.type = "Request"
        message.request_line = request_or_response
        message.method = reqP.group(1)
    # TODO: Implement body parsing
    return message


if __name__ == "__main__":
    i = '''GET / HTTP/1.1
Host: su.ff.avast.com
Accept: */*
Content-Type: application/octet-stream
Pragma: no-cache
Connection: keep-alive


'''
    j = buildMessage(i, {})
    print(j.contents())
