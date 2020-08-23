"""\
Purpose: Simulate a CSTA Application
Initial Version: Costas Skarakis 7/20/2020  
"""
import os
import traceback
from _socket import timeout as sock_timeout
from threading import Lock
from time import sleep

from common.client import TCPClient
from common.tc_logging import debug, warning, exception
from csta.CstaEndpoint import get_xml
from csta.CstaUser import CstaUser
from csta.CstaParser import parseBytes, buildMessageFromFile, buildMessage


class CstaApplication:
    def __init__(self, server=False):
        self.ip = None
        self.port = None
        self.link = None
        self.min_event_id = 0
        self.users = {}
        self.parameters = {}
        self.server = server
        self.message_buffer = []
        self.waitForCstaMessage = self.wait_for_csta_message  # compatibility alias
        self.lock = Lock()

    def connect(self, local_address, destination_address, protocol="tcp"):
        """ Connect to CSTA Server """
        local_ip, local_port = local_address
        self.ip = local_ip
        self.port = local_port
        # params = {"source_ip": local_ip, "source_port": local_port, "transport": protocol}
        dest_ip, dest_port = destination_address
        # Only TCP implemented
        # 0 means bind to any available local port
        csta_link = TCPClient(local_ip, local_port)
        self.link = csta_link
        csta_link.connect(dest_ip, dest_port)

        inBytes = csta_link.waitForData()
        req = parseBytes(inBytes)

        resp = buildMessageFromFile(get_xml("SystemStatusResponse.xml"), {}, eventid=req.eventid)
        csta_link.send(resp.contents())

        reg = buildMessageFromFile(get_xml("SystemRegister.xml"), {}, eventid=0)
        csta_link.send(reg.contents())

        inBytes = csta_link.waitForData()
        reg_resp = parseBytes(inBytes)
        assert reg_resp.event == "SystemRegisterResponse", 'Invalid Response to System Register Request'
        return csta_link

    def new_user(self, directory_number):
        """ Add a new user to the Application
        :param directory_number: The users number as a string
        :return: The CstaUser object created for this user
        """
        if directory_number in self.users:
            warning(directory_number + " already exists")
            return self.users[directory_number]
        else:
            user = CstaUser(directory_number, self)
            self.users[directory_number] = user
            return user

    def get_user(self, directory_number):
        return self.users[directory_number]

    def monitor_start(self, directory_number):
        """ Send MonitorStart and add directory number to monitored users"""
        user = self.get_user(directory_number)
        user.parameters["user"] = directory_number
        user.send("MonitorStart")
        inmessage = user.wait_for_message("MonitorStartResponse")
        user.parameters["monitorCrossRefID"] = inmessage["monitorCrossRefID"]

    # def monitor_stop(self, directory_number):
    #     """ Send MonitorStop and delete directory number from monitored users"""
    #     csta_link = self.link
    #     m = buildMessageFromFile(get_xml("MonitorStop.xml"), {"user": directory_number}, eventid=1)
    #     csta_link.send(m.contents())
    #     in_bytes = csta_link.waitForData()
    #     inmessage = parseBytes(in_bytes)
    #     assert inmessage.event == "MonitorStopResponse", "Sent:{}  Received:{}".format(m.event, str(inmessage))
    #     self.parameters.pop(directory_number)

    def get_monitored_users(self):
        return list(user for user in self.users if self.get_user(user).parameters["monitorCrossRefID"] is not None)

    def send(self, message, from_user=None, to_user=None):
        """ Send a CSTA message

        :param from_user: calling number
        :param to_user: called number
        :param message: This could be a predefined csta message or just the type of the message.
                       There are already several builtin xml files that are named after the corresponding messages
                       In order to access them just provide the type of the CSTA message.
                       There should be a matching filename in csta/xml

                       Example: C.send_csta("MakeCall")
        """
        if isinstance(to_user, CstaUser):
            to_user = to_user.number
        user = self.users[from_user]
        if from_user and message not in ("MonitorStart", "MonitorStart.xml"):
            assert from_user in self.get_monitored_users(), "User {} must be monitored before sending messages".format(
                from_user)
        user.set_parameter("callingDevice", from_user)
        user.set_parameter("calledDirectoryNumber", to_user)
        if message.strip().startswith("<?xml"):
            m = buildMessage(message, user.parameters, eventid=0)
        else:
            m = buildMessageFromFile(get_xml(message), user.parameters, eventid=0)
        eventid = user.get_transaction_id(m.event)
        m.set_eventid(eventid)
        # old_link = self.link
        # try:
        self.link.send(m.contents())
        # except IOError:
        #     while old_link is self.link:
        #         sleep(0.1)
        #     debug("Retransmitting {} after disconnection and reconnection".format(m.event))
        #     self.link.send(m.contents())
        user.update_outgoing_transactions(m)
        return m

    def wait_for_csta_message(self, for_user, message, ignore_messages=(), timeout=5.0):
        """
        Wait for CSTA message
        :param for_user: The message intended recipient
        :param message: The message to wait for
        :param ignore_messages: Messages to ignore
        :param timeout: Defined timeout in seconds.
        :return: the CstaMessage received
        """
        inmessage = None
        user = self.users[for_user]
        other_users = [usr for usr in self.users if usr != user]

        while not inmessage:

            if self.message_buffer:
                # first get a message from the buffer
                inmessage = self.get_buffered_message(for_user)

            sleep(0.1)

            if self.server:
                continue

            if not inmessage:
                # no (more) buffered messages. try the network
                try:
                    # print("Waiting for", message)
                    # inbytes = self.link.waitForCstaData(timeout=0.2)
                    inbytes = self.link.waitForCstaData(timeout=timeout)
                    inmessage = parseBytes(inbytes)
                # except sock_timeout:
                #     inmessage = None
                #     timeout -= 0.2
                #     if timeout <= 0:
                #         raise
                #     else:
                #         continue
                except UnicodeDecodeError:
                    debug("Ignoring malformed data")
                    inmessage = None
                    continue
                except sock_timeout:
                    exception(for_user + " No" + message + " " + str(self.message_buffer))

            inmessage_type = inmessage.event
            if inmessage_type in ignore_messages:
                inmessage = None
                continue

            if message and \
                    ((isinstance(message, str) and message != inmessage_type) or
                     (type(message) in (list, tuple) and not any([m == inmessage_type for m in message])) or
                     (inmessage["monitorCrossRefID"] and "monitorCrossRefID" in user.parameters and
                      inmessage["monitorCrossRefID"] != user.parameters["monitorCrossRefID"] and
                      inmessage_type != "MonitorStartResponse") or
                     inmessage.is_response() and inmessage.eventid not in user.out_transactions):

                # we have received an unexpected message.
                if inmessage["deviceID"] and any(usr in inmessage["deviceID"] for usr in other_users):
                    # TODO apply here the deviceID fix as well
                    self.message_buffer.append(inmessage)
                    inmessage = None
                else:
                    raise AssertionError('{}: Got "{}" with callID {} and xrefid {} while expecting "{}" with '
                                         'callID {} and xrefid {}.\n{} '.format(for_user,
                                                                                inmessage_type,
                                                                                inmessage["callID"],
                                                                                inmessage["monitorCrossRefID"],
                                                                                message,
                                                                                user.parameters.get("callID", None),
                                                                                user.parameters.get("monitorCrossRefID",
                                                                                                    None),
                                                                                inmessage))

        # Evaluate the invoke id
        user.update_incoming_transactions(inmessage)
        return inmessage

    def get_buffered_message(self, directory_number):
        """
        Return the first buffered message found for the given directory number's deviceID

        :param directory_number: The monitored directory number
        :return: the buffered SipMessage
        """
        self.lock.acquire()
        msg = None
        for i in range(len(self.message_buffer)):
            message = self.message_buffer.pop(0)
            user = self.get_user(directory_number)
            try:
                device_ID = message["deviceID"]
            except AttributeError:
                device_ID = None
            if device_ID is None or user.deviceID in device_ID:
                # using string contains instead of ==  before the device ID in messages seems to come
                # like this: N&lt;302101150013&gt;
                # TODO: find a better way to get the deviceID from messages
                msg = message
                break
            else:
                self.message_buffer.append(message)
        self.lock.release()
        return msg

    def update_call_parameters(self, directory_number, inresponse):
        """ Update our parameters based on the given incoming CSTA message """
        try:
            if not inresponse.event.endswith("Event") and not inresponse.event.endswith("Response"):
                self.parameters[directory_number]["last_request_eventid"] = inresponse.eventid
            for key in "deviceID", "monitorCrossRefID", "callID":
                if inresponse[key]:
                    self.parameters[directory_number][key] = inresponse[key]
        except AttributeError:
            self.parameters[directory_number].setdefault("deviceID", None)

    def close(self):
        self.link.socket.close()
        self.link = None
