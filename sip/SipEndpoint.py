"""\
Purpose: Simulate a SIP phone/line appearance/user
Initial Version: Costas Skarakis
"""
from common.tc_logging import exception
from sip.SipParser import parseBytes, buildMessage
import common.util as util
import common.client as client
import sip.SipFlows as flow
from copy import copy


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
        self.parameters = {"user": directory_number,
                           "callId": None,
                           "fromTag": None,
                           "viaBranch": None,
                           "epid": None,
                           "cseq": None
                           }
        self.last_messages_per_dialog = []
        self.dialogs = []
        self.requests = []
        self.current_dialog = {
            "Call-ID": None,
            "from_tag": None,
            "to_tag": None
            # "epid": None,
        }

        self.current_transaction = {"via_branch": None,
                                    "cseq": "0",
                                    "method": None
                                    }

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

    def update_to_tag(self, in_dialog):
        """
        Update the to_tag on an existing dialog that has no to_tag
        :param in_dialog: the complete dialog
        :return: None
        """
        for dialog in self.dialogs:
            if dialog["Call-ID"] == in_dialog["Call-ID"] \
                    and dialog["from_tag"] == in_dialog["from_tag"]\
                    and not dialog["to_tag"]:
                dialog["to_tag"] = in_dialog["to_tag"]

    def get_complete_dialog(self, in_dialog):
        """
        Look for a complete existing dialog in case the provided one doesn't have a to tag
        :param in_dialog: the possibly incomplete dialog
        :return: in_dialog if it is complete or a corresponding complete one is not found,
                otherwise an existing corresponding complete dialog
        """
        if in_dialog["to_tag"]:
            return in_dialog
        for dialog in self.dialogs:
            if dialog["Call-ID"] == in_dialog["Call-ID"] \
                    and dialog["from_tag"] == in_dialog["from_tag"]\
                    and dialog["to_tag"]:
                return dialog
        return in_dialog

    def use_link(self, link):
        """ Convenience function to use an existing network connection"""
        protocol = ["TCP", "UDP"][link.socket.proto]
        local_ip = link.ip
        local_port = link.port
        dest_ip = link.rip
        dest_port = link.rport
        self.link = link
        self.ip = local_ip
        self.port = local_port
        self.parameters["source_ip"] = local_ip
        self.parameters["source_port"] = local_port
        self.parameters["dest_ip"] = dest_ip
        self.parameters["dest_port"] = dest_port
        self.parameters["transport"] = protocol

    def set_dialog(self, dialog):
        """ Change current dialog to the one provided """
        if not type(dialog) == type(dict):
            exception("Must provide a dialog in the form of Python dictionary")
        for key in self.current_dialog:
            if key not in dialog:
                exception("Not a valid dialog. Missing key: " + key)
        if dialog not in self.dialogs:
            self.dialogs.append(dialog)
        self.current_dialog = self.get_complete_dialog(dialog)
        self.parameters["callId"] = self.current_dialog["Call-ID"]
        self.parameters["fromTag"] = self.current_dialog["from_tag"]
        self.parameters["toTag"] = self.current_dialog["to_tag"]

    def set_transaction(self, transaction):
        """ Change current transaction to the one provided """
        if not type(transaction) == type(dict):
            exception("Must provide a transaction in the form of Python dictionary")
        for key in self.current_transaction:
            if key not in transaction:
                exception("Not a valid transaction. Missing key: " + key)
        for key in self.current_transaction:
            self.current_transaction[key] = transaction[key]

    def start_new_dialog(self):
        """ Refresh the SIP dialog specific parameters """
        self.current_dialog = {
            "Call-ID": util.randomCallID(),
            "from_tag": util.randomTag(),
            "to_tag": None
            # "epid": lambda x=6: "SC" + util.randStr(x),
        }
        self.dialogs.append(self.current_dialog)

    def get_last_message_in(self, dialog):
        """ Get the last message sent or received in the provided dialog """
        for message in self.last_messages_per_dialog:
            if message.get_dialog() == dialog:
                return message
        raise Exception("No message found in dialog: " + str(dialog))

    def save_message(self, message):
        """ Search for previously received message in the same dialog.
            If found, replace with given message, otherwise append message to message list """
        for i in range(len(self.last_messages_per_dialog)):
            if message.get_dialog() == self.last_messages_per_dialog[i].get_dialog():
                self.last_messages_per_dialog[i] = message
                return
        self.last_messages_per_dialog.append(message)

    def start_new_transaction(self, method):
        """ Refresh the via branch and CSeq header """
        if method in ("ACK", "CANCEL"):
            # Not really a new transaction
            # find transaction from last message in dialog
            transaction = self.get_last_message_in(self.current_dialog).get_transaction()
            cseq = transaction["cseq"]
            branch = transaction["via_branch"]
        elif method in self.requests:
            transaction = self.get_last_message_in(self.current_dialog).get_transaction()
            cseq = str(int(transaction["cseq"]) + 1)
            branch = transaction["via_branch"]
        else:
            cseq = str(len(self.requests))
            branch = util.randomBranch()
            if method != "REGISTER":
                # Ignore REGISTER otherwise unregister breaks
                # TODO: check if reRegistrations will work
                self.requests.append(method)
        self.current_transaction["via_branch"] = branch
        self.current_transaction["cseq"] = cseq  # str(int(self.current_transaction["cseq"]) + 1)
        self.current_transaction["method"] = method

    def send_new(self, target_sip_ep=None, message_string="", expected_response=None, ignore_messages=[]):
        """ Start a new dialog and send a message """
        if target_sip_ep:
            self.parameters["userA"] = self.number
            self.parameters["userB"] = target_sip_ep.number
        else:
            # In cases like REGISTER, there is no B-side
            # Clear parameters to avoid unexpected results
            self.parameters.pop("userA", None)
            self.parameters.pop("userB", None)

        m = buildMessage(message_string, self.parameters)
        assert m.type == "Request", 'Tried to start a new dialog with a SIP Response'

        self.start_new_dialog()
        self.start_new_transaction(m.method)  # m should always be a request

        m.set_dialog_from(self.current_dialog)
        m.set_transaction_from(self.current_transaction)

        self.link.send(m.contents())
        self.save_message(m)

        if expected_response:
            try:
                self.waitForMessage(expected_response, ignore_messages)
            except AssertionError:
                raise AssertionError('{}: "{}" response to "{}"\n{}'.format(self.number,
                                                                            self.get_last_message_in(m.get_dialog()).status,
                                                                            m.method,
                                                                            m))
        # We return a copy because this is a reference to an object and
        # we want the current value at this point in time
        return copy(self.current_dialog)

    def send(self, message_string="", expected_response=None, ignore_messages=[], dialog=None):
        """ Send a message within a dialog """
        self.reply(message_string, dialog)
        if expected_response:
            self.waitForMessage(expected_response, ignore_messages)
        # We return a copy because this is a reference to an object and
        # we want the current value at this point in time
        return copy(self.current_dialog)

    def reply(self, message_string, dialog=None):
        """ Send a response to a previously received message """
        if dialog:
            self.set_dialog(dialog)
        if "callId" not in self.parameters or not self.parameters['callId']:
            raise Exception("Cannot reply when we are not in a dialog")
        m = buildMessage(message_string, self.parameters)
        m.make_response_to(self.get_last_message_in(self.current_dialog))

        if m.type == "Request":
            # This is a new request in the same dialog, so fix the CSeq
            # m.increase_cseq()
            self.start_new_transaction(m.method)

        m.set_transaction_from(self.current_transaction)

        # TODO: fix CSeq according to RFC3261 and ACK according to section 17.1.1.3
        #            self.parameters["cseq"] += 1
        #            m["CSeq"] = "{} {}".format(self.parameters["cseq"], m.method)
        self.link.send(m.contents())
        # We return a copy because this is a reference to an object and
        # we want the current value at this point in time
        return copy(self.current_dialog)

    def waitForMessage(self, message_type, ignore_messages=[]):
        """
        Wait for a specific type of SIP message.
        :message_type is a string that we will make sure is
        contained in the received message request or response line
        """
        inmessage = None
        last_sent_message = self.get_last_message_in(self.current_dialog)
        while not inmessage or inmessage.get_status_or_method() in ignore_messages:
            inbytes = self.link.waitForSipData()
            inmessage = self.handleDA(last_sent_message, parseBytes(inbytes))
            self.save_message(inmessage)
            if inmessage.type == "Request":
                self.set_transaction(inmessage.get_transaction())
            else:
                self.update_to_tag(inmessage.get_dialog())
            self.set_dialog(inmessage.get_dialog())
        assert message_type in inmessage.get_status_or_method(), \
            '{}: Got "{}" while expecting "{}"'.format(self.number, inmessage.get_status_or_method(), message_type)
        return inmessage

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
        if response.type == "Response" and response.status == "401 Unauthorized":
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
