"""\
Purpose: SIP message object
Initial Version: Costas Skarakis 11/11/2018
"""

import re
import hashlib
import time


class SipMessage(object):
    """
    Representation of a SIP message
    """

    def __init__(self, header_dict, body):
        self.header = header_dict
        self.headers = self.header
        self.body = body
        if body:
            self.header["Content-Length"] = str(len(body.strip()) + 2)

    def __getitem__(self, key):
        return self.header[key]

    def __setitem__(self, key, value):
        self.header[key] = value

    def __repr__(self):
        if self.type == "Request":
            first_line = self.request_line
        else:
            first_line = self.status_line
        result = first_line + "\r\n"
        result += "\r\n".join(k + ": " + v for k, v in self.header.items())
        result += "\r\n"
        result += "\r\n" + self.body
        return result

    def __str__(self):
        return repr(self)

    def message(self):
        return repr(self)

    def contents(self):
        return self.message()

    def increase_cseq(self):
        cseq, method = self.header["CSeq"].split()
        self["CSeq"] = " ".join([str(int(cseq) + 1), method])

    def addAuthorization(self, indata, user, pwd):
        """indata is the WWW-Authenticate header we received"""
        self.increase_cseq()
        md5_a1hash = hashlib.md5()
        md5_a2hash = hashlib.md5()
        md5_responsehash = hashlib.md5()

        data = [x.split("=") for x in indata.split(',')]
        D = dict((x[0].strip(), x[1].strip()) for x in data)
        Uri = re.search("sip:(.*) SIP", self.request_line)
        User = user
        RemoteIP = Uri.group(1)
        NcStr = "00000001"  # str(int(time.time()))
        RealmStr = D["Digest realm"][1:-1]
        NonceStr = D["nonce"][1:-1]
        CnonceStr = "970b9994"
        UriStr = "sip:" + RemoteIP
        md5_a1hash.update(bytes(User + ":" + RealmStr + ":" + pwd, encoding="utf8"))
        MD5_A1Str = md5_a1hash.hexdigest()
        md5_a2hash.update(bytes(self.method + ":" + UriStr, encoding="utf8"))
        MD5_A2Str = md5_a2hash.hexdigest()
        md5_responsehash.update(bytes(MD5_A1Str + ":" +
                                      NonceStr + ":" +
                                      NcStr + ":" +
                                      CnonceStr + ":" +
                                      "auth" + ":" +
                                      MD5_A2Str, encoding="utf8"))
        MD5_ResponseStr = md5_responsehash.hexdigest()
        authorization = 'Digest response="{}",'
        authorization += 'nc={},'
        authorization += 'username="{}",'
        authorization += 'realm="{}",'
        authorization += 'nonce="{}",'
        authorization += 'algorithm=MD5,'
        authorization += 'qop=auth,'
        authorization += 'cnonce="{}",'
        authorization += 'uri="{}"'
        authorization = authorization.format(MD5_ResponseStr,
                                             NcStr,
                                             User,
                                             RealmStr,
                                             NonceStr,
                                             CnonceStr,
                                             UriStr)
        self.__setitem__("Authorization", authorization)


if __name__ == "__main__":
    pass
