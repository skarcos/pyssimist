"""\
Purpose: Simulate a CSTA Application
Initial Version: Costas Skarakis 7/20/2020
"""
import os
import traceback
from _socket import timeout as sock_timeout
from threading import Lock, Thread, Event
from time import time, sleep

from common.client import TCPClient
from common.tc_logging import debug, warning, exception
from csta.CstaEndpoint import get_xml
from csta.CstaUser import CstaUser
from csta.CstaParser import parseBytes, buildMessageFromFile, buildMessage


def get_buffered_message(buffer, message, call_id=None, monitor_x_ref_id=None, calling_device=None):
    """
    Get a message from the specified buffer.
    Best used within a threading.Lock context

    :param buffer: the buffer to search
    :param message: the message_type to get
    :param call_id: the callID (if any) to request
    :param calling_device: used to separate csta events when needed
    :param monitor_x_ref_id: the monitorCrossRefID (if any) to request
    :return: the corresponding CstaMessage object
    """
    if message.endswith("Event"):
        # This will fail for first csta event
        key = str(call_id) + str(monitor_x_ref_id) + str(message)
        if key in buffer:
            buffered_message = buffer[key].pop(0)
            if not buffer[key]:
                buffer.pop(key)
            return buffered_message

    # Here we look for first csta event, or csta responses
    for k in buffer:
        if ((message.endswith("Event") and call_id is None) or message.endswith("Response")) and \
                k.endswith(str(message)):
            buffered_message = buffer[k][0]

            if (calling_device is not None and
                    calling_device not in str(buffered_message).split("callingDevice")[1].split("callingDevice")[0]):
                continue
            else:
                buffer[k].pop(0)
                if not buffer[k]:
                    buffer.pop(k)
                return buffered_message


class CstaApplication:
    def __init__(self, server=False):
        self.ip = None
        self.port = None
        self.link = None
        self.min_event_id = 0
        self.users = {}
        self.parameters = {}
        self.server = server
        self.message_buffer = {}
        self.buffer_mod_time = None
        self.buffer_trigger_count = 0
        self.lock = Lock()
        self.buffer_event = Event()
        self.shutdown_flag = False
        self.waitForCstaMessage = self.wait_for_csta_message  # compatibility alias
        self.wait_thread = None

    def shutdown(self):
        """
        Try to stop threads and cleanup connections
        """
        self.shutdown_flag = True
        self.link.shutdown()
        self.wait_thread.join()

    def start_wait_thread(self):
        """
        Starts a separate thread that will consume incoming csta traffic and place it into buffers
        """
        self.wait_thread = Thread(target=self.wait_loop)
        self.wait_thread.start()

    def wait_loop(self):
        """
        Continuously wait for incoming csta messages. Add all messages to buffers
        """
        while not self.shutdown_flag:
            try:
                inbytes = self.link.waitForCstaData(timeout=None)
            except ConnectionError:
                # might need to add what kind of disconnection that was
                warning("Disconnected. Exiting")
                break
            if inbytes is None:
                warning("Disconnected. Will retry in 1 second")
                sleep(1)
            else:
                inmessage = parseBytes(inbytes)
                try:
                    net_object = self
                    for dn in self.users:
                        user = self.users[dn]
                        if (inmessage.is_event() and user.monitorCrossRefID == inmessage["monitorCrossRefID"]) or \
                                (inmessage.is_response() and inmessage.eventid in user.out_transactions):
                            net_object = user
                            break
                    with net_object.lock:
                        self.buffer_message(net_object, inmessage)
                except:
                    exception(traceback.format_exc())

    def connect(self, local_address, destination_address, protocol="tcp"):
        """ Connect to CSTA Server """
        local_ip, local_port = local_address
        self.ip = local_ip
        # params = {"source_ip": local_ip, "source_port": local_port, "transport": protocol}
        dest_ip, dest_port = destination_address
        # Only TCP implemented
        # 0 means bind to any available local port
        csta_link = TCPClient(local_ip, local_port)
        self.link = csta_link
        csta_link.connect(dest_ip, dest_port)
        self.port = csta_link.port

        inBytes = csta_link.waitForData()
        req = parseBytes(inBytes)

        resp = buildMessageFromFile(get_xml("SystemStatusResponse.xml"), {}, eventid=req.eventid)
        csta_link.send(resp.contents())

        reg = buildMessageFromFile(get_xml("SystemRegister.xml"), {}, eventid=0)
        csta_link.send(reg.contents())

        inBytes = csta_link.waitForData()
        reg_resp = parseBytes(inBytes)
        assert reg_resp.event == "SystemRegisterResponse", 'Invalid Response to System Register Request'
        self.start_wait_thread()
        return csta_link

    def new_user(self, directory_number):
        """ Add a new user to the Application
        :param directory_number: The users number as a string
        :return: The CstaUser object created for this user
        """
        directory_number = str(directory_number)
        if directory_number in self.users:
            warning(directory_number + " already exists")
            return self.users[directory_number]
        else:
            user = CstaUser(directory_number, self)
            self.users[directory_number] = user
            return user

    def get_user(self, directory_number):
        return self.users[str(directory_number)]

    def monitor_start(self, directory_number, force=False):
        """
        Send MonitorStart and add directory number to monitored users


        :param directory_number: The DN of the device to monitor
        :param force: Force sending another monitor request and create another Monitor Record for the same device
        :return: None
        """

        directory_number = str(directory_number)
        user = self.get_user(directory_number)
        if force or user.monitorCrossRefID is None:
            user.monitorCrossRefID = ""  # set this temporarily to avoid race condition sending monitor twice for a user
            user.parameters["user"] = directory_number
            try:
                user.send("MonitorStart")
                inmessage = user.wait_for_message("MonitorStartResponse")
                user.parameters["monitorCrossRefID"] = inmessage["monitorCrossRefID"]
                user.monitorCrossRefID = user.parameters["monitorCrossRefID"]
            except sock_timeout:
                user.monitorCrossRefID = None
        else:
            debug("Skip MonitorStart for already Monitored user: " + directory_number + ". Use force=True to override.")

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
        return list(user for user in self.users if self.users[str(user)].monitorCrossRefID is not None)

    def prepare_message(self, from_user, message):
        """
        Convert a SIP message string to SipMessage object

        :param message: The message string
        :param from_user: The originating CSTA subscriber object
        :return: A CstaMessage object
        """
        user = self.users[from_user]
        return buildMessage(message, user.parameters)

    def send(self, message, from_user=None, to_user=None, callID=None):
        """ Send a CSTA message

        :param callID: if provided, will use this callID in the outgoing message
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
        user.set_parameter("callingDevice", from_user)
        user.set_parameter("calledDirectoryNumber", to_user)
        if message.strip().startswith("<?xml"):
            m = buildMessage(message, user.parameters, eventid=0)
        else:
            m = buildMessageFromFile(get_xml(message), user.parameters, eventid=0)
        if from_user and m.event != "MonitorStart":
            assert user.monitorCrossRefID, "User {} must be monitored before sending messages".format(
                from_user)
        with self.lock:
            # must do this serially to avoid sending multiple requests with the same invoke id
            eventid = user.get_transaction_id(m.event)
            m.set_eventid(eventid)
            if m["deviceID"] and m["callID"]:
                m["deviceID"] = user.deviceID
                if callID:
                    m["callID"] = callID
                    user.callID = callID
                else:
                    m["callID"] = user.callID
            user.update_outgoing_transactions(m)
            user.update_call_id(m)
        # old_link = self.link
        # try:
        self.link.send(m.contents())
        # except IOError:
        #     while old_link is self.link:
        #         sleep(0.1)
        #     debug("Retransmitting {} after disconnection and reconnection".format(m.event))
        #     self.link.send(m.contents())

        return m

    def wait_for_csta_message(self, for_user, message, calling_device=None, ignore_messages=(), timeout=5.0):
        """
        Wait for CSTA message
        :param for_user: The message intended recipient
        :param message: The message to wait for
        :param calling_device: The calling device number. Used to separated csta events when necessary
        :param ignore_messages: Messages to ignore
        :param timeout: Defined timeout in seconds.
        :return: the CstaMessage received
        """
        callID = None
        # other_users_xrefid = [usr.parameters["monitorCrossRefID"]
        #                       if "monitorCrossRefID" in usr.parameters else None
        #                       for usr in self.users.values() if usr != for_user]
        # other_users_transactions = [usr.out_transactions for usr in self.users.values() if usr != for_user]
        user_xrefid = None
        this_user = None
        net_object = self
        if for_user is not None:
            this_user = self.users[for_user]
            # We are not using the below line, because if the same user is used, the xref id will be global
            # not thread specific
            # user_xrefid = this_user.parameters.get("monitorCrossRefID", None)
            user_xrefid = this_user.monitorCrossRefID
            net_object = this_user
            callID = this_user.parameters["callID"]
        # checked_buffer = None
        t0_tout = time()
        with net_object.lock:
            inmessage = get_buffered_message(net_object.message_buffer, message, callID, user_xrefid, calling_device)
        while not inmessage:
            # if not checked_buffer == net_object.buffer_mod_time:
            #     checked_buffer = net_object.buffer_mod_time
            if self.server:
                continue

            #            if not inmessage:
            rem_timeout = timeout - (time() - t0_tout)
            if rem_timeout > 0:
                net_object.buffer_event.wait(rem_timeout)
                net_object.buffer_event.clear()
                with net_object.lock:
                    inmessage = get_buffered_message(net_object.message_buffer, message, callID, user_xrefid,
                                                     calling_device)
                    if inmessage is None:
                        continue
            else:
                exception("%s (CSTA) No %s. Buffer lengths: %s. " % (for_user,
                                                                     message,
                                                                     str([(k, len(net_object.message_buffer[k]))
                                                                          for k in net_object.message_buffer])))
                raise sock_timeout

                # try:
                #     inbytes = self.link.waitForCstaData(timeout=timeout)
                #     inmessage = parseBytes(inbytes)

                # except UnicodeDecodeError:
                #     debug("Ignoring malformed data")
                #     inmessage = None
                #     continue
                # except sock_timeout:
                #     exception(str(for_user) + " No " + str(message) + " " + str(net_object.message_buffer))
                #     raise

            inmessage_type = inmessage.event
            if inmessage_type in ignore_messages:
                inmessage = None
                continue

            if message and (
                    # received message is not of expected type or
                    (isinstance(message, str) and message != inmessage_type) or

                    # received message type is not in list of expected types or
                    (type(message) in (list, tuple) and not any([m == inmessage_type for m in message])) or

                    # received message is event and has an unexpected callID
                    (inmessage.is_event() and
                     this_user is not None and
                     inmessage["callID"] and
                     callID and
                     callID != inmessage["callID"])  # or

                    # received message is a csta response that has an unknown/incorrect invokeID (eventid)
                    # (this_user is not None and
                    #  inmessage.is_response() and
                    #  inmessage.eventid not in this_user.out_transactions) or

                    # received message type is for another user (different xref_id and not MonitorStartResponse)
                    # # ie we are expecting message for a specific user
                    # (this_user is not None and
                    # # the message has a xrefid tag and our user has an xrefid parameter (although it may be empty)
                    # inmessage["monitorCrossRefID"] and user_xrefid is not None and
                    # # # the message xrefid is different than our user's xrefid
                    # inmessage["monitorCrossRefID"] != user_xrefid and
                    # # the message is not a MonitorStartResponse. This is the normal case where we send MonitorStart
                    # # at which time the user will not have xrefid assigned yet and we expect a response that we will
                    # # use to assign xrefid to the user
                    # inmessage_type != "MonitorStartResponse")
            ):

                # buffer received message if it is intended for another user or if it is an event that came sooner
                # than expected or if it is a response to a request from another user
                if (
                        # (this_user is not None and
                        #  inmessage["monitorCrossRefID"] and user_xrefid and
                        #  inmessage["monitorCrossRefID"] != user_xrefid and
                        #  inmessage["monitorCrossRefID"] in other_users_xrefid) or

                        (inmessage.is_event() and
                         inmessage["monitorCrossRefID"] and user_xrefid and
                         inmessage["monitorCrossRefID"] == user_xrefid) or

                        (inmessage.is_event() and
                         inmessage["monitorCrossRefID"] and
                         user_xrefid is None) or

                        (inmessage.is_event() and
                         inmessage["callID"] in this_user.calls)

                        # (this_user is not None and
                        #  inmessage.is_response() and
                        #  {inmessage.eventid: inmessage_type.replace("Response", "")} in other_users_transactions)
                ):
                    with net_object.lock:
                    # with self.lock:
                        # trying global lock to buffer messages
                        self.buffer_message(net_object, inmessage, ntfy_subs=False)
                    # warning(
                    #     "BUFFERED MESSAGE '{}' with callID '{}' for '{}' because I am '{}' waiting for '{}' in '{}' '{}'".format(
                    #         inmessage_type,
                    #         inmessage["callID"],
                    #         inmessage["deviceID"], for_user, message,
                    #         this_user.monitorCrossRefID, this_user.callID))
                    inmessage = None
                else:
                    if this_user is None:
                        raise AssertionError('Got "{}" with callID {} and xrefid {} '
                                             'while expecting "{}"'.format(inmessage_type,
                                                                           inmessage["callID"],
                                                                           inmessage["monitorCrossRefID"],
                                                                           message))
                    else:
                        raise AssertionError(
                            'Got "{}" with callID {}, eventid {} and xrefid {} while expecting "{}" with '
                            'callID {} and xrefid {}. '
                            'Known transactions are:\n"{}"\n{} '.format(inmessage_type,
                                                                        inmessage["callID"],
                                                                        inmessage.eventid,
                                                                        inmessage["monitorCrossRefID"],
                                                                        message,
                                                                        this_user.parameters.get(
                                                                            "callID",
                                                                            None),
                                                                        this_user.parameters.get(
                                                                            "monitorCrossRefID",
                                                                            None),
                                                                        this_user.out_transactions,
                                                                        inmessage))
        if this_user is not None:
            # Evaluate the invoke id
            this_user.update_incoming_transactions(inmessage)
            this_user.update_call_id(inmessage)

        return inmessage

    def buffer_message(self, user, message, ntfy_subs=True):
        """
        Add csta message to csta user's or csta application's buffer.
        :param message: the message to buffer
        :param ntfy_subs: notify the user whose buffer was changed
        :param user: the user who's buffer to use
        :return: None
        """
        if user is self:
            warning("Unexpected message. Adding to global buffer: " + str(message))

        key = str(message["callID"]) + str(message["monitorCrossRefID"]) + str(message.event)
        if key in user.message_buffer:
            user.message_buffer[key].append(message)
        else:
            user.message_buffer[key] = [message]
        user.buffer_mod_time = time()
        if ntfy_subs:
            self.buffer_trigger_count += 1
        if self.buffer_trigger_count:
            user.buffer_event.set()
            self.buffer_trigger_count -= 1

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
