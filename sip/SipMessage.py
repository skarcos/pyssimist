"""\
Purpose: SIP message object
Initial Version: Costas Skarakis 11/11/2018
"""

import re
import hashlib
from common import util


class SipMessage(object):
    """
    Representation of a SIP message
    """

    def __init__(self, header_dict, body):
        self.header = header_dict
        self.headers = self.header
        self.status = None
        self.method = None
        self.type = None
        self.status_line = ""
        self.request_line = ""
        self.body = body
        if body:
            self.header["Content-Length"] = str(len(body.strip()) + 2)
        else:
            self.header["Content-Length"] = "0"
        self.to_tag = ""
        self.from_tag = ""
        self.via_branch = ""
        M = re.search(r"tag=([^;]+)",self.header["To"])
        if M:
            self.to_tag = M.group(1)
        M = re.search(r"tag=([^;]+)",self.header["From"])
        if M:
            self.from_tag = M.group(1)
        M = re.search(r"branch=([^;]+)",self.header["Via"])
        if M:
            self.via_branch = M.group(1)

    def __getitem__(self, key):
        return self.header[key]

    def __setitem__(self, key, value):
        self.header[key] = value

    def __repr__(self):
        if self.from_tag:
            if "tag" in self.header["From"]:
                self.header["From"] = re.sub("tag=[^;]+", "tag=%s", self.header["From"]) % self.from_tag
            else:
                self.header["From"] = self.header["From"]+";tag="+self.from_tag

        if self.to_tag:
            if "tag" in self.header["To"]:
                self.header["To"] = re.sub("tag=[^;]+", "tag=%s", self.header["To"]) % self.to_tag
            else:
                self.header["To"] = self.header["To"] + ";tag=" + self.to_tag

        if self.via_branch:
            if "branch" in self.header["Via"]:
                self.header["Via"] = re.sub("branch=[^;]+", "branch=%s", self.header["Via"]) % self.via_branch
            else:
                self.header["Via"] = self.header["Via"] + ";branch=" + self.via_branch

        if self.type == "Request":
            first_line = self.request_line
        else:
            first_line = self.status_line
        result = first_line + "\r\n"
        result += "\r\n".join(k + ": " + v for k, v in self.header.items())
        result += "\r\n"
        result += "\r\n" + self.body
        return result

    def set_dialog_from(self, other):
        self.from_tag = other.from_tag
        self.to_tag = other.to_tag
        self.header["Call-ID"] = other["Call-ID"]

    def make_response_to(self, other):
        """ RFC 3261 Section 8.2.6.2 Headers and Tags"""
        self.set_dialog_from(other)
        self.via_branch = other.via_branch
        self["From"] = other["From"]
        self["Call-ID"] = other["Call-ID"]
        self["Via"] = other["Via"]
        if other.to_tag:
            self["To"] = other["To"]
        else:
            self.to_tag = util.randomTag()

    def __str__(self):
        return repr(self)

    def message(self):
        return repr(self)

    def contents(self):
        return self.message()

    def get_status_or_method(self):
        """" Return what kind of message this is. Handy for assertions """
        if self.type == "Request":
            return self.method
        elif self.type == "Response":
            return self.status


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
