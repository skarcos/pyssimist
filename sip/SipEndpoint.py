"""\
Purpose: Simulate a SIP phone/line appearance/user
Initial Version: Costas Skarakis
"""
from threading import Timer

from common.tc_logging import exception, debug
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
                           "expires": 360,
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

        self.waitForMessage = self.wait_for_message  # compatibility alias
        self.secondary_lines = []
        self.message_buffer = []
        self.registered = False
        self.re_register_timer = None
        self.busy = False

    def update_parameters(self, params, force=False):
        """
        Update endpoint parameters. This is useful for adding more flexibility in the creation of SIP messages

        :param params: The key-value pairs input
        :param force: Force update of existing variables
        :return: None
        """
        for parameter in params:
            if parameter not in self.parameters or force is True:
                self.parameters[parameter] = params[parameter]

    def connect(self, local_address, destination_address, protocol="tcp", certificate=None, subject_name="localhost"):
        """ Connect to the SIP Server """
        local_ip, local_port = local_address
        dest_ip, dest_port = destination_address

        self.parameters["dest_ip"] = dest_ip
        self.parameters["dest_port"] = dest_port
        self.parameters["transport"] = protocol
        if protocol in ("tcp", "TCP"):
            self.link = client.TCPClient(local_ip, local_port)
        elif protocol in ("udp", "UDP"):
            self.link = client.UDPClient(local_ip, local_port)
        elif protocol in ("tls", "TLS"):
            # for MTLS this might be needed
            # context.load_cert_chain('/path/to/certchain.pem', '/path/to/private.key')
            self.link = client.TLSClient(local_ip, local_port, certificate)
        else:
            raise NotImplementedError("{} client not implemented".format(protocol))
        self.set_address((local_ip, self.link.port))
        self.link.connect(dest_ip, dest_port)

    def update_to_tag(self, in_dialog):
        """
        Update the to_tag on an existing dialog that has no to_tag
        :param in_dialog: the complete dialog
        :return: None
        """
        for dialog in self.dialogs:
            if dialog["Call-ID"] == in_dialog["Call-ID"] \
                    and dialog["from_tag"] == in_dialog["from_tag"] \
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
                    and dialog["from_tag"] == in_dialog["from_tag"] \
                    and dialog["to_tag"]:
                return dialog
        return in_dialog

    def set_address(self, address):
        """
        We can create and Endpoint just to use it as target for sip messages

        :param address: The address as an (ip, port) tuple
        :return: None
        """
        local_ip, local_port = address
        self.ip = local_ip
        self.port = local_port
        self.parameters["source_ip"] = local_ip
        self.parameters["source_port"] = local_port

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
        # self.link.endpoints_connected += 1

    def set_dialog(self, dialog):
        """ Change current dialog to the one provided """
        if not isinstance(dialog, dict):
            exception("Must provide a dialog in the form of Python dictionary")
        for key in self.current_dialog:
            if key not in dialog:
                exception("Not a valid dialog. Missing key: " + key)
        if dialog not in self.dialogs:
            self.dialogs.append(dialog)
            self.requests.append([])
        dialog = self.get_complete_dialog(dialog)
        self.current_dialog = dialog
        self.parameters["callId"] = self.current_dialog["Call-ID"]
        self.parameters["fromTag"] = self.current_dialog["from_tag"]
        self.parameters["toTag"] = self.current_dialog["to_tag"]
        return dialog

    def set_transaction(self, transaction):
        """ Change current transaction to the one provided """
        if not isinstance(transaction, dict):
            exception("Must provide a transaction in the form of Python dictionary")
        for key in self.current_transaction:
            if key not in transaction:
                exception("Not a valid transaction. Missing key: " + key)
        for key in self.current_transaction:
            self.current_transaction[key] = transaction[key]

    def start_new_dialog(self):
        """ Refresh the SIP dialog specific parameters """
        dialog = {
            "Call-ID": util.randomCallID(),
            "from_tag": util.randomTag(),
            "to_tag": ""
            # "epid": lambda x=6: "SC" + util.randStr(x),
        }
        self.current_dialog = dialog
        self.dialogs.append(dialog)
        self.requests.append([])
        return dialog

    def get_last_message_in(self, dialog):
        """ Get the last message sent or received in the provided dialog """
        # If we have received no messages yet return None
        if self.current_dialog == {"Call-ID": None, "from_tag": None, "to_tag": None}:
            return None
        # First check for complete dialogs
        for message in self.last_messages_per_dialog:
            if message.get_dialog() == dialog:
                return message
        # Second check for incomplete dialogs
        for message in self.last_messages_per_dialog:
            d = message.get_dialog()
            if d["Call-ID"] == dialog["Call-ID"] and d["from_tag"] == dialog["from_tag"]:
                return message
        raise Exception("No message found in dialog {}. Other dialogs active: ".format(dialog, self.dialogs))

    def save_message(self, message):
        """ Search for previously received message in the same dialog.
            If found, replace with given message, otherwise append message to message list """
        if message.get_status_or_method() in ("ACK", "CANCEL"):
            return
        for i in range(len(self.last_messages_per_dialog)):
            if message.get_dialog() == self.last_messages_per_dialog[i].get_dialog():
                self.last_messages_per_dialog[i] = message
                return
        self.last_messages_per_dialog.append(message)

    def start_new_transaction(self, method, dialog=None):
        """ Refresh the via branch and CSeq header """
        if not dialog:
            dialog = self.current_dialog
        if method in ("ACK", "CANCEL"):
            # Not really a new transaction
            # find transaction from last message in dialog
            transaction = self.get_last_message_in(dialog).get_transaction()
            cseq = transaction["cseq"]
            branch = transaction["via_branch"]
        elif method in self.requests[self.dialogs.index(dialog)]:
            transaction = self.get_last_message_in(dialog).get_transaction()
            cseq = str(int(transaction["cseq"]) + 1)
            branch = transaction["via_branch"]
        else:
            cseq = str(len(self.requests[self.dialogs.index(dialog)]))
            branch = util.randomBranch()
            if method != "REGISTER":
                # Ignore REGISTER otherwise unregister breaks
                # TODO: check if reRegistrations will work
                self.requests[self.dialogs.index(dialog)].append(method)
        transaction = {}
        transaction["via_branch"] = branch
        transaction["cseq"] = cseq  # str(int(self.current_transaction["cseq"]) + 1)
        transaction["method"] = method
        self.current_transaction = transaction
        return transaction

    def send_new(self, target_sip_ep=None, message_string="", expected_response=None, ignore_messages=[]):
        """ Start a new dialog and send a message """
        self.parameters["userA"] = self.number
        if target_sip_ep:
            if isinstance(target_sip_ep, SipEndpoint):
                self.parameters["userB"] = target_sip_ep.number
                target_sip_ep.parameters["userB"] = self.number
            elif isinstance(target_sip_ep, str):
                self.parameters["userB"] = target_sip_ep
            else:
                raise Exception("target_sip_ep must be str or SipEndpoint, not {}".format(type(target_sip_ep)))
        else:
            # In cases like REGISTER, there is no B-side
            # Clear parameters to avoid unexpected results
            # self.parameters.pop("userA", None)
            # self.parameters.pop("userB", None)
            pass

        m = buildMessage(message_string, self.parameters)
        assert m.type == "Request", 'Tried to start a new dialog with a SIP Response'

        new_dialog = self.start_new_dialog()
        new_transaction = self.start_new_transaction(m.method)  # m should always be a request

        m.set_dialog_from(new_dialog)
        m.set_transaction_from(new_transaction)

        self.link.send(m.contents())
        self.save_message(m)

        if expected_response:
            # try:
            self.waitForMessage(message_type=expected_response, dialog=new_dialog, ignore_messages=ignore_messages)
        # except AssertionError:
        #     raise AssertionError('{}: "{}" response to "{}"\n{}'.format(self.number,
        #                                                                 self.get_last_message_in(
        #                                                                     m.get_dialog()).get_status_or_method(),
        #                                                                 m.method,
        #                                                                 m))
        return m

    def send_in_ctx_of(self, reference_message, this_message_string="", expected_response=None, ignore_messages=[]):
        """ Send a message within the same dialog and transaction as 'reference_message' """
        self.set_transaction(reference_message.get_transaction())
        return self.send(message_string=this_message_string,
                         expected_response=expected_response,
                         ignore_messages=ignore_messages,
                         dialog=reference_message.get_dialog())

    def send(self, message_string="", expected_response=None, ignore_messages=[], dialog=None):
        """ Send a message within a dialog """
        m = self.reply(message_string, dialog)
        if expected_response:
            self.waitForMessage(message_type=expected_response, ignore_messages=ignore_messages, dialog=dialog)
        return m

    def reply(self, message_string, dialog=None):
        """ Send a response to a previously received message """
        if dialog:
            dialog = self.set_dialog(dialog)
        else:
            dialog = self.current_dialog

        if "callId" not in self.parameters or not self.parameters['callId']:
            raise Exception("Cannot reply when we are not in a dialog")

        m = buildMessage(message_string, self.parameters)

        try:
            previous_message = self.get_last_message_in(dialog)
            m.make_response_to(previous_message)
        except:
            # New dialog, same call-id, eg NOTIFY after Keyset SUBSCRIBE.
            # Must be a SIP Response
            assert m.type == "Request", \
                "Attempted to send a {} response in a new dialog".format(m.get_status_or_method())
            m.set_dialog_from(dialog)

        self.save_message(m)
        if m.type == "Request":
            # This is a new request in the same dialog, so fix the CSeq
            # m.increase_cseq()
            self.start_new_transaction(m.method)

        m.set_transaction_from(self.current_transaction)

        # TODO: fix CSeq according to RFC3261 and ACK according to section 17.1.1.3
        #            self.parameters["cseq"] += 1
        #            m["CSeq"] = "{} {}".format(self.parameters["cseq"], m.method)
        self.link.send(m.contents())
        return m

    def get_buffered_message(self, dialog):
        """
        Return the first buffered message found in the given dialog

        :param dialog: The dialog in question
        :return: the buffered SipMessage
        """
        msg = None
        # for message in self.message_buffer:
        for i in range(len(self.message_buffer)):
            message = self.message_buffer[i]
            d = message.get_dialog()
            # If we have received no messages yet return the first message in the buffer
            if self.current_dialog == {"Call-ID": None, "from_tag": None, "to_tag": None} or \
                    (d["Call-ID"] == dialog["Call-ID"] and d["from_tag"] == dialog["from_tag"]):
                msg = message
                self.message_buffer.pop(i)
                break
        return msg

    def wait_for_message(self, message_type, dialog=None, ignore_messages=(), link=None, timeout=5.0):
        """
        Wait for a specific type of SIP message.
        :param message_type: is a string that we will make sure is
                             contained in the received message request or response line
                             Set this to None or "" to accept any incoming message

                             if a list or tuple is given any of the contained message types
                             will be accepted

        :param dialog: Set the dialog to expect the message in. If None will expect a message in current dialog
        :param ignore_messages: a list of message_types to ignore if they come before
                                the expected message_type
        :param timeout: Defined timeout in seconds.
        :return: A SipMessage constructed from the incoming message
        """
        if not link:
            link = self.link
        if not dialog:
            dialog = self.current_dialog
        else:
            dialog = self.get_complete_dialog(dialog)

        inmessage = None
        last_sent_message = self.get_last_message_in(dialog)
        if last_sent_message:
            transaction = last_sent_message.get_transaction()
        len_buffer = len(self.message_buffer)
        count = 0

        while not inmessage:

            if count < len_buffer:
                # first get a message from the buffer
                inmessage = self.get_buffered_message(dialog)
                count += 1

            if not inmessage:
                # no (more) buffered messages. try the network
                inbytes = self.link.waitForSipData(timeout=timeout, client=link)
                inmessage = self.handleDA(last_sent_message, parseBytes(inbytes))

            inmessage_type = inmessage.get_status_or_method()
            inmessage_dialog = inmessage.get_dialog()
            inmessage.cseq_method = inmessage.get_transaction()["method"]

            if inmessage_type in ignore_messages:
                inmessage = None
                continue

            if message_type and \
                    ((isinstance(message_type, str) and message_type not in inmessage_type) or
                     (type(message_type) in (list, tuple) and not any([m in inmessage_type for m in message_type])) or
                     (inmessage.type == "Response" and inmessage.cseq_method != transaction["method"])):
                # we have received an unexpected message. buffer it if there is an active dialog for it
                if inmessage_dialog in self.dialogs or inmessage_type == "INVITE":
                    # message is part of another active dialog or a new call, so buffer it
                    self.message_buffer.append(inmessage)
                    debug("Appended {} with {} to buffer. Will keep waiting for {}".format(inmessage_type,
                                                                                           inmessage_dialog,
                                                                                           message_type))
                    inmessage = None
                else:
                    d = ["sip:{}@".format(line.number) in inmessage["To"] for line in self.secondary_lines]
                    if any(d):
                        # message is meant for another line in this device
                        self.secondary_lines[d.index(True)].message_buffer.append(inmessage)
                        inmessage = None
                    else:
                        raise AssertionError('{}: Got "{}" in {} while expecting "{}" in {}. '
                                             'Other active dialogs:{}.'.format(self.number,
                                                                               inmessage_type,
                                                                               inmessage_dialog,
                                                                               message_type,
                                                                               dialog,
                                                                               self.dialogs))

        self.save_message(inmessage)
        if inmessage.type == "Request":
            self.set_transaction(inmessage.get_transaction())
        else:
            assert inmessage.cseq_method == transaction["method"], \
                "Got {} to {} instead of {} to {}".format(inmessage.get_status_or_method(),
                                                          inmessage.cseq_method,
                                                          message_type,
                                                          transaction["method"])
            self.update_to_tag(inmessage.get_dialog())
        self.set_dialog(inmessage.get_dialog())
        return inmessage

    def wait_for_messages(self, *list_of_message_types, in_order=False, ignore_messages=[]):
        """
        Wait for a list of messages. To be used in a loop or with the next() function.
        Each invocation will return the next SipMessage received.
        The loop will exit when all messages have been received

        :param list_of_message_types: The list of messages expected eg ["NOTIFY", "SUBSCRIBE", "403 Forbidden"]
        :param in_order: Impose the given order for incoming messages
        :param ignore_messages:
        :return: SipMessage received after each invocation
        """
        l = len(list_of_message_types)
        not_received_messages = list(list_of_message_types)
        received_messages = []
        for i in range(l):
            try:
                sip_message = self.wait_for_message(None, ignore_messages)
            except TimeoutError:
                raise TimeoutError("Timeout waiting for {}. Messages already received: {}".format(not_received_messages,
                                                                                                  received_messages))
            message_received = sip_message.get_status_or_method()
            assert message_received in not_received_messages, \
                'After receiving {} we expected one of {} but got {}'.format(received_messages,
                                                                             not_received_messages,
                                                                             message_received)
            if in_order:
                message_order = list_of_message_types.index(message_received)
                assert i == message_order, \
                    '{} arrived in order {} instead of {}'.format(message_received, i, message_order)
            not_received_messages.remove(message_received)
            received_messages.append(message_received)
            yield sip_message

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

    def register(self, expiration_in_seconds=360, re_register_time=180):
        """ Convenience function to register a SipEndpoint """
        if re_register_time:
            self.re_register_timer = Timer(re_register_time, self.register, (expiration_in_seconds, re_register_time))
            self.re_register_timer.start()
        flow.register(self, expiration_in_seconds)
        self.registered = True

    def unregister(self):
        """ Convenience function to un-register a SipEndpoint"""
        if self.re_register_timer:
            self.re_register_timer.cancel()
        flow.unregister(self)
        self.registered = False
