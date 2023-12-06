"""\
Purpose: Simulate a SIP phone/line appearance/user
Initial Version: Costas Skarakis
"""
from threading import Timer, Event

from _socket import timeout as sock_timeout
import traceback
from common.tc_logging import exception, warning
from sip.SipParser import parseBytes, buildMessage
import common.util as util
import common.client as client
import sip.SipFlows as flow
from threading import Lock, Thread
from sip.SipMessage import SipMessage
from time import time, sleep


def dialog_hash(dialog):
    return "|".join([dialog["Call-ID"], dialog["from_tag"], dialog["to_tag"]])


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
                           "cseq": "0",
                           "method": None
                           }
        self.last_messages_per_dialog = []
        self.dialogs = []
        self.known_call_ids = set()
        self.requests = []
        self.current_dialog = {
            "Call-ID": None,
            "from_tag": None,
            "to_tag": None
            # "epid": None,
        }
        self.tags = {}
        self.current_transaction = {"via_branch": None,
                                    "cseq": "0",
                                    "method": None
                                    }

        self.waitForMessage = self.wait_for_message  # compatibility alias
        self.reply_to = self.send_in_ctx_of  # method alias
        self.secondary_lines = []
        self.message_buffer = set()
        self.buffer_event = Event()
        # self.buffer_mod_count = [0]  # using a int in a list to be able to share and muate between objects in use_link()
        self.registered = False
        self.re_register_timer = None
        self.busy = False
        self.lock = Lock()
        self.wait_thread = None
        self.shutdown_flag = False

    def shutdown(self):
        """
        Try to stop threads and cleanup connections
        """
        self.shutdown_flag = True
        self.link.shutdown()
        self.wait_thread.join()

    def make_busy(self, busy=True):
        self.busy = busy

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
        self.link.connect(dest_ip, dest_port)
        self.set_address((local_ip, self.link.port))
        self.start_wait_thread()

    def start_wait_thread(self):
        """
        Starts a separate thread that will consume incoming csta traffic and place it into buffers
        """
        if self.wait_thread is None:
            self.wait_thread = Thread(target=self.wait_loop, daemon=True)
            self.wait_thread.start()

    def wait_loop(self):
        """
        Continuously wait for incoming sip messages. Add all messages to buffers
        """
        while not self.shutdown_flag:
            try:
                inbytes = self.link.waitForSipData(timeout=None)
                # inbytes = self.link.waitForSipData(timeout=timeout, client=link)
            except ConnectionError:
                # might need to add what kind of disconnection that was
                warning("Disconnected. Exiting")
                break
            if inbytes is None:
                warning("Disconnected. Will retry in 1 second")
                sleep(1)
            else:
                inmessage = parseBytes(inbytes)
                # TODO: Add "on message" functionality, eg 200OK on OPTIONS
                try:
                    self.message_buffer.add(inmessage)
                    self.buffer_event.set()
                except:
                    exception(traceback.format_exc())

    def update_to_tag(self, in_dialog):
        """
        Update the to_tag on an existing dialog that has no to_tag
        :param in_dialog: the complete dialog
        :return: None
        """
        with self.lock:
            for dialog in self.dialogs:
                if dialog["Call-ID"] == in_dialog["Call-ID"] \
                        and dialog["from_tag"] == in_dialog["from_tag"] \
                        and not dialog["to_tag"]:
                    dhash = dialog_hash(dialog)
                    dialog["to_tag"] = in_dialog["to_tag"]
                    dhash_complete = dialog_hash(dialog)
                    self.tags[dhash_complete] = self.tags[dhash]

    def get_complete_dialog(self, in_dialog):
        """
        Look for a complete existing dialog in case the provided one doesn't have a to tag
        :param in_dialog: the possibly incomplete dialog
        :return: in_dialog if it is complete or a corresponding complete one is not found,
                 otherwise the existing corresponding complete dialog
        """
        if in_dialog["to_tag"]:
            return in_dialog
        with self.lock:
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

    def use_link(self, other):
        """ Convenience function to use an existing network connection
        If parameter is SipEndpoint, we will use also share a common message buffer and dialog tracking
        """
        if isinstance(other, SipEndpoint):
            link = other.link
            self.message_buffer = other.message_buffer
            self.dialogs = other.dialogs
            self.requests = other.requests
            self.last_messages_per_dialog = other.last_messages_per_dialog
            self.buffer_event = other.buffer_event
            self.wait_thread = other.wait_thread
        else:
            link = other
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

    def get_dialog(self):
        """ Will use this method to get thread-local dialogs """
        if "toTag" not in self.parameters:
            return {"Call-ID": self.parameters["callId"],
                    "from_tag": self.parameters["fromTag"]}
        else:
            return {"Call-ID": self.parameters["callId"],
                    "from_tag": self.parameters["fromTag"],
                    "to_tag": self.parameters["toTag"]}

    def get_transaction(self):
        """ Will use this method to get thread-local transactions """
        return {"via_branch": self.parameters["viaBranch"],
                "cseq": self.parameters["cseq"],
                "method": self.parameters["method"]}

    def set_dialog(self, dialog):
        """ Change current dialog to the one provided """
        if not isinstance(dialog, dict):
            exception("Must provide a dialog in the form of Python dictionary")
        for key in self.get_dialog():
            if key not in dialog:
                exception("Not a valid dialog. Missing key: " + key)
        dialog = self.get_complete_dialog(dialog)
        if dialog not in self.dialogs:
            self.dialogs.append(dialog)
            self.known_call_ids.add(dialog["Call-ID"])
            self.requests.append([])
            # If we don't know this dialog it means we didn't started so it must be an incoming Request
            with self.lock:
                self.tags[dialog_hash(dialog)] = "to_tag"
        self.current_dialog = dialog
        self.parameters["callId"] = dialog["Call-ID"]
        self.parameters["fromTag"] = dialog["from_tag"]
        self.parameters["toTag"] = dialog["to_tag"]
        return dialog

    def reset_dialog_and_transaction(self):
        """
        Reset current dialog and transaction to initial state
        :return: None
        """
        self.parameters["viaBranch"] = None
        self.parameters["epid"] = None
        self.parameters["cseq"] = "0"
        self.parameters["method"] = None
        self.parameters["callId"] = None
        self.parameters["fromTag"] = None
        self.parameters["toTag"] = None
        self.current_dialog = {
            "Call-ID": None,
            "from_tag": None,
            "to_tag": None
        }
        self.current_transaction = {"via_branch": None,
                                    "cseq": "0",
                                    "method": None
                                    }

    def switch_tags(self, dialog=None):
        if not dialog:
            dialog = self.get_dialog()
        dhash = dialog_hash(dialog)
        dialog["from_tag"], dialog["to_tag"] = dialog["to_tag"], dialog["from_tag"]
        dhash_switched = dialog_hash(dialog)
        self.set_dialog(dialog)
        with self.lock:
            if self.tags[dhash] == "to_tag":
                self.tags[dhash_switched] = "from_tag"
            else:
                self.tags[dhash_switched] = "to_tag"

    def set_transaction(self, transaction):
        """ Change current transaction to the one provided """
        if not isinstance(transaction, dict):
            exception("Must provide a transaction in the form of Python dictionary")
            return
        for key in self.current_transaction:
            if key not in transaction:
                exception("Not a valid transaction. Missing key: " + key)
                return
        for key in self.current_transaction:
            self.current_transaction[key] = transaction[key]
        self.parameters["viaBranch"] = transaction["via_branch"]
        self.parameters["cseq"] = transaction["cseq"]
        self.parameters["method"] = transaction["method"]

    def start_new_dialog(self):
        """ Refresh the SIP dialog specific parameters """
        dialog = {
            "Call-ID": util.randomCallID(),
            "from_tag": util.randomTag(),
            "to_tag": ""
            # "epid": lambda x=6: "SC" + util.randStr(x),
        }
        self.current_dialog = dialog
        self.parameters["callId"] = dialog["Call-ID"]
        self.parameters["fromTag"] = dialog["from_tag"]
        self.parameters["toTag"] = dialog["to_tag"]
        with self.lock:
            self.tags[dialog_hash(dialog)] = "from_tag"
        self.dialogs.append(dialog)
        self.known_call_ids.add(dialog["Call-ID"])
        self.requests.append([])
        return dialog

    def get_last_message_in(self, dialog):
        """ Get the last message sent or received in the provided dialog """
        # If we have received no messages yet return None
        null_d = {"Call-ID": None, "from_tag": None, "to_tag": None}
        if self.current_dialog == null_d or dialog == null_d:
            return None
        with self.lock:
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
        with self.lock:
            for i in range(len(self.last_messages_per_dialog)):
                if message.get_dialog() == self.last_messages_per_dialog[i].get_dialog():
                    self.last_messages_per_dialog[i] = message
                    return
            self.last_messages_per_dialog.append(message)

    def prepare_message(self, message):
        """
        Convert a SIP message string to SipMessage object

        :param message: The message string
        :return: A SipMessage object
        """
        return buildMessage(message, self.parameters)

    def start_new_transaction(self, method, dialog=None):
        """ Refresh the via branch and CSeq header """
        if not dialog:
            dialog = self.get_dialog()
        try:
            last_message_in_dialog = self.get_last_message_in(dialog)
        except:
            last_message_in_dialog = None
        branch = util.randomBranch()
        if method in ("ACK", "CANCEL"):
            # Not really a new transaction
            # find transaction from last message in dialog
            # which should not be none because what are we sending ACK or CANCEL to?
            transaction = last_message_in_dialog.get_transaction()
            cseq = transaction["cseq"]
        elif last_message_in_dialog:
            transaction = last_message_in_dialog.get_transaction()
            cseq = str(int(transaction["cseq"]) + 1)
        else:
            with self.lock:
                cseq = str(len(self.requests[self.dialogs.index(dialog)]))
                if method != "REGISTER":
                    # Ignore REGISTER otherwise unregister breaks
                    # TODO: check if reRegistrations will work
                    self.requests[self.dialogs.index(dialog)].append(method)
        transaction = {"via_branch": branch, "cseq": cseq, "method": method}
        self.set_transaction(transaction)
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

        if isinstance(message_string, SipMessage):
            m = message_string
        else:
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
        if "callId" not in self.parameters or not self.parameters['callId']:
            raise Exception("Cannot reply when we are not in a dialog")

        if isinstance(message_string, SipMessage):
            # We can also get a SipEndpoint type as input but it will be sent as is
            m = message_string
        else:
            m = buildMessage(message_string, self.parameters)

        if dialog:
            dialog = self.set_dialog(dialog)
        else:
            dialog = self.get_dialog()

        try:
            previous_message = self.get_last_message_in(dialog)
            m.make_response_to(previous_message)
            self.update_to_tag(m.get_dialog())
        except:  # caused by get_last_message_in(dialog) if no message has been exchanged in this dialog yet
            # New dialog, same call-id, eg NOTIFY after Keyset SUBSCRIBE.
            # Must be a SIP Request
            previous_message = None
            assert m.type == "Request", \
                "Attempted to send a {} response in a new dialog".format(m.get_status_or_method())

        if m.type == "Request":
            # This is a new request in the same dialog, so fix the CSeq
            # m.increase_cseq()
            self.start_new_transaction(m.method)
            # If B side sends the new request we must switch from and to tags
            if previous_message is not None and \
                    m.method not in ("ACK", "CANCEL") and \
                    self.tags[dialog_hash(dialog)] == "to_tag":
                self.switch_tags(dialog)
            m.set_dialog_from(dialog)
        else:
            self.free_resources(m)
        self.save_message(m)

        m.set_transaction_from(self.get_transaction())
        self.link.send(m.contents())
        return m

    def get_buffered_message(self, message_type, dialog):
        """
        Return the first buffered message found in the given dialog

        :param message_type: the requested message type
        :param dialog: The dialog in question
        :return: the buffered SipMessage
        """
        msg = None
        # for message in self.message_buffer:
        with self.lock:
            for message in self.message_buffer:
                m_dialog = message.get_dialog()
                m_type = message.get_status_or_method()
                # If we have received no messages yet return the first message in the buffer
                if message_type in m_type and (dialog is None or m_dialog["Call-ID"] == dialog["Call-ID"]):
                    msg = message
                    self.message_buffer.remove(message)
                    break
                # else:
                #     self.message_buffer.append(message)
        # if msg is None:
        #     print(self.number, "Buffer returned None for", message_type, "in callid and from_tag", dialog["Call-ID"], dialog["from_tag"], "although it has", self.message_buffer)
        return msg

    def wait_for_message(self, message_type, dialog=None, ignore_messages=(), timeout=5.0):
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

        # if not dialog:
        #     dialog = {"Call-ID": self.parameters["callId"],
        #               "from_tag": self.parameters["fromTag"]}
        #     if "toTag" in self.parameters:
        #         dialog["to_tag"] = self.parameters["toTag"]

        if dialog:
            dialog = self.get_complete_dialog(dialog)
            explicit_dialog = dialog
        else:
            explicit_dialog = None
            dialog = {"Call-ID": self.parameters["callId"],
                      "from_tag": self.parameters["fromTag"]}
            if "toTag" in self.parameters:
                dialog["to_tag"] = self.parameters["toTag"]

        last_sent_message = self.get_last_message_in(dialog)
        transaction = None
        if last_sent_message:
            transaction = last_sent_message.get_transaction()

        t0_tout = time()
        inmessage = self.get_buffered_message(message_type, explicit_dialog)
        inmessage = self.handleDA(last_sent_message, inmessage)

        while not inmessage:
            rem_timeout = timeout - (time() - t0_tout)
            if rem_timeout > 0:
                self.buffer_event.wait(rem_timeout)
                self.buffer_event.clear()
                inmessage = self.get_buffered_message(message_type, explicit_dialog)
                inmessage = self.handleDA(last_sent_message, inmessage)
                if inmessage is None:
                    continue
            else:
                exception("%s No %s. Buffer length: %d." % (self.number,
                                                            message_type,
                                                            len(self.message_buffer)))
                raise sock_timeout

            # if not inmessage:
            #     # no (more) buffered messages. try the network
            #     inbytes = self.link.waitForSipData(timeout=timeout, client=link)
            #     inmessage = self.handleDA(last_sent_message, parseBytes(inbytes))

            inmessage_type = inmessage.get_status_or_method()
            inmessage_dialog = inmessage.get_dialog()
            inmessage.cseq_method = inmessage.get_transaction()["method"]

            # when sharing buffers we can get a message of other endpoints
            # buffer message of correct type but unknown callid
            # keep it if we are mentioned in the "To" or "Route" headers
            if inmessage_type == message_type and \
                    inmessage_dialog["Call-ID"] not in self.known_call_ids and \
                    ("@" in inmessage["To"] and "sip:{}@{}".format(self.number, self.ip) not in inmessage["To"]) and \
                    not inmessage.header_contains("Route", self.number):
                # print(self.number, "Aborting", inmessage_type, "with callid", inmessage_dialog["Call-ID"])
                # print(self.number, "My callid is", dialog["Call-ID"])
                with self.lock:
                    self.message_buffer.add(inmessage)
                self.buffer_event.set()
                inmessage = None
                continue

            if inmessage_type in ignore_messages:
                inmessage = None
                continue

            if message_type and \
                    ((isinstance(message_type, str) and message_type not in inmessage_type) or
                     (type(message_type) in (list, tuple) and not any([m in inmessage_type for m in message_type])) or
                     (inmessage.type == "Response" and inmessage.cseq_method != transaction["method"])):
                # we have received an unexpected message. buffer it if there is an active dialog for it
                if self.get_complete_dialog(inmessage_dialog) or inmessage_type == "INVITE":
                    # message is part of another active dialog or a new call, so buffer it
                    # print(self.number, "Aborting", inmessage_type, "with callid", inmessage_dialog["Call-ID"])
                    with self.lock:
                        self.message_buffer.add(inmessage)
                    self.buffer_event.set()
                    # print("Appended {} with {} to buffer. Will keep waiting for {} in {} ".format(inmessage_type,
                    #                                                                        inmessage_dialog,
                    #                                                                        message_type,
                    #                                                                            dialog))
                    inmessage = None
                else:
                    d = ["sip:{}@".format(line.number) in inmessage["To"] for line in self.secondary_lines]
                    if any(d):
                        # message is meant for another line in this device
                        with self.lock:
                            self.secondary_lines[d.index(True)].message_buffer.add(inmessage)
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
            inmessage_transaction = inmessage.get_transaction()
            self.set_transaction(inmessage_transaction)
        else:
            assert inmessage.get_transaction()["method"] == transaction["method"], \
                "Got {} to {} instead of {} to {}".format(inmessage.get_status_or_method(),
                                                          inmessage.get_transaction()["method"],
                                                          message_type,
                                                          transaction["method"])
            self.update_to_tag(inmessage.get_dialog())
            self.free_resources(inmessage)
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
        if response is None:
            return
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
        if not expiration_in_seconds:
            return self.unregister()
        if re_register_time and self.registered:
            self.re_register_timer = Timer(re_register_time, self.register, (expiration_in_seconds, re_register_time))
            self.re_register_timer.start()
        flow.register(self, expiration_in_seconds)
        self.reset_dialog_and_transaction()
        self.registered = True

    def unregister(self):
        """ Convenience function to un-register a SipEndpoint"""
        if self.re_register_timer:
            self.re_register_timer.cancel()
        flow.unregister(self)
        self.registered = False

    def free_resources(self, message):
        """ Free memory allocated to a cleared call """

        status_or_method = message.get_status_or_method()
        cseq_method = message["CSeq"].split()[1]
        call_ended_successfully = status_or_method.startswith("2") and cseq_method in ("BYE", "CANCEL")
        call_rejected_with_error = status_or_method[0] in "3456"
        if call_ended_successfully or call_rejected_with_error:
            dialog = message.get_dialog()
            with self.lock:
                # TODO: actually free up memory from completed calls
                dialog_index = self.dialogs.index(dialog)
                # self.dialogs.pop(dialog_index)
                # self.requests.pop(dialog_index)
                # self.tags.pop(dialog_hash(dialog))
                # self.last_messages_per_dialog.pop(dialog_index)
                # print("Cleared call number", dialog_index, "after message", status_or_method, "with cseq", cseq_method,
                #       ". Sizes are", len(self.dialogs), len(self.requests), len(self.tags))
