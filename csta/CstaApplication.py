"""\
Purpose: Simulate a CSTA Application
Initial Version: Costas Skarakis 7/20/2020  
"""
from _socket import timeout

from common.client import TCPClient
from common.tc_logging import debug
from csta.CstaEndpoint import get_xml
from csta.CstaParser import parseBytes, buildMessageFromFile, buildMessage


class CstaApplication:
    def __init__(self):
        self.ip = None
        self.port = None
        self.link = None
        self.parameters = {}
        self.message_buffer = []
        self.waitForCstaMessage = self.wait_for_csta_message  # compatibility alias

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

    def monitor_start(self, directory_number):
        """ Send MonitorStart and add directory number to monitored users"""
        csta_link = self.link
        m = buildMessageFromFile(get_xml("MonitorStart.xml"), {"user": directory_number}, eventid=1)
        csta_link.send(m.contents())
        in_bytes = csta_link.waitForData()
        inmessage = parseBytes(in_bytes)
        assert inmessage.event == "MonitorStartResponse", "Sent:{}  Received:{}".format(m.event, str(inmessage))
        self.parameters.setdefault(directory_number, {"eventid": 1, "deviceID": None})

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
        return list(self.parameters.keys())

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
        if from_user and message not in ("MonitorStart", "MonitorStart.xml"):
            assert from_user in self.get_monitored_users(), "User {} must be monitored before sending messages".format(from_user)
            if "Response" not in message:
                self.parameters[from_user]["eventid"] += 1
            else:
                self.parameters[from_user]["eventid"] = self.parameters[from_user]["last_request_eventid"]
            self.parameters[from_user]["callingDevice"] = from_user
            self.parameters[from_user]["calledDirectoryNumber"] = to_user
            params = self.parameters[from_user]
            if message.endswith("Event"):
                params["eventid"] = 9999
        else:
            params = {"eventid": 1}
        if message.strip().startswith("<?xml"):
            m = buildMessage(message, self.parameters[from_user], self.parameters[from_user]["eventid"])
        else:
            m = buildMessageFromFile(get_xml(message), params,
                                     params["eventid"])
        self.link.send(m.contents())
        return m

    def wait_for_csta_message(self, for_user, message, ignore_messages=(), new_call=False, timeout=5.0):
        """
        Wait for CSTA message
        :param for_user: The message intended recipient
        :param message: The message to wait for
        :param ignore_messages: Messages to ignore
        :param new_call: If False, the incoming session ID must be the same as the one of the message we last sent (same dialog)
        :param timeout: Defined timeout in seconds.
        :return: the CstaMessage received
        """
        inmessage = None
        event_id = self.parameters[for_user]["eventid"]
        len_buffer = len(self.message_buffer)
        count = 0

        while not inmessage:

            if count < len_buffer:
                # first get a message from the buffer
                inmessage = self.get_buffered_message(for_user)
                count += 1

            if not inmessage:
                # no (more) buffered messages. try the network
                inbytes = self.link.waitForCstaData(timeout=timeout)
                inmessage = parseBytes(inbytes)

            inmessage_type = inmessage.event
            if inmessage_type in ignore_messages:
                inmessage = None
                continue

            if message and \
                    ((isinstance(message, str) and message not in inmessage_type) or
                     (type(message) in (list, tuple) and not any([m in inmessage_type for m in message]))):
                # we have received an unexpected message.
                raise AssertionError('{}: Got "{}" in {} while expecting "{}". '.format(for_user,
                                                                                        inmessage_type,
                                                                                        inmessage.eventid,
                                                                                        message))

        if inmessage.eventid != 9999 and not new_call:
            assert inmessage.eventid == event_id, \
                'User {}: Wrong event id received: {} \n' \
                'Event id expected: {}\n' \
                '\nMessage received:\n{}\n'.format(for_user,
                                                   inmessage.eventid,
                                                   event_id,
                                                   inmessage)
            self.update_call_parameters(for_user, inmessage)
        return inmessage

    def get_buffered_message(self, directory_number):
        """
        Return the first buffered message found for the given directory number's deviceID

        :param directory_number: The monitored directory number
        :return: the buffered SipMessage
        """
        msg = None
        for i in range(len(self.message_buffer)):
            message = self.message_buffer[i]
            try:
                device_ID = message["deviceID"]
            except AttributeError:
                device_ID = None
            if device_ID == self.parameters[directory_number]["deviceID"] or device_ID is None:
                msg = message
                self.message_buffer.pop(i)
                break
        return msg

    def update_call_parameters(self, directory_number, inresponse):
        """ Update our deviceID based on the given incoming CSTA message """
        try:
            if not inresponse.event.endswith("Event") and not inresponse.event.endswith("Response"):
                self.parameters[directory_number]["last_request_eventid"] = inresponse.eventid
            self.parameters[directory_number]["deviceID"] = inresponse["deviceID"]
        except AttributeError:
            self.parameters[directory_number].setdefault("deviceID", None)

    def close(self):
        self.link.socket.close()
        self.link = None
