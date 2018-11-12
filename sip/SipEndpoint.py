"""\
Purpose: Simulate a SIP phone/line appearance/user
Initial Version: Costas Skarakis
"""
from sip.SipParser import parseBytes, buildMessage
import common.util as util
import common.client as client
import sip.SipFlows as flow


class SipEndpoint(object):
    """\
    Representation of a SIP Endpoint
    """

    def __init__(self, directory_number):
        """
        Set some initial attribute values
        """
        self.ip = None
        self.port = None
        self.link = None
        self.number = directory_number
        self.parameters = {"user": directory_number}
        self.last_sent_message = None
        self.last_received_message = None

    def connect(self, local_address, destination_address, protocol="tcp"):
        """ Connect to the SIP Server """
        local_ip, local_port = local_address
        dest_ip, dest_port = destination_address
        if protocol in ("tcp", "TCP"):
            self.link = client.TCPClient(local_ip, local_port)
        elif protocol in ("udp", "UDP"):
            self.link = client.UDPClient(local_ip, local_port)
        else:
            raise NotImplementedError("{} client not implemented".format(protocol))
        self.link.connect(dest_ip, dest_port)
        self.ip = local_ip
        self.port = local_port
        self.parameters["source_ip"] = local_ip
        self.parameters["source_port"] = local_port
        self.parameters["dest_ip"] = dest_ip
        self.parameters["dest_port"] = dest_port
        self.parameters["transport"] = protocol

    def start_new_dialog(self):
        """ Refresh the SIP dialog specific parameters """
        self.parameters.update({
                        "callId": util.randomCallID(),
                        "fromTag": util.randomTag(),
                        "viaBranch": util.randomBranch(),
                        "epid": lambda x=6: "SC" + util.randStr(x),
                        "cseq": 1
            }
        )

    def send_new(self, target_sip_ep=None, message_string="", expected_response=None):
        """ Start a new dialog and send a message """
        if target_sip_ep:
            self.parameters["userA"] = self.number
            self.parameters["userB"] = target_sip_ep.number
        else:
            # In cases like REGISTER, there is no B-side
            # Clear parameters to avoid unexpected results
            self.parameters.pop("userA", None)
            self.parameters.pop("userB", None)

        self.start_new_dialog()

        m = buildMessage(message_string, self.parameters)
        self.link.send(m.contents())
        self.last_sent_message = m

        if expected_response:
            try:
                self.waitForMessage(expected_response)
            except AssertionError:
                raise AssertionError('{}: "{}" response to "{}"\n{}'.format(self.number,
                                                                            self.last_received_message.status,
                                                                            self.last_sent_message.method,
                                                                            self.last_received_message))

    def send(self, message_string="", expected_response=None):
        """ Send a message within a dialog """
        self.reply(message_string)
        if expected_response:
            self.waitForMessage(expected_response)

    def reply(self, message_string):
        """ Send a response to a previously received message """
        if "callId" not in self.parameters or not self.parameters['callId']:
            raise Exception("Cannot reply when we are not in a dialog")
        m = buildMessage(message_string, self.parameters)
        for h in ("To", "From", "Via", "Call-ID"):
            m[h] = self.last_received_message[h]
        # do we need to set the to tag for all responses? check rfc3261
        if "tag=" not in m['To']:
            m['To'] += ";tag=" + util.randStr(8)
        if message_string.strip().startswith("SIP"):
            # Sip response. Use received CSeq
            m["CSeq"] = self.last_received_message["CSeq"]
        else:
            # This is not a response, but a new request in the same dialog, so fix the CSeq
            # TODO: fix CSeq according to RFC3261
            self.parameters["cseq"] += 1
            m["CSeq"] = "{} {}".format(self.parameters["cseq"], m.method)
        self.link.send(m.contents())

    def waitForMessage(self, message_type):
        """
        Wait for a specific type of SIP message.
        :message_type is a string that we will make sure is
        contained in the received message request or response line
        """
        inbytes = self.link.waitForSipData()
        inmessage = self.handleDA(self.last_sent_message, parseBytes(inbytes))
        self.last_received_message = inmessage
        assert message_type in inmessage.get_status_or_method(), \
            '{}: Got "{}" while expecting "{}"'.format(self.number, inmessage.get_status_or_method(), message_type)

    def set_digest_credentials(self, username, password, realm=""):
        """
        Set the digest authentication credentials
        :param username: digest username
        :param password: digest password
        :param realm: digest realm - no effect at the moment since it is overridden by 401 response realm
        """
        self.parameters.update({
            "da_user": username,
            "da_pass": password,
            "realm": realm
        })

    def handleDA(self, request, response):
        """" Add DA to message and send again """
        # Usual case in lab, password same as username
        if "da_pass" not in self.parameters or "da_user" not in self.parameters:
            self.set_digest_credentials(self.number, self.number, "")
        user, pwd = self.parameters["da_user"], self.parameters["da_pass"]
        if response.type=="Response" and response.status=="401 Unauthorized":
            request.addAuthorization(response["WWW-Authenticate"], user, pwd)
            self.link.send(request.contents())
            inBytes = self.link.waitForSipData()
            return parseBytes(inBytes)
        else:
            return response

    def register(self, expiration_in_seconds=360):
        """ Convenience function to register a SipEndpoint """
        flow.register(self, expiration_in_seconds)

    def unregister(self):
        """ Contenience function to un-register a SipEndpoint"""
        flow.unregister(self)
