"""\
Purpose: SIP message object
Initial Version: Costas Skarakis 11/11/2018
"""

import re
import hashlib
from common import util


def get_user_from_message(sip_message, header=None):
    pattern = r"<?sip:([^;>]*).*[>;]"
    if not header:
        header_value = sip_message.request_line
    else:
        header_value = sip_message[header]
    M = re.search(pattern, header_value)
    if M:
        return M.group(1)
    else:
        return None


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
            self.header["Content-Length"] = str(len(body.strip()) + 4)
        else:
            self.header["Content-Length"] = "0"
        self.to_tag = ""
        self.from_tag = ""
        self.via_branch = ""
        if "To" in self.header:
            M = re.search(r"tag=([^;]+)", self.header["To"])
            if M:
                self.to_tag = M.group(1)
        if "From" in self.header:
            M = re.search(r"tag=([^;]+)", self.header["From"])
            if M:
                self.from_tag = M.group(1)
        if "Via" in self.header:
            M = re.search(r"branch=([^;]+)", self.header["Via"])
            if M:
                self.via_branch = M.group(1)

    def __hash__(self):
        return hash(repr(self))

    def __eq__(self, other):
        """
        Override equality operator to return comparison based on string comparison

        :param other: The other string message or SipMessage to compare against
        :return: True or False
        """
        if isinstance(other, str):
            other_contents = other
        elif isinstance(other, SipMessage):
            other_contents = repr(other)
        else:
            raise Exception("Can only compare SipMessage to str or SipMessage, "
                            "not {}".format(type(other)))

        return repr(self) == other_contents

    def __getitem__(self, key):
        for k in self.header:
            # handle different letter case
            if k.upper() == key.upper():
                return self.header[k]
        raise KeyError("%s not in message headers" % key)

    def __setitem__(self, key, value):
        self.header[key] = value

    def __repr__(self):
        if self.from_tag:
            if "tag" in self.header["From"]:
                self.header["From"] = re.sub("tag=[^;]+", "tag=%s", self.header["From"]) % self.from_tag
            else:
                self.header["From"] = self.header["From"] + ";tag=" + self.from_tag

        if self.to_tag:
            if "tag" in self.header["To"]:
                self.header["To"] = re.sub("tag=[^;]+", "tag=%s", self.header["To"]) % self.to_tag
            else:
                self.header["To"] = self.header["To"] + ";tag=" + self.to_tag
        else:
            if "tag" in self.header["To"]:
                self.header["To"] = self.header["To"].split(";tag=")[0]

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
        result += "\r\n".join(k.split("#")[0] + ": " + v for k, v in self.header.items())
        result += "\r\n"
        result += "\r\n" + self.body
        return result

    def get_transaction(self):
        try:
            cseq, method = self.header["CSeq"].split()
        except:
            cseq, method = self.header["cseq"].split()
        return {"via_branch": self.via_branch,
                "cseq": cseq,
                "method": method
                }

    def get_dialog(self):
        return {"Call-ID": self["Call-ID"],
                "to_tag": self.to_tag,
                "from_tag": self.from_tag}

    def get_dialog_string(self):
        """

        :return: Dialog string in CallID:FromTag:ToTag format
        """
        return "%s:%s:%s" % (self["Call-ID"], self.from_tag, self.to_tag)

    def set_dialog_from(self, other):
        """
        Set current dialog elements from another sip message, or dialog string, or dialog dict
        :SipMessage other: The message/dict/string to get the dialog elements from
        """
        if type(other) == type(self):
            self.from_tag = other.from_tag
            self.to_tag = other.to_tag
            self.header["Call-ID"] = other["Call-ID"]
        elif isinstance(other, dict):
            self.from_tag = other["from_tag"]
            self.to_tag = other["to_tag"]
            self.header["Call-ID"] = other["Call-ID"]
        elif isinstance(other, str):
            self.header["Call-ID"], self.from_tag, self.to_tag = other.split(":")
        else:
            raise Exception("Cannot set SipMessage dialog from %s" % type(other))

    def set_transaction_from(self, other):
        """
        Set current transaction elements from another sip message, or dialog string, or dialog dict
        :SipMessage other: The message/dict/string to get the transaction elements from
        """
        if type(other) == type(self):
            self.via_branch = other.via_branch
            method = self.method if self.method else other.method
            cseq = self.header["CSeq"].split()[0]
            self.header["CSeq"] = " ".join([cseq, method])
        elif isinstance(other, dict):
            self.via_branch = other["via_branch"]
            method = self.method if self.method else other["method"]
            self.header["CSeq"] = " ".join([other["cseq"], method])
        elif isinstance(other, str):
            self.header["CSeq"], self.via_branch = other.split(":")
        else:
            raise Exception("Cannot set SipMessage transaction from %s" % type(other))

    def make_response_to(self, other, dialog={}):
        """ RFC 3261 Section 8.2.6.2 Headers and Tags
        :dict dialog: The current sip dialog we are in, represented by
            a dictionary with keys as in the return type of self.get_dialog()
        """
        self.set_dialog_from(other)
        self.via_branch = other.via_branch
        self["From"] = other["From"]
        self["Call-ID"] = other["Call-ID"]
        if self.type == "Response":
            # Update Via only when we send a response.
            # Otherwise adjust this request for the current dialog
            self["Via"] = other["Via"]
        # else:
        #     self["Via"] = "SIP/2.0/{} {}:{};branch={}".format(self.proto, self.ip, self.port, self.via_branch)
        self["To"] = other["To"]
        if not other.to_tag:
            # This is useful when we make a response to an initial invite.
            # The invite has no to tag. But we made one for Trying
            # and now we must use it for Ringing as well.
            if "to_tag" in dialog and dialog["to_tag"]:
                self.to_tag = dialog["to_tag"]
            else:
                self.to_tag = util.randomTag()
        return self.get_dialog()

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
